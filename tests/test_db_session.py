"""
Integration tests for the Qdrant database layer.

Validates:
  - Session context manager lifecycle
  - Collection provisioning (hybrid: dense + sparse)
  - Health check mechanism
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from app.db.session import (
    DENSE_VECTOR_DIM,
    LEGAL_COLLECTION,
    QdrantSession,
    ensure_collection,
)


class TestQdrantSession:

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        """Verify the client is always closed after use."""
        mock_client = AsyncMock()

        with patch("app.db.session.AsyncQdrantClient", return_value=mock_client):
            session = QdrantSession()
            async with session.get_client() as client:
                assert client is mock_client
            mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager_closes_on_exception(self) -> None:
        """Verify cleanup even when an error occurs."""
        mock_client = AsyncMock()

        with patch("app.db.session.AsyncQdrantClient", return_value=mock_client):
            session = QdrantSession()
            with pytest.raises(RuntimeError):
                async with session.get_client():
                    raise RuntimeError("simulated failure")
            mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        mock_client = AsyncMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])

        with patch("app.db.session.AsyncQdrantClient", return_value=mock_client):
            session = QdrantSession()
            result = await session.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        mock_client = AsyncMock()
        mock_client.get_collections.side_effect = ConnectionError("refused")

        with patch("app.db.session.AsyncQdrantClient", return_value=mock_client):
            session = QdrantSession()
            result = await session.health_check()
            assert result is False


class TestEnsureCollection:

    @pytest.mark.asyncio
    async def test_creates_collection_when_missing(self) -> None:
        client = AsyncMock()
        client.get_collections.return_value = MagicMock(collections=[])

        await ensure_collection(client)

        client.create_collection.assert_awaited_once()
        call_kwargs = client.create_collection.call_args.kwargs
        assert call_kwargs["collection_name"] == LEGAL_COLLECTION
        assert "dense" in call_kwargs["vectors_config"]
        assert "sparse" in call_kwargs["sparse_vectors_config"]

    @pytest.mark.asyncio
    async def test_skips_when_collection_exists(self) -> None:
        existing = MagicMock()
        existing.name = LEGAL_COLLECTION
        client = AsyncMock()
        client.get_collections.return_value = MagicMock(collections=[existing])

        await ensure_collection(client)

        client.create_collection.assert_not_awaited()
