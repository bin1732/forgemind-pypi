# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import tempfile

import pytest


class TestEmbeddingsModel:
    def test_dim_property(self):
        from forgemind.core.multimodal import EmbeddingsModel
        # 不真加载,只测 dim 属性
        emb = EmbeddingsModel(model_name="BAAI/bge-m3")
        assert emb.dim >= 768

    def test_refuses_when_model_unavailable(self):
        """模型不可用时必须抛错,不能 fallback 到随机向量

        原实现的 fallback 是 np.random.randn(注释:"保证 pipeline 跑得通")。
        随机向量两两等距,语义检索会退化成随机排序 —— 用户拿到一份
        "检索结果"却毫无相关性,却看不出模型根本没加载。
        """
        from forgemind.core.multimodal import EmbeddingsModel
        from forgemind.core.multimodal.embedding import (
            EmbeddingModelUnavailableError,
        )

        emb = EmbeddingsModel()
        if emb.model is None:
            with pytest.raises(EmbeddingModelUnavailableError):
                emb.embed(["测试", "hello world"])
        else:
            vectors = emb.embed(["测试", "hello world"])
            assert vectors.shape[0] == 2
            assert vectors.shape[1] >= 768


class TestPDFParser:
    def test_parse_nonexistent_raises_instead_of_fake_page_text(self):
        """失败时必须抛错,不能把提示语当成页面正文返回

        返回 {"pages": ["[PDF 解析需要 pypdf: ...]"]} —— 那段提示
        会被检索器当文档内容嵌入、索引、返回给用户,外观与真实正文无异。
        """
        from forgemind.core.multimodal import PDFParser
        from forgemind.core.multimodal.embedding import MultimodalUnavailableError

        with pytest.raises(MultimodalUnavailableError):
            PDFParser().parse("/nonexistent/file.pdf")

    def test_extract_chunks_does_not_return_the_error_as_content(self):
        """失败提示不是文档内容

        这条测试原来的注释写着"pypdf 不存在时是 [错误提示]"—— 也就是说,
        它把"返回错误提示当 chunk"当成期望行为写进了契约。
        """
        from forgemind.core.multimodal import PDFParser
        from forgemind.core.multimodal.embedding import MultimodalUnavailableError

        with pytest.raises(MultimodalUnavailableError):
            PDFParser().extract_chunks("/nonexistent/file.pdf", chunk_size=500)


class TestOCRProcessor:
    def test_recognize_never_returns_a_placeholder_as_text(self):
        """任何失败路径都不得把提示语当成识别结果

        之前有两条分支:
          ImportError → "[OCR 需要 pytesseract: ...]"
          其它异常    → "[OCR 失败: {e}]"
        两条都被当作**识别出的文本**返回。只测不存在的路径只能覆盖到
        第一条 —— 注入第二条时测试依然全绿。
        """
        import inspect

        from forgemind.core.multimodal import OCRProcessor

        src = inspect.getsource(OCRProcessor.recognize)
        assert "raise MultimodalUnavailableError" in src
        # 不得再有把提示语当结果的 return
        assert 'return f"[OCR' not in src, "OCR 又开始把失败提示当文本返回了"
        assert "except Exception as exc" in src, "第二个 except 分支未被覆盖"

    def test_recognize_nonexistent_raises(self):
        from forgemind.core.multimodal import OCRProcessor
        from forgemind.core.multimodal.embedding import MultimodalUnavailableError

        with pytest.raises(MultimodalUnavailableError):
            OCRProcessor().recognize("/nonexistent/image.png")


class TestASRProcessor:
    def test_transcribe_nonexistent_raises(self):
        """返回 {"text": "[ASR 失败: ...]"} —— 提示语被当成转写结果"""
        from forgemind.core.multimodal import ASRProcessor
        from forgemind.core.multimodal.embedding import MultimodalUnavailableError

        with pytest.raises(MultimodalUnavailableError):
            ASRProcessor().transcribe("/nonexistent/audio.mp3")


class TestMultimodalRetriever:
    def test_add_and_search(self):
        """添加文档 → 搜索(模型不可用时应拒绝,而非返回随机检索结果)"""
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever
        from forgemind.core.multimodal.embedding import (
            EmbeddingModelUnavailableError,
        )

        emb = EmbeddingsModel()
        retriever = MultimodalRetriever(emb)
        if emb.model is None:
            with pytest.raises(EmbeddingModelUnavailableError):
                retriever.add_documents(["测试文档"], metadata=[{"k": "v"}])
            return

        # 添加文档
        retriever.add_documents(
            ["贵州茅台是中国最大的白酒公司", "腾讯是做社交和游戏的科技公司", "苹果公司生产 iPhone"],
            metadata=[{"company": "maotai"}, {"company": "tencent"}, {"company": "apple"}],
        )

        # 搜索
        results = retriever.search("白酒 公司", top_k=2)
        assert len(results) > 0
        assert "text" in results[0]
        assert "score" in results[0]
        # 没装 sentence-transformers 时是随机向量,不能保证茅台排第一
        # 但应该返回所有文档之一
        assert any("茅台" in r["text"] or "腾讯" in r["text"] or "苹果" in r["text"] for r in results)
        # size 正确
        assert retriever.size() == 3

    def test_empty_search(self):
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever
        emb = EmbeddingsModel()
        retriever = MultimodalRetriever(emb)
        results = retriever.search("查询")
        assert results == []


class TestMultimodalStorage:
    def test_create_dirs(self):
        from forgemind.core.multimodal import MultimodalStorage
        with tempfile.TemporaryDirectory() as tmp:
            storage = MultimodalStorage(base_path=tmp)
            assert storage.pdf_dir.exists()
            assert storage.ocr_dir.exists()
            assert storage.asr_dir.exists()
            assert storage.charts_dir.exists()


class TestIntegration:
    def test_pdf_to_retriever(self):
        """PDF → Retriever 集成(模型不可用时应拒绝)"""
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever, PDFParser
        from forgemind.core.multimodal.embedding import (
            EmbeddingModelUnavailableError,
        )

        emb = EmbeddingsModel()
        if emb.model is None:
            with pytest.raises(EmbeddingModelUnavailableError):
                MultimodalRetriever(emb).add_documents(
                    ["x"], metadata=[{"k": "v"}])
            return
        parser = PDFParser()
        retriever = MultimodalRetriever(emb)

        # 解析 PDF
        # 模拟 PDF 内容
        chunks = parser.extract_chunks("/tmp/dummy.pdf", chunk_size=100)

        if chunks:
            retriever.add_documents(chunks)
            results = retriever.search("财务", top_k=3)
            # 应该能搜到(可能为空因为 mock)
            assert isinstance(results, list)
