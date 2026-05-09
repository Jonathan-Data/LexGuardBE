# 🕵️ Audit Methodology & Logs

## Methodology
LexGuardBE employs a "Red-Teaming" compliance approach. Instead of a simple checklist, our agents attempt to "break" the compliance model of the AI system under review.

1. **Adversarial Legal Search**: The Auditor Agent searches for edge cases in the EU AI Act that might apply to the system's specific use case.
2. **Conflict Resolution**: If the Prover and Auditor agents disagree on a risk tier, the case is automatically escalated to a [[Human-in-the-loop (HITL) Interventions|HITL Node]].

## Immutable Audit Logs
Every transaction is logged in a `compliance_audit_trail` table.
- **ID**: UUID v4
- **Agent_ID**: The specific LLM/Agent version used.
- **Legal_Context**: The specific articles retrieved from [[Qdrant]].
- **Hash**: SHA-256 hash of the previous log entry to ensure chain integrity.

---
[[Lexguard|← Back to Hub]]
