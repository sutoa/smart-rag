"""LLM-assisted semantic chunking service for Smart RAG."""

import logging
from typing import Optional

from src.lib.openai_client import OpenAIClient, get_openai_client
from src.models.chunk import Chunk, ChunkMetadata
from src.models.config import Settings, get_settings
from src.services.pdf_extractor import ExtractedPage

logger = logging.getLogger(__name__)


class Chunker:
    """LLM-assisted semantic chunking with variable boundaries.

    Chunks are determined by natural semantic boundaries (paragraphs,
    sections, logical units) rather than fixed token counts.
    """

    # Maximum characters to send to LLM for chunking at once
    MAX_CHUNK_INPUT_CHARS = 12000

    # Fallback chunk size when LLM chunking fails
    FALLBACK_CHUNK_SIZE = 2000

    # Minimum chunk size (characters)
    MIN_CHUNK_SIZE = 50

    def __init__(
        self,
        settings: Optional[Settings] = None,
        openai_client: Optional[OpenAIClient] = None,
    ):
        """Initialize chunker.

        Args:
            settings: Application settings.
            openai_client: OpenAI client for LLM operations.
        """
        self.settings = settings or get_settings()
        self.openai_client = openai_client

    def _get_client(self) -> OpenAIClient:
        """Get OpenAI client (lazy initialization).

        Returns:
            OpenAI client instance.
        """
        if self.openai_client is None:
            self.openai_client = get_openai_client()
        return self.openai_client

    def chunk_pages(
        self,
        pages: list[ExtractedPage],
        document_id: str,
        document_name: str,
    ) -> list[Chunk]:
        """Chunk extracted pages using LLM-assisted semantic boundaries.

        Args:
            pages: List of extracted pages.
            document_id: Parent document ID.
            document_name: Document filename for metadata.

        Returns:
            List of Chunk objects with embeddings.
        """
        all_chunks: list[Chunk] = []
        chunk_index = 0

        for page in pages:
            content = page.combined_content
            if not content or len(content.strip()) < self.MIN_CHUNK_SIZE:
                continue

            # Get semantic chunks for this page
            page_chunks = self._chunk_text(
                text=content,
                page_number=page.page_number,
                document_id=document_id,
                document_name=document_name,
                start_chunk_index=chunk_index,
            )

            all_chunks.extend(page_chunks)
            chunk_index += len(page_chunks)

        if not all_chunks:
            logger.warning(f"No chunks created for document {document_name}")
            return []

        # Generate embeddings in batch
        all_chunks = self._add_embeddings(all_chunks)

        logger.info(
            f"Created {len(all_chunks)} chunks for {document_name} "
            f"({len(pages)} pages)"
        )

        return all_chunks

    def _chunk_text(
        self,
        text: str,
        page_number: int,
        document_id: str,
        document_name: str,
        start_chunk_index: int,
    ) -> list[Chunk]:
        """Chunk text using LLM for semantic boundaries.

        Args:
            text: Text to chunk.
            page_number: Source page number.
            document_id: Parent document ID.
            document_name: Source document filename.
            start_chunk_index: Starting index for chunks.

        Returns:
            List of Chunk objects (without embeddings).
        """
        chunks: list[Chunk] = []

        # If text is short enough, try LLM chunking
        if len(text) <= self.MAX_CHUNK_INPUT_CHARS:
            try:
                llm_chunks = self._llm_chunk(text, page_number)
                for i, chunk_data in enumerate(llm_chunks):
                    content = chunk_data.get("content", "").strip()
                    if len(content) >= self.MIN_CHUNK_SIZE:
                        chunks.append(
                            Chunk(
                                document_id=document_id,
                                document_name=document_name,
                                content=content,
                                page_number=page_number,
                                chunk_index=start_chunk_index + i,
                                metadata=ChunkMetadata(
                                    has_table=chunk_data.get("has_table", False),
                                    section_title=chunk_data.get("section_title"),
                                    extraction_method="text",
                                ),
                            )
                        )
                if chunks:
                    return chunks
            except Exception as e:
                logger.warning(f"LLM chunking failed, using fallback: {e}")

        # Fallback: simple text splitting
        return self._fallback_chunk(
            text=text,
            page_number=page_number,
            document_id=document_id,
            document_name=document_name,
            start_chunk_index=start_chunk_index,
        )

    def _llm_chunk(self, text: str, page_number: int) -> list[dict]:
        """Use LLM to identify semantic chunk boundaries.

        Args:
            text: Text to chunk.
            page_number: Page number for context.

        Returns:
            List of chunk dictionaries with content and metadata.
        """
        client = self._get_client()
        page_info = f"Page {page_number}"
        return client.chunk_text(text, page_info)

    def _fallback_chunk(
        self,
        text: str,
        page_number: int,
        document_id: str,
        document_name: str,
        start_chunk_index: int,
    ) -> list[Chunk]:
        """Fallback chunking using paragraph boundaries.

        Args:
            text: Text to chunk.
            page_number: Source page number.
            document_id: Parent document ID.
            document_name: Source document filename.
            start_chunk_index: Starting index for chunks.

        Returns:
            List of Chunk objects.
        """
        chunks: list[Chunk] = []

        # Split by double newlines (paragraphs)
        paragraphs = text.split("\n\n")

        current_chunk = ""
        chunk_index = start_chunk_index

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph would exceed max size, save current chunk
            if current_chunk and len(current_chunk) + len(para) > self.FALLBACK_CHUNK_SIZE:
                if len(current_chunk) >= self.MIN_CHUNK_SIZE:
                    chunks.append(
                        Chunk(
                            document_id=document_id,
                            document_name=document_name,
                            content=current_chunk.strip(),
                            page_number=page_number,
                            chunk_index=chunk_index,
                            metadata=ChunkMetadata(
                                has_table="[Table]" in current_chunk,
                                extraction_method="text",
                            ),
                        )
                    )
                    chunk_index += 1
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk and len(current_chunk) >= self.MIN_CHUNK_SIZE:
            chunks.append(
                Chunk(
                    document_id=document_id,
                    document_name=document_name,
                    content=current_chunk.strip(),
                    page_number=page_number,
                    chunk_index=chunk_index,
                    metadata=ChunkMetadata(
                        has_table="[Table]" in current_chunk,
                        extraction_method="text",
                    ),
                )
            )

        return chunks

    # Maximum chunks per embedding batch (OpenAI limit is ~8K tokens input)
    EMBEDDING_BATCH_SIZE = 50

    # Maximum characters per chunk for embedding (8192 tokens * ~3.5 chars/token, with safety margin)
    MAX_EMBEDDING_CHARS = 24000

    def _split_oversized_chunk(self, chunk: Chunk) -> list[Chunk]:
        """Split a chunk that exceeds embedding token limit.

        Args:
            chunk: Chunk that may be too large.

        Returns:
            List of chunks, possibly split if original was too large.
        """
        if len(chunk.content) <= self.MAX_EMBEDDING_CHARS:
            return [chunk]

        # Split into smaller pieces
        content = chunk.content
        sub_chunks = []
        chunk_idx = 0

        while content:
            # Take up to MAX_EMBEDDING_CHARS, but try to split at paragraph boundary
            if len(content) <= self.MAX_EMBEDDING_CHARS:
                piece = content
                content = ""
            else:
                # Find a good split point (paragraph or sentence)
                split_point = self.MAX_EMBEDDING_CHARS
                # Look for paragraph break
                para_break = content.rfind("\n\n", 0, split_point)
                if para_break > split_point // 2:
                    split_point = para_break
                else:
                    # Look for sentence break
                    for sep in [". ", ".\n", "? ", "!\n"]:
                        sent_break = content.rfind(sep, 0, self.MAX_EMBEDDING_CHARS)
                        if sent_break > split_point // 2:
                            split_point = sent_break + len(sep)
                            break

                piece = content[:split_point].strip()
                content = content[split_point:].strip()

            if piece and len(piece) >= self.MIN_CHUNK_SIZE:
                sub_chunks.append(
                    Chunk(
                        document_id=chunk.document_id,
                        document_name=chunk.document_name,
                        content=piece,
                        page_number=chunk.page_number,
                        chunk_index=chunk.chunk_index + chunk_idx,
                        metadata=chunk.metadata,
                    )
                )
                chunk_idx += 1

        logger.info(f"Split oversized chunk into {len(sub_chunks)} smaller chunks")
        return sub_chunks if sub_chunks else [chunk]

    def _add_embeddings(self, chunks: list[Chunk]) -> list[Chunk]:
        """Add embeddings to chunks in optimized batches.

        Batches API calls for efficiency while respecting rate limits.

        Args:
            chunks: List of chunks without embeddings.

        Returns:
            Same chunks with embeddings added.
        """
        if not chunks:
            return chunks

        # Split any oversized chunks before embedding
        processed_chunks: list[Chunk] = []
        for chunk in chunks:
            processed_chunks.extend(self._split_oversized_chunk(chunk))

        client = self._get_client()

        # Process in batches for optimal API usage
        all_embeddings: list[list[float]] = []

        for i in range(0, len(processed_chunks), self.EMBEDDING_BATCH_SIZE):
            batch = processed_chunks[i : i + self.EMBEDDING_BATCH_SIZE]
            texts = [chunk.content for chunk in batch]

            try:
                # Batch embedding generation
                batch_embeddings = client.get_embeddings(texts)
                all_embeddings.extend(batch_embeddings)

                if len(processed_chunks) > self.EMBEDDING_BATCH_SIZE:
                    logger.debug(
                        f"Embedded batch {i // self.EMBEDDING_BATCH_SIZE + 1}/"
                        f"{(len(processed_chunks) - 1) // self.EMBEDDING_BATCH_SIZE + 1}"
                    )

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch: {e}")
                raise

        # Assign embeddings to chunks
        for chunk, embedding in zip(processed_chunks, all_embeddings):
            chunk.embedding = embedding
            chunk.estimate_tokens()

        return processed_chunks

    def chunk_single_text(
        self,
        text: str,
        document_id: str,
        document_name: str = "",
        page_number: int = 1,
    ) -> list[Chunk]:
        """Chunk a single text string.

        Convenience method for chunking arbitrary text.

        Args:
            text: Text to chunk.
            document_id: Document ID for chunks.
            document_name: Document filename.
            page_number: Page number to assign.

        Returns:
            List of Chunk objects with embeddings.
        """
        chunks = self._chunk_text(
            text=text,
            page_number=page_number,
            document_id=document_id,
            document_name=document_name,
            start_chunk_index=0,
        )

        if chunks:
            chunks = self._add_embeddings(chunks)

        return chunks
