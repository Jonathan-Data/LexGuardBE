"""
Async Qdrant search interface for the Legal RAG layer.

Hybrid search (dense + sparse) with exact-match metadata filtering.

Filter keys are arbitrary payload fields (``article``, ``annex``,
``version_date``, ``regulation_id``, ``jurisdiction`` …). Each value may
be a single string (exact match) or a list of strings (OR / MatchAny).

Note
----
Earlier revisions used ``MatchText`` which performs full-text search and
silently fails on payload fields without a text index — that is why exact
look-ups for ``"Art. 6"`` or ``"2026-05-08"`` returned empty results in
production. This module now uses ``MatchValue`` / ``MatchAny`` so filters
are deterministic regardless of payload-index configuration.
"""

from __future__ import annotations

from typing import Optional, Union

from loguru import logger
from qdrant_client import models

from app.db.session import LEGAL_COLLECTION, qdrant_session

FilterValue = Union[str, list[str]]


def _build_filter(filters: dict[str, FilterValue]) -> models.Filter:
    """Translate a flat ``{key: value | [values]}`` dict into a Qdrant
    ``must``-conjunction of exact-match conditions."""
    conditions: list[models.FieldCondition] = []
    for key, value in filters.items():
        if isinstance(value, (list, tuple, set)):
            match: models.Match = models.MatchAny(any=list(value))
        else:
            match = models.MatchValue(value=value)
        conditions.append(models.FieldCondition(key=key, match=match))
    return models.Filter(must=conditions)


async def search_legal_docs(
    query_vector: list[float],
    *,
    sparse_indices: Optional[list[int]] = None,
    sparse_values: Optional[list[float]] = None,
    limit: int = 5,
    filters: Optional[dict[str, FilterValue]] = None,
    collection_name: str = LEGAL_COLLECTION,
) -> list[models.ScoredPoint]:
    """Hybrid search: dense + optional sparse + exact metadata filters.

    Parameters
    ----------
    query_vector
        1536-dim dense embedding for semantic ranking.
    sparse_indices, sparse_values
        Optional sparse term vector for keyword recall (Article numbers,
        Annex labels, defined terms).
    filters
        ``{"annex": "Annex III"}`` for a single value, or
        ``{"article": ["Art. 6", "Art. 6(3)"]}`` for OR-semantics.
        Combined fields are AND-conjoined.
    """
    qdrant_filter = _build_filter(filters) if filters else None

    async with qdrant_session.get_client() as client:
        prefetch: list[models.Prefetch] = [
            models.Prefetch(
                query=query_vector,
                using="dense",
                limit=limit * 2,
                filter=qdrant_filter,
            ),
        ]

        if sparse_indices and sparse_values:
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_indices,
                        values=sparse_values,
                    ),
                    using="sparse",
                    limit=limit * 2,
                    filter=qdrant_filter,
                )
            )

        results = await client.query_points(
            collection_name=collection_name,
            prefetch=prefetch,
            query=query_vector,
            using="dense",
            limit=limit,
            query_filter=qdrant_filter,
        )

        logger.debug(
            f"search_legal_docs filters={filters} → {len(results.points)} hits"
        )
        return results.points
