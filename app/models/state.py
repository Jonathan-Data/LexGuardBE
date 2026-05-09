"""
Unified audit-graph state for LexGuardBE.

This module is the SINGLE SOURCE OF TRUTH for ``AuditState``. Every node,
the workflow compiler, and the FastAPI entrypoint must import from here
(``app.graph.state`` re-exports for backward compatibility).

Design rules
------------
* ``is_high_risk`` is set during classification and NEVER mutated by the
  Art. 6(3) auditor. Exemption outcome lives in ``is_exempt`` +
  ``exemption_reasoning`` so the audit trail keeps the original
  classification intact (Art. 11 traceability requirement).
* All free-text reasoning fields are filled by an LLM grounded on
  retrieved legal excerpts — never by keyword matching.
"""

from __future__ import annotations

from typing import List, Optional, TypedDict

from pydantic import BaseModel


class SystemMetadata(BaseModel):
    """API-level description of the AI system being audited."""

    name: str
    description: str
    industry: str
    intended_use: str
    user_base: str
    is_ai_generated: bool = False


class AuditState(TypedDict, total=False):
    """Lifecycle state for one compliance audit.

    Marked ``total=False`` so nodes can populate fields incrementally;
    the workflow seed in ``app.main`` provides safe defaults for every key.
    """

    # ── Input ─────────────────────────────────────────────────────────
    system_metadata: SystemMetadata
    description: str
    is_ai_generated: bool

    # ── Art. 5 — Prohibited check ─────────────────────────────────────
    is_prohibited: bool
    prohibited_practice: Optional[str]      # e.g. "Art. 5(1)(c) social scoring"
    prohibited_reasoning: Optional[str]     # LLM rationale grounded in Art. 5 text

    # ── Annex III — High-Risk classification ──────────────────────────
    risk_tier: Optional[str]                # "Prohibited" | "High" | "Limited" | "Minimal"
    is_high_risk: bool                      # NEVER overwritten by the auditor

    # ── Art. 6(3) — Escape Route exemption ────────────────────────────
    is_exempt: bool                         # True iff one of (a)-(d) is satisfied
    exemption_criterion: Optional[str]      # "6(3)(a)" .. "6(3)(d)"
    exemption_reasoning: Optional[str]      # LLM rationale grounded in Art. 6 text

    # ── Art. 50 / May 2026 Transparency Guidelines ────────────────────
    transparency_obligations: List[str]     # citations from version_date=2026-05-08

    # ── Evidence & trail ──────────────────────────────────────────────
    applicable_articles: List[str]
    citations: List[str]
    reasoning_trail: List[str]
    next_steps: List[str]


def new_audit_state(
    description: str,
    *,
    system_metadata: Optional[SystemMetadata] = None,
    is_ai_generated: bool = False,
) -> AuditState:
    """Construct an ``AuditState`` with all keys initialised to safe defaults.

    Use this from API handlers and tests — TypedDict alone does not give
    you defaults, and missing keys are the #1 source of KeyError crashes
    in LangGraph nodes.
    """
    state: AuditState = {
        "system_metadata": system_metadata,  # type: ignore[typeddict-item]
        "description": description,
        "is_ai_generated": is_ai_generated,
        "is_prohibited": False,
        "prohibited_practice": None,
        "prohibited_reasoning": None,
        "risk_tier": None,
        "is_high_risk": False,
        "is_exempt": False,
        "exemption_criterion": None,
        "exemption_reasoning": None,
        "transparency_obligations": [],
        "applicable_articles": [],
        "citations": [],
        "reasoning_trail": [],
        "next_steps": [],
    }
    return state
