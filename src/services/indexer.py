"""Document indexing service for Smart RAG."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from src.lib.metadata_store import MetadataStore, get_metadata_store
from src.lib.vector_store import VectorStore, get_vector_store
from src.models.config import Settings, get_settings
from src.models.document import Document, DocumentStatus
from src.services.chunker import Chunker
from src.services.pdf_extractor import (
    PDFCorruptedError,
    PDFExtractionError,
    PDFExtractor,
    PDFPasswordProtectedError,
)

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    """Result of indexing a single document.

    Attributes:
        document: The indexed document.
        success: Whether indexing succeeded.
        error_message: Error message if failed.
        chunks_created: Number of chunks created.
    """

    document: Document
    success: bool
    error_message: Optional[str] = None
    chunks_created: int = 0


@dataclass
class IndexingSummary:
    """Summary of a batch indexing operation.

    Attributes:
        total_documents: Total PDFs found.
        indexed: Number successfully indexed.
        skipped: Number skipped (already indexed or errors).
        failed: Number that failed with errors.
        total_chunks: Total chunks created.
        elapsed_seconds: Time taken in seconds.
        results: Individual document results.
    """

    total_documents: int
    indexed: int
    skipped: int
    failed: int
    total_chunks: int
    elapsed_seconds: float
    results: list[IndexingResult]

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.indexed / self.total_documents) * 100


class Indexer:
    """Orchestrate PDF extraction, chunking, and storage.

    Handles:
    - Document discovery and validation
    - Status management (pending → processing → completed/failed)
    - Progress feedback
    - Error handling for corrupt/protected PDFs
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        extractor: Optional[PDFExtractor] = None,
        chunker: Optional[Chunker] = None,
        vector_store: Optional[VectorStore] = None,
        metadata_store: Optional[MetadataStore] = None,
    ):
        """Initialize indexer with dependencies.

        Args:
            settings: Application settings.
            extractor: PDF extractor service.
            chunker: Chunking service.
            vector_store: Vector database.
            metadata_store: Document metadata store.
        """
        self.settings = settings or get_settings()
        self.extractor = extractor or PDFExtractor()
        self.chunker = chunker or Chunker(settings=self.settings)
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    def _get_vector_store(self) -> VectorStore:
        """Get vector store (lazy initialization)."""
        if self.vector_store is None:
            self.vector_store = get_vector_store()
        return self.vector_store

    def _get_metadata_store(self) -> MetadataStore:
        """Get metadata store (lazy initialization)."""
        if self.metadata_store is None:
            self.metadata_store = get_metadata_store()
        return self.metadata_store

    def index_folder(
        self,
        folder_path: Path,
        recursive: bool = False,
        force: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        show_progress: bool = True,
    ) -> IndexingSummary:
        """Index all PDF files in a folder.

        Args:
            folder_path: Path to folder containing PDFs.
            recursive: Include subdirectories.
            force: Reindex already indexed documents.
            progress_callback: Optional callback(filename, current, total).
            show_progress: Show rich progress bar.

        Returns:
            IndexingSummary with results.
        """
        start_time = datetime.now()

        # Discover PDF files
        pdf_files = self._discover_pdfs(folder_path, recursive)

        if not pdf_files:
            return IndexingSummary(
                total_documents=0,
                indexed=0,
                skipped=0,
                failed=0,
                total_chunks=0,
                elapsed_seconds=0.0,
                results=[],
            )

        results: list[IndexingResult] = []
        indexed_count = 0
        skipped_count = 0
        failed_count = 0
        total_chunks = 0

        metadata_store = self._get_metadata_store()

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Indexing PDFs...", total=len(pdf_files))

                for i, pdf_path in enumerate(pdf_files):
                    progress.update(
                        task,
                        description=f"Processing: {pdf_path.name}",
                        completed=i,
                    )

                    result = self._index_document(
                        pdf_path, force, metadata_store
                    )
                    results.append(result)

                    if result.success:
                        indexed_count += 1
                        total_chunks += result.chunks_created
                    elif result.error_message and "already indexed" in result.error_message.lower():
                        skipped_count += 1
                    else:
                        failed_count += 1

                    if progress_callback:
                        progress_callback(pdf_path.name, i + 1, len(pdf_files))

                progress.update(task, completed=len(pdf_files))
        else:
            for i, pdf_path in enumerate(pdf_files):
                result = self._index_document(pdf_path, force, metadata_store)
                results.append(result)

                if result.success:
                    indexed_count += 1
                    total_chunks += result.chunks_created
                elif result.error_message and "already indexed" in result.error_message.lower():
                    skipped_count += 1
                else:
                    failed_count += 1

                if progress_callback:
                    progress_callback(pdf_path.name, i + 1, len(pdf_files))

        elapsed = (datetime.now() - start_time).total_seconds()

        return IndexingSummary(
            total_documents=len(pdf_files),
            indexed=indexed_count,
            skipped=skipped_count,
            failed=failed_count,
            total_chunks=total_chunks,
            elapsed_seconds=elapsed,
            results=results,
        )

    def index_document(self, file_path: Path, force: bool = False) -> IndexingResult:
        """Index a single PDF document.

        Args:
            file_path: Path to PDF file.
            force: Reindex if already indexed.

        Returns:
            IndexingResult with status.
        """
        metadata_store = self._get_metadata_store()
        return self._index_document(file_path, force, metadata_store)

    def _index_document(
        self,
        file_path: Path,
        force: bool,
        metadata_store: MetadataStore,
    ) -> IndexingResult:
        """Internal method to index a single document.

        Args:
            file_path: Path to PDF file.
            force: Reindex if already indexed.
            metadata_store: Metadata store instance.

        Returns:
            IndexingResult with status.
        """
        vector_store = self._get_vector_store()

        # Check if already indexed
        existing = metadata_store.get_by_path(str(file_path.absolute()))
        if existing and not force:
            if existing.status == DocumentStatus.COMPLETED:
                return IndexingResult(
                    document=existing,
                    success=False,
                    error_message="Already indexed (use --force to reindex)",
                )

        # Validate PDF
        is_valid, error_msg = self.extractor.is_valid_pdf(file_path)
        if not is_valid:
            # Create failed document record
            try:
                page_count = 0
            except Exception:
                page_count = 0

            doc = Document(
                name=file_path.name,
                file_path=str(file_path.absolute()),
                page_count=page_count or 1,
                status=DocumentStatus.FAILED,
                error_message=error_msg,
            )

            if existing:
                doc.id = existing.id
                metadata_store.update(doc)
            else:
                metadata_store.add(doc)

            return IndexingResult(
                document=doc,
                success=False,
                error_message=error_msg,
            )

        try:
            # Get page count
            page_count = self.extractor.get_page_count(file_path)

            # Create or update document record
            if existing:
                doc = existing
                doc.status = DocumentStatus.PROCESSING
                doc.error_message = None
                metadata_store.update(doc)

                # Remove old chunks if reindexing
                vector_store.delete_by_document_id(doc.id)
            else:
                doc = Document.from_file(file_path, page_count)
                doc.status = DocumentStatus.PROCESSING
                metadata_store.add(doc)

            # Extract pages
            pages = list(self.extractor.extract_pages(file_path))

            # Chunk and embed
            chunks = self.chunker.chunk_pages(
                pages=pages,
                document_id=doc.id,
                document_name=doc.name,
            )

            if not chunks:
                doc.mark_failed("No content could be extracted")
                metadata_store.update(doc)
                return IndexingResult(
                    document=doc,
                    success=False,
                    error_message="No content extracted",
                )

            # Store chunks in vector database
            vector_store.add_chunks(chunks)

            # Update document status
            doc.mark_completed(len(chunks))
            metadata_store.update(doc)

            logger.info(f"Indexed {doc.name}: {len(chunks)} chunks")

            return IndexingResult(
                document=doc,
                success=True,
                chunks_created=len(chunks),
            )

        except PDFPasswordProtectedError as e:
            error_msg = "Password protected"
            doc = self._create_failed_document(
                file_path, error_msg, existing, metadata_store
            )
            return IndexingResult(document=doc, success=False, error_message=error_msg)

        except PDFCorruptedError as e:
            error_msg = "Unable to read PDF (corrupted)"
            doc = self._create_failed_document(
                file_path, error_msg, existing, metadata_store
            )
            return IndexingResult(document=doc, success=False, error_message=error_msg)

        except PDFExtractionError as e:
            error_msg = f"Extraction error: {e}"
            doc = self._create_failed_document(
                file_path, error_msg, existing, metadata_store
            )
            return IndexingResult(document=doc, success=False, error_message=error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.exception(f"Failed to index {file_path}")
            doc = self._create_failed_document(
                file_path, error_msg, existing, metadata_store
            )
            return IndexingResult(document=doc, success=False, error_message=error_msg)

    def _create_failed_document(
        self,
        file_path: Path,
        error_message: str,
        existing: Optional[Document],
        metadata_store: MetadataStore,
    ) -> Document:
        """Create or update a failed document record.

        Args:
            file_path: Path to PDF.
            error_message: Error description.
            existing: Existing document if any.
            metadata_store: Metadata store.

        Returns:
            Document with failed status.
        """
        if existing:
            existing.mark_failed(error_message)
            metadata_store.update(existing)
            return existing

        doc = Document(
            name=file_path.name,
            file_path=str(file_path.absolute()),
            page_count=1,
            status=DocumentStatus.FAILED,
            error_message=error_message,
        )
        metadata_store.add(doc)
        return doc

    def _discover_pdfs(self, folder_path: Path, recursive: bool) -> list[Path]:
        """Discover PDF files in a folder.

        Args:
            folder_path: Folder to search.
            recursive: Include subdirectories.

        Returns:
            List of PDF file paths.
        """
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(folder_path.glob(pattern))

        # Also check case-insensitive
        pattern_upper = "**/*.PDF" if recursive else "*.PDF"
        pdf_files.extend(
            p for p in folder_path.glob(pattern_upper) if p not in pdf_files
        )

        # Sort for consistent ordering
        pdf_files.sort(key=lambda p: p.name.lower())

        logger.info(f"Found {len(pdf_files)} PDF files in {folder_path}")
        return pdf_files

    def clear_all(self) -> tuple[int, int]:
        """Clear all indexed data.

        Returns:
            Tuple of (documents_deleted, chunks_deleted).
        """
        vector_store = self._get_vector_store()
        metadata_store = self._get_metadata_store()

        chunks_deleted = vector_store.delete_all()
        docs_deleted = metadata_store.delete_all()

        logger.info(f"Cleared {docs_deleted} documents and {chunks_deleted} chunks")
        return docs_deleted, chunks_deleted
