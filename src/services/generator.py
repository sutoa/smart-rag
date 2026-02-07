"""Grounded response generation service for Smart RAG."""

import logging
import re
import time
from typing import Optional

from src.lib.openai_client import OpenAIClient, get_openai_client
from src.models.config import Settings, get_settings
from src.models.response import Citation, Response, ResponseMetadata
from src.services.retriever import RetrievedChunk, RetrievalResult

logger = logging.getLogger(__name__)

# Patterns that indicate entity/list queries
ENTITY_QUERY_PATTERNS = [
    r"^who\s+(are|is|were|was)\s+",
    r"^what\s+(are|is|were|was)\s+all\s+",
    r"^what\s+(are|is)\s+the\s+\w+s\b",
    r"^list\s+(all\s+)?(the\s+)?",
    r"^name\s+(all\s+)?(the\s+)?",
    r"^which\s+\w+s\s+(are|were|have|had)",
    r"^how\s+many\s+",
    r"^give\s+me\s+(a\s+)?list\s+",
    r"^enumerate\s+",
    r"^identify\s+(all\s+)?(the\s+)?",
]


class Generator:
    """Generate grounded responses with citations from retrieved chunks.

    Ensures all responses are based on document content with verifiable citations.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        openai_client: Optional[OpenAIClient] = None,
    ):
        """Initialize generator.

        Args:
            settings: Application settings.
            openai_client: OpenAI client for LLM operations.
        """
        self.settings = settings or get_settings()
        self.openai_client = openai_client

    def _get_openai_client(self) -> OpenAIClient:
        """Get OpenAI client (lazy initialization)."""
        if self.openai_client is None:
            self.openai_client = get_openai_client()
        return self.openai_client

    def generate(
        self,
        query: str,
        retrieval_result: RetrievalResult,
        max_sources: int = 5,
    ) -> Response:
        """Generate a grounded response from retrieved chunks.

        Automatically detects entity/list queries and uses appropriate
        generation strategy.

        Args:
            query: User's question.
            retrieval_result: Result from retriever with ranked chunks.
            max_sources: Maximum number of citations to include.

        Returns:
            Response with answer and citations.
        """
        start_time = time.time()

        chunks = retrieval_result.chunks[:max_sources]

        # Handle case with no relevant chunks
        if not chunks:
            generation_time_ms = int((time.time() - start_time) * 1000)
            total_time_ms = retrieval_result.total_time_ms + generation_time_ms
            return Response.not_found_response(
                query_text=query,
                chunks_retrieved=retrieval_result.total_retrieved,
                processing_time_ms=total_time_ms,
            )

        # Note: Relevance filtering disabled - let LLM decide relevance
        # The reranker already scores chunks; additional filtering was too aggressive
        # if self._chunks_irrelevant(chunks):
        #     ...pass chunks to LLM regardless

        # Detect if this is an entity/list query
        is_entity_query = self._is_entity_query(query)

        # Generate response using appropriate strategy
        client = self._get_openai_client()
        context_chunks = [chunk.to_context_dict() for chunk in chunks]

        if is_entity_query:
            llm_response = self._generate_aggregated_response(client, query, context_chunks)
        else:
            llm_response = client.generate_response(query, context_chunks)

        generation_time_ms = int((time.time() - start_time) * 1000)
        total_time_ms = retrieval_result.total_time_ms + generation_time_ms

        # Handle "not found" response from LLM
        if llm_response.get("not_found", False):
            return Response.not_found_response(
                query_text=query,
                chunks_retrieved=retrieval_result.total_retrieved,
                processing_time_ms=total_time_ms,
            )

        # Build citations from LLM response
        citations, quotes_verified = self._extract_citations(
            llm_response.get("citations", []),
            chunks,
        )

        # Calculate confidence score based on relevance scores
        confidence_score = self._calculate_confidence(chunks, citations)

        return Response(
            answer=llm_response.get("answer", ""),
            citations=citations,
            query_text=query,
            metadata=ResponseMetadata(
                chunks_retrieved=retrieval_result.total_retrieved,
                chunks_used=len(citations),
                processing_time_ms=total_time_ms,
                confidence_score=confidence_score,
                quotes_verified=quotes_verified,
            ),
            not_found=False,
        )

    def _is_entity_query(self, query: str) -> bool:
        """Detect if query is asking for a list of entities.

        Args:
            query: User's question.

        Returns:
            True if this appears to be an entity/list query.
        """
        query_lower = query.lower().strip()
        for pattern in ENTITY_QUERY_PATTERNS:
            if re.search(pattern, query_lower):
                return True
        return False

    def _calculate_confidence(
        self,
        chunks: list[RetrievedChunk],
        citations: list[Citation],
    ) -> float:
        """Calculate overall confidence score for the response.

        Confidence is based on:
        - Average relevance score of used chunks
        - Number of citations (more sources = higher confidence)
        - Spread of relevance scores (consistent high scores = higher confidence)

        Args:
            chunks: Retrieved chunks with relevance scores.
            citations: Citations used in the response.

        Returns:
            Confidence score between 0 and 1.
        """
        if not chunks or not citations:
            return 0.0

        # Get relevance scores from citations
        citation_scores = [c.relevance_score for c in citations if c.relevance_score > 0]

        if not citation_scores:
            # Fall back to chunk scores
            citation_scores = [c.relevance_score for c in chunks[:len(citations)]]

        if not citation_scores:
            return 0.0

        # Base confidence: average relevance score
        avg_score = sum(citation_scores) / len(citation_scores)

        # Bonus for multiple sources (up to 10% boost)
        source_bonus = min(len(citations) * 0.02, 0.1)

        # Penalty for high variance in scores (inconsistent relevance)
        if len(citation_scores) > 1:
            variance = sum((s - avg_score) ** 2 for s in citation_scores) / len(citation_scores)
            variance_penalty = min(variance * 0.5, 0.1)
        else:
            variance_penalty = 0.0

        # Calculate final confidence
        confidence = avg_score + source_bonus - variance_penalty

        # Clamp to 0-1 range
        return max(0.0, min(1.0, round(confidence, 2)))

    def _generate_aggregated_response(
        self,
        client: OpenAIClient,
        query: str,
        context_chunks: list[dict],
    ) -> dict:
        """Generate an aggregated response for entity/list queries.

        Uses a specialized prompt that synthesizes information across
        multiple sources and groups citations by item.

        Args:
            client: OpenAI client.
            query: User's question.
            context_chunks: Retrieved chunks with metadata.

        Returns:
            Dictionary with 'answer', 'citations', and 'not_found' keys.
        """
        # Format context for the prompt
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            source = f"[Source {i}: {chunk['document_name']}, page {chunk['page_number']}]"
            context_parts.append(f"{source}\n{chunk['content']}\n")

        context = "\n---\n".join(context_parts)

        system_prompt = """You are a precise document question-answering assistant specializing in aggregating information from multiple sources.

