"""CLI commands for Smart RAG."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from src.models.config import get_settings
from src.models.document import DocumentStatus

# Initialize Typer app
app = typer.Typer(
    name="smart-rag",
    help="RAG-based PDF document search system with grounded responses.",
    add_completion=False,
)

# Rich console for pretty output
console = Console()


def handle_error(error: Exception) -> None:
    """Handle errors with user-friendly messages per CLI contract.

    Args:
        error: The exception that occurred.
    """
    error_str = str(error).lower()

    # API rate limiting
    if "rate limit" in error_str or "rate_limit" in error_str:
        console.print(
            "[red]Error:[/red] API rate limit exceeded.\n"
            "Please wait a moment and try again."
        )
    # API authentication errors
    elif "invalid api key" in error_str or "authentication" in error_str:
        console.print(
            "[red]Error:[/red] Invalid OpenAI API key.\n"
            "Please check your OPENAI_API_KEY environment variable."
        )
    # Network errors
    elif "connection" in error_str or "network" in error_str or "timeout" in error_str:
        console.print(
            "[red]Error:[/red] Network connection failed.\n"
            "Please check your internet connection and try again."
        )
    # PDF-specific errors
    elif "password" in error_str or "encrypted" in error_str:
        console.print(
            "[red]Error:[/red] Password protected PDF encountered.\n"
            "Remove password protection or skip this file."
        )
    elif "corrupt" in error_str or "unable to read" in error_str:
        console.print(
            "[red]Error:[/red] Unable to read PDF file.\n"
            "The file may be corrupted or in an unsupported format."
        )
    # File system errors
    elif "permission denied" in error_str:
        console.print(
            "[red]Error:[/red] Permission denied.\n"
            "Please check file permissions and try again."
        )
    elif "no space" in error_str or "disk full" in error_str:
        console.print(
            "[red]Error:[/red] Insufficient disk space.\n"
            "Please free up disk space and try again."
        )
    # Generic error
    else:
        console.print(f"[red]Error:[/red] {error}")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich handler.

    Args:
        verbose: If True, set DEBUG level; otherwise use config level.
    """
    settings = get_settings()
    level = logging.DEBUG if verbose else getattr(logging, settings.log_level.upper())

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
        force=True,
    )


