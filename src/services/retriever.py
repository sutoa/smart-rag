"""Retrieval service with similarity search and reranking for Smart RAG."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from sentence_transformers import CrossEncoder

from src.lib.openai_client import OpenAIClient, get_openai_client
from src.lib.vector_store import VectorStore, get_vector_store
from src.models.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Global reranker model (loaded once, reused)
_reranker: Optional[CrossEncoder] = None


def get_reranker(model_name: str) -> CrossEncoder:
    """Get the reranker model (lazy loading with caching).

    Args:
        model_name: Name of the cross-encoder model.

    Returns:
        CrossEncoder instance.
    """
    global _reranker
    if _reranker is None:
        logger.info(f"Loading reranker model: {model_name}")
        _reranker = CrossEncoder(model_name)
    return _reranker


@dataclass
class RetrievedChunk:
    """A retrieved and scored chunk.

    Attributes:
        id: Chunk ID.
        content: Chunk text content.
        document_id: Parent document ID.
        document_name: Source document filename.
        page_number: Source page number.
        page_end: End page if spans pages.
        chunk_index: Order within document.
        has_table: Whether chunk contains table data.
        similarity_score: Initial vector similarity score (0-1, higher is better).
        relevance_score: Reranker relevance score (0-1, higher is better).
    """

    id: str
    content: str
    document_id: str
    document_name: str
    page_number: int
    page_end: Optional[int]
    chunk_index: int
    has_table: bool
    similarity_score: float
    relevance_score: float = 0.0

    def to_context_dict(self) -> dict:
        """Convert to dictionary format for generator context.

        Returns:
            Dictionary with content and metadata.
        """
        return {
            "content": self.content,
            "document_name": self.document_name,
            "page_number": self.page_number,
            "relevance_score": self.relevance_score,
        }


@dataclass
class RetrievalResult:
    """Result of a retrieval operation.

    Attributes:
        query: Original query text.
        chunks: List of retrieved chunks (sorted by relevance).
        total_retrieved: Number of chunks from initial retrieval.
        embedding_time_ms: Time for query embedding in milliseconds.
        retrieval_time_ms: Time for vector search in milliseconds.
        rerank_time_ms: Time for reranking in milliseconds.
    """

    query: str
    chunks: list[RetrievedChunk]
    total_retrieved: int
    embedding_time_ms: int = 0
    retrieval_time_ms: int = 0
    rerank_time_ms: int = 0

    @property
    def total_time_ms(self) -> int:
        """Total retrieval and reranking time."""
        return self.embedding_time_ms + self.retrieval_time_ms + self.rerank_time_ms

    def get_timing_breakdown(self) -> str:
        """Get human-readable timing breakdown.

        Returns:
            Formatted timing string.
        """
        parts = []
        if self.embedding_time_ms > 0:
            parts.append(f"embed: {self.embedding_time_ms}ms")
        if self.retrieval_time_ms > 0:
            parts.append(f"search: {self.retrieval_time_ms}ms")
        if self.rerank_time_ms > 0:
            parts.append(f"rerank: {self.rerank_time_ms}ms")
        return ", ".join(parts) if parts else "0ms"


class Retriever:
    """Retrieve and rank relevant chunks for queries.

    Uses two-stage retrieval:
    1. Vector similarity search (ChromaDB) for initial candidates
    2. Cross-encoder reranking for precise relevance scoring
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        vector_store: Optional[VectorStore] = None,
        openai_client: Optional[OpenAIClient] = None,
    ):
        """Initialize retriever.

        Args:
            settings: Application settings.
            vector_store: Vector database.
            openai_client: OpenAI client for query embedding.
        """
        self.settings = settings or get_settings()
        self.vector_store = vector_store
        self.openai_client = openai_client
        self._reranker: Optional[CrossEncoder] = None

    def _get_vector_store(self) -> VectorStore:
        """Get vector store (lazy initialization)."""
        if self.vector_store is None:
            self.vector_store = get_vector_store()
        return self.vector_store

    def _get_openai_client(self) -> OpenAIClient:
        """Get OpenAI client (lazy initialization)."""
        if self.openai_client is None:
            self.openai_client = get_openai_client()
        return self.openai_client

    def _get_reranker(self) -> CrossEncoder:
        """Get reranker model (cached for reuse)."""
        if self._reranker is None:
            self._reranker = get_reranker(self.settings.retrieval.reranker_model)
        return self._reranker

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank_top_k: Optional[int] = None,
    ) -> RetrievalResult:
        """Retrieve relevant chunks for a query.

        Args:
            query: Natural language query.
            top_k: Number of chunks to retrieve initially (default from settings).
            rerank_top_k: Number of chunks to return after reranking (default from settings).

        Returns:
            RetrievalResult with ranked chunks.
        """
        top_k = top_k or self.settings.retrieval.top_k
        rerank_top_k = rerank_top_k or self.settings.retrieval.rerank_top_k

        # Stage 1: Vector similarity search (includes embedding time)
        candidates, embedding_time_ms, search_time_ms = self._similarity_search(query, top_k)

        if not candidates:
            return RetrievalResult(
                query=query,
                chunks=[],
                total_retrieved=0,
                embedding_time_ms=embedding_time_ms,
                retrieval_time_ms=search_time_ms,
            )

        # Stage 2: Cross-encoder reranking
        start_time = time.time()
        ranked_chunks = self._rerank(query, candidates, rerank_top_k)
        rerank_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Retrieved {len(candidates)} chunks, reranked to top {len(ranked_chunks)} "
            f"(embed: {embedding_time_ms}ms, search: {search_time_ms}ms, rerank: {rerank_time_ms}ms)"
        )

        return RetrievalResult(
            query=query,
            chunks=ranked_chunks,
            total_retrieved=len(candidates),
            embedding_time_ms=embedding_time_ms,
            retrieval_time_ms=search_time_ms,
            rerank_time_ms=rerank_time_ms,
        )

    def _similarity_search(
        self, query: str, top_k: int
    ) -> tuple[list[RetrievedChunk], int, int]:
        """Perform vector similarity search.

        Args:
            query: Query text.
            top_k: Number of results to retrieve.

        Returns:
            Tuple of (chunks, embedding_time_ms, search_time_ms).
        """
        # Generate query embedding
        embed_start = time.time()
        client = self._get_openai_client()
        query_embedding = client.get_embedding(query)
        embedding_time_ms = int((time.time() - embed_start) * 1000)

        # Query vector store
        search_start = time.time()
        vector_store = self._get_vector_store()
        results = vector_store.query(query_embedding, n_results=top_k)
        search_time_ms = int((time.time() - search_start) * 1000)

        # Convert to RetrievedChunk objects
        chunks = []
        for result in results:
            metadata = result.get("metadata", {})
            # Convert distance to similarity score (ChromaDB uses L2 distance)
            # Lower distance = more similar, so we invert
            distance = result.get("distance", 0.0)
            similarity = 1.0 / (1.0 + distance)  # Normalize to 0-1

            chunks.append(
                RetrievedChunk(
                    id=result["id"],
                    content=result["content"],
                    document_id=metadata.get("document_id", ""),
                    document_name=metadata.get("document_name", ""),
                    page_number=metadata.get("page_number", 1),
                    page_end=metadata.get("page_end"),
                    chunk_index=metadata.get("chunk_index", 0),
                    has_table=metadata.get("has_table", False),
                    similarity_score=similarity,
                )
            )

        return chunks, embedding_time_ms, search_time_ms

    def _rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Rerank chunks using cross-encoder model.

        Args:
            query: Query text.
            chunks: Candidate chunks from similarity search.
            top_k: Number of top chunks to return.

        Returns:
            Top-k chunks sorted by relevance score.
        """
        if not chunks:
            return []

        # Prepare query-document pairs for reranking
        pairs = [[query, chunk.content] for chunk in chunks]

        # Get reranker scores
        reranker = self._get_reranker()
        raw_scores = reranker.predict(pairs)

        # Normalize scores to 0-1 range using sigmoid-like transformation
        normalized_scores = self._normalize_scores(raw_scores)

        # Update chunks with relevance scores
        for chunk, score in zip(chunks, normalized_scores):
            chunk.relevance_score = score

        # Sort by relevance and return top-k
        chunks.sort(key=lambda c: c.relevance_score, reverse=True)
        return chunks[:top_k]

    def _normalize_scores(self, scores: list[float]) -> list[float]:
        """Normalize reranker scores to 0-1 range.

        Cross-encoder scores can vary widely, so we normalize them.

        Args:
            scores: Raw reranker scores.

        Returns:
            Normalized scores (0-1).
        """
        if not scores:
            return []

        # Use sigmoid for normalization (works well for cross-encoder scores)
        import math

        normalized = []
        for score in scores:
            # Sigmoid transformation
            normalized_score = 1.0 / (1.0 + math.exp(-score))
            normalized.append(round(normalized_score, 4))

        return normalized

    def retrieve_from_multiple_documents(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank_top_k: Optional[int] = None,
        min_docs: int = 2,
        max_chunks_per_doc: int = 3,
    ) -> RetrievalResult:
        """Retrieve chunks ensuring coverage from multiple documents.

        Used for entity queries that need aggregated information from
        across the document corpus.

        Args:
            query: Natural language query.
            top_k: Number of chunks to retrieve initially.
            rerank_top_k: Number of chunks to return after reranking.
            min_docs: Minimum number of documents to include.
            max_chunks_per_doc: Maximum chunks from any single document.

        Returns:
            RetrievalResult with chunks from multiple documents.
        """
        # Retrieve more candidates for better document coverage
        extended_top_k = (top_k or self.settings.retrieval.top_k) * 3
        rerank_top_k = rerank_top_k or self.settings.retrieval.rerank_top_k

        # Stage 1: Vector similarity search with extended results
        candidates, embedding_time_ms, search_time_ms = self._similarity_search(
            query, extended_top_k
        )

        if not candidates:
            return RetrievalResult(
                query=query,
                chunks=[],
                total_retrieved=0,
                embedding_time_ms=embedding_time_ms,
                retrieval_time_ms=search_time_ms,
            )

        # Stage 2: Rerank all candidates
        start_time = time.time()
        # Rerank more than we need to ensure good document coverage
        ranked_chunks = self._rerank(query, candidates, len(candidates))
        rerank_time_ms = int((time.time() - start_time) * 1000)

        # Stage 3: Select chunks with document diversity
        final_chunks = self._select_diverse_chunks(
            ranked_chunks,
            target_count=rerank_top_k,
            min_docs=min_docs,
            max_per_doc=max_chunks_per_doc,
        )

        logger.info(
            f"Multi-doc retrieval: {len(candidates)} candidates -> "
            f"{len(final_chunks)} chunks from {len(set(c.document_id for c in final_chunks))} docs "
            f"(embed: {embedding_time_ms}ms, search: {search_time_ms}ms, rerank: {rerank_time_ms}ms)"
        )

        return RetrievalResult(
            query=query,
            chunks=final_chunks,
            total_retrieved=len(candidates),
            embedding_time_ms=embedding_time_ms,
            retrieval_time_ms=search_time_ms,
            rerank_time_ms=rerank_time_ms,
        )

    def _select_diverse_chunks(
        self,
        chunks: list[RetrievedChunk],
        target_count: int,
        min_docs: int,
        max_per_doc: int,
    ) -> list[RetrievedChunk]:
        """Select chunks ensuring document diversity.

        Args:
            chunks: Ranked chunks (by relevance).
            target_count: Target number of chunks to return.
            min_docs: Try to include at least this many documents.
            max_per_doc: Maximum chunks from any single document.

        Returns:
            Selected chunks with document diversity.
        """
        if not chunks:
            return []

        selected: list[RetrievedChunk] = []
        doc_counts: dict[str, int] = {}

        # First pass: ensure minimum document coverage
        for chunk in chunks:
            doc_id = chunk.document_id
            if doc_id not in doc_counts:
                selected.append(chunk)
                doc_counts[doc_id] = 1
                if len(doc_counts) >= min_docs and len(selected) >= target_count:
                    break

        # Second pass: fill remaining slots respecting max_per_doc
        for chunk in chunks:
            if len(selected) >= target_count:
                break
            if chunk in selected:
                continue

            doc_id = chunk.document_id
            if doc_counts.get(doc_id, 0) < max_per_doc:
                selected.append(chunk)
                doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1

        # Sort final selection by relevance
        selected.sort(key=lambda c: c.relevance_score, reverse=True)
        return selected
