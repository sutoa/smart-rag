# Implementation Plan: PDF Document RAG Search System

**Branch**: `001-pdf-rag-search` | **Date**: 2026-02-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pdf-rag-search/spec.md`

## Summary

Build a RAG-based document search system that indexes ~100 PDF documents (20-300+ pages each) and answers natural language queries with accurate, grounded responses. Key technical approach: LLM-assisted semantic chunking with variable boundaries, deep retrieval (30+ chunks), reranking for relevance, and response generation with verbatim source citations. Uses OpenAI API for embeddings/LLM and a free vector database for persistence.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- PDF extraction: PyMuPDF (fitz) or pdfplumber for text/table extraction
- Embeddings: OpenAI text-embedding-3-small/large
- Vector DB: ChromaDB (free, persistent, local)
- LLM: OpenAI GPT-4o for chunking assistance and response generation
- Reranking: Cohere Rerank or cross-encoder model
- CLI: Click or Typer

**Storage**: ChromaDB (persistent local storage), SQLite for document metadata
**Testing**: pytest with fixtures for PDF samples
**Target Platform**: macOS/Linux CLI (local execution)
**Project Type**: Single project with CLI interface
**Performance Goals**: Query response < 30 seconds, indexing with progress feedback
**Constraints**: OpenAI API rate limits, free-tier vector DB capacity (~100 docs)
**Scale/Scope**: ~100 documents, ~5000 pages total, single user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution template has not been customized for this project. Proceeding with standard best practices:

| Principle | Status | Notes |
|-----------|--------|-------|
| Modular Design | ✅ Pass | Separate modules for extraction, chunking, indexing, retrieval, generation |
| Testability | ✅ Pass | Each component independently testable with sample PDFs |
| CLI Interface | ✅ Pass | Two commands: `index` and `query` |
| Error Handling | ✅ Pass | Graceful handling of corrupt/protected PDFs |
| Simplicity | ✅ Pass | Single project, no over-engineering |

## Project Structure

### Documentation (this feature)

```text
specs/001-pdf-rag-search/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface spec)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── document.py      # Document, Chunk, Response models
│   └── config.py        # Configuration management
├── services/
│   ├── pdf_extractor.py # PDF text/table extraction
│   ├── chunker.py       # LLM-assisted semantic chunking
│   ├── indexer.py       # Vector DB indexing operations
│   ├── retriever.py     # Similarity search + reranking
│   └── generator.py     # Grounded response generation
├── cli/
│   └── main.py          # CLI commands (index, query)
└── lib/
    ├── openai_client.py # OpenAI API wrapper
    └── vector_store.py  # ChromaDB abstraction

tests/
├── fixtures/
│   └── sample_pdfs/     # Test PDF documents
├── unit/
│   ├── test_extractor.py
│   ├── test_chunker.py
│   ├── test_retriever.py
│   └── test_generator.py
└── integration/
    ├── test_indexing.py
    └── test_query.py

data/
├── chromadb/            # Persistent vector store
└── metadata.db          # SQLite document metadata
```

**Structure Decision**: Single project structure selected. CLI-based tool with modular services for each RAG pipeline stage. Tests organized by unit/integration with sample PDF fixtures.

## Complexity Tracking

> No constitution violations. Standard single-project structure with appropriate modularity.

| Component | Complexity | Justification |
|-----------|------------|---------------|
| LLM-assisted chunking | Medium | Required for semantic boundaries per spec |
| Deep retrieval + reranking | Medium | Required for completeness (30+ chunks) |
| Verbatim citation extraction | Low | Straightforward with chunk metadata |
