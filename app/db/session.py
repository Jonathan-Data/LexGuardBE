"""
Async Qdrant session management for LexGuardBE.

Provides a reusable async context manager with connection pooling,
health checks, and automatic collection provisioning for hybrid search.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Final, Optional

from loguru import logger
from pydantic_settings import BaseSettings
from qdrant_client import AsyncQdrantClient, models

# ── Configuration ──────────────────────────────────────────────────────────────


class QdrantSettings(BaseSettings):
    """Reads QDRANT_* env vars with sensible local-dev defaults."""

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_grpc_port: int = 6334
    qdrant_timeout: float = 30.0

    model_config = {"env_prefix": ""}


settings = QdrantSettings()

# ── Constants ──────────────────────────────────────────────────────────────────

LEGAL_COLLECTION: Final[str] = "legal_knowledge"
DENSE_VECTOR_DIM: Final[int] = 1536  # text-embedding-3-small

# ── Collection Schema ──────────────────────────────────────────────────────────


async def ensure_collection(client: AsyncQdrantClient) -> None:
    """Create the legal_knowledge collection with hybrid (dense + sparse) vectors
    if it does not already exist."""

    collections = await client.get_collections()
    existing = {c.name for c in collections.collections}

    if LEGAL_COLLECTION in existing:
        logger.debug(
            f"Collection '{LEGAL_COLLECTION}' already exists — skipping creation."
        )
        return

    await client.create_collection(
        collection_name=LEGAL_COLLECTION,
        vectors_config={
            "dense": models.VectorParams(
                size=DENSE_VECTOR_DIM,
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            ),
        },
    )
    logger.success(f"Created hybrid collection '{LEGAL_COLLECTION}'.")


# ── Session Context Manager ───────────────────────────────────────────────────


class QdrantSession:
    """Thin wrapper that yields a managed AsyncQdrantClient."""

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[AsyncQdrantClient, None]:
        client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            port=settings.qdrant_grpc_port,
            prefer_grpc=True,
            timeout=settings.qdrant_timeout,
        )
        try:
            yield client
        finally:
            await client.close()

    async def health_check(self) -> bool:
        """Verify connectivity to Qdrant."""
        try:
            async with self.get_client() as client:
                await client.get_collections()
            return True
        except Exception as exc:
            logger.error(f"Qdrant health check failed: {exc}")
            return False


qdrant_session = QdrantSession()
