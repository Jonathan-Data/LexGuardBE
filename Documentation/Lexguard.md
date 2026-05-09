# 🏛️ LexGuardBE: The Belgian AI Compliance Engine

> [!IMPORTANT]
> **Regulatory Context:** Designed for the August 2026 enforcement of the EU AI Act (Regulation 2024/1689).
> **Objective:** Transforming "Black Box" AI into "Glass Box" compliance through agentic governance.

## 🌐 Project Vision
LexGuardBE is an automated compliance-as-code layer that sits between raw AI development and regulatory oversight. In the Belgian landscape, where the BIPT (Belgian Institute for Postal services and Telecommunications) serves as a key supervisory authority, LexGuardBE provides the technical evidence required for conformity assessments.

Our mission is to bridge the gap between high-speed AI iteration and the rigorous transparency requirements of the EU AI Act.

- [[Vision & Philosophy|Read more about the Glass Box approach]]

---

## 🧭 Core Documentation

### ⚖️ Regulatory Intelligence
Understand how LexGuardBE maps your systems against the EU legal framework.
- [[Regulatory Mapping]]: Deep dive into Annex III and Risk Tiering.
- [[BIPT Guidelines]]: Belgian-specific regulatory nuances.
- [[Roadmap]]: Project timeline and development phases.

### 🏗️ Technical Architecture
Explore the "Agentic" stack powering our compliance cycles.
- [[The Agentic Stack]]: LangGraph, Qdrant, and FastAPI integration.
- [[Legal RAG]]: How we ensure zero-hallucination legal retrieval.

### 🛠️ Compliance Modules
Features designed to automate the heavy lifting of AI auditing.
- [[Compliance Features]]: Automated Bias Scans, Traceability, and HITL.
- [[Audit Logs]]: Immutable evidence for regulatory bodies.

---

## 👥 Persona-Based Guides

### 👨‍💻 For Developers
Learn how to integrate LexGuardBE into your CI/CD pipeline and Python ecosystem.
- [[Developer Integration Guide]]
- [[API Documentation]]

### ⚖️ For Regulators & Auditors
How LexGuardBE generates human-readable conformity reports and technical documentation (Art. 11).
- [[Regulatory Reporting Standards]]
- [[Audit Methodology]]

---

## 🚀 Quick Start
```bash
# Clone the compliance engine
git clone https://github.com/lexguard/lexguard-be.git

# Initialize the legal vector store
python scripts/ingest_legal_docs.py --region BE
```

---
**Status:** `v1.0.0-rc1` | **Maintainer:** LexGuard Technical Team