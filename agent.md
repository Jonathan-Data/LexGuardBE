# 🤖 LexGuardBE: Agent Context & Compliance Ledger

## 📌 Project Overview
**Goal:** Automated EU AI Act Compliance (Regulation 2024/1689).
**Enforcement Deadline:** August 2026.
**Stack:** FastAPI, LangGraph, Qdrant, Python 3.12+.
**Regulatory Baseline:** May 8, 2026 European Commission Transparency Guidelines.

## 🏗️ Current State: Phase 2 — Agent Development (Refactor Complete)
The LangGraph compliance engine has been hardened against the 9 issues found
in the Phase 2 audit. All keyword heuristics have been replaced with
LLM-grounded reasoning over Qdrant-retrieved legal text.

## ✅ Completed Tasks
- [x] Initial Audit of Documentation (EU AI Act, BIPT Guidelines).
- [x] Project Directory Structure Generation.
- [x] Core Boilerplate Initialization.
- [x] Asynchronous Ingestion Pipeline (Phase 1 Foundation).
- [x] Phase 1 Code Review & Optimization.
- [x] Test Suite Creation (4 modules, 30+ cases).
- [x] **Phase 2 Refactor — all 9 issues resolved (see ledger below).**

## 📋 To-Do List
- [x] Implement `RiskCategorizer` node logic → now `classifier_node` (LLM-grounded).
- [x] Build LangGraph skeleton (`app/graph/nodes.py`, `app/graph/workflow.py`).
- [x] LLM-grounded Art. 5 prohibition check.
- [x] LLM-grounded Art. 6(3) escape-route reasoning over retrieved text.
- [x] Strict `version_date == "2026-05-08"` filter for Transparency Guidelines.
- [x] Conditional edge: prohibited systems bypass the auditor.
- [ ] Build Legal RAG query service abstraction on top of `app/db/qdrant.py`.
- [ ] Create FastAPI endpoint streaming audit results (Server-Sent Events).
- [ ] Implement HITL Review Dashboard (Art. 14).
- [ ] Ingest actual EU AI Act PDF and BIPT Circular.
- [ ] Ingest May 8, 2026 EC Transparency Guidelines (must match `version_date`).
- [ ] Add CI pipeline with `pytest` gate.

## ⚖️ Strict Compliance Instructions
1. **Zero Hallucination Policy:** All regulatory citations MUST be verified
   against the Qdrant legal vector store. Never guess an Article number.
2. **Traceability:** Every node must log its reasoning AND the retrieved
   legal snippet that grounded its decision (`reasoning_trail` + `citations`).
3. **No Mutation of Classification:** `is_high_risk` is set once by the
   classifier and is NEVER overwritten. Art. 6(3) outcomes live in
   `is_exempt` / `exemption_criterion` / `exemption_reasoning`.
4. **Data Privacy:** Client metadata handled per GDPR. No PII in vectors.
5. **Transparency:** AI-generated reports must declare AI authorship and
   require human oversight (Art. 14 + Art. 50(2) machine-readable marks).
6. **Versioning:** Every chunk carries a `version_date`. EC Guidelines of
   8 May 2026 are queried with a strict exact-match filter.

---

## 📊 Phase 2: Logic Audit — RESOLUTION LEDGER

| # | Severity | Issue | Resolution |
|---|---|---|---|
| **C-1** | Critical | `get_embedding` not exposed | ✅ Public `async def get_embedding` on `IngestionService` (`app/services/ingestion.py:155`). |
| **C-2** | Critical | `search_legal_docs` used `MatchText` (full-text) — failed exact lookups for `"Art. 6"` / `"2026-05-08"` | ✅ Rewritten with `MatchValue` + `MatchAny`. Filters now accept either `str` (exact) or `list[str]` (OR). Filter is also pushed into both prefetch arms for sparse+dense parity. |
| **C-3** | Critical | Two competing `AuditState` definitions (`app/models/state.py` and `app/graph/state.py`) plus a stale `app/graph/nodes/risk_categorizer.py` | ✅ Consolidated into `app/models/state.py` with a `new_audit_state(...)` factory. `app/graph/state.py` now re-exports. The `app/graph/nodes/` subpackage that shadowed `nodes.py` was removed. |
| **H-1** | High | Art. 6(3) decided by `pattern in desc_lower` keyword matching | ✅ Replaced with `ChatOpenAI.with_structured_output(ExemptionDecision)` evaluating the four cumulative criteria + the profiling carve-out. |
| **H-2** | High | Auditor overwrote `is_high_risk` when applying exemption | ✅ Auditor now only writes `is_exempt`, `exemption_criterion`, `exemption_reasoning`. `is_high_risk` is preserved for Art. 11 traceability. |
| **H-3** | High | `exemption_docs` were retrieved but never passed to the LLM | ✅ `_format_excerpts(docs)` injects numbered excerpts directly into the prompt. The LLM is instructed to cite excerpt numbers in its reasoning. |
| **H-4** | High | Transparency check used loose text matching for `version_date` | ✅ Strict `MatchValue("2026-05-08")` plus `MatchValue("Art. 50")` filter. Constant `_TRANSPARENCY_VERSION_DATE` in `app/graph/nodes.py` is the single source of truth. |
| **M-1** | Medium | Workflow fell through prohibited systems into the auditor | ✅ `add_conditional_edges("classifier", _route_after_classifier, …)` routes prohibited systems straight to `END`. |
| **M-2** | Medium | No Article 5 evaluation | ✅ Classifier runs an LLM-grounded Art. 5 check FIRST against retrieved Art. 5 excerpts. Sets `is_prohibited`, `prohibited_practice`, `prohibited_reasoning`. |

### Summary: How the May 8, 2026 Transparency Guidelines are Programmatically Enforced

1. **Ingestion contract** — every chunk in `legal_knowledge` carries
   `version_date` (Pydantic `date`, serialised as ISO `2026-05-08` in JSON
   payload mode). `LegalMetadata` makes this field mandatory for the
   May Guidelines ingest.
2. **Exact-match retrieval** — `search_legal_docs` uses
   `models.MatchValue` (not `MatchText`), so the filter
   `{"article": "Art. 50", "version_date": "2026-05-08"}` cannot be
   silently relaxed by missing payload indexes.
3. **Single source of truth** — `_TRANSPARENCY_VERSION_DATE` is a module
   constant in `app/graph/nodes.py`. Only one line to update if the
   Commission re-issues the guidelines.
4. **Triggering rule** — the transparency block runs whenever
   `state["is_ai_generated"]` is true, regardless of risk tier. AI-generated
   content carries Art. 50 obligations even outside Annex III.
5. **Fail-loud absence** — if zero results match `version_date=2026-05-08`,
   the audit emits a CRITICAL `next_step` requiring ingestion of the
   guidelines before the audit can be considered complete. No silent
   degradation to the 2024/1689 baseline.
6. **Output channel** — matched obligations populate
   `state["transparency_obligations"]`, separate from generic citations,
   so the Art. 14 HITL dashboard can display them under a dedicated
   "Machine-readable marking" section.

---

## 🔁 Verification Tests (new)

| Scenario | Input fixture | Expected outcome |
|---|---|---|
| **VT-1 Prohibited bypass** | `description="staff emotion-monitoring system in a call centre"` | `is_prohibited=True`, `risk_tier="Prohibited"`, `is_exempt=False` (default), workflow routes around `compliance_auditor`. `prohibited_reasoning` cites Art. 5(1)(f). |
| **VT-2 Art. 6(3) genuine exemption** | `description="resume PDF-to-text formatter, no scoring, no profiling"` | `is_high_risk=True` AND `is_exempt=True`, `exemption_criterion="6(3)(a)"`, `exemption_reasoning` references retrieved Art. 6 excerpt. **Critical assertion: `state["is_high_risk"] is True` AFTER auditor runs.** |
| **VT-3 Profiling carve-out** | `description="Annex III HR tool that profiles candidates"` | `is_high_risk=True`, `is_exempt=False` because profiling forfeits the exemption (Art. 6(3) final subparagraph). |
| **VT-4 Strict version filter** | Ingest two Art. 50 chunks: one `version_date=2024-08-01`, one `version_date=2026-05-08`. Run audit with `is_ai_generated=True`. | Only the `2026-05-08` chunk appears in `transparency_obligations`. |
| **VT-5 Missing guidelines** | Ingest only the 2024/1689 baseline. Run audit with `is_ai_generated=True`. | No transparency hits, but `next_steps` contains a CRITICAL ingest directive. Audit does not crash. |
| **VT-6 MatchAny filter** | Ingest chunks tagged `article="Art. 6"` and `article="Art. 6(3)"`. Auditor query with `["Art. 6", "Art. 6(3)"]` returns both. | Both chunks appear in `exemption_docs`. |
| **VT-7 Empty Art. 6 store** | No Art. 6 chunks ingested, system is High-Risk. | Auditor sets `is_exempt=False` with explicit "cannot ground decision" reasoning, queues an ingestion `next_step`. Does not crash. |
| **VT-8 State factory completeness** | Call `new_audit_state(description="x")`. | All 14 keys present with safe defaults; passing into `compliance_engine.ainvoke(...)` does not raise `KeyError`. |
| **VT-9 Conditional routing** | Trace LangGraph execution for a prohibited system. | `compliance_auditor` is NOT invoked (assert via mock or LangGraph state inspection). |

---

## 🤝 Handoff: Phase 3 — Hallucination Guard & HITL

### Objective
1. Add a `hallucination_guard` node downstream of the auditor that
   cross-checks every claim in `reasoning_trail` against the article
   actually retrieved.
2. Wire `state["citations"]` into a Streamlit / Next.js dashboard for
   Article 14 human oversight.
3. Ingest the canonical EU AI Act PDF and the May 8, 2026 EC Transparency
   Guidelines so the strict `version_date` filter has data to match.

### Technical Debt Carried Forward
- **Sparse-vector hashing:** `_build_sparse_vector` uses `hash(tok) % 2**16`
  — collision rate is unmeasured against the real legal corpus. Migrate
  to a deterministic vocabulary (e.g., the BPE tokeniser used for dense
  embeddings) before the August 2026 deadline.
- **LLM cost:** every audit triggers up to 2 `gpt-4o` structured-output
  calls plus 3 embedding calls. Add request-level caching keyed on
  `(description, retrieved_doc_ids)`.
- **No fallback model:** `_get_llm()` hard-codes `gpt-4o`. Wrap in a
  router that can fall back to Claude / a local model for sovereignty
  guarantees required by some BE clients.
- **Qdrant version compatibility:** `query_points` with `prefetch` requires
  Qdrant ≥ 1.10. Pin in `requirements.txt` once the staging cluster is
  upgraded.
- **`main.py` CLI/HTTP coexistence:** still uses `sys.argv` heuristic.
  Split into `app/cli.py` and `app/api.py` before adding more commands.
