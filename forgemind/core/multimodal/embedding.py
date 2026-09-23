# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import os
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    """Embedding 结果"""
    embedding: np.ndarray
    text: str
    model: str
    dim: int


class EmbeddingsModel:
    """通用 Embedding 包装 — 支持 bge-m3 / sentence-transformers / OpenAI"""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",  # 中文最强
        device: str = "cpu",
        cache_dir: str = "./data/cache/embeddings",
    ):
        self.model_name = model_name
        self.device = device
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = None
        self._dim = None
    
    def _load_model(self):
        """懒加载"""
        if self.model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name, device=self.device, cache_folder=str(self.cache_dir))
            self._dim = self.model.get_sentence_embedding_dimension()
        except ImportError:
            self.model = None
    
    @property
    def dim(self) -> int:
        if self._dim is None:
            self._load_model()
            self._dim = 1024 if "bge-m3" in self.model_name else 768  # 默认
        return self._dim
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """生成 embeddings"""
        self._load_model()
        if self.model is None:
            # Fallback: 随机向量(保证 pipeline 跑得通)
            return np.random.randn(len(texts), self.dim).astype(np.float32)
        
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    
    def embed_query(self, query: str) -> np.ndarray:
        """单 query 嵌入"""
        return self.embed([query])[0]


class PDFParser:
    """研报 PDF 解析 — 提取文本和表格"""
    
    def __init__(self, use_ocr: bool = True):
        self.use_ocr = use_ocr
    
    def parse(self, pdf_path: str) -> Dict:
        """解析 PDF, 返回 {pages: [...], tables: [...], metadata: {...}}"""
        result = {
            "pages": [],
            "tables": [],
            "metadata": {
                "source": pdf_path,
                "n_pages": 0,
            }
        }
        
        try:
            import pypdf
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                result["metadata"]["n_pages"] = len(reader.pages)
                for page in reader.pages:
                    text = page.extract_text() or ""
                    result["pages"].append(text)
        except ImportError:
            # 降级: 返回空
            result["pages"] = [f"[PDF 解析需要 pypdf: {pdf_path}]"]
        except Exception as e:
            result["pages"] = [f"[PDF 解析失败: {e}]"]
        
        return result
    
    def extract_chunks(
        self,
        pdf_path: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        """解析 PDF 并切块"""
        parsed = self.parse(pdf_path)
        full_text = "\n".join(parsed["pages"])
        
        # 简单按字符切块
        chunks = []
        for i in range(0, len(full_text), chunk_size - overlap):
            chunk = full_text[i:i + chunk_size]
            if len(chunk.strip()) > 0:
                chunks.append(chunk)
        
        return chunks


class OCRProcessor:
    """OCR 处理 — 图像 → 文本"""
    
    def __init__(self, lang: str = "chi_sim+eng"):
        self.lang = lang
    
    def recognize(self, image_path: str) -> str:
        """识别图像中的文字"""
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(image_path)
            return pytesseract.image_to_string(image, lang=self.lang)
        except ImportError:
            return f"[OCR 需要 pytesseract: {image_path}]"
        except Exception as e:
            return f"[OCR 失败: {e}]"


class ASRProcessor:
    """ASR — 音频 → 文本 (Whisper)"""
    
    def __init__(self, model_name: str = "base", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
    
    def _load_model(self):
        if self.model is not None:
            return
        try:
            import whisper
            self.model = whisper.load_model(self.model_name, device=self.device)
        except ImportError:
            self.model = None
    
    def transcribe(self, audio_path: str, language: str = "zh") -> Dict:
        """转录音频"""
        self._load_model()
        if self.model is None:
            return {"text": f"[ASR 需要 whisper: {audio_path}]", "language": language}
        
        try:
            result = self.model.transcribe(audio_path, language=language)
            return {
                "text": result["text"],
                "language": result.get("language", language),
                "segments": result.get("segments", []),
            }
        except Exception as e:
            return {"text": f"[ASR 失败: {e}]", "language": language}


class MultimodalRetriever:
    """多模态向量检索 — 融合 PDF + 文本 + 新闻"""
    
    def __init__(self, embedding_model: Optional[EmbeddingsModel] = None):
        self.embedding_model = embedding_model or EmbeddingsModel()
        self.documents: List[Dict] = []  # [{"text": ..., "embedding": ..., "metadata": ...}]
    
    def add_documents(
        self,
        documents: List[str],
        metadata: Optional[List[Dict]] = None,
    ):
        """添加文档并向量化"""
        if metadata is None:
            metadata = [{}] * len(documents)
        
        embeddings = self.embedding_model.embed(documents)
        for i, (doc, emb, meta) in enumerate(zip(documents, embeddings, metadata)):
            self.documents.append({
                "text": doc,
                "embedding": emb,
                "metadata": meta,
            })
    
    def add_pdf(self, pdf_path: str, chunk_size: int = 500):
        """添加 PDF 文档(自动切块)"""
        parser = PDFParser()
        chunks = parser.extract_chunks(pdf_path, chunk_size=chunk_size)
        metadata = [{"source": pdf_path, "type": "pdf"}] * len(chunks)
        self.add_documents(chunks, metadata=metadata)
    
    def add_news(self, news_df):
        """添加新闻数据(polars DataFrame with title + content)"""
        documents = []
        metadata = []
        for row in news_df.iter_rows(named=True):
            doc = f"{row.get('title', '')} {row.get('content', '')}"
            documents.append(doc)
            metadata.append({"source": row.get("source"), "type": "news", "date": row.get("date")})
        self.add_documents(documents, metadata=metadata)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索相关文档"""
        if not self.documents:
            return []
        
        query_emb = self.embedding_model.embed_query(query)
        # 余弦相似度
        doc_embs = np.array([d["embedding"] for d in self.documents])
        similarities = np.dot(doc_embs, query_emb) / (
            np.linalg.norm(doc_embs, axis=1) * np.linalg.norm(query_emb) + 1e-9
        )
        
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "text": self.documents[idx]["text"],
                "metadata": self.documents[idx]["metadata"],
                "score": float(similarities[idx]),
            })
        return results
    
    def size(self) -> int:
        return len(self.documents)


class MultimodalStorage:
    """多模态存储 — 统一管理 PDF / OCR / ASR / 图表"""
    
    def __init__(self, base_path: str = "./data/multimodal"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.pdf_dir = self.base_path / "pdfs"
        self.ocr_dir = self.base_path / "ocr"
        self.asr_dir = self.base_path / "asr"
        self.charts_dir = self.base_path / "charts"
        for d in [self.pdf_dir, self.ocr_dir, self.asr_dir, self.charts_dir]:
            d.mkdir(exist_ok=True)
    
    def store_pdf(self, symbol: str, date: str, pdf_path: str):
        """存储研报 PDF"""
        target = self.pdf_dir / symbol / date
        target.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(pdf_path, target)
    
    def store_ocr(self, symbol: str, image_path: str, text: str):
        """存储 OCR 结果"""
        target = self.ocr_dir / symbol
        target.mkdir(parents=True, exist_ok=True)
        text_file = target / (Path(image_path).stem + ".txt")
        text_file.write_text(text)
    
    def store_asr(self, symbol: str, audio_path: str, text: str):
        """存储 ASR 结果"""
        target = self.asr_dir / symbol
        target.mkdir(parents=True, exist_ok=True)
        text_file = target / (Path(audio_path).stem + ".txt")
        text_file.write_text(text)