"""RAG pipeline: document loading, chunking, embedding, and retrieval."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc"}


class RAGService:
    """Manage knowledge base indexing and semantic search."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.embeddings = OpenAIEmbeddings(
            model=self.settings.openai_embedding_model,
            openai_api_key=self.settings.openai_api_key,
        )
        self._vectorstore: Optional[Chroma] = None
        self._metadata: dict[str, Any] = self._load_metadata()

    def _load_metadata(self) -> dict[str, Any]:
        path = self.settings.metadata_path
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Corrupted metadata.json, resetting")
        return {
            "documents": [],
            "total_chunks": 0,
            "last_indexed_at": None,
            "collection": self.settings.chroma_collection,
        }

    def _save_metadata(self) -> None:
        self.settings.metadata_path.write_text(
            json.dumps(self._metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name=self.settings.chroma_collection,
                embedding_function=self.embeddings,
                persist_directory=str(self.settings.chroma_dir),
            )
        return self._vectorstore

    def _get_splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )

    def _load_file(self, file_path: Path) -> list[Document]:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif suffix in {".docx", ".doc"}:
            loader = Docx2txtLoader(str(file_path))
        elif suffix == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = file_path.name
            doc.metadata["source_path"] = str(file_path)
        return docs

    def _discover_data_files(self) -> list[Path]:
        data_dir = self.settings.data_dir
        if not data_dir.exists():
            logger.warning("Data directory does not exist: %s", data_dir)
            return []

        files: list[Path] = []
        for path in sorted(data_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
        return files

    async def index_documents(self) -> dict[str, Any]:
        """Load all files from data/, chunk, embed, and persist to Chroma."""
        files = self._discover_data_files()
        if not files:
            return {
                "success": False,
                "message": f"No supported files found in {self.settings.data_dir}",
                "documents_indexed": 0,
                "chunks_created": 0,
            }

        splitter = self._get_splitter()
        all_chunks: list[Document] = []
        indexed_docs: list[dict[str, Any]] = []

        for file_path in files:
            try:
                raw_docs = self._load_file(file_path)
                chunks = splitter.split_documents(raw_docs)
                all_chunks.extend(chunks)
                indexed_docs.append(
                    {
                        "filename": file_path.name,
                        "chunks": len(chunks),
                        "size_bytes": file_path.stat().st_size,
                    }
                )
                logger.info("Processed %s -> %d chunks", file_path.name, len(chunks))
            except Exception as exc:
                logger.exception("Failed to index %s: %s", file_path, exc)
                indexed_docs.append(
                    {"filename": file_path.name, "error": str(exc)}
                )

        if not all_chunks:
            return {
                "success": False,
                "message": "No chunks were created from source documents",
                "documents_indexed": 0,
                "chunks_created": 0,
            }

        # Re-create collection for a clean re-index.
        self._vectorstore = Chroma.from_documents(
            documents=all_chunks,
            embedding=self.embeddings,
            collection_name=self.settings.chroma_collection,
            persist_directory=str(self.settings.chroma_dir),
        )

        now = datetime.now(timezone.utc).isoformat()
        self._metadata = {
            "documents": indexed_docs,
            "total_chunks": len(all_chunks),
            "last_indexed_at": now,
            "collection": self.settings.chroma_collection,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
        }
        self._save_metadata()

        return {
            "success": True,
            "message": f"Indexed {len(files)} document(s), {len(all_chunks)} chunks",
            "documents_indexed": len(files),
            "chunks_created": len(all_chunks),
            "details": indexed_docs,
        }

    async def search(self, query: str, top_k: Optional[int] = None) -> list[Document]:
        """Retrieve relevant chunks for a user query."""
        k = top_k or self.settings.rag_top_k
        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return results
        except Exception as exc:
            logger.exception("RAG search failed: %s", exc)
            return []

    def format_context(self, documents: list[Document]) -> str:
        if not documents:
            return "Релевантные фрагменты из базы знаний не найдены."

        parts: list[str] = []
        for idx, doc in enumerate(documents, start=1):
            source = doc.metadata.get("source", "unknown")
            parts.append(f"[{idx}] Источник: {source}\n{doc.page_content.strip()}")
        return "\n\n---\n\n".join(parts)

    async def get_stats(self) -> dict[str, Any]:
        """Return indexing and collection statistics."""
        collection_count = 0
        try:
            collection = self.vectorstore._collection  # noqa: SLF001
            collection_count = collection.count()
        except Exception as exc:
            logger.warning("Could not read Chroma collection count: %s", exc)

        chroma_size_bytes = sum(
            f.stat().st_size
            for f in self.settings.chroma_dir.rglob("*")
            if f.is_file()
        )

        return {
            "collection_name": self.settings.chroma_collection,
            "documents_in_metadata": len(self._metadata.get("documents", [])),
            "total_chunks_metadata": self._metadata.get("total_chunks", 0),
            "collection_count": collection_count,
            "chroma_size_mb": round(chroma_size_bytes / (1024 * 1024), 2),
            "last_indexed_at": self._metadata.get("last_indexed_at"),
            "data_dir": str(self.settings.data_dir),
            "documents": self._metadata.get("documents", []),
        }
