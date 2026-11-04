"""
RAG Pipeline — Healthcare Knowledge Retrieval
==============================================
Purpose: Retrieval-Augmented Generation pipeline using a simple TF-IDF-based
         in-memory retriever (no chromadb dependency required).
         Falls back gracefully when no documents are indexed.

         For production with large document sets, swap _SimpleRetriever for
         a ChromaDB or FAISS backend once pydantic-compatible versions are available.

Dependencies: sklearn (optional, for TF-IDF), or pure-Python fallback
"""

import os
import re
import json
import math
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

from config.settings import settings
from utils.logger import app_logger, audit_logger


# ─── Simple keyword-based retriever (no external vector DB needed) ─────────────

class _SimpleRetriever:
    """
    Lightweight in-memory retriever using TF-IDF cosine similarity.
    No chromadb, no hnswlib, no pydantic-settings required.
    Falls back to keyword overlap if sklearn is unavailable.
    """

    def __init__(self):
        self._documents: dict[str, list[dict]] = defaultdict(list)
        # {collection_name: [{"text": ..., "source": ..., "page": ...}, ...]}
        self._tfidf_fitted: dict[str, Any] = {}

    def add_documents(self, collection: str, chunks: list[dict]) -> None:
        """Add document chunks to a collection."""
        self._documents[collection].extend(chunks)
        self._tfidf_fitted.pop(collection, None)  # invalidate cached vectoriser

    def count(self, collection: str) -> int:
        return len(self._documents.get(collection, []))

    def query(self, collection: str, query_text: str, top_k: int = 5) -> list[dict]:
        """Return top-k chunks by relevance to query_text."""
        docs = self._documents.get(collection, [])
        if not docs:
            return []

        try:
            return self._tfidf_query(docs, query_text, top_k)
        except Exception:
            return self._keyword_query(docs, query_text, top_k)

    # ── TF-IDF path ────────────────────────────────────────────────────────
    def _tfidf_query(self, docs: list[dict], query: str, top_k: int) -> list[dict]:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        texts = [d["text"] for d in docs]
        vec = TfidfVectorizer(stop_words="english", max_features=10000)
        tfidf_matrix = vec.fit_transform(texts)
        q_vec = vec.transform([query])
        scores = cosine_similarity(q_vec, tfidf_matrix).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({**docs[idx], "relevance_score": round(float(scores[idx]), 3)})
        return results

    # ── Keyword overlap fallback ───────────────────────────────────────────
    def _keyword_query(self, docs: list[dict], query: str, top_k: int) -> list[dict]:
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for doc in docs:
            doc_words = set(re.findall(r'\w+', doc["text"].lower()))
            overlap = len(query_words & doc_words)
            if overlap > 0:
                score = overlap / (math.sqrt(len(query_words)) * math.sqrt(len(doc_words)) + 1e-9)
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {**doc, "relevance_score": round(score, 3)}
            for score, doc in scored[:top_k]
        ]


# ─── RAG Pipeline ─────────────────────────────────────────────────────────────

