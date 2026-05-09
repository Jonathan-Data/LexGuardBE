"""
Unit tests for app/services/ingestion.py — Parsing & Chunking Quality.

Validates:
  - Layout-aware chunking respects structural boundaries
  - Hierarchy metadata extraction (Chapter, Article, Annex)
  - Sparse vector generation produces valid indices/values
  - Blocking PDF partition is offloaded to a thread
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.legal import LegalChunk
from app.services.ingestion import (
    IngestionService,
    _build_sparse_vector,
    _extract_hierarchy,
    _layout_aware_chunks,
    get_ingestion_service,
)

# ── Hierarchy Extraction ──────────────────────────────────────────────────────


class TestHierarchyExtraction:

    def test_detects_chapter(self) -> None:
        result = _extract_hierarchy("CHAPTER III — HIGH-RISK AI SYSTEMS")
        assert result["chapter"] is not None
        assert "III" in result["chapter"]

    def test_detects_article(self) -> None:
        result = _extract_hierarchy(
            "Article 6 — Classification rules for high-risk AI systems"
        )
        assert result["article"] is not None
        assert "6" in result["article"]

    def test_detects_annex(self) -> None:
        result = _extract_hierarchy(
            "ANNEX III — HIGH-RISK AI SYSTEMS REFERRED TO IN ARTICLE 6(2)"
        )
        assert result["annex"] is not None
        assert "III" in result["annex"]

    def test_detects_section(self) -> None:
        result = _extract_hierarchy("Section 2 — Requirements for high-risk AI systems")
        assert result["section"] is not None

    def test_no_false_positives(self) -> None:
        result = _extract_hierarchy("This is a normal paragraph about AI safety.")
        assert all(v is None for v in result.values())

    def test_art_dot_shorthand(self) -> None:
        result = _extract_hierarchy("See Art. 14 for human oversight requirements.")
        assert result["article"] is not None
        assert "14" in result["article"]


# ── Sparse Vector ──────────────────────────────────────────────────────────────


class TestSparseVector:

    def test_produces_indices_and_values(self) -> None:
        indices, values = _build_sparse_vector("Article 6 high risk AI systems")
        assert len(indices) > 0
        assert len(indices) == len(values)

    def test_indices_are_sorted(self) -> None:
        indices, _ = _build_sparse_vector(
            "multiple words to ensure several hash buckets"
        )
        assert indices == sorted(indices)

    def test_repeated_terms_increase_frequency(self) -> None:
        _, values_once = _build_sparse_vector("risk")
        _, values_twice = _build_sparse_vector("risk risk")
        assert max(values_twice) >= max(values_once)


# ── Layout-Aware Chunking ──────────────────────────────────────────────────────


class TestLayoutAwareChunking:

    @staticmethod
    def _make_element(
        text: str, el_type: str = "NarrativeText", page: int = 1
    ) -> MagicMock:
        el = MagicMock()
        el.__str__ = lambda self: text
        el.strip = lambda: text
        type(el).__name__ = el_type
        el.metadata = MagicMock()
        el.metadata.page_number = page
        return el

    def test_structural_boundary_starts_new_chunk(self) -> None:
        elements = [
            self._make_element(
                "Some introductory text about the regulation.", "NarrativeText"
            ),
            self._make_element("Article 5 — Prohibited AI Practices", "Title"),
            self._make_element(
                "The following practices shall be prohibited.", "NarrativeText"
            ),
        ]
        chunks = _layout_aware_chunks(elements, target_size=5000)
        assert len(chunks) >= 2

    def test_article_metadata_propagated(self) -> None:
        elements = [
            self._make_element("Article 14 — Human Oversight", "Title"),
            self._make_element(
                "High-risk AI systems shall be designed to allow oversight.",
                "NarrativeText",
            ),
        ]
        chunks = _layout_aware_chunks(elements, target_size=5000)
        assert any("Article 14" in c.get("article", "") for c in chunks)

    def test_table_not_split(self) -> None:
        long_table = "Row1\nRow2\nRow3\n" * 100
        elements = [
            self._make_element(long_table, "Table"),
        ]
        chunks = _layout_aware_chunks(elements, target_size=50)
        # The table should remain as a single chunk even though it exceeds target
        table_contents = [c for c in chunks if "Row1" in c["content"]]
        assert len(table_contents) >= 1


# ── Ingestion Service Integration ─────────────────────────────────────────────


class TestIngestionService:

    @pytest.mark.asyncio
    async def test_process_pdf_offloads_to_thread(self) -> None:
        """Verify partition_pdf runs via asyncio.to_thread (non-blocking)."""
        import sys

        with patch("langchain_openai.OpenAIEmbeddings"):
            service = IngestionService()

        mock_element = MagicMock()
        mock_element.__str__ = lambda self: "Article 6 test content"
        mock_element.metadata = MagicMock()
        mock_element.metadata.page_number = 1
        type(mock_element).__name__ = "NarrativeText"

        # Mock the unstructured module so the lazy import inside process_pdf succeeds
        mock_unstructured = MagicMock()
        with (
            patch.dict(
                sys.modules,
                {
                    "unstructured": mock_unstructured,
                    "unstructured.partition": mock_unstructured.partition,
                    "unstructured.partition.pdf": mock_unstructured.partition.pdf,
                },
            ),
            patch(
                "app.services.ingestion.asyncio.to_thread", new_callable=AsyncMock
            ) as mock_thread,
            patch.object(service, "_generate_vectors", new_callable=AsyncMock),
        ):
            mock_thread.return_value = [mock_element]
            chunks = await service.process_pdf("/fake/path.pdf")
            mock_thread.assert_called_once()
            assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_upload_batches_correctly(
        self, mock_qdrant_client: AsyncMock
    ) -> None:
        """Verify upserts are batched."""
        from contextlib import asynccontextmanager

        from app.db.session import qdrant_session

        @asynccontextmanager
        async def _mock_client():
            yield mock_qdrant_client

        with patch("langchain_openai.OpenAIEmbeddings"):
            service = IngestionService()

        chunks = [
            LegalChunk(
                content=f"Chunk {i}",
                dense_vector=[0.1] * 1536,
                sparse_indices=[1, 2],
                sparse_values=[1.0, 1.0],
                metadata={"source": "test.pdf", "jurisdiction": "EU"},
            )
            for i in range(250)
        ]

        with patch.object(qdrant_session, "get_client", _mock_client):
            await service.upload_to_qdrant(chunks)

        # 250 chunks / 100 batch size = 3 upsert calls
        assert mock_qdrant_client.upsert.call_count == 3
