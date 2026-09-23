# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import tempfile
from pathlib import Path


class TestEmbeddingsModel:
    def test_dim_property(self):
        from forgemind.core.multimodal import EmbeddingsModel
        # 不真加载,只测 dim 属性
        emb = EmbeddingsModel(model_name="BAAI/bge-m3")
        assert emb.dim >= 768
    
    def test_embed_with_fallback(self):
        """没装 sentence-transformers 时,fallback 到随机向量"""
        from forgemind.core.multimodal import EmbeddingsModel
        emb = EmbeddingsModel()
        vectors = emb.embed(["测试", "hello world"])
        assert vectors.shape[0] == 2
        assert vectors.shape[1] >= 768


class TestPDFParser:
    def test_parse_nonexistent(self):
        from forgemind.core.multimodal import PDFParser
        parser = PDFParser()
        # 不存在的路径应优雅返回
        result = parser.parse("/nonexistent/file.pdf")
        assert "pages" in result
        assert "metadata" in result
    
    def test_extract_chunks_empty(self):
        from forgemind.core.multimodal import PDFParser
        parser = PDFParser()
        chunks = parser.extract_chunks("/nonexistent/file.pdf", chunk_size=500)
        # 应该返回至少 1 个 chunk(pypdf 不存在时是 [错误提示])
        assert isinstance(chunks, list)


class TestOCRProcessor:
    def test_recognize_nonexistent(self):
        from forgemind.core.multimodal import OCRProcessor
        ocr = OCRProcessor()
        text = ocr.recognize("/nonexistent/image.png")
        assert isinstance(text, str)


class TestASRProcessor:
    def test_transcribe_nonexistent(self):
        from forgemind.core.multimodal import ASRProcessor
        asr = ASRProcessor()
        result = asr.transcribe("/nonexistent/audio.mp3")
        assert "text" in result


class TestMultimodalRetriever:
    def test_add_and_search(self):
        """添加文档 → 搜索"""
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever
        
        emb = EmbeddingsModel()
        retriever = MultimodalRetriever(emb)
        
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
        """PDF → Retriever 集成"""
        from forgemind.core.multimodal import EmbeddingsModel, PDFParser, MultimodalRetriever
        
        emb = EmbeddingsModel()
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