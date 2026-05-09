# Phase 2 Logic Audit — LangGraph Nodes

> [!CAUTION]
> **9 issues found** · 3 Critical · 4 High · 2 Medium

---

## 1. Critical Bugs (Will Crash at Runtime)

### C-1: `get_embedding()` does not exist on `IngestionService`

[nodes.py:17](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L17) calls `service.get_embedding(description)` but `IngestionService` has no such method. The private `_embeddings.aembed_query()` is never exposed.

```python
# nodes.py:17 — will raise AttributeError
query_vector = await service.get_embedding(description)
```

**Fix:** Add a public `async def get_embedding(self, text: str) -> list[float]` method to `IngestionService`.

### C-2: Qdrant filter targets wrong metadata key for Annex III

[nodes.py:22](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L22) passes `article_filter="Annex III"`, but `search_legal_docs` filters on the `article` field. Annex data is stored in the `annex` payload key, not `article`.

```python
# qdrant.py:33 — filter always matches against "article"
models.FieldCondition(key="article", match=...)
```

**Result:** Annex III chunks will **never be returned**. Every system will be classified as "Minimal/Limited" regardless of actual risk.

**Fix:** `search_legal_docs` needs a generic `filter_key`/`filter_value` parameter, or separate `annex_filter`.

### C-3: Duplicate `AuditState` definitions — import collision

[app/models/state.py](file:///Users/jolauwer/Documents/LexGuardBE/app/models/state.py) and [app/graph/state.py](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/state.py) both define `AuditState` with **different schemas**. The workflow imports from `app.graph.state`, but `main.py` still imports from `app.models.state`. This will cause silent runtime mismatches.

---

## 2. Article 6(3) Escape Route — False Negative Analysis

> [!WARNING]
> **The current implementation has a near-100% false-negative rate.** Legitimate Art. 6(3) exemptions will almost never be detected.

### H-1: Keyword matching is fatally narrow

[nodes.py:75](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L75):

```python
if "accessory" in state["description"].lower() or "purely technical" in state["description"].lower():
```

Article 6(3) provides **four** independent exemption criteria. The code only checks for two English keywords. This misses:

| Art. 6(3) Criterion | Current Coverage |
|---|---|
| (a) Performs a narrow procedural task | ❌ Not checked |
| (b) Improves the result of a previously completed activity | ❌ Not checked |
| (c) Detects decision-making patterns without replacing human assessment | ❌ Not checked |
| (d) Performs a preparatory task for a high-risk assessment | ❌ Not checked |
| "purely accessory" general exemption | ⚠️ Keyword only — misses synonyms |

**False-negative scenario:** An AI that "prepares data for a human recruiter's final decision" is exempt under 6(3)(d), but the string `"accessory"` never appears in that description.

### H-2: Exemption result flips `is_high_risk` — destroys audit trail

[nodes.py:77](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L77):

```python
state["is_high_risk"] = False  # Effectively downgraded
```

Setting `is_high_risk = False` after an exemption makes the system **indistinguishable** from a genuinely low-risk system in any downstream node. The original classification evidence is lost.

**Compliance risk:** Art. 11 (Technical Documentation) requires documenting *why* an exemption was applied. Overwriting `is_high_risk` eliminates the paper trail.

### H-3: Retrieved `exemption_docs` are never used

[nodes.py:67-71](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L67-L71) performs a Qdrant search for Art. 6 criteria, stores results in `exemption_docs`, then **ignores them entirely**. The decision at line 75 is purely keyword-based.

This violates the Zero Hallucination Policy — the decision is made without consulting the legal vector store.

---

## 3. May 8, 2026 Transparency Guidelines — Prompt Engineering Review

### H-4: No actual `version_date` filtering

[nodes.py:35](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L35):

```python
# Note: In real implementation, we'd filter for version_date="2026-05-08"
```

The comment acknowledges the gap but doesn't implement it. Without filtering on `version_date`, the search returns **any** Art. 13 chunk — including the base 2024 text. The May 2026 update introduced new transparency obligations for GPAI models. Returning the old text is a compliance violation.

### M-1: Transparency result is not actionable

[nodes.py:47](file:///Users/jolauwer/Documents/LexGuardBE/app/graph/nodes.py#L47):

```python
state["citations"].extend(["Compliant with May 2026 Transparency Guidelines"])
```

This appends a **hardcoded compliance claim** regardless of what the search actually returned. Even if zero results come back, the system claims compliance. This is the opposite of zero-hallucination.

### M-2: No `is_prohibited` check in the classifier

The `classifier_node` sets `is_high_risk` but never evaluates `is_prohibited` (Art. 5). The state field exists but is never written. A prohibited system (e.g., social scoring) would be classified as "High Risk" instead of being immediately blocked.

---

## 4. Summary Matrix

| ID | Severity | Location | Issue |
|---|---|---|---|
| C-1 | **Critical** | `nodes.py:17` | `get_embedding()` doesn't exist |
| C-2 | **Critical** | `nodes.py:22` + `qdrant.py:33` | Annex filter targets wrong key |
| C-3 | **Critical** | `state.py` (x2) | Duplicate `AuditState` definitions |
| H-1 | High | `nodes.py:75` | Art. 6(3) — 2 keywords vs 4 legal criteria |
| H-2 | High | `nodes.py:77` | Exemption destroys `is_high_risk` audit trail |
| H-3 | High | `nodes.py:67-71` | Retrieved exemption docs ignored |
| H-4 | High | `nodes.py:35` | No `version_date` filter for May 2026 |
| M-1 | Medium | `nodes.py:47` | Hardcoded compliance claim |
| M-2 | Medium | `nodes.py` | `is_prohibited` never evaluated |
