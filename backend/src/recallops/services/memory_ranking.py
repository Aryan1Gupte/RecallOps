"""Deterministic ranking for semantically recalled memories."""

from dataclasses import dataclass
from datetime import datetime
import math
from uuid import UUID

SEMANTIC_WEIGHT = 0.70
RELIABILITY_WEIGHT = 0.20
SAME_SERVICE_WEIGHT = 0.10
RANKING_FORMULA = (
    "final_score = 0.70 * semantic_similarity "
    "+ 0.20 * reliability + 0.10 * same_service_score"
)


@dataclass(frozen=True)
class MemoryRankingCandidate:
    memory_id: UUID
    incident_id: UUID | None
    memory_incident_service: str | None
    memory_type: str
    summary: str
    root_cause: str | None
    resolution: str | None
    status: str
    embedding_model_id: str
    embedding_dimension: int
    success_count: int
    failure_count: int
    cosine_distance: float
    created_at: datetime | None


@dataclass(frozen=True)
class RankedMemoryCandidate:
    candidate: MemoryRankingCandidate
    rank: int
    similarity: float
    reliability: float
    same_service: bool
    same_service_score: float
    final_score: float
    why_recalled: str


def calculate_reliability(success_count: int, failure_count: int) -> float:
    """Calculate Laplace-smoothed reliability from observed outcomes."""

    if success_count < 0 or failure_count < 0:
        raise ValueError("Memory success and failure counts must be non-negative")
    return (success_count + 1) / (success_count + failure_count + 2)


def calculate_same_service_score(
    query_service: str,
    memory_service: str | None,
) -> float:
    """Return a small deterministic boost for exact linked-service matches."""

    if memory_service is None:
        return 0.0
    return 1.0 if query_service == memory_service else 0.0


def calculate_final_score(
    similarity: float,
    reliability: float,
    same_service_score: float,
) -> float:
    """Combine deterministic ranking components without rounding."""

    _validate_unit_score("semantic similarity", similarity)
    _validate_unit_score("reliability", reliability)
    _validate_unit_score("same-service score", same_service_score)
    return (
        SEMANTIC_WEIGHT * similarity
        + RELIABILITY_WEIGHT * reliability
        + SAME_SERVICE_WEIGHT * same_service_score
    )


def rank_memory_candidates(
    candidates: list[MemoryRankingCandidate],
    *,
    query_service: str,
    min_similarity: float,
    top_k: int,
) -> list[RankedMemoryCandidate]:
    """Apply the semantic gate before deterministic ranking and limiting."""

    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    _validate_unit_score("minimum similarity", min_similarity)

    ranked_candidates: list[RankedMemoryCandidate] = []
    for candidate in candidates:
        similarity = 1 - candidate.cosine_distance
        if similarity < min_similarity:
            continue

        reliability = calculate_reliability(
            candidate.success_count,
            candidate.failure_count,
        )
        same_service_score = calculate_same_service_score(
            query_service,
            candidate.memory_incident_service,
        )
        final_score = calculate_final_score(
            similarity,
            reliability,
            same_service_score,
        )
        ranked_candidates.append(
            RankedMemoryCandidate(
                candidate=candidate,
                rank=0,
                similarity=similarity,
                reliability=reliability,
                same_service=same_service_score == 1.0,
                same_service_score=same_service_score,
                final_score=final_score,
                why_recalled=_build_why_recalled(
                    similarity=similarity,
                    reliability=reliability,
                    success_count=candidate.success_count,
                    failure_count=candidate.failure_count,
                    same_service_score=same_service_score,
                ),
            )
        )

    sorted_candidates = sorted(ranked_candidates, key=_ranking_sort_key)
    limited_candidates = sorted_candidates[:top_k]
    return [
        RankedMemoryCandidate(
            candidate=ranked.candidate,
            rank=index,
            similarity=ranked.similarity,
            reliability=ranked.reliability,
            same_service=ranked.same_service,
            same_service_score=ranked.same_service_score,
            final_score=ranked.final_score,
            why_recalled=ranked.why_recalled,
        )
        for index, ranked in enumerate(limited_candidates, start=1)
    ]


def _build_why_recalled(
    *,
    similarity: float,
    reliability: float,
    success_count: int,
    failure_count: int,
    same_service_score: float,
) -> str:
    base = (
        f"Passed semantic gate with {_format_score(similarity)} similarity; "
        f"reliability {_format_score(reliability)} from "
        f"{success_count} {_pluralize('success', success_count)} and "
        f"{failure_count} {_pluralize('failure', failure_count)}; "
    )
    if same_service_score == 1.0:
        return base + "same service match contributed to final ranking."
    return base + "no same-service boost."


def _ranking_sort_key(ranked: RankedMemoryCandidate) -> tuple[float | str, ...]:
    created_at = ranked.candidate.created_at
    created_timestamp = created_at.timestamp() if created_at is not None else 0.0
    return (
        -ranked.final_score,
        -ranked.similarity,
        -ranked.reliability,
        -created_timestamp,
        str(ranked.candidate.memory_id),
    )


def _validate_unit_score(label: str, value: float) -> None:
    if not math.isfinite(value) or value < 0 or value > 1:
        raise ValueError(f"{label} must be between 0 and 1")


def _format_score(value: float) -> str:
    return f"{value:.2f}"


def _pluralize(label: str, count: int) -> str:
    if count == 1:
        return label
    if label == "success":
        return "successes"
    return f"{label}s"
