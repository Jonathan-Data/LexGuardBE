"""
LangGraph nodes for the LexGuardBE compliance audit.

Architecture
------------
classifier_node      Art. 5 (Prohibited) → Annex III (High-Risk) → Art. 50 transparency
compliance_auditor   Art. 6(3) "Escape Route" — only runs if not prohibited

All free-text decisions are produced by an LLM grounded on Qdrant
excerpts. Keyword heuristics were removed (audit findings H-1, M-2):
the EU AI Act's prohibitions and exemption criteria are intent-based,
not lexical, and ``"social scoring"`` cannot be detected by string match.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from app.db.qdrant import search_legal_docs
from app.models.state import AuditState
from app.services.ingestion import get_ingestion_service


# ══════════════════════════════════════════════════════════════════════════════
#  LLM client (lazy singleton)
# ══════════════════════════════════════════════════════════════════════════════

_llm = None
_TRANSPARENCY_VERSION_DATE = "2026-05-08"  # EC Guidelines, Art. 50


def _get_llm():
    """Return a temperature-0 ChatOpenAI singleton.

    Lazy-loaded so importing this module does not require an OpenAI key
    at startup (tests and ingestion can run without it).
    """
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(model="gpt-4o", temperature=0)
    return _llm


def _format_excerpts(docs) -> str:
    """Render Qdrant ScoredPoint payloads as numbered excerpts for the prompt."""
    lines: list[str] = []
    for i, doc in enumerate(docs, start=1):
        payload = doc.payload or {}
        article = payload.get("article") or payload.get("annex") or "—"
        content = (payload.get("content") or "").strip()
        version = payload.get("version_date") or payload.get("regulation_id") or ""
        header = f"[{i}] {article}"
        if version:
            header += f"  (version: {version})"
        lines.append(f"{header}\n{content}")
    return "\n\n".join(lines) if lines else "(no legal text retrieved)"


# ══════════════════════════════════════════════════════════════════════════════
#  LLM output schemas
# ══════════════════════════════════════════════════════════════════════════════

class ProhibitedDecision(BaseModel):
    """Structured output for the Art. 5 prohibition check."""

    is_prohibited: bool = Field(
        description="True only if the system meets one of the practices "
                    "expressly prohibited by Article 5(1)(a)–(h)."
    )
    matched_practice: Optional[str] = Field(
        default=None,
        description="Citation of the specific prohibition, e.g. "
                    "'Art. 5(1)(c) — social scoring by public authorities'.",
    )
    reasoning: str = Field(
        description="Explanation grounded in the retrieved Article 5 text. "
                    "Reference excerpt numbers ([1], [2], …)."
    )


class ExemptionDecision(BaseModel):
    """Structured output for the Art. 6(3) escape-route evaluation."""

    is_exempt: bool = Field(
        description="True iff at least one of the four cumulative criteria "
                    "in Art. 6(3)(a)–(d) is satisfied AND the system does not "
                    "perform profiling of natural persons."
    )
    criterion: Optional[str] = Field(
        default=None,
        description="Which sub-paragraph applies: '6(3)(a)', '6(3)(b)', "
                    "'6(3)(c)', or '6(3)(d)'. Null when not exempt.",
    )
    reasoning: str = Field(
        description="Justification grounded in the retrieved Art. 6 text. "
                    "Reference excerpt numbers ([1], [2], …) and explain "
                    "why the criterion is met or unmet."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  NODE 1: CLASSIFIER  (Art. 5 → Annex III → Art. 50)
# ══════════════════════════════════════════════════════════════════════════════

async def classifier_node(state: AuditState) -> AuditState:
    """Risk classification with three sequential checks:

    1. **Art. 5 (Prohibited)** — LLM evaluates retrieved Art. 5 excerpts
       against the system description. If prohibited, classification ends
       immediately and the workflow routes around the auditor.
    2. **Annex III (High-Risk)** — Hybrid Qdrant search filtered to Annex III.
    3. **Art. 50 / May 2026 Transparency Guidelines** — strict exact-match
       on ``version_date == "2026-05-08"``.
    """

    description = state["description"]
    logger.info(f"Classifying system: {description[:80]}…")

    service = get_ingestion_service()
    query_vector = await service.get_embedding(description)
    llm = _get_llm()

    # ── Step 1: Art. 5 — LLM-grounded prohibition check ────────────────
    art5_query_vec = await service.get_embedding(
        "Article 5 prohibited AI practices social scoring biometric "
        "categorisation emotion recognition workplace subliminal manipulation"
    )
    art5_docs = await search_legal_docs(
        query_vector=art5_query_vec,
        filters={"article": "Art. 5"},
        limit=6,
    )
    art5_excerpts = _format_excerpts(art5_docs)

    prohibition_prompt = (
        "You are an EU AI Act compliance auditor evaluating Article 5 "
        "(Regulation (EU) 2024/1689, applicable since 2 February 2025).\n\n"
        "Determine whether the system below constitutes a PROHIBITED practice "
        "under Art. 5(1)(a)–(h). The eight prohibited categories are:\n"
        "  (a) subliminal/manipulative techniques causing significant harm;\n"
        "  (b) exploitation of vulnerabilities (age, disability, social/economic);\n"
        "  (c) social scoring by public authorities or on their behalf;\n"
        "  (d) predictive policing based solely on profiling/personality traits;\n"
        "  (e) untargeted scraping of facial images for recognition databases;\n"
        "  (f) emotion recognition in workplaces and education institutions;\n"
        "  (g) biometric categorisation inferring race, opinions, orientation, etc.;\n"
        "  (h) real-time remote biometric identification in publicly accessible "
        "spaces for law enforcement (subject to narrow exceptions).\n\n"
        f"=== System description ===\n{description}\n\n"
        f"=== Retrieved Article 5 legal text ===\n{art5_excerpts}\n\n"
        "Respond with structured output. Set is_prohibited=true ONLY when the "
        "system clearly meets one of the eight categories. Cite the excerpt "
        "number(s) in your reasoning."
    )

    prohibited_llm = llm.with_structured_output(ProhibitedDecision)
    decision_p: ProhibitedDecision = await prohibited_llm.ainvoke(prohibition_prompt)

    if decision_p.is_prohibited:
        logger.warning(
            f"PROHIBITED practice detected: {decision_p.matched_practice}"
        )
        state["is_prohibited"] = True
        state["prohibited_practice"] = decision_p.matched_practice
        state["prohibited_reasoning"] = decision_p.reasoning
        state["risk_tier"] = "Prohibited"
        state["is_high_risk"] = False
        state["citations"].append(
            f"Art. 5 — {decision_p.matched_practice or 'prohibited practice'}"
        )
        for doc in art5_docs:
            content = (doc.payload or {}).get("content", "")[:160]
            state["citations"].append(f"Art. 5 excerpt: {content}…")
        state["reasoning_trail"].append(
            f"Art. 5 prohibition: {decision_p.reasoning}"
        )
        state["next_steps"].append(
            "IMMEDIATE: Block deployment. Escalate to Legal Officer. "
            "System falls under Art. 5 — no high-risk pathway available."
        )
        return state  # short-circuit: no Annex III / transparency / Art. 6(3)

    state["is_prohibited"] = False
    state["reasoning_trail"].append(
        f"Art. 5 cleared: {decision_p.reasoning}"
    )

    # ── Step 2: Annex III — High-Risk classification ───────────────────
    annex_matches = await search_legal_docs(
        query_vector=query_vector,
        filters={"annex": "Annex III"},
        limit=5,
    )

    if annex_matches:
        state["risk_tier"] = "High Risk"
        state["is_high_risk"] = True
        for match in annex_matches:
            payload = match.payload or {}
            content = payload.get("content", "")[:150]
            article = payload.get("article", "Annex III")
            state["citations"].append(f"Annex III ({article}): {content}…")
            state["applicable_articles"].append(article)
        state["reasoning_trail"].append(
            f"Annex III matched on {len(annex_matches)} chunks → High Risk."
        )
    else:
        state["risk_tier"] = "Limited"
        state["is_high_risk"] = False
        state["reasoning_trail"].append(
            "No Annex III matches → Limited / Minimal risk tier."
        )

    # ── Step 3: Art. 50 / May 2026 Transparency Guidelines ─────────────
    if state.get("is_ai_generated"):
        logger.info(
            "is_ai_generated=True → applying May 8, 2026 Transparency check."
        )

        transparency_query_vec = await service.get_embedding(
            "Article 50 transparency obligations AI-generated content "
            "machine-readable marks watermarking deepfake disclosure"
        )
        transparency_results = await search_legal_docs(
            query_vector=transparency_query_vec,
            filters={
                "article": "Art. 50",
                "version_date": _TRANSPARENCY_VERSION_DATE,  # strict exact-match
            },
            limit=4,
        )

        if transparency_results:
            for r in transparency_results:
                payload = r.payload or {}
                content = payload.get("content", "")[:160]
                citation = (
                    f"Art. 50 / EC Guidelines {_TRANSPARENCY_VERSION_DATE}: "
                    f"{content}…"
                )
                state["citations"].append(citation)
                state["transparency_obligations"].append(citation)
            state["reasoning_trail"].append(
                f"Loaded {len(transparency_results)} obligations from EC "
                f"Guidelines (version_date={_TRANSPARENCY_VERSION_DATE})."
            )
            state["next_steps"].append(
                "Implement machine-readable marking per EC Guidelines of "
                "8 May 2026 (Art. 50(2) — synthetic content)."
            )
        else:
            state["reasoning_trail"].append(
                "WARNING: No documents matched version_date="
                f"{_TRANSPARENCY_VERSION_DATE}. The EC Transparency "
                "Guidelines must be ingested before this audit is valid."
            )
            state["next_steps"].append(
                f"CRITICAL: Ingest EC Guidelines (version_date="
                f"{_TRANSPARENCY_VERSION_DATE}) into the legal_knowledge collection."
            )

    state["reasoning_trail"].append("Classification phase complete.")
    return state


# ══════════════════════════════════════════════════════════════════════════════
#  NODE 2: COMPLIANCE AUDITOR  (Article 6(3) Escape Route)
# ══════════════════════════════════════════════════════════════════════════════

async def compliance_auditor(state: AuditState) -> AuditState:
    """LLM-driven Article 6(3) escape-route evaluation.

    Article 6(3) (Reg. 2024/1689) says a system listed in Annex III is NOT
    high-risk if it does not pose a significant risk of harm because it:
        (a) performs a narrow procedural task;
        (b) improves the result of a previously completed human activity;
        (c) detects decision-making patterns or deviations without
            intending to replace or influence the human assessment without
            proper human review;
        (d) performs a preparatory task to an assessment relevant for the
            purposes of the use cases listed in Annex III.

    Crucially: the exemption is FORFEITED if the system performs profiling
    of natural persons. The LLM enforces this carve-out.

    This node never mutates ``is_high_risk`` — the original classification
    is preserved for Art. 11 traceability. The exemption outcome lives in
    ``is_exempt`` / ``exemption_criterion`` / ``exemption_reasoning``.
    """

    if state.get("is_prohibited"):
        # Defence-in-depth: the workflow routes around us when prohibited,
        # but if we ever get called we must not run the escape route.
        state["reasoning_trail"].append(
            "Art. 6(3) skipped — system is Prohibited under Art. 5."
        )
        return state

    if not state.get("is_high_risk"):
        state["reasoning_trail"].append(
            "Art. 6(3) skipped — system is not classified as High Risk."
        )
        return state

    logger.info("Evaluating Article 6(3) escape-route exemption…")
    description = state["description"]

    # ── Retrieve Art. 6 legal text to ground the LLM decision ──────────
    service = get_ingestion_service()
    query_vector = await service.get_embedding(
        "Article 6 paragraph 3 exemption Annex III narrow procedural task "
        "preparatory human assessment profiling natural persons"
    )
    exemption_docs = await search_legal_docs(
        query_vector=query_vector,
        filters={"article": ["Art. 6", "Art. 6(3)"]},  # MatchAny on either label
        limit=6,
    )

    if not exemption_docs:
        # H-3 fail-safe: without legal text the LLM cannot ground a decision.
        state["is_exempt"] = False
        state["exemption_criterion"] = None
        state["exemption_reasoning"] = (
            "No Article 6 text found in the legal store; cannot ground an "
            "exemption decision. Defaulting to conservative outcome (no exemption)."
        )
        state["reasoning_trail"].append(state["exemption_reasoning"])
        state["next_steps"].append(
            "Ingest Article 6 of Regulation 2024/1689 before re-running the auditor."
        )
        state["next_steps"].append("Complete full Annex III conformity assessment.")
        return state

    excerpts = _format_excerpts(exemption_docs)
    for doc in exemption_docs:
        content = (doc.payload or {}).get("content", "")[:140]
        state["citations"].append(f"Art. 6 reference: {content}…")
    state["reasoning_trail"].append(
        f"Retrieved {len(exemption_docs)} Art. 6 chunks to ground exemption analysis."
    )

    # ── LLM-grounded evaluation against the four cumulative criteria ───
    prompt = (
        "You are an EU AI Act compliance auditor evaluating the Article 6(3) "
        "'escape route' exemption for an Annex III high-risk system.\n\n"
        "Article 6(3) provides that a system is NOT high-risk if it does not "
        "pose a significant risk of harm AND meets at least one of:\n"
        "  (a) performs a narrow procedural task;\n"
        "  (b) improves the result of a previously completed human activity;\n"
        "  (c) detects decision-making patterns / deviations without replacing "
        "      or influencing the prior human assessment without proper review;\n"
        "  (d) performs a preparatory task for a use case listed in Annex III.\n\n"
        "OVERRIDING CARVE-OUT: the exemption is FORFEITED if the system "
        "performs profiling of natural persons (Art. 6(3) final subparagraph).\n\n"
        f"=== System description ===\n{description}\n\n"
        f"=== Retrieved Article 6 legal text ===\n{excerpts}\n\n"
        "Decide whether the exemption applies. If yes, identify which "
        "sub-paragraph (a–d) and explain how the description satisfies it, "
        "citing excerpt numbers. If no, explain which criterion failed or "
        "whether the profiling carve-out applies."
    )

    exemption_llm = _get_llm().with_structured_output(ExemptionDecision)
    decision_e: ExemptionDecision = await exemption_llm.ainvoke(prompt)

    # ── Apply the decision (NEVER touch is_high_risk) ──────────────────
    state["is_exempt"] = decision_e.is_exempt
    state["exemption_criterion"] = decision_e.criterion if decision_e.is_exempt else None
    state["exemption_reasoning"] = decision_e.reasoning

    if decision_e.is_exempt:
        crit = decision_e.criterion or "Art. 6(3)"
        # Original tier preserved; we annotate the *display* string only.
        state["risk_tier"] = f"High Risk (Exempt: {crit})"
        state["reasoning_trail"].append(
            f"Art. 6(3) exemption APPLIED — {crit}: {decision_e.reasoning}. "
            "is_high_risk preserved for Art. 11 traceability."
        )
        state["next_steps"].append(
            f"REQUIRED: Human auditor must verify {crit} exemption (Art. 14). "
            "System remains in High-Risk registry until manual confirmation."
        )
    else:
        state["reasoning_trail"].append(
            f"Art. 6(3) exemption DENIED: {decision_e.reasoning}"
        )
        state["next_steps"].append("Complete full Annex III conformity assessment.")
        state["next_steps"].append(
            "Requirements: Art. 9 (Risk Mgmt), Art. 10 (Data Governance), "
            "Art. 11 (Technical Documentation), Art. 14 (Human Oversight)."
        )

    state["reasoning_trail"].append("Compliance auditor phase complete.")
    return state
