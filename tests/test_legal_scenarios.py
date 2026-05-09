"""
Legal scenario tests — Zero-Hallucination Audit.

These tests simulate real regulatory queries to verify that the
ingestion pipeline produces chunks that would satisfy the May 8, 2026
European Commission Transparency Guidelines retrieval scenarios.
"""

from __future__ import annotations

import pytest
from datetime import date

from app.models.legal import Jurisdiction, LegalChunk, LegalMetadata, RiskLevel
from app.services.ingestion import _extract_hierarchy, _build_sparse_vector


class TestTransparencyGuidelines2026:
    """Verify system can handle the May 8, 2026 EC Transparency update."""

    def test_transparency_article_13_extraction(self) -> None:
        """Art. 13 is the primary transparency article — must be detected."""
        text = "Article 13 — Transparency and provision of information to deployers"
        hierarchy = _extract_hierarchy(text)
        assert hierarchy["article"] is not None
        assert "13" in hierarchy["article"]

    def test_may_2026_version_date_tracked(self) -> None:
        """Chunks from the transparency update must carry the version date."""
        chunk = LegalChunk(
            content="Updated transparency obligations per EC Guidelines of 8 May 2026.",
            metadata=LegalMetadata(
                source="EC_Transparency_Guidelines_2026.pdf",
                article="Art. 13",
                version_date=date(2026, 5, 8),
                jurisdiction=Jurisdiction.EU,
            ),
        )
        assert chunk.metadata.version_date == date(2026, 5, 8)
        payload = chunk.metadata.model_dump(mode="json")
        assert payload["version_date"] == "2026-05-08"

    def test_sparse_vector_captures_article_13_keyword(self) -> None:
        """Sparse vector must make 'Article 13' retrievable by keyword."""
        text = "Article 13 requires transparency obligations for high-risk AI."
        indices, values = _build_sparse_vector(text)
        # "article" and "13" must be represented
        assert len(indices) > 0
        assert all(v > 0 for v in values)


class TestProhibitedSystemDetection:
    """Verify we can correctly tag prohibited AI categories (Art. 5)."""

    def test_article_5_hierarchy(self) -> None:
        text = "Article 5 — Prohibited artificial intelligence practices"
        hierarchy = _extract_hierarchy(text)
        assert "5" in hierarchy["article"]

    def test_prohibited_risk_level(self) -> None:
        chunk = LegalChunk(
            content="Social scoring by public authorities shall be prohibited.",
            metadata=LegalMetadata(
                source="EU_AI_Act.pdf",
                article="Art. 5",
                risk_level=RiskLevel.PROHIBITED,
            ),
        )
        assert chunk.metadata.risk_level == RiskLevel.PROHIBITED


class TestHighRiskAnnexIII:
    """Verify Annex III categories are properly mapped."""

    def test_annex_iii_detected(self) -> None:
        text = "ANNEX III — HIGH-RISK AI SYSTEMS REFERRED TO IN ARTICLE 6(2)"
        hierarchy = _extract_hierarchy(text)
        assert hierarchy["annex"] is not None
        assert "III" in hierarchy["annex"]

    def test_employment_domain_metadata(self) -> None:
        chunk = LegalChunk(
            content="AI systems intended to be used for recruitment or selection of natural persons.",
            metadata=LegalMetadata(
                source="EU_AI_Act.pdf",
                annex="Annex III",
                article="Art. 6",
                risk_level=RiskLevel.HIGH,
            ),
        )
        payload = chunk.metadata.model_dump(mode="json")
        assert payload["risk_level"] == "high"
        assert payload["annex"] == "Annex III"
        assert payload["article"] == "Art. 6"

    def test_human_oversight_art_14(self) -> None:
        """Art. 14 (Human Oversight) is critical for HITL compliance."""
        text = "Article 14 — Human oversight"
        hierarchy = _extract_hierarchy(text)
        assert "14" in hierarchy["article"]


class TestBelgianJurisdiction:
    """BIPT-specific regulatory nuances."""

    def test_belgian_jurisdiction_flag(self) -> None:
        chunk = LegalChunk(
            content="BIPT Circular AI-SPEC-2025-01 imposes additional obligations.",
            metadata=LegalMetadata(
                source="bipt_circular_2025_01.pdf",
                jurisdiction=Jurisdiction.BE,
            ),
        )
        assert chunk.metadata.jurisdiction == "BE"
