"""
Shared fixtures for the LexGuardBE test suite.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.legal import Jurisdiction, LegalChunk, LegalMetadata, RiskLevel

# ── Reusable Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_metadata() -> LegalMetadata:
    return LegalMetadata(
        source="EU_AI_Act_2024_1689.pdf",
        jurisdiction=Jurisdiction.EU,
        chapter="Chapter III",
        section="Section 2",
        article="Art. 6",
        annex="Annex III",
        risk_level=RiskLevel.HIGH,
        page=42,
        element_type="NarrativeText",
        regulation_id="2024/1689",
    )


@pytest.fixture
def sample_chunk(sample_metadata: LegalMetadata) -> LegalChunk:
    return LegalChunk(
        content="High-risk AI systems referred to in Article 6(2) shall comply with the requirements laid down in this Section.",
        dense_vector=[0.1] * 1536,
        sparse_indices=[100, 200, 300],
        sparse_values=[1.0, 2.0, 1.0],
        metadata=sample_metadata,
    )


@pytest.fixture
def mock_qdrant_client() -> AsyncMock:
    """A mocked AsyncQdrantClient."""
    client = AsyncMock()
    client.get_collections.return_value = MagicMock(collections=[])
    client.create_collection.return_value = True
    client.upsert.return_value = True
    client.close.return_value = None
    return client