Your task is to compile a COMPLETE list or answer by synthesizing information from ALL provided sources.

CRITICAL RULES:
1. AGGREGATE information from ALL sources - do not limit to just one source
2. For each item in your list, cite the specific source(s) where it was found using [Source N]
3. If the same entity/item appears in multiple sources, mention all sources
4. Eliminate duplicates - if the same item appears in multiple sources, list it once but cite all sources
5. ONLY include information actually present in the sources - never fabricate
6. If sources contain partial or different information about the same topic, synthesize them
7. Format lists clearly with each item on its own line

Output format: Return a JSON object with:
- "answer": Your complete aggregated answer with inline citations [Source N] for each item
- "citations": Array of objects with "source_index" (1-based), "verbatim_quote" (exact text supporting an item)
- "not_found": Boolean, true if sources don't contain relevant information

Example for "Who are the managers?":
{
  "answer": "Based on the documents, the managers are:\\n\\n1. John Smith - Regional Manager [Source 1]\\n2. Jane Doe - Department Manager [Source 1, Source 2]\\n3. Bob Wilson - Project Manager [Source 3]",
  "citations": [
    {"source_index": 1, "verbatim_quote": "John Smith serves as Regional Manager"},
    {"source_index": 1, "verbatim_quote": "Jane Doe is the Department Manager"},
    {"source_index": 2, "verbatim_quote": "Jane Doe manages the engineering department"},
    {"source_index": 3, "verbatim_quote": "Bob Wilson, Project Manager, oversees..."}
  ],
  "not_found": false
}"""

        user_message = f"""Question: {query}

Sources:
{context}

