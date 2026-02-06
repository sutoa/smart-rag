# Smart RAG

A RAG-based PDF document search system with grounded responses. Index PDF documents and query them using natural language to get accurate, cited answers.

## Features

- **PDF Indexing**: Extract and index text from PDF files with LLM-assisted semantic chunking
- **Natural Language Queries**: Ask questions in plain English and get accurate answers
- **Source Citations**: Every answer includes verbatim quotes with page numbers
- **Multiple Document Support**: Query across your entire document corpus
- **Fast Retrieval**: Two-stage retrieval with vector similarity + cross-encoder reranking

## Prerequisites

- Python 3.11+
- OpenAI API key

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

## Quick Start

### 1. Index Your Documents

```bash
python -m src.cli.main index /path/to/your/pdfs
```

Example output:
```
Indexing PDFs from: /path/to/your/pdfs

Processing: handbook.pdf (45 pages)...
Processing: policies.pdf (120 pages)...

Indexing complete!
  Documents indexed: 3
  Total chunks: 234
  Time elapsed: 1m 45s
```

### 2. Query Your Documents

```bash
python -m src.cli.main query "What is the definition of CSM?"
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

### 3. Get JSON Output (Optional)

```bash
python -m src.cli.main query "Who are the CSMs?" --json
```

## Commands

### `index`

Index PDF documents from a folder.

```bash
python -m src.cli.main index <folder_path> [OPTIONS]
```

Options:
- `--recursive`, `-r`: Include subdirectories
- `--force`, `-f`: Reindex already indexed documents
- `--verbose`, `-v`: Show detailed progress

### `query`

Query indexed documents.

```bash
python -m src.cli.main query "<question>" [OPTIONS]
```

Options:
- `--json`, `-j`: Output as JSON
- `--no-quotes`: Omit verbatim quotes from citations
- `--max-sources`: Maximum citations to include (default: 5)
- `--verbose`, `-v`: Show detailed timing breakdown

### `status`

Show indexing status.

```bash
python -m src.cli.main status
```

### `clear`

Clear all indexed data.

```bash
python -m src.cli.main clear [--yes]
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for embeddings and LLM |
| `SMART_RAG_DATA_DIR` | No | Custom data directory (default: `./data`) |
| `SMART_RAG_LOG_LEVEL` | No | Log level: DEBUG, INFO, WARNING, ERROR |

### Configuration File (Optional)

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

## How It Works

### Indexing Pipeline

1. **PDF Extraction**: Extract text and tables from PDFs using pdfplumber
2. **Semantic Chunking**: GPT-4o identifies natural semantic boundaries
3. **Embedding**: Generate embeddings using text-embedding-3-large
4. **Storage**: Store in ChromaDB (vectors) and SQLite (metadata)

### Query Pipeline

1. **Query Embedding**: Convert question to embedding vector
2. **Similarity Search**: Find top 30 candidate chunks
3. **Reranking**: Cross-encoder model scores relevance
4. **Response Generation**: GPT-4o generates grounded answer with citations

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `OPENAI_API_KEY not set` | Run `export OPENAI_API_KEY="..."` |
| `No PDF files found` | Check folder path contains .pdf files |
| `Unable to read PDF` | PDF may be corrupted, will be skipped |
| `Password protected` | Remove password from PDF |

## Development

```bash
# Run tests
pytest

# Lint code
ruff check .

# Format code
black .
```

## License

MIT
