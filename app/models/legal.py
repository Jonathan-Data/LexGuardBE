"""
Pydantic v2 schemas for legal document ingestion.

Covers EU AI Act structural hierarchy:
  Regulation → Chapter → Section → Article → Paragraph
"""

from __future__ import annotations

import sys
import uuid
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# Python 3.11+ has StrEnum natively; for older runtimes, emulate it.
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):
        """Backport of StrEnum for Python < 3.11."""
        pass


class Jurisdiction(StrEnum):
    EU = "EU"
    BE = "BE"


class RiskLevel(StrEnum):
    PROHIBITED = "prohibited"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class LegalMetadata(BaseModel):
    """Rich metadata capturing the legal hierarchy and provenance."""

    source: str = Field(..., description="Filename or URI of the source document.")
    jurisdiction: Jurisdiction = Jurisdiction.EU

    # ── Legal hierarchy ─────────────────────────────────────────────
    chapter: Optional[str] = Field(None, description="e.g. 'Chapter III'")
    section: Optional[str] = Field(None, description="e.g. 'Section 2'")
    article: Optional[str] = Field(None, description="e.g. 'Art. 6'")
    annex: Optional[str] = Field(None, description="e.g. 'Annex III'")
    paragraph: Optional[str] = Field(None, description="e.g. '§2(b)'")

    # ── Risk & classification ──────────────────────────────────────
    risk_level: Optional[RiskLevel] = None

    # ── Versioning ─────────────────────────────────────────────────
    regulation_id: str = Field(
        default="2024/1689",
        description="Official regulation identifier.",
    )
    version_date: Optional[date] = Field(
        None,
        description="Date of the specific legal text version (e.g. May 8, 2026 transparency update).",
    )

    # ── Physical position ──────────────────────────────────────────
    page: Optional[int] = None
    element_type: Optional[str] = Field(
        None,
        description="Unstructured element type: NarrativeText, Table, Title, etc.",
    )


class LegalChunk(BaseModel):
    """A single vectorised chunk of a legal document."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    dense_vector: Optional[list[float]] = None
    sparse_indices: Optional[list[int]] = None
    sparse_values: Optional[list[float]] = None
    metadata: LegalMetadata
