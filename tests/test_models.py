"""
Unit tests for app/models/legal.py — Schema Robustness.

Validates:
  - Legal hierarchy fields (Chapter → Article → Annex)
  - Versioning and regulatory update tracking
  - Risk level enum enforcement
  - Hybrid vector field population
"""

from __future__ import annotations

import pytest
from datetime import date
from pydantic import ValidationError

from app.models.legal import (
    Jurisdiction,
    LegalChunk,
    LegalMetadata,
    RiskLevel,
)


class TestLegalMetadata:
    """Schema robustness for the metadata sub-model."""

    def test_full_hierarchy(self, sample_metadata: LegalMetadata) -> None:
        assert sample_metadata.chapter == "Chapter III"
        assert sample_metadata.section == "Section 2"
        assert sample_metadata.article == "Art. 6"
        assert sample_metadata.annex == "Annex III"

    def test_default_jurisdiction(self) -> None:
        meta = LegalMetadata(source="test.pdf")
        assert meta.jurisdiction == Jurisdiction.EU

    def test_belgian_jurisdiction(self) -> None:
        meta = LegalMetadata(source="bipt_circular.pdf", jurisdiction=Jurisdiction.BE)
        assert meta.jurisdiction == Jurisdiction.BE

    def test_risk_level_enum(self) -> None:
        meta = LegalMetadata(source="test.pdf", risk_level=RiskLevel.PROHIBITED)
        assert meta.risk_level == "prohibited"

    def test_invalid_risk_level_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LegalMetadata(source="test.pdf", risk_level="catastrophic")  # type: ignore

    def test_versioning_fields(self) -> None:
        meta = LegalMetadata(
            source="transparency_update.pdf",
            regulation_id="2024/1689",
            version_date=date(2026, 5, 8),
        )
        assert meta.regulation_id == "2024/1689"
        assert meta.version_date == date(2026, 5, 8)

    def test_may_2026_transparency_guidelines(self) -> None:
        """Verify we can track the May 8, 2026 Commission update."""
        meta = LegalMetadata(
            source="EC_Transparency_Guidelines_2026.pdf",
            article="Art. 13",
            version_date=date(2026, 5, 8),
            jurisdiction=Jurisdiction.EU,
        )
        assert meta.version_date.year == 2026
        assert meta.version_date.month == 5

    def test_model_dump_json_serialization(self, sample_metadata: LegalMetadata) -> None:
        data = sample_metadata.model_dump(mode="json")
        assert isinstance(data["risk_level"], str)
        assert data["jurisdiction"] == "EU"


class TestLegalChunk:
    """Schema robustness for the chunk model."""

    def test_auto_generated_id(self) -> None:
        chunk = LegalChunk(
            content="Test content.",
            metadata=LegalMetadata(source="test.pdf"),
        )
        assert chunk.chunk_id is not None
        assert len(chunk.chunk_id) == 36  # UUID4 format

    def test_dense_vector_population(self, sample_chunk: LegalChunk) -> None:
        assert sample_chunk.dense_vector is not None
        assert len(sample_chunk.dense_vector) == 1536

    def test_sparse_vector_population(self, sample_chunk: LegalChunk) -> None:
        assert sample_chunk.sparse_indices is not None
        assert sample_chunk.sparse_values is not None
        assert len(sample_chunk.sparse_indices) == len(sample_chunk.sparse_values)

    def test_metadata_article_preserved(self, sample_chunk: LegalChunk) -> None:
        """Critical: article_id must survive the full model lifecycle."""
        dumped = sample_chunk.model_dump(mode="json")
        assert dumped["metadata"]["article"] == "Art. 6"
        assert dumped["metadata"]["annex"] == "Annex III"