def check_api_key() -> bool:
    """Check if OpenAI API key is configured.

    Returns:
        True if API key is set, False otherwise.
    """
    settings = get_settings()
    if not settings.openai.api_key:
        console.print(
            "[red]Error:[/red] OPENAI_API_KEY not set.\n"
            "Please set the environment variable or add it to your config file.",
        )
        return False
    return True


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted size string (e.g., "1.5 MB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


@app.command()
def index(
    folder_path: Path = typer.Argument(
        ...,
        help="Path to folder containing PDF files",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="Include subdirectories"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Reindex already indexed documents"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed progress"
    ),
) -> None:
    """Index PDF documents from a folder."""
    setup_logging(verbose)

    if not check_api_key():
        raise typer.Exit(code=1)

    console.print(f"[blue]Indexing PDFs from:[/blue] {folder_path}\n")

    # Import here to avoid circular imports and allow lazy loading
    from src.services.indexer import Indexer

    indexer = Indexer()

    try:
        summary = indexer.index_folder(
            folder_path=folder_path,
            recursive=recursive,
            force=force,
            show_progress=True,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    # Print results
    console.print()

    if summary.total_documents == 0:
        console.print("[yellow]No PDF files found in the specified folder.[/yellow]")
        raise typer.Exit(code=0)

    # Show individual results if verbose
    if verbose:
        for result in summary.results:
            if result.success:
                console.print(
                    f"[green]✓[/green] {result.document.name} "
                    f"({result.document.page_count} pages, {result.chunks_created} chunks)"
                )
            else:
                console.print(
                    f"[red]✗[/red] {result.document.name}: {result.error_message}"
                )
        console.print()

    # Summary
    console.print("[bold green]Indexing complete![/bold green]")
    console.print(f"  Documents indexed: {summary.indexed}")
    if summary.skipped > 0:
        console.print(f"  Documents skipped: {summary.skipped}")
    if summary.failed > 0:
        console.print(f"  Documents failed: {summary.failed}")
    console.print(f"  Total chunks: {summary.total_chunks}")
    console.print(f"  Time elapsed: {format_duration(summary.elapsed_seconds)}")


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language query"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
    no_quotes: bool = typer.Option(
        False, "--no-quotes", help="Omit verbatim quotes from citations"
    ),
    max_sources: int = typer.Option(
        5, "--max-sources", help="Maximum citations to include"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed timing breakdown"
    ),
) -> None:
    """Query indexed documents."""
    setup_logging(verbose)

    if not check_api_key():
        raise typer.Exit(code=1)

    # Check if documents are indexed
    from src.lib.metadata_store import get_metadata_store

    metadata_store = get_metadata_store()
    doc_count = metadata_store.count(DocumentStatus.COMPLETED)

    if doc_count == 0:
        console.print(
            "[red]Error:[/red] No documents have been indexed yet.\n"
            "Run 'smart-rag index <folder>' to index documents first."
        )
        raise typer.Exit(code=1)

    # Import services
    from src.services.retriever import Retriever
    from src.services.generator import Generator, ENTITY_QUERY_PATTERNS
    import json
    import re

    try:
        retriever = Retriever()
        generator = Generator()

        # Detect entity queries and use appropriate retrieval strategy
        is_entity_query = any(
            re.search(pattern, question.lower().strip())
            for pattern in ENTITY_QUERY_PATTERNS
        )

        if is_entity_query:
            # Use multi-document retrieval for entity/list queries
            retrieval_result = retriever.retrieve_from_multiple_documents(
                question,
                max_chunks_per_doc=2,
            )
        else:
            # Standard retrieval for definition queries
            retrieval_result = retriever.retrieve(question)

        # Generate response
        response = generator.generate(
            query=question,
            retrieval_result=retrieval_result,
            max_sources=max_sources,
        )

        # Output response
        if json_output:
            # JSON output format per CLI contract
            output = response.to_json_dict()
            # Add timing breakdown to JSON if verbose
            if verbose:
                output["timing"] = {
                    "embedding_ms": retrieval_result.embedding_time_ms,
                    "search_ms": retrieval_result.retrieval_time_ms,
                    "rerank_ms": retrieval_result.rerank_time_ms,
                    "total_retrieval_ms": retrieval_result.total_time_ms,
                    "total_ms": response.metadata.processing_time_ms,
                }
            console.print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            console.print(response.format_human_readable(include_quotes=not no_quotes))

            # Show timing breakdown in verbose mode
            if verbose:
                console.print()
                console.print("[dim]Timing breakdown:[/dim]")
                console.print(f"  [dim]Embedding:  {retrieval_result.embedding_time_ms}ms[/dim]")
                console.print(f"  [dim]Search:     {retrieval_result.retrieval_time_ms}ms[/dim]")
                console.print(f"  [dim]Reranking:  {retrieval_result.rerank_time_ms}ms[/dim]")
                generation_time = response.metadata.processing_time_ms - retrieval_result.total_time_ms
                console.print(f"  [dim]Generation: {generation_time}ms[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Show indexing status."""
    setup_logging()

    from src.lib.metadata_store import get_metadata_store
    from src.lib.vector_store import get_vector_store

    metadata_store = get_metadata_store()
    vector_store = get_vector_store()

    # Get counts
    total_docs = metadata_store.count()
    completed_docs = metadata_store.count(DocumentStatus.COMPLETED)
    failed_docs = metadata_store.count(DocumentStatus.FAILED)
    total_chunks = vector_store.get_count()

    # Get storage sizes
    vector_size = vector_store.get_storage_size_bytes()
    metadata_size = metadata_store.get_storage_size_bytes()

    # Get recent documents
    recent_docs = metadata_store.get_recent(limit=5)

    # Display status
    console.print("[bold]Smart RAG Index Status[/bold]")
    console.print("=" * 24)
    console.print(f"Documents indexed: {completed_docs}")
    if failed_docs > 0:
        console.print(f"Documents failed: {failed_docs}")
    console.print(f"Total chunks: {total_chunks}")

    if recent_docs:
        last_indexed = recent_docs[0].indexed_at.strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"Last indexed: {last_indexed}")

    console.print()
    console.print("[bold]Storage:[/bold]")
    console.print(f"  Vector DB: {format_size(vector_size)} (data/chromadb/)")
    console.print(f"  Metadata: {format_size(metadata_size)} (data/metadata.db)")

    if recent_docs:
        console.print()
        console.print("[bold]Recent documents:[/bold]")
        for doc in recent_docs:
            status_icon = "✓" if doc.status == DocumentStatus.COMPLETED else "✗"
            status_color = "green" if doc.status == DocumentStatus.COMPLETED else "red"
            console.print(
                f"  [{status_color}]{status_icon}[/{status_color}] {doc.name} "
                f"({doc.page_count} pages, {doc.chunk_count} chunks)"
            )


@app.command()
def clear(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Clear all indexed data."""
    setup_logging()

    from src.lib.metadata_store import get_metadata_store
    from src.lib.vector_store import get_vector_store

    metadata_store = get_metadata_store()
    vector_store = get_vector_store()

    # Check if there's anything to clear
    doc_count = metadata_store.count()
    chunk_count = vector_store.get_count()

    if doc_count == 0 and chunk_count == 0:
        console.print("[yellow]No indexed data to clear.[/yellow]")
        raise typer.Exit(code=0)

    if not yes:
        console.print(
            f"This will delete {doc_count} documents and {chunk_count} chunks."
        )
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(code=0)

    # Clear data
    from src.services.indexer import Indexer

    indexer = Indexer()
    docs_deleted, chunks_deleted = indexer.clear_all()

    console.print(f"[green]Cleared {docs_deleted} documents and {chunks_deleted} chunks.[/green]")


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", help="Show version and exit"
    ),
) -> None:
    """Smart RAG - PDF Document Search System."""
    if version:
        from src import __version__

        console.print(f"smart-rag version {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
