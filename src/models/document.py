"""Document model for Smart RAG."""

import hashlib
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class DocumentStatus(str, Enum):
    """Document indexing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    """Represents an indexed PDF file.

    Attributes:
        id: Unique identifier (UUID).
        name: Original filename.
        file_path: Absolute path to PDF.
        page_count: Number of pages.
        indexed_at: When document was indexed.
        status: Indexing status.
        error_message: Error details if failed.
        file_hash: SHA-256 hash for duplicate detection.
        chunk_count: Number of chunks created.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, description="Original filename")
    file_path: str = Field(..., description="Absolute path to PDF")
    page_count: int = Field(..., ge=1, description="Number of pages")
    indexed_at: datetime = Field(default_factory=datetime.utcnow)
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)
    error_message: Optional[str] = Field(default=None)
    file_hash: Optional[str] = Field(default=None, description="SHA-256 hash of file")
    chunk_count: int = Field(default=0, ge=0, description="Number of chunks created")

    @field_validator("name")
    @classmethod
    def validate_pdf_extension(cls, v: str) -> str:
        """Ensure filename ends with .pdf (case-insensitive)."""
        if not v.lower().endswith(".pdf"):
            raise ValueError("Document name must end with .pdf")
        return v

    @classmethod
    def from_file(cls, file_path: Path, page_count: int) -> "Document":
        """Create a Document from a file path.

        Args:
            file_path: Path to the PDF file.
            page_count: Number of pages in the PDF.

        Returns:
            New Document instance.
        """
        return cls(
            name=file_path.name,
            file_path=str(file_path.absolute()),
            page_count=page_count,
            file_hash=cls.compute_file_hash(file_path),
        )

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of a file.

        Args:
            file_path: Path to the file.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def mark_processing(self) -> None:
        """Mark document as processing."""
        self.status = DocumentStatus.PROCESSING

    def mark_completed(self, chunk_count: int) -> None:
        """Mark document as completed.

        Args:
            chunk_count: Number of chunks created.
        """
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count

    def mark_failed(self, error_message: str) -> None:
        """Mark document as failed.

        Args:
            error_message: Error description.
        """
        self.status = DocumentStatus.FAILED
        self.error_message = error_message

    def to_dict(self) -> dict:
        """Convert to dictionary for storage.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "name": self.name,
            "file_path": self.file_path,
            "page_count": self.page_count,
            "indexed_at": self.indexed_at.isoformat(),
            "status": self.status.value,
            "error_message": self.error_message,
            "file_hash": self.file_hash,
            "chunk_count": self.chunk_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Create from dictionary.

        Args:
            data: Dictionary with document fields.

        Returns:
            Document instance.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            file_path=data["file_path"],
            page_count=data["page_count"],
            indexed_at=datetime.fromisoformat(data["indexed_at"]),
            status=DocumentStatus(data["status"]),
            error_message=data.get("error_message"),
            file_hash=data.get("file_hash"),
            chunk_count=data.get("chunk_count", 0),
        )
