from datetime import datetime, timezone
from uuid import UUID

import pytest

from recallops.services.memory_ranking import (
    calculate_final_score,
    calculate_reliability,
    calculate_same_service_score,
    calculate_semantic_similarity,
    rank_memory_candidates,
    MemoryRankingCandidate,
)


def ranking_candidate(
    *,
    memory_id: str,
    cosine_distance: float,
    success_count: int = 0,
    failure_count: int = 0,
    memory_incident_service: str | None = None,
    created_at: datetime | None = None,
) -> MemoryRankingCandidate:
    return MemoryRankingCandidate(
        memory_id=UUID(memory_id),
        incident_id=None,
        memory_incident_service=memory_incident_service,
        memory_type="resolution",
        summary=memory_id,
        root_cause=None,
        resolution=None,
        status="active",
        embedding_model_id="fake-memory-model",
        embedding_dimension=1024,
        success_count=success_count,
        failure_count=failure_count,
        superseded_by=None,
        superseded_at=None,
        supersession_reason=None,
        cosine_distance=cosine_distance,
        created_at=created_at,
    )


def test_reliability_formula_zero_counts_returns_half() -> None:
    assert calculate_reliability(0, 0) == 0.5


def test_reliability_formula_uses_successes_and_failures() -> None:
    assert calculate_reliability(1, 0) == pytest.approx(0.67, abs=0.01)
    assert calculate_reliability(2, 0) == 0.75
    assert calculate_reliability(0, 1) == pytest.approx(0.33, abs=0.01)
    assert calculate_reliability(0, 2) == 0.25
    assert calculate_reliability(2, 1) == 0.6


def test_reliability_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        calculate_reliability(-1, 0)
    with pytest.raises(ValueError, match="non-negative"):
        calculate_reliability(0, -1)


def test_same_service_score_exact_match() -> None:
    assert calculate_same_service_score("checkout-api", "checkout-api") == 1.0


def test_same_service_score_different_service() -> None:
    assert calculate_same_service_score("checkout-api", "payments-api") == 0.0


def test_same_service_score_missing_linked_incident_service() -> None:
    assert calculate_same_service_score("checkout-api", None) == 0.0


def test_final_score_uses_configured_weights() -> None:
    assert calculate_final_score(0.8, 0.75, 1.0) == pytest.approx(0.81)


def test_semantic_similarity_clamps_float32_negative_cosine_distance() -> None:
    assert calculate_semantic_similarity(-1.192e-7) == 1.0


def test_semantic_similarity_clamps_tiny_negative_similarity() -> None:
    assert calculate_semantic_similarity(1.000000000001) == 0.0


def test_near_identical_vector_search_result_clamps_similarity_to_one() -> None:
    ranked = rank_memory_candidates(
        [
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000221",
                cosine_distance=-1.192e-7,
            )
        ],
        query_service="checkout-api",
        min_similarity=0.60,
        top_k=5,
    )

    assert ranked[0].similarity == 1.0


def test_semantic_similarity_rejects_genuinely_invalid_distances() -> None:
    with pytest.raises(ValueError, match="negative"):
        calculate_semantic_similarity(-0.01)
    with pytest.raises(ValueError, match="valid cosine distance"):
        calculate_semantic_similarity(3.0)


def test_semantic_gate_happens_before_ranking() -> None:
    ranked = rank_memory_candidates(
        [
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000201",
                cosine_distance=0.41,
                success_count=100,
                failure_count=0,
                memory_incident_service="checkout-api",
            ),
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000202",
                cosine_distance=0.39,
            ),
        ],
        query_service="checkout-api",
        min_similarity=0.60,
        top_k=5,
    )

    assert [candidate.candidate.memory_id for candidate in ranked] == [
        UUID("00000000-0000-0000-0000-000000000202")
    ]


def test_candidates_sort_by_final_score_descending() -> None:
    ranked = rank_memory_candidates(
        [
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000203",
                cosine_distance=0.05,
                success_count=0,
                failure_count=1,
            ),
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000204",
                cosine_distance=0.10,
                success_count=10,
                failure_count=0,
                memory_incident_service="checkout-api",
            ),
        ],
        query_service="checkout-api",
        min_similarity=0.60,
        top_k=5,
    )

    assert [candidate.candidate.memory_id for candidate in ranked] == [
        UUID("00000000-0000-0000-0000-000000000204"),
        UUID("00000000-0000-0000-0000-000000000203"),
    ]
    assert [candidate.rank for candidate in ranked] == [1, 2]


def test_tie_breaking_is_deterministic() -> None:
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 2, tzinfo=timezone.utc)
    ranked = rank_memory_candidates(
        [
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000205",
                cosine_distance=0.20,
                created_at=older,
            ),
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000206",
                cosine_distance=0.20,
                created_at=newer,
            ),
        ],
        query_service="checkout-api",
        min_similarity=0.60,
        top_k=5,
    )

    assert [candidate.candidate.memory_id for candidate in ranked] == [
        UUID("00000000-0000-0000-0000-000000000206"),
        UUID("00000000-0000-0000-0000-000000000205"),
    ]


def test_top_k_applies_after_ranking() -> None:
    ranked = rank_memory_candidates(
        [
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000207",
                cosine_distance=0.05,
                success_count=0,
                failure_count=1,
            ),
            ranking_candidate(
                memory_id="00000000-0000-0000-0000-000000000208",
                cosine_distance=0.10,
                success_count=10,
                failure_count=0,
                memory_incident_service="checkout-api",
            ),
        ],
        query_service="checkout-api",
        min_similarity=0.60,
        top_k=1,
    )

    assert [candidate.candidate.memory_id for candidate in ranked] == [
        UUID("00000000-0000-0000-0000-000000000208")
    ]
