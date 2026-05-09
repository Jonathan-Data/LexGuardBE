# LexGuardBE — Agentic EU AI Act Compliance Engine

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red.svg)](https://qdrant.tech/)

**LexGuardBE** is a production-grade, multi-agent compliance engine designed to automate the classification and auditing of AI systems under the **EU AI Act (Regulation 2024/1689)**. Built for the rigorous standards of the Belgian and European legal-tech markets, it bridges the gap between raw AI capabilities and strict regulatory requirements.

---

## Project Overview
As the EU AI Act moves towards full enforceability in **August 2026**, organizations face complex obligations ranging from transparency disclosures to high-risk conformity assessments. LexGuardBE provides a deterministic, zero-hallucination framework to:
- Identify **Prohibited Practices** (Art. 5).
- Classify **High-Risk Systems** (Annex III).
- Execute the **Article 6(3) "Escape Route"** using LLM-grounded legal reasoning.
- Enforce the **May 8, 2026 Transparency Guidelines** for synthetic content.

## Key Features
- **Agentic Workflow**: Orchestrated via **LangGraph**, ensuring predictable state transitions and complex "escape route" logic that simple RAG pipelines cannot handle.
- **Hybrid RAG (Dense + Sparse)**: Powered by **Qdrant**, combining semantic understanding (OpenAI `text-embedding-3-small`) with precise keyword recall for Article and Annex numbers.
- **Legal Grounding**: Every decision is anchored in retrieved legal text. The engine rejects hardcoded heuristics in favor of intent-based reasoning (e.g., detecting "social scoring" via context rather than string matching).
- **Audit Traceability**: Maintains a full `AuditState` including reasoning trails, citations, and next steps, satisfying Article 11 (Technical Documentation) requirements.

## Tech Stack
- **Core**: Python 3.12+ (Async-first architecture)
- **Orchestration**: LangGraph
- **API Framework**: FastAPI
- **Vector Database**: Qdrant (Hybrid Search)
- **LLM**: GPT-4o (Structured Outputs via Pydantic)
- **Ingestion**: Unstructured.io (Layout-aware PDF partitioning)

---

## Installation & Setup

### 1. Environment Setup
Clone the repository and initialize the asynchronous Python environment:
```bash
git clone git@github.com:Jonathan-Data/LexGuardBE.git
cd LexGuardBE
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Infrastructure (Qdrant)
Run a local Qdrant instance via Docker:
```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant
```

### 3. Legal Data Ingestion
Ingest the EU AI Act and the May 2026 Transparency Guidelines:
```bash
export OPENAI_API_KEY="your-key"
python -m app.main ingest --file-path data/legal/eu_ai_act.pdf --jurisdiction EU
```

---

## Regulatory Compliance Note
LexGuardBE is strictly updated to reflect the **May 8, 2026 Transparency Guidelines** issued by the European Commission. It specifically monitors obligations for GPAI models and synthetic content marking under Article 50(2).

## About
Developed for the Belgian legal-tech ecosystem, LexGuardBE emphasizes **Production-Readiness**, **Legal Precision**, and **Auditability**.

---
*Disclaimer: This tool is intended to assist legal professionals and compliance officers. It does not constitute legal advice.*