Compile a COMPLETE answer by aggregating information from ALL sources. For list queries, include ALL matching items found across all documents. Return ONLY the JSON object."""

        response = client.chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.0,
            max_tokens=4096,
        )

        # Parse JSON response
        import json

        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            result = json.loads(response.strip())
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse aggregated response: {e}")
            return {
                "answer": response,
                "citations": [],
                "not_found": False,
            }

    def _chunks_irrelevant(
        self,
        chunks: list[RetrievedChunk],
        threshold: float = 0.1,
    ) -> bool:
        """Check if retrieved chunks are too irrelevant.

        Args:
            chunks: Retrieved chunks with relevance scores.
            threshold: Minimum relevance score for top chunk.

        Returns:
            True if chunks are likely irrelevant to query.
        """
        if not chunks:
            return True

        # If the best chunk has very low relevance, probably irrelevant
        top_score = chunks[0].relevance_score
        return top_score < threshold

    def _extract_citations(
        self,
        llm_citations: list[dict],
        chunks: list[RetrievedChunk],
    ) -> tuple[list[Citation], int]:
        """Extract and validate citations from LLM response.

        Args:
            llm_citations: Citations from LLM response.
            chunks: Original retrieved chunks.

        Returns:
            Tuple of (validated Citation objects, number of verified quotes).
        """
        citations = []
        seen_quotes = set()
        verified_count = 0

        for cit in llm_citations:
            source_index = cit.get("source_index", 0) - 1  # Convert to 0-indexed

            if source_index < 0 or source_index >= len(chunks):
                logger.debug(f"Invalid source index: {source_index + 1}")
                continue

            chunk = chunks[source_index]
            verbatim_quote = cit.get("verbatim_quote", "")

            # Skip duplicate quotes
            if verbatim_quote in seen_quotes:
                continue
            seen_quotes.add(verbatim_quote)

            # Validate quote exists in chunk (fuzzy match)
            quote_verified = False
            if verbatim_quote:
                if self._validate_quote(verbatim_quote, chunk.content):
                    quote_verified = True
                    verified_count += 1
                else:
                    # Try to find a similar quote in the chunk
                    logger.debug(f"Quote not found exactly, finding similar: {verbatim_quote[:50]}...")
                    verbatim_quote = self._find_similar_quote(verbatim_quote, chunk.content)

            citations.append(
                Citation(
                    document_name=chunk.document_name,
                    page_number=chunk.page_number,
                    verbatim_quote=verbatim_quote,
                    relevance_score=chunk.relevance_score,
                )
            )

        # If LLM didn't provide citations, create from top chunks
        if not citations and chunks:
            for chunk in chunks[:3]:
                # Extract a meaningful quote from the chunk
                quote = self._extract_best_quote(chunk.content)
                citations.append(
                    Citation(
                        document_name=chunk.document_name,
                        page_number=chunk.page_number,
                        verbatim_quote=quote,
                        relevance_score=chunk.relevance_score,
                    )
                )
                # Extracted quotes are always verified since they come from the chunk
                verified_count += 1

        return citations, verified_count

    def _validate_quote(self, quote: str, content: str) -> bool:
        """Validate that a quote exists in the content.

        Args:
            quote: Verbatim quote to validate.
            content: Source content.

        Returns:
            True if quote is found in content.
        """
        if not quote or not content:
            return False

        # Normalize for comparison
        quote_lower = quote.lower().strip()
        content_lower = content.lower()

        # Exact match
        if quote_lower in content_lower:
            return True

        # Check for substantial overlap (80% of words)
        quote_words = set(quote_lower.split())
        content_words = set(content_lower.split())
        overlap = quote_words & content_words

        if len(quote_words) > 0:
            overlap_ratio = len(overlap) / len(quote_words)
            return overlap_ratio >= 0.8

        return False

    def _find_similar_quote(self, quote: str, content: str, max_len: int = 200) -> str:
        """Find a similar passage in content when exact quote not found.

        Args:
            quote: Original quote that wasn't found.
            content: Source content to search.
            max_len: Maximum length of returned quote.

        Returns:
            Best matching passage from content.
        """
        if not content:
            return quote

        # Find sentences in content
        sentences = content.replace("\n", " ").split(". ")

        # Score each sentence by word overlap with quote
        quote_words = set(quote.lower().split())
        best_sentence = ""
        best_score = 0

        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(quote_words & sentence_words)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence.strip()

        if best_sentence:
            if len(best_sentence) > max_len:
                best_sentence = best_sentence[:max_len] + "..."
            return best_sentence

        return quote[:max_len] if len(quote) > max_len else quote

    def _extract_best_quote(self, content: str, max_len: int = 200) -> str:
        """Extract the most informative quote from content.

        Args:
            content: Source content.
            max_len: Maximum quote length.

        Returns:
            Best quote from content.
        """
        if not content:
            return ""

        # Get first substantial sentence
        sentences = content.replace("\n", " ").split(". ")
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= 50:
                if len(sentence) > max_len:
                    return sentence[:max_len] + "..."
                return sentence

        # Fallback to truncated content
        if len(content) > max_len:
            return content[:max_len] + "..."
        return content
