# Quickstart: PDF Document RAG Search System

**Date**: 2026-02-02
**Branch**: `001-pdf-rag-search`

## Prerequisites

- Python 3.11+
- OpenAI API key
- PDF documents to index

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/smart-rag.git
cd smart-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

## Quick Start (3 Steps)

### Step 1: Index Your Documents

```bash
smart-rag index /path/to/your/pdfs
```

Example output:
```
Indexing PDFs from: /path/to/your/pdfs

Processing: handbook.pdf (45 pages)... ✓
Processing: policies.pdf (120 pages)... ✓
Processing: guide.pdf (30 pages)... ✓

Indexing complete!
  Documents indexed: 3
  Total chunks: 234
  Time elapsed: 1m 45s
```

### Step 2: Query Your Documents

```bash
smart-rag query "What is the definition of CSM?"
```

Example output:
```
Query: What is the definition of CSM?

Answer:
A Client Senior Manager (CSM) is a senior-level professional responsible
for managing key client relationships and ensuring successful delivery.

Sources:
1. handbook.pdf (page 23)
   "A Client Senior Manager (CSM) is defined as a senior-level
   professional responsible for managing key client relationships..."

---
Retrieved 32 chunks | Used 3 sources | Response time: 6.2s
```

### Step 3: Get JSON Output (Optional)

```bash
smart-rag query "Who are the CSMs?" --json
```

## Common Commands

```bash
# Index with verbose output
smart-rag index /path/to/pdfs --verbose

# Reindex documents (force)
smart-rag index /path/to/pdfs --force

# Check index status
smart-rag status

# Clear all indexed data
smart-rag clear
```

## Project Structure

```
smart-rag/
├── src/
│   ├── models/          # Data models
│   ├── services/        # Core services
│   ├── cli/             # CLI commands
│   └── lib/             # Utilities
├── tests/               # Test suite
├── data/                # Index storage (created on first run)
│   ├── chromadb/        # Vector database
│   └── metadata.db      # Document metadata
└── requirements.txt
```

## Configuration (Optional)

Create `smart-rag.yaml` in your project root:

```yaml
openai:
  embedding_model: text-embedding-3-large
  llm_model: gpt-4o

retrieval:
  top_k: 30           # Chunks to retrieve
  rerank_top_k: 5     # Chunks after reranking

storage:
  data_dir: ./data
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `OPENAI_API_KEY not set` | Run `export OPENAI_API_KEY="..."` |
| `No PDF files found` | Check folder path contains .pdf files |
| `Unable to read PDF` | PDF may be corrupted, will be skipped |
| `Password protected` | Remove password from PDF |

## Next Steps

- Run `smart-rag --help` for all available options
- See [CLI Interface](./contracts/cli-interface.md) for full command reference
- See [Data Model](./data-model.md) for entity details
