"""Chunk model for Smart RAG."""

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ChunkMetadata(BaseModel):
    """Additional metadata for a chunk.

    Attributes:
        has_table: Whether the chunk contains table data.
        section_title: Title of the section if detected.
        extraction_method: How the content was extracted.
    """

    has_table: bool = Field(default=False)
    section_title: Optional[str] = Field(default=None)
    extraction_method: str = Field(default="text", pattern="^(text|table)$")


class Chunk(BaseModel):
    """A semantically coherent segment of text from a document.

    Attributes:
        id: Unique identifier (UUID).
        document_id: Reference to parent document.
        document_name: Source document filename.
        content: Extracted text content.
        page_number: Source page number (1-indexed).
        page_end: End page if chunk spans pages.
        chunk_index: Order within document (0-indexed).
        token_count: Approximate token count.
        embedding: OpenAI embedding vector (3072 dimensions).
        metadata: Additional extraction info.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str = Field(..., description="Reference to parent document")
    document_name: str = Field(default="", description="Source document filename")
    content: str = Field(..., min_length=1, description="Extracted text content")
    page_number: int = Field(..., ge=1, description="Source page number")
    page_end: Optional[int] = Field(default=None, ge=1, description="End page if spans pages")
    chunk_index: int = Field(..., ge=0, description="Order within document")
    token_count: int = Field(default=0, ge=0, description="Approximate token count")
    embedding: Optional[list[float]] = Field(default=None, description="Embedding vector")
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: str) -> str:
        """Ensure content has minimum length (50 chars to avoid trivial chunks)."""
        if len(v.strip()) < 50:
            raise ValueError("Chunk content must be at least 50 characters")
        return v

    @field_validator("page_end")
    @classmethod
    def validate_page_end(cls, v: Optional[int], info) -> Optional[int]:
        """Ensure page_end >= page_number if set."""
        if v is not None:
            page_number = info.data.get("page_number", 1)
            if v < page_number:
                raise ValueError("page_end must be >= page_number")
        return v

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        """Validate embedding has correct dimensions (3072 for text-embedding-3-large)."""
        if v is not None and len(v) != 3072:
            raise ValueError(f"Embedding must have 3072 dimensions, got {len(v)}")
        return v

    def to_chromadb_format(self) -> dict[str, Any]:
        """Convert to ChromaDB storage format.

        Returns:
            Dictionary with id, document, embedding, and metadata.
        """
        return {
            "id": self.id,
            "document": self.content,
            "embedding": self.embedding,
            "metadata": {
                "document_id": self.document_id,
                "document_name": self.document_name,
                "page_number": self.page_number,
                "page_end": self.page_end,
                "chunk_index": self.chunk_index,
                "has_table": self.metadata.has_table,
                "section_title": self.metadata.section_title,
                "extraction_method": self.metadata.extraction_method,
            },
        }

    @classmethod
    def from_chromadb_result(
        cls,
        id: str,
        content: str,
        embedding: Optional[list[float]],
        metadata: dict[str, Any],
    ) -> "Chunk":
        """Create from ChromaDB query result.

        Args:
            id: Chunk ID.
            content: Text content.
            embedding: Embedding vector.
            metadata: Chunk metadata.

        Returns:
            Chunk instance.
        """
        return cls(
            id=id,
            document_id=metadata["document_id"],
            document_name=metadata.get("document_name", ""),
            content=content,
            page_number=metadata["page_number"],
            page_end=metadata.get("page_end"),
            chunk_index=metadata.get("chunk_index", 0),
            embedding=embedding,
            metadata=ChunkMetadata(
                has_table=metadata.get("has_table", False),
                section_title=metadata.get("section_title"),
                extraction_method=metadata.get("extraction_method", "text"),
            ),
        )

    def estimate_tokens(self) -> int:
        """Estimate token count based on content length.

        Uses rough approximation of ~4 characters per token.

        Returns:
            Estimated token count.
        """
        self.token_count = len(self.content) // 4
        return self.token_count
