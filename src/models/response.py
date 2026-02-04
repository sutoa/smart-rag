"""Response and Citation models for Smart RAG."""

from typing import Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Source reference for a finding.

    Attributes:
        document_name: Source document filename.
        page_number: Page where content was found.
        verbatim_quote: Exact text excerpt from source.
        relevance_score: Reranker confidence score (0-1).
    """

    document_name: str = Field(..., description="Source document filename")
    page_number: int = Field(..., ge=1, description="Page where content found")
    verbatim_quote: str = Field(..., description="Exact text excerpt")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")

    def format_human_readable(self, index: int, include_quote: bool = True) -> str:
        """Format citation for human-readable output.

        Args:
            index: Citation number (1-indexed).
            include_quote: Whether to include the verbatim quote.

        Returns:
            Formatted citation string.
        """
        lines = [f"{index}. {self.document_name} (page {self.page_number})"]
        if include_quote and self.verbatim_quote:
            # Indent and truncate long quotes
            quote = self.verbatim_quote
            if len(quote) > 200:
                quote = quote[:200] + "..."
            lines.append(f'   "{quote}"')
        return "\n".join(lines)


class ResponseMetadata(BaseModel):
    """Metadata about response generation.

    Attributes:
        chunks_retrieved: Number of chunks searched.
        chunks_used: Number of chunks in response.
        processing_time_ms: Total processing time in milliseconds.
        confidence_score: Overall confidence in response (0-1, based on relevance scores).
        quotes_verified: Number of citations with verified quotes.
    """

    chunks_retrieved: int = Field(default=0, ge=0)
    chunks_used: int = Field(default=0, ge=0)
    processing_time_ms: int = Field(default=0, ge=0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quotes_verified: int = Field(default=0, ge=0)


class Response(BaseModel):
    """Generated answer with citations.

    Attributes:
        answer: Generated response text.
        citations: List of source citations.
        query_text: Original query.
        metadata: Response generation metadata.
        not_found: Whether no relevant information was found.
    """

    answer: str = Field(..., description="Generated response text")
    citations: list[Citation] = Field(default_factory=list)
    query_text: str = Field(..., description="Original query")
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)
    not_found: bool = Field(default=False, description="No relevant info found")

    def format_human_readable(self, include_quotes: bool = True) -> str:
        """Format response for human-readable CLI output.

        Args:
            include_quotes: Whether to include verbatim quotes in citations.

        Returns:
            Formatted response string.
        """
        lines = [f"Query: {self.query_text}", ""]

        if self.not_found:
            lines.extend([
                "No relevant information found in the indexed documents.",
                "",
                "This query may be outside the scope of the indexed content.",
            ])
        else:
            lines.extend(["Answer:", self.answer, ""])

            if self.citations:
                lines.append("Sources:")
                for i, citation in enumerate(self.citations, 1):
                    lines.append(citation.format_human_readable(i, include_quotes))
                    lines.append("")

        # Add metadata footer
        lines.append("---")
        footer_parts = [
            f"Retrieved {self.metadata.chunks_retrieved} chunks",
            f"Used {self.metadata.chunks_used} sources",
        ]
        if self.metadata.confidence_score > 0:
            confidence_pct = int(self.metadata.confidence_score * 100)
            footer_parts.append(f"Confidence: {confidence_pct}%")
        footer_parts.append(f"Response time: {self.metadata.processing_time_ms / 1000:.1f}s")
        lines.append(" | ".join(footer_parts))

        return "\n".join(lines)

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dictionary per CLI contract.

        Returns:
            Dictionary matching CLI contract format.
        """
        return {
            "query": self.query_text,
            "answer": self.answer,
            "citations": [
                {
                    "document_name": c.document_name,
                    "page_number": c.page_number,
                    "verbatim_quote": c.verbatim_quote,
                    "relevance_score": c.relevance_score,
                }
                for c in self.citations
            ],
            "metadata": {
                "chunks_retrieved": self.metadata.chunks_retrieved,
                "chunks_used": self.metadata.chunks_used,
                "processing_time_ms": self.metadata.processing_time_ms,
                "confidence_score": round(self.metadata.confidence_score, 2),
                "quotes_verified": self.metadata.quotes_verified,
            },
        }

    @classmethod
    def not_found_response(
        cls,
        query_text: str,
        chunks_retrieved: int = 0,
        processing_time_ms: int = 0,
    ) -> "Response":
        """Create a 'not found' response.

        Args:
            query_text: Original query.
            chunks_retrieved: Number of chunks that were searched.
            processing_time_ms: Processing time.

        Returns:
            Response indicating no relevant information found.
        """
        return cls(
            answer="No relevant information found in the indexed documents.",
            citations=[],
            query_text=query_text,
            metadata=ResponseMetadata(
                chunks_retrieved=chunks_retrieved,
                chunks_used=0,
                processing_time_ms=processing_time_ms,
            ),
            not_found=True,
        )


class Query(BaseModel):
    """Represents a user search query (runtime only, not persisted).

    Attributes:
        text: Natural language question.
        embedding: Query embedding vector.
    """

    text: str = Field(..., min_length=1, description="Natural language question")
    embedding: Optional[list[float]] = Field(default=None, description="Query embedding")
