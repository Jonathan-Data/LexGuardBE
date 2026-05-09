"""
Legal document ingestion pipeline for LexGuardBE.

Flow:  PDF → Unstructured (hi_res) → Layout-Aware Chunking
       → Parallel Embedding (dense + sparse) → Batched Qdrant Upsert
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Final, Optional

from loguru import logger

from app.db.session import (
    LEGAL_COLLECTION,
    ensure_collection,
    qdrant_session,
)
from app.models.legal import Jurisdiction, LegalChunk, LegalMetadata

if TYPE_CHECKING:
    from langchain_openai import OpenAIEmbeddings
    from qdrant_client import models


# ── Constants ──────────────────────────────────────────────────────────────────

CHUNK_TARGET_CHARS: Final[int] = 900
CHUNK_OVERLAP_CHARS: Final[int] = 100
EMBED_BATCH_SIZE: Final[int] = 64
QDRANT_UPSERT_BATCH: Final[int] = 100

# Regex patterns for EU AI Act structural markers
_RE_CHAPTER = re.compile(r"(?i)\bchapter\s+[IVXLCDM\d]+\b")
_RE_SECTION = re.compile(r"(?i)\bsection\s+\d+\b")
_RE_ARTICLE = re.compile(r"(?i)\bart(?:icle)?\.?\s*\d+\b")
_RE_ANNEX = re.compile(r"(?i)\bannex\s+[IVXLCDM]+\b")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_hierarchy(text: str) -> dict[str, str | None]:
    """Scan a text fragment for structural markers."""
    return {
        "chapter": m.group() if (m := _RE_CHAPTER.search(text)) else None,
        "section": m.group() if (m := _RE_SECTION.search(text)) else None,
        "article": m.group() if (m := _RE_ARTICLE.search(text)) else None,
        "annex": m.group() if (m := _RE_ANNEX.search(text)) else None,
    }


def _build_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Build a simple term-frequency sparse vector for keyword retrieval.

    This targets precise Article/Annex number look-ups without relying
    solely on semantic similarity.
    """
    tokens = re.findall(r"\b\w+\b", text.lower())
    freq: dict[int, float] = defaultdict(float)
    for tok in tokens:
        freq[hash(tok) % (2**16)] += 1.0
    indices = sorted(freq.keys())
    values = [freq[i] for i in indices]
    return indices, values


# ── Layout-Aware Chunking ──────────────────────────────────────────────────────

