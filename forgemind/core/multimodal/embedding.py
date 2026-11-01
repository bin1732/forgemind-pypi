# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""多模态组件(OCR / ASR / PDF / embedding)。

组件不可用或处理失败时,把提示语当成解析出的内容返回:
    "[OCR 失败: {e}]"        → 当作识别出的文本
    {"text": "[ASR 失败: {e}]"} → 当作转写结果
    "[PDF 解析需要 pypdf: ...]" → 当作页面正文

这些字符串会被检索器当文档内容嵌入、索引、返回给用户,
于是"识别结果"里混着失败提示,而外观与真实内容毫无区别。
"""

from pathlib import Path

import numpy as np

from forgemind.core.config.settings import data_path


class MultimodalUnavailableError(RuntimeError):
    """多模态组件不可用"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class EmbeddingModelUnavailableError(RuntimeError):
    """embedding 模型不可用 —— 不能用随机向量冒充语义表示"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"embedding 模型不可用:{reason}")


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
        cache_dir: str | None = None,
    ):
        self.model_name = model_name
        self.device = device
        self.cache_dir = Path(cache_dir) if cache_dir else data_path("cache", "embeddings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = None
        self._dim = None

    def is_available(self) -> tuple[bool, str]:
        """(是否可用, 不可用原因)"""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            return False, (
                "未安装 sentence-transformers,无法生成真实 embedding。"
                "装它:pip install 'forgemind[multimodal]' 并额外安装 "
                "sentence-transformers,或先 download 对应模型。"
            )
        return True, ""

    def _load_model(self):
        """懒加载"""
        if self.model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(
                self.model_name, device=self.device, cache_folder=str(self.cache_dir)
            )
            self._dim = self.model.get_sentence_embedding_dimension()
        except ImportError:
            self.model = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._load_model()
            self._dim = 1024 if "bge-m3" in self.model_name else 768  # 默认
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        """生成 embeddings

        模型不可用时**抛错**,不返回随机向量。以前这里 fallback 到
        np.random.randn(注释写"保证 pipeline 跑得通"),而随机向量两两等距,
        相似度检索退化成随机排序 —— 用户会拿到一份"检索结果"却毫无相关性,
        却完全看不出模型根本没加载。
        """
        self._load_model()
        if self.model is None:
            raise EmbeddingModelUnavailableError(self.is_available()[1] or "模型加载失败")

        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def embed_query(self, query: str) -> np.ndarray:
        """单 query 嵌入"""
        return self.embed([query])[0]


class PDFParser:
    """研报 PDF 解析 — 提取文本和表格"""

    def __init__(self, use_ocr: bool = True):
        self.use_ocr = use_ocr

    def parse(self, pdf_path: str) -> dict:
        """解析 PDF, 返回 {pages: [...], tables: [...], metadata: {...}}"""
        result = {
            "pages": [],
            "tables": [],
            "metadata": {
                "source": pdf_path,
                "n_pages": 0,
            },
        }

        try:
            import pypdf

            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                result["metadata"]["n_pages"] = len(reader.pages)
                for page in reader.pages:
                    text = page.extract_text() or ""
                    result["pages"].append(text)
        except ImportError as exc:
            raise MultimodalUnavailableError(
                f"PDF 解析需要 pypdf:pip install 'forgemind[multimodal]' ({pdf_path})"
            ) from exc
        except Exception as exc:
            raise MultimodalUnavailableError(
                f"PDF 解析失败 ({type(exc).__name__}: {exc}):{pdf_path}"
            ) from exc

        return result

    def extract_chunks(
        self,
        pdf_path: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> list[str]:
        """解析 PDF 并切块"""
        parsed = self.parse(pdf_path)
        full_text = "\n".join(parsed["pages"])

        # 简单按字符切块
        chunks = []
        for i in range(0, len(full_text), chunk_size - overlap):
            chunk = full_text[i : i + chunk_size]
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
        except ImportError as exc:
            raise MultimodalUnavailableError(
                f"OCR 需要 pytesseract 与 tesseract 二进制:pip install pytesseract"
                f" 并安装 tesseract-ocr({image_path})"
            ) from exc
        except Exception as exc:
            raise MultimodalUnavailableError(
                f"OCR 失败 ({type(exc).__name__}: {exc}):{image_path}"
            ) from exc


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

    def transcribe(self, audio_path: str, language: str = "zh") -> dict:
        """转录音频"""
        self._load_model()
        if self.model is None:
            raise MultimodalUnavailableError(
                f"ASR 需要 whisper:pip install openai-whisper 并下载模型({audio_path})"
            )

        try:
            result = self.model.transcribe(audio_path, language=language)
            return {
                "text": result["text"],
                "language": result.get("language", language),
                "segments": result.get("segments", []),
            }
        except Exception as exc:
            raise MultimodalUnavailableError(
                f"ASR 失败 ({type(exc).__name__}: {exc}):{audio_path}"
            ) from exc


class MultimodalRetriever:
    """多模态向量检索 — 融合 PDF + 文本 + 新闻"""

    def __init__(self, embedding_model: EmbeddingsModel | None = None):
        self.embedding_model = embedding_model or EmbeddingsModel()
        self.documents: list[dict] = []  # [{"text": ..., "embedding": ..., "metadata": ...}]

    def add_documents(
        self,
        documents: list[str],
        metadata: list[dict] | None = None,
    ):
        """添加文档并向量化"""
        if metadata is None:
            metadata = [{}] * len(documents)

        embeddings = self.embedding_model.embed(documents)
        for _i, (doc, emb, meta) in enumerate(zip(documents, embeddings, metadata)):
            self.documents.append(
                {
                    "text": doc,
                    "embedding": emb,
                    "metadata": meta,
                }
            )

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

    def search(self, query: str, top_k: int = 5) -> list[dict]:
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
            results.append(
                {
                    "text": self.documents[idx]["text"],
                    "metadata": self.documents[idx]["metadata"],
                    "score": float(similarities[idx]),
                }
            )
        return results

    def size(self) -> int:
        return len(self.documents)


class MultimodalStorage:
    """多模态存储 — 统一管理 PDF / OCR / ASR / 图表"""

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path) if base_path else data_path("multimodal")
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
