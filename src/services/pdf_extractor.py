"""PDF text and table extraction service for Smart RAG."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

import pdfplumber
from pdfplumber.page import Page

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPage:
    """Extracted content from a PDF page.

    Attributes:
        page_number: 1-indexed page number.
        text: Extracted text content.
        tables: List of extracted tables (as list of rows).
        has_tables: Whether the page contains tables.
    """

    page_number: int
    text: str
    tables: list[list[list[str]]]
    has_tables: bool

    @property
    def combined_content(self) -> str:
        """Get combined text and table content.

        Returns:
            Text with tables formatted as readable text.
        """
        parts = []

        if self.text:
            parts.append(self.text)

        for table in self.tables:
            if table:
                table_text = self._format_table(table)
                if table_text:
                    parts.append(f"\n[Table]\n{table_text}\n[/Table]")

        return "\n".join(parts)

    def _format_table(self, table: list[list[str]]) -> str:
        """Format a table as readable text.

        Args:
            table: List of rows, each row is a list of cell values.

        Returns:
            Formatted table string.
        """
        if not table:
            return ""

        rows = []
        for row in table:
            # Filter None values and convert to strings
            cells = [str(cell) if cell is not None else "" for cell in row]
            rows.append(" | ".join(cells))

        return "\n".join(rows)


class PDFExtractionError(Exception):
    """Error during PDF extraction."""

    pass


class PDFPasswordProtectedError(PDFExtractionError):
    """PDF is password protected."""

    pass


class PDFCorruptedError(PDFExtractionError):
    """PDF is corrupted or unreadable."""

    pass


class PDFExtractor:
    """Extract text and tables from PDF files.

    Uses pdfplumber for extraction with memory-efficient page iteration.
    """

    def __init__(self):
        """Initialize PDF extractor."""
        pass

    def get_page_count(self, file_path: Path) -> int:
        """Get the number of pages in a PDF.

        Args:
            file_path: Path to PDF file.

        Returns:
            Number of pages.

        Raises:
            PDFPasswordProtectedError: If PDF is password protected.
            PDFCorruptedError: If PDF is corrupted.
            PDFExtractionError: For other extraction errors.
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            self._handle_extraction_error(e, file_path)
            raise  # This line won't be reached but satisfies type checker

    def extract_pages(
        self,
        file_path: Path,
        start_page: int = 1,
        end_page: Optional[int] = None,
    ) -> Generator[ExtractedPage, None, None]:
        """Extract content from PDF pages.

        Uses generator pattern with flush_cache() for memory efficiency
        when processing large documents.

        Args:
            file_path: Path to PDF file.
            start_page: First page to extract (1-indexed).
            end_page: Last page to extract (inclusive). None for all pages.

        Yields:
            ExtractedPage for each page.

        Raises:
            PDFPasswordProtectedError: If PDF is password protected.
            PDFCorruptedError: If PDF is corrupted.
            PDFExtractionError: For other extraction errors.
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)

                # Adjust page range
                start_idx = max(0, start_page - 1)
                end_idx = min(total_pages, end_page) if end_page else total_pages

                for page_idx in range(start_idx, end_idx):
                    page = pdf.pages[page_idx]
                    page_number = page_idx + 1

                    try:
                        extracted = self._extract_page(page, page_number)
                        yield extracted
                    except Exception as e:
                        logger.warning(
                            f"Error extracting page {page_number} from {file_path}: {e}"
                        )
                        # Yield empty page instead of failing completely
                        yield ExtractedPage(
                            page_number=page_number,
                            text="",
                            tables=[],
                            has_tables=False,
                        )
                    finally:
                        # Flush cache after each page for memory efficiency
                        page.flush_cache()

        except Exception as e:
            self._handle_extraction_error(e, file_path)

    def extract_all(self, file_path: Path) -> list[ExtractedPage]:
        """Extract all pages from a PDF.

        Args:
            file_path: Path to PDF file.

        Returns:
            List of ExtractedPage objects.

        Raises:
            PDFPasswordProtectedError: If PDF is password protected.
            PDFCorruptedError: If PDF is corrupted.
            PDFExtractionError: For other extraction errors.
        """
        return list(self.extract_pages(file_path))

    def extract_text_only(self, file_path: Path) -> str:
        """Extract all text from a PDF (without table formatting).

        Args:
            file_path: Path to PDF file.

        Returns:
            Combined text from all pages.
        """
        pages = self.extract_all(file_path)
        return "\n\n".join(
            page.combined_content for page in pages if page.combined_content
        )

    def _extract_page(self, page: Page, page_number: int) -> ExtractedPage:
        """Extract content from a single page.

        Args:
            page: pdfplumber Page object.
            page_number: 1-indexed page number.

        Returns:
            ExtractedPage with extracted content.
        """
        # Extract text with layout preservation for better table handling
        text = page.extract_text(layout=True) or ""

        # Extract tables
        tables = []
        try:
            raw_tables = page.extract_tables()
            if raw_tables:
                for table in raw_tables:
                    if table and any(any(cell for cell in row) for row in table):
                        tables.append(table)
        except Exception as e:
            logger.debug(f"Table extraction failed for page {page_number}: {e}")

        return ExtractedPage(
            page_number=page_number,
            text=text.strip(),
            tables=tables,
            has_tables=len(tables) > 0,
        )

    def _handle_extraction_error(self, error: Exception, file_path: Path) -> None:
        """Handle extraction errors and raise appropriate exceptions.

        Args:
            error: Original exception.
            file_path: Path to the PDF file.

        Raises:
            PDFPasswordProtectedError: If PDF is password protected.
            PDFCorruptedError: If PDF is corrupted.
            PDFExtractionError: For other errors.
        """
        error_str = str(error).lower()

        if "password" in error_str or "encrypted" in error_str:
            raise PDFPasswordProtectedError(
                f"PDF is password protected: {file_path}"
            ) from error

        if (
            "corrupt" in error_str
            or "invalid" in error_str
            or "unable to read" in error_str
            or "no pdf" in error_str
        ):
            raise PDFCorruptedError(f"PDF is corrupted or invalid: {file_path}") from error

        raise PDFExtractionError(f"Failed to extract PDF: {file_path} - {error}") from error

    def is_valid_pdf(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """Check if a file is a valid, readable PDF.

        Args:
            file_path: Path to PDF file.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        if not file_path.suffix.lower() == ".pdf":
            return False, f"Not a PDF file: {file_path}"

        try:
            with pdfplumber.open(file_path) as pdf:
                # Try to access pages to verify it's readable
                _ = len(pdf.pages)
                if pdf.pages:
                    # Try to extract first page to verify content access
                    _ = pdf.pages[0].extract_text()
            return True, None
        except Exception as e:
            error_str = str(e).lower()
            if "password" in error_str or "encrypted" in error_str:
                return False, "Password protected"
            return False, f"Unable to read PDF: {e}"
