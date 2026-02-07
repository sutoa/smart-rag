"""Configuration management for Smart RAG."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    """OpenAI API configuration."""

    api_key: str = Field(default="", description="OpenAI API key")
    embedding_model: str = Field(
        default="text-embedding-3-large", description="Model for embeddings"
    )
    llm_model: str = Field(default="gpt-4o", description="Model for chat completions")

    model_config = SettingsConfigDict(env_prefix="OPENAI_")


class RetrievalSettings(BaseSettings):
    """Retrieval configuration."""

    top_k: int = Field(default=50, description="Number of chunks to retrieve")
    rerank_top_k: int = Field(default=10, description="Number of chunks after reranking")
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-12-v2",
        description="Cross-encoder model for reranking",
    )

    model_config = SettingsConfigDict(env_prefix="SMART_RAG_RETRIEVAL_")


class StorageSettings(BaseSettings):
    """Storage configuration."""

    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    chromadb_dir: str = Field(default="chromadb", description="ChromaDB subdirectory")
    metadata_db: str = Field(default="metadata.db", description="SQLite database filename")

    model_config = SettingsConfigDict(env_prefix="SMART_RAG_STORAGE_")

    @property
    def chromadb_path(self) -> Path:
        """Get full path to ChromaDB directory."""
        return self.data_dir / self.chromadb_dir

    @property
    def metadata_db_path(self) -> Path:
        """Get full path to metadata database."""
        return self.data_dir / self.metadata_db


class Settings(BaseSettings):
    """Main application settings."""

    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(
        env_prefix="SMART_RAG_",
        env_nested_delimiter="__",
    )

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Settings":
        """Load settings from environment and optional YAML config file.

        Args:
            config_path: Optional path to YAML config file.
                        If None, looks for smart-rag.yaml in current dir or ~/.smart-rag/config.yaml

        Returns:
            Settings instance with merged configuration.
        """
        config_data: dict = {}

        # Look for config file in standard locations
        if config_path is None:
            candidates = [
                Path("smart-rag.yaml"),
                Path("smart-rag.yml"),
                Path.home() / ".smart-rag" / "config.yaml",
                Path.home() / ".smart-rag" / "config.yml",
            ]
            for candidate in candidates:
                if candidate.exists():
                    config_path = candidate
                    break

        # Load YAML config if found
        if config_path and config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}

        # Build nested settings from config file
        openai_config = config_data.get("openai", {})
        retrieval_config = config_data.get("retrieval", {})
        storage_config = config_data.get("storage", {})

        # Environment variables override config file
        # OpenAI API key from environment
        api_key = os.getenv("OPENAI_API_KEY", openai_config.get("api_key", ""))

        openai_settings = OpenAISettings(
            api_key=api_key,
            embedding_model=openai_config.get("embedding_model", "text-embedding-3-large"),
            llm_model=openai_config.get("llm_model", "gpt-4o"),
        )

        retrieval_settings = RetrievalSettings(
            top_k=retrieval_config.get("top_k", 50),
            rerank_top_k=retrieval_config.get("rerank_top_k", 10),
            reranker_model=retrieval_config.get(
                "reranker_model", "cross-encoder/ms-marco-MiniLM-L-12-v2"
            ),
        )

        # Handle data_dir from env or config
        data_dir = os.getenv("SMART_RAG_DATA_DIR", storage_config.get("data_dir", "./data"))
        storage_settings = StorageSettings(
            data_dir=Path(data_dir),
            chromadb_dir=storage_config.get("chromadb_dir", "chromadb"),
            metadata_db=storage_config.get("metadata_db", "metadata.db"),
        )

        log_level = os.getenv("SMART_RAG_LOG_LEVEL", config_data.get("log_level", "INFO"))

        return cls(
            openai=openai_settings,
            retrieval=retrieval_settings,
            storage=storage_settings,
            log_level=log_level,
        )

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.storage.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage.chromadb_path.mkdir(parents=True, exist_ok=True)


# Global settings instance (lazy loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns:
        Settings instance, loading from config if not already loaded.
    """
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings(config_path: Optional[Path] = None) -> Settings:
    """Reload settings from config file.

    Args:
        config_path: Optional path to YAML config file.

    Returns:
        New Settings instance.
    """
    global _settings
    _settings = Settings.load(config_path)
    return _settings
