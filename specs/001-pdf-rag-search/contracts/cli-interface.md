# CLI Interface Contract: PDF Document RAG Search System

**Date**: 2026-02-02
**Branch**: `001-pdf-rag-search`

## Overview

This document defines the command-line interface contract for the PDF RAG system. The CLI provides two primary commands: `index` and `query`.

---

## Installation

```bash
pip install smart-rag  # or local install
```

---

## Commands

### 1. `smart-rag index`

Index PDF documents from a folder.

#### Usage
```bash
smart-rag index <folder_path> [OPTIONS]
```

#### Arguments
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `folder_path` | PATH | Yes | Path to folder containing PDF files |

#### Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--recursive` / `-r` | flag | False | Include subdirectories |
| `--force` / `-f` | flag | False | Reindex already indexed documents |
| `--verbose` / `-v` | flag | False | Show detailed progress |

#### Output (Success)
```
Indexing PDFs from: /path/to/documents

Processing: document1.pdf (45 pages)... ✓
Processing: document2.pdf (120 pages)... ✓
Processing: document3.pdf (corrupted)... ✗ Skipped: Unable to read PDF
Processing: document4.pdf (password protected)... ✗ Skipped: Password protected

Indexing complete!
  Documents indexed: 2
  Documents skipped: 2
  Total chunks: 234
  Time elapsed: 2m 34s
```

#### Output (Error)
```
Error: Folder not found: /invalid/path
```

#### Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success (all or some documents indexed) |
| 1 | Error (folder not found, no PDFs found, etc.) |

---

### 2. `smart-rag query`

Query indexed documents.

#### Usage
```bash
smart-rag query "<question>" [OPTIONS]
```

#### Arguments
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `question` | TEXT | Yes | Natural language query |

#### Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` / `-j` | flag | False | Output as JSON |
| `--no-quotes` | flag | False | Omit verbatim quotes from citations |
| `--max-sources` | INT | 5 | Maximum citations to include |

#### Output (Success - Human Readable)
```
Query: What is the definition of CSM (Client Senior Manager)?

Answer:
A Client Senior Manager (CSM) is a senior-level professional responsible
for managing key client relationships and ensuring successful delivery of
services. CSMs serve as the primary point of contact for strategic clients
and are accountable for client satisfaction and retention.

Sources:
1. company_handbook.pdf (page 23)
   "A Client Senior Manager (CSM) is defined as a senior-level
   professional responsible for managing key client relationships..."

2. roles_guide.pdf (page 7)
   "CSMs serve as the primary point of contact for strategic
   clients and are accountable for client satisfaction..."

---
Retrieved 32 chunks | Used 5 sources | Response time: 8.2s
```

#### Output (Success - JSON)
```json
{
  "query": "What is the definition of CSM (Client Senior Manager)?",
  "answer": "A Client Senior Manager (CSM) is a senior-level professional...",
  "citations": [
    {
      "document_name": "company_handbook.pdf",
      "page_number": 23,
      "verbatim_quote": "A Client Senior Manager (CSM) is defined as...",
      "relevance_score": 0.94
    },
    {
      "document_name": "roles_guide.pdf",
      "page_number": 7,
      "verbatim_quote": "CSMs serve as the primary point of contact...",
      "relevance_score": 0.89
    }
  ],
  "metadata": {
    "chunks_retrieved": 32,
    "chunks_used": 5,
    "processing_time_ms": 8234
  }
}
```

#### Output (No Results)
```
Query: What is the weather today?

No relevant information found in the indexed documents.

This query may be outside the scope of the indexed content.
```

#### Output (No Index)
```
Error: No documents have been indexed yet.
Run 'smart-rag index <folder>' to index documents first.
```

#### Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success (answer found or "not found" response) |
| 1 | Error (no index, system error) |

---

### 3. `smart-rag status`

Show indexing status.

#### Usage
```bash
smart-rag status
```

#### Output
```
Smart RAG Index Status
======================
Documents indexed: 47
Total chunks: 3,421
Last indexed: 2026-02-02 14:32:15

Storage:
  Vector DB: 12.4 MB (data/chromadb/)
  Metadata: 0.2 MB (data/metadata.db)

Recent documents:
  - company_handbook.pdf (45 pages, 234 chunks)
  - policies_2026.pdf (128 pages, 567 chunks)
  - employee_guide.pdf (67 pages, 312 chunks)
```

---

### 4. `smart-rag clear`

Clear all indexed data.

#### Usage
```bash
smart-rag clear [OPTIONS]
```

#### Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--yes` / `-y` | flag | False | Skip confirmation prompt |

#### Output
```
This will delete all indexed documents and chunks.
Are you sure? [y/N]: y

Cleared 47 documents and 3,421 chunks.
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for embeddings and LLM |
| `SMART_RAG_DATA_DIR` | No | Custom data directory (default: `./data`) |

---

## Configuration File (Optional)

`~/.smart-rag/config.yaml` or `./smart-rag.yaml`:

```yaml
openai:
  embedding_model: text-embedding-3-large
  llm_model: gpt-4o

retrieval:
  top_k: 30
  rerank_top_k: 5

storage:
  data_dir: ./data
```

---

## Error Messages

| Error | Cause | Resolution |
|-------|-------|------------|
| `OPENAI_API_KEY not set` | Missing API key | Set environment variable |
| `Folder not found` | Invalid path | Check folder path |
| `No PDF files found` | Empty folder | Add PDF files to folder |
| `Unable to read PDF` | Corrupt file | File will be skipped |
| `Password protected` | Encrypted PDF | Remove password or skip |
| `No documents indexed` | Empty index | Run index command first |
| `API rate limit exceeded` | Too many requests | Wait and retry |