def _layout_aware_chunks(
    elements: list,
    target_size: int = CHUNK_TARGET_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[dict]:
    """Merge Unstructured elements into chunks that respect layout boundaries.

    Rules
    -----
    * Never split in the middle of a ``Title`` or ``Table`` element.
    * Start a new chunk whenever a structural marker (Chapter/Section/Article)
      is detected in a ``Title`` element.
    * Respect ``target_size`` softly — allow overshoot for atomic elements.
    """
    chunks: list[dict] = []
    buffer: list[str] = []
    buffer_len = 0
    current_meta: dict = {}

    def _flush() -> None:
        nonlocal buffer, buffer_len
        if not buffer:
            return
        text = "\n".join(buffer)
        chunks.append({"content": text, **current_meta})
        # keep last element as overlap seed
        if overlap and buffer:
            last = buffer[-1]
            buffer = [last]
            buffer_len = len(last)
        else:
            buffer = []
            buffer_len = 0

    for el in elements:
        el_text = str(el).strip()
        if not el_text:
            continue

        el_type = type(el).__name__
        page = getattr(getattr(el, "metadata", None), "page_number", None)

        # Detect structural break on Title elements
        is_boundary = el_type == "Title" and (
            _RE_CHAPTER.search(el_text)
            or _RE_SECTION.search(el_text)
            or _RE_ARTICLE.search(el_text)
            or _RE_ANNEX.search(el_text)
        )

        if is_boundary and buffer:
            _flush()

        # Update running metadata from hierarchy markers
        hierarchy = _extract_hierarchy(el_text)
        for key in ("chapter", "section", "article", "annex"):
            if hierarchy[key]:
                current_meta[key] = hierarchy[key]
        current_meta["page"] = page
        current_meta["element_type"] = el_type

        buffer.append(el_text)
        buffer_len += len(el_text)

        # Flush if we exceed the soft target (but never mid-Table)
        if buffer_len >= target_size and el_type != "Table":
            _flush()

    _flush()  # remaining buffer
    return chunks


# ── Ingestion Service ──────────────────────────────────────────────────────────

class IngestionService:
    """End-to-end: PDF → vectors → Qdrant."""

    def __init__(self) -> None:
        from langchain_openai import OpenAIEmbeddings
        self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    async def get_embedding(self, text: str) -> list[float]:
        """Generate a dense embedding vector for a query string."""
        return await self._embeddings.aembed_query(text)

    def get_sparse_vector(self, text: str) -> tuple[list[int], list[float]]:
        """Generate a sparse vector for keyword retrieval."""
        return _build_sparse_vector(text)

    # ── PDF Parsing ────────────────────────────────────────────────

    async def process_pdf(
        self,
        file_path: str,
        jurisdiction: Jurisdiction = Jurisdiction.EU,
    ) -> list[LegalChunk]:
        logger.info(f"Partitioning PDF (hi_res): {file_path}")

        # partition_pdf is CPU-bound — run in a thread to avoid blocking the loop
        from unstructured.partition.pdf import partition_pdf
        elements = await asyncio.to_thread(
            partition_pdf,
            filename=file_path,
            strategy="hi_res",
            infer_table_structure=True,
        )
        logger.info(f"Extracted {len(elements)} elements from {os.path.basename(file_path)}")

        raw_chunks = _layout_aware_chunks(elements)
        logger.info(f"Produced {len(raw_chunks)} layout-aware chunks")

        # Build LegalChunk objects (vectors are empty until embedding step)
        chunks: list[LegalChunk] = []
        for raw in raw_chunks:
            chunks.append(
                LegalChunk(
                    content=raw["content"],
                    metadata=LegalMetadata(
                        source=os.path.basename(file_path),
                        jurisdiction=jurisdiction,
                        chapter=raw.get("chapter"),
                        section=raw.get("section"),
                        article=raw.get("article"),
                        annex=raw.get("annex"),
                        page=raw.get("page"),
                        element_type=raw.get("element_type"),
                    ),
                )
            )

        # Generate dense + sparse vectors
        await self._generate_vectors(chunks)
        return chunks

    # ── Embedding Generation ───────────────────────────────────────

    async def _generate_vectors(self, chunks: list[LegalChunk]) -> None:
        """Batch-embed in slices of EMBED_BATCH_SIZE to stay within API limits."""
        logger.info(f"Generating vectors for {len(chunks)} chunks (batch={EMBED_BATCH_SIZE})…")
        contents = [c.content for c in chunks]

        # Dense embeddings — batched via asyncio.gather
        for start in range(0, len(contents), EMBED_BATCH_SIZE):
            batch = contents[start : start + EMBED_BATCH_SIZE]
            vectors = await asyncio.gather(
                *(self._embeddings.aembed_query(text) for text in batch)
            )
            for i, vec in enumerate(vectors):
                chunks[start + i].dense_vector = vec

        # Sparse vectors — cheap, CPU-only
        for chunk in chunks:
            indices, values = _build_sparse_vector(chunk.content)
            chunk.sparse_indices = indices
            chunk.sparse_values = values

        logger.success("Vector generation complete.")

    # ── Qdrant Upload ──────────────────────────────────────────────

    async def upload_to_qdrant(
        self,
        chunks: list[LegalChunk],
        collection_name: str = LEGAL_COLLECTION,
    ) -> None:
        logger.info(f"Uploading {len(chunks)} chunks → Qdrant '{collection_name}'")

        async with qdrant_session.get_client() as client:
            await ensure_collection(client)

            for start in range(0, len(chunks), QDRANT_UPSERT_BATCH):
                batch = chunks[start : start + QDRANT_UPSERT_BATCH]
                from qdrant_client import models as qdrant_models
                points = [
                    qdrant_models.PointStruct(
                        id=chunk.chunk_id,
                        vector={
                            "dense": chunk.dense_vector,
                            "sparse": qdrant_models.SparseVector(
                                indices=chunk.sparse_indices,
                                values=chunk.sparse_values,
                            ),
                        },
                        payload=chunk.metadata.model_dump(mode="json")
                        | {"content": chunk.content},
                    )
                    for chunk in batch
                    if chunk.dense_vector is not None
                ]
                await client.upsert(
                    collection_name=collection_name,
                    points=points,
                )
                logger.debug(f"  ↳ upserted batch {start}–{start + len(batch)}")

        logger.success("Upload complete.")


_ingestion_service: Optional[IngestionService] = None


def get_ingestion_service() -> IngestionService:
    """Lazy singleton — avoids importing OpenAIEmbeddings at module load."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service
