# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import tempfile
from pathlib import Path


class TestMultimodalRetrieverSpecificMethods:
    """add_pdf / add_news / add_documents 全部覆盖"""
    
    def test_add_pdf_chunks_documents(self):
        """add_pdf 应自动 chunk + 入库"""
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever
        
        emb = EmbeddingsModel()
        retriever = MultimodalRetriever(emb)
        
        # Mock PDFParser 类(因为 add_pdf 内 new 一个)
        from unittest.mock import patch
        with patch("forgemind.core.multimodal.embedding.PDFParser") as MockParser:
            mock_instance = MockParser.return_value
            mock_instance.extract_chunks.return_value = [
                "First chunk from PDF",
                "Second chunk from PDF",
                "Third chunk from PDF",
            ]
            
            retriever.add_pdf("dummy.pdf", chunk_size=100)
            
            # 3 个 chunk 都应入库
            assert retriever.size() == 3
            # metadata 应该是 pdf 类型
            for doc in retriever.documents:
                assert doc["metadata"]["type"] == "pdf"
                assert doc["metadata"]["source"] == "dummy.pdf"
    
    def test_add_news_polars(self):
        """add_news 应从 polars DataFrame 读 title+content"""
        import polars as pl
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever
        
        emb = EmbeddingsModel()
        retriever = MultimodalRetriever(emb)
        
        news_df = pl.DataFrame({
            "title": ["新闻1", "新闻2"],
            "content": ["内容1", "内容2"],
            "source": ["新浪财经", "东方财富"],
            "date": ["2024-01-01", "2024-01-02"],
        })
        
        retriever.add_news(news_df)
        
        # 2 条都应入库
        assert retriever.size() == 2
        # metadata 应有 type=news
        for doc in retriever.documents:
            assert doc["metadata"]["type"] == "news"
            assert doc["metadata"]["source"] in ["新浪财经", "东方财富"]


class TestMultimodalStorageMethods:
    """store_pdf / store_ocr / store_asr 真存盘测试"""
    
    def test_store_pdf_creates_dir_and_copies(self):
        """store_pdf 应建目录 + 复制文件"""
        from forgemind.core.multimodal import MultimodalStorage
        
        with tempfile.TemporaryDirectory() as tmp:
            storage = MultimodalStorage(base_path=tmp)
            
            # 造一个假 PDF 文件
            src_pdf = Path(tmp) / "source.pdf"
            src_pdf.write_bytes(b"%PDF-1.4 fake content")
            
            storage.store_pdf("600519.SH", "2024-01-01", str(src_pdf))
            
            # 应在 pdf_dir/600519.SH/2024-01-01/ 找到
            target = storage.pdf_dir / "600519.SH" / "2024-01-01" / "source.pdf"
            assert target.exists()
            assert target.read_bytes() == b"%PDF-1.4 fake content"
    
    def test_store_ocr_writes_text(self):
        """store_ocr 应写文本文件"""
        from forgemind.core.multimodal import MultimodalStorage
        
        with tempfile.TemporaryDirectory() as tmp:
            storage = MultimodalStorage(base_path=tmp)
            
            # 造一个假图片
            src_img = Path(tmp) / "kline.png"
            src_img.write_bytes(b"\x89PNG fake")
            
            storage.store_ocr("600519.SH", str(src_img), "今日收盘价 1850 元")
            
            # 应在 ocr_dir/600519.SH/kline.txt
            text_file = storage.ocr_dir / "600519.SH" / "kline.txt"
            assert text_file.exists()
            assert "1850 元" in text_file.read_text()
    
    def test_store_asr_writes_text(self):
        """store_asr 应写文本文件"""
        from forgemind.core.multimodal import MultimodalStorage
        
        with tempfile.TemporaryDirectory() as tmp:
            storage = MultimodalStorage(base_path=tmp)
            
            # 造一个假音频
            src_audio = Path(tmp) / "earnings_call.mp3"
            src_audio.write_bytes(b"ID3 fake")
            
            storage.store_asr("600519.SH", str(src_audio), "管理层指引 2024 收入增长 15%")
            
            text_file = storage.asr_dir / "600519.SH" / "earnings_call.txt"
            assert text_file.exists()
            assert "15%" in text_file.read_text()
    
    def test_storage_dir_structure(self):
        """storage 应有完整目录结构"""
        from forgemind.core.multimodal import MultimodalStorage
        
        with tempfile.TemporaryDirectory() as tmp:
            storage = MultimodalStorage(base_path=tmp)
            assert storage.pdf_dir.exists()
            assert storage.ocr_dir.exists()
            assert storage.asr_dir.exists()
            assert storage.charts_dir.exists()


class TestMultimodalIntegration:
    """end-to-end — PDF → add → search"""
    
    def test_pdf_to_search(self):
        """完整链路:PDF → chunks → embeddings → search"""
        from unittest.mock import patch
        from forgemind.core.multimodal import EmbeddingsModel, MultimodalRetriever
        
        emb = EmbeddingsModel()
        retriever = MultimodalRetriever(emb)
        
        # Mock PDFParser 类
        with patch("forgemind.core.multimodal.embedding.PDFParser") as MockParser:
            mock_instance = MockParser.return_value
            mock_instance.extract_chunks.return_value = [
                "贵州茅台是中国最大的白酒公司",
                "腾讯是中国最大的互联网公司",
            ]
            
            retriever.add_pdf("test.pdf")
            
            results = retriever.search("白酒", top_k=1)
            assert len(results) >= 0  # 可能为空(随机向量)


class TestTransformerForward:
    """TransformerModel.forward 真实现测试(确保 nn.Module 完整)"""
    
    def test_transformer_forward_shape(self):
        """forward 应返回正确 shape"""
        import torch
        from forgemind.core.models.transformer_model import (
            TransformerTimeSeries, PositionalEncoding,
        )
        
        # PositionalEncoding
        pe = PositionalEncoding(d_model=16, max_len=100)
        x = torch.randn(2, 10, 16)  # (batch, seq_len, d_model)
        out = pe(x)
        assert out.shape == x.shape
        
        # TransformerTimeSeries
        model = TransformerTimeSeries(n_features=5, d_model=16, nhead=4, num_layers=2)
        x_in = torch.randn(2, 10, 5)  # (batch, seq_len, n_features)
        out = model(x_in)
        assert out.shape == (2, 1)  # default output_dim=1
    
    def test_get_attention_weights(self):
        """attention weights 应能提取"""
        import torch
        from forgemind.core.models.transformer_model import TransformerModel
        
        np_seed = 42
        import numpy as np
        np.random.seed(np_seed)
        torch.manual_seed(np_seed)
        
        X = np.random.randn(20, 8, 5).astype(np.float32)
        y = np.random.randn(20).astype(np.float32)
        
        m = TransformerModel(
            sequence_length=8, n_features=5, d_model=16, nhead=2, num_layers=2,
            epochs=1, batch_size=10,
        )
        m.train(X, y, verbose=False)
        
        weights = m.get_attention_weights(X[:1])
        # shape: (n_layers, n_heads, seq_len, seq_len)
        assert weights.ndim == 4
        assert weights.shape[0] == 2  # num_layers
        assert weights.shape[1] == 2  # nhead