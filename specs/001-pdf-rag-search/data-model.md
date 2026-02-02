# Data Model: PDF Document RAG Search System

**Date**: 2026-02-02
**Branch**: `001-pdf-rag-search`

## Overview

This document defines the data entities, relationships, and storage structure for the PDF RAG system.

---

## Entities

### 1. Document

Represents an indexed PDF file.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | string (UUID) | Unique identifier | Primary key, auto-generated |
| `name` | string | Original filename | Required, non-empty |
| `file_path` | string | Absolute path to PDF | Required, valid path |
| `page_count` | integer | Number of pages | Required, ≥ 1 |
| `indexed_at` | datetime | When document was indexed | Auto-set on creation |
| `status` | enum | Indexing status | `pending`, `processing`, `completed`, `failed` |
| `error_message` | string | Error details if failed | Optional |
| `file_hash` | string | SHA-256 hash of file | For duplicate detection |
| `chunk_count` | integer | Number of chunks created | Set after chunking |

**Lifecycle States:**
```
pending → processing → completed
                    ↘ failed
```

---

### 2. Chunk

A semantically coherent segment of text from a document.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | string (UUID) | Unique identifier | Primary key, auto-generated |
| `document_id` | string (UUID) | Reference to parent document | Foreign key, required |
| `content` | string | Extracted text content | Required, non-empty |
| `page_number` | integer | Source page number | Required, ≥ 1 |
| `page_end` | integer | End page (if spans pages) | Optional, ≥ page_number |
| `chunk_index` | integer | Order within document | Required, ≥ 0 |
| `token_count` | integer | Approximate token count | Computed |
| `embedding` | vector(3072) | OpenAI embedding vector | Required for search |
| `metadata` | JSON | Additional extraction info | Optional |

**Metadata Schema:**
```json
{
  "has_table": boolean,
  "section_title": string | null,
  "extraction_method": "text" | "table"
}
```

---

### 3. Query (Runtime Only)

Represents a user search query. Not persisted.

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Natural language question |
| `embedding` | vector(3072) | Query embedding |
| `timestamp` | datetime | When query was submitted |

---

### 4. Response (Runtime Only)

Generated answer with citations. Not persisted.

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Generated response text |
| `citations` | Citation[] | List of source citations |
| `query_text` | string | Original query |
| `processing_time_ms` | integer | Total processing time |
| `chunks_retrieved` | integer | Number of chunks searched |
| `chunks_used` | integer | Number of chunks in response |

---

### 5. Citation (Embedded in Response)

Source reference for a finding.

| Field | Type | Description |
|-------|------|-------------|
| `document_name` | string | Source document filename |
| `page_number` | integer | Page where content found |
| `verbatim_quote` | string | Exact text excerpt |
| `relevance_score` | float | Reranker confidence (0-1) |

---

## Storage Architecture

### SQLite (Document Metadata)
```
data/metadata.db
└── documents table
    └── All Document entity fields
```

### ChromaDB (Vector Store)
```
data/chromadb/
└── documents collection
    ├── embeddings (vector)
    ├── documents (chunk content)
    ├── metadatas (chunk metadata)
    └── ids (chunk UUIDs)
```

**ChromaDB Metadata per Chunk:**
```python
{
    "document_id": str,
    "document_name": str,
    "page_number": int,
    "page_end": int | None,
    "chunk_index": int,
    "has_table": bool
}
```

---

## Relationships

```
Document (1) ──────< Chunk (N)
    │
    └── One document has many chunks
        Chunks are deleted when document is removed
```

---

## Validation Rules

### Document
- `name`: Must end with `.pdf` (case-insensitive)
- `file_path`: Must be valid, readable file path
- `page_count`: Must match actual PDF page count
- `file_hash`: Used to detect duplicate indexing attempts

### Chunk
- `content`: Minimum 50 characters (skip trivial chunks)
- `page_number`: Must be within document's page range
- `embedding`: Must be 3072-dimensional vector (text-embedding-3-large)

---

## Indexing Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max documents | ~100 | Per spec requirement |
| Max pages per doc | 300+ | Per spec requirement |
| Max chunk size | ~2000 tokens | Context window management |
| Min chunk size | 50 chars | Avoid trivial chunks |

---

## Example Data Flow

### Indexing Flow
```
PDF File
    ↓ (pdfplumber)
Raw Text + Tables + Page Numbers
    ↓ (GPT-4o chunking)
Semantic Chunks with metadata
    ↓ (text-embedding-3-large)
Chunks with embeddings
    ↓
ChromaDB + SQLite
```

### Query Flow
```
User Query
    ↓ (text-embedding-3-large)
Query Embedding
    ↓ (ChromaDB similarity search)
Top 30+ Chunks
    ↓ (Cross-encoder reranking)
Top Ranked Chunks
    ↓ (GPT-4o generation)
Response with Citations
```