class HealthcareRAGPipeline:
    """
    Healthcare-specific RAG pipeline.

    Architecture:
        Documents (TXT/PDF) → Text Splitter → In-memory TF-IDF index
        Query → Similarity Search → Top-K Chunks → LLM Context

    Collections:
        - healthcare_guidelines
        - government_schemes
        - facility_knowledge
        - emergency_protocols
    """

    COLLECTIONS = [
        "healthcare_guidelines",
        "government_schemes",
        "facility_knowledge",
        "emergency_protocols",
    ]

    def __init__(self):
        self._retriever = _SimpleRetriever()
        self._initialized = False
        # Auto-index documents on first use
        self._docs_indexed = False

    def _ensure_indexed(self) -> None:
        """Index knowledge documents on first access (lazy)."""
        if self._docs_indexed:
            return
        self._docs_indexed = True  # set early to prevent re-entry
        try:
            self.index_all_documents()
        except Exception as e:
            app_logger.warning(f"Auto-indexing failed (RAG will be limited): {e}")

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        size = settings.RAG_CHUNK_SIZE
        overlap = settings.RAG_CHUNK_OVERLAP
        # Split on paragraph boundaries first, then hard-split if too long
        paragraphs = re.split(r'\n{2,}', text)
        chunks = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) + 2 <= size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                # Hard split long paragraphs
                if len(para) > size:
                    for i in range(0, len(para), size - overlap):
                        chunks.append(para[i:i + size])
                else:
                    current = para
        if current:
            chunks.append(current)
        return chunks

    def index_document(
        self,
        file_path: str,
        collection_name: str = "healthcare_guidelines",
        source_label: str = "",
    ) -> dict[str, Any]:
        """Index a TXT or PDF file into the in-memory retriever."""
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            if path.suffix.lower() == ".pdf":
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(str(path))
                    text = "\n\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                except ImportError:
                    return {"success": False, "error": "pypdf not installed; cannot read PDF"}
            else:
                text = path.read_text(encoding="utf-8", errors="ignore")

            chunks = self._split_text(text)
            source = source_label or path.name
            docs = [
                {"text": chunk, "source": source, "page": i, "collection": collection_name}
                for i, chunk in enumerate(chunks)
            ]
            self._retriever.add_documents(collection_name, docs)
            app_logger.info(f"Indexed {len(chunks)} chunks from {path.name} → {collection_name}")
            return {"success": True, "chunks_indexed": len(chunks), "collection": collection_name}

        except Exception as e:
            app_logger.error(f"Indexing error for {file_path}: {e}")
            return {"success": False, "error": str(e)}

    def query(
        self,
        query_text: str,
        collection_name: str = "healthcare_guidelines",
        top_k: int = None,
        session_id: str = "system",
    ) -> dict[str, Any]:
        """Retrieve relevant knowledge chunks for a query."""
        self._ensure_indexed()
        top_k = top_k or settings.RAG_TOP_K

        try:
            if self._retriever.count(collection_name) == 0:
                return {
                    "success": True,
                    "results": [],
                    "context": "",
                    "note": f"Collection '{collection_name}' is empty. No documents indexed yet.",
                }

            raw_results = self._retriever.query(collection_name, query_text, top_k)

            formatted = []
            for i, r in enumerate(raw_results):
                formatted.append({
                    "rank": i + 1,
                    "text": r["text"],
                    "source": r.get("source", "Unknown"),
                    "page": r.get("page", 0),
                    "relevance_score": r.get("relevance_score", 0.0),
                })

            context = "\n\n---\n\n".join(
                f"[Source: {r['source']}, Relevance: {r['relevance_score']}]\n{r['text']}"
                for r in formatted
            )

            audit_logger.log(
                session_id=session_id,
                action_type="rag_query",
                agent_name="RAGPipeline",
                action=f"query: {query_text[:100]}",
                outcome="success",
                metadata={"collection": collection_name, "results_count": len(formatted)},
            )

            app_logger.info(
                f"RAG query | collection={collection_name} | "
                f"results={len(formatted)} | query='{query_text[:60]}'"
            )
            return {
                "success": True,
                "total_results": len(formatted),
                "results": formatted,
                "context": context,
                "collection": collection_name,
            }

        except Exception as e:
            app_logger.error(f"RAG query error: {e}")
            return {"success": False, "error": str(e), "results": [], "context": ""}

    def index_all_documents(self) -> dict[str, Any]:
        """Index all documents found in the rag/documents directory."""
        docs_dir = Path(settings.BASE_DIR) / "rag" / "documents"
        if not docs_dir.exists():
            return {"success": False, "error": "Documents directory not found"}

        results = []
        for file_path in docs_dir.rglob("*"):
            if file_path.suffix.lower() in [".pdf", ".txt"]:
                name_lower = file_path.stem.lower()
                if "emergency" in name_lower or "protocol" in name_lower:
                    collection = "emergency_protocols"
                elif "scheme" in name_lower or "ayushman" in name_lower or "pmjay" in name_lower:
                    collection = "government_schemes"
                elif "facility" in name_lower or "hospital" in name_lower:
                    collection = "facility_knowledge"
                else:
                    collection = "healthcare_guidelines"

                result = self.index_document(str(file_path), collection, file_path.stem)
                results.append({"file": file_path.name, **result})

        return {"success": True, "indexed_files": results}


# ─── Global singleton ────────────────────────────────────────────────────────
rag_pipeline = HealthcareRAGPipeline()
