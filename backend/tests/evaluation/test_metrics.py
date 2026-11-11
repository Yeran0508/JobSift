from datetime import UTC, datetime, timedelta

import pytest
from jobsift.acquisition.audit import AcquisitionRunManifest, RunStage, RunStatus
from jobsift.acquisition.models import AcquisitionMethod, FetchStats, ParserKind
from jobsift.evaluation.metrics import (
    evaluate_suite,
    ndcg_at_k,
    percentile,
    pipeline_snapshot,
    precision_at_k,
)
from jobsift.evaluation.models import RelevanceCase, RelevanceSuite
from jobsift.processing.models import CleaningReport


def test_precision_and_ndcg_reward_relevant_results_and_rank() -> None:
    relevance = {"a": 3, "b": 1, "c": 0}

    assert precision_at_k(["a", "c"], relevance, 2) == 0.5
    assert ndcg_at_k(["a", "b"], relevance, 2) == pytest.approx(1.0)
    assert ndcg_at_k(["b", "a"], relevance, 2) < 1.0
    assert ndcg_at_k(["unknown"], {"a": 0}, 1) == 0.0
    with pytest.raises(ValueError, match="at least one"):
        precision_at_k([], relevance, 0)


def test_suite_is_versioned_and_aggregates_case_metrics() -> None:
    suite = RelevanceSuite.model_validate(
        {
            "version": "v1",
            "dataset": "fixture-v1",
            "judged_at": "2026-11-11T00:00:00Z",
            "grade_scale": {0: "no", 3: "high"},
            "cases": [
                {
                    "case_id": "backend",
                    "request": {"query": "backend"},
                    "relevance": {"a": 3, "b": 0},
                    "rationale": "title match",
                }
            ],
        }
    )

    report = evaluate_suite(suite, {"backend": ["a"]}, k=1)

    assert report.suite_version == "v1"
    assert report.mean_precision_at_k == 1.0
    assert report.mean_ndcg_at_k == 1.0
    with pytest.raises(ValueError, match="between zero and three"):
        suite.cases[0].model_copy(update={"relevance": {"a": 4}}).validate_relevance()
    with pytest.raises(ValueError, match="at least one judgment"):
        RelevanceCase(
            case_id="empty-case",
            request={"query": "nothing"},
            relevance={},
            rationale="invalid on purpose",
        )


def test_percentile_interpolates_and_validates_bounds() -> None:
    assert percentile([], 50) is None
    assert percentile([10], 50) == 10
    assert percentile([10, 20, 30, 40], 50) == 25
    assert percentile([10, 20, 30, 40], 95) == pytest.approx(38.5)
    with pytest.raises(ValueError, match="between zero and 100"):
        percentile([1], 101)


def test_pipeline_snapshot_reports_success_missing_duplicates_freshness_and_latency(
    search_document_factory,
) -> None:
    now = datetime(2026, 11, 11, 12, 5, tzinfo=UTC)
    manifest = AcquisitionRunManifest(
        run_id="run-1",
        source="fixture",
        method=AcquisitionMethod.FIXTURE,
        parser_kind=ParserKind.HTML,
        status=RunStatus.SUCCEEDED,
        started_at=now,
        finished_at=now,
        duration_ms=10,
        stage=RunStage.COMPLETED,
        fetch_stats=FetchStats(attempts=1),
    )
    cleaning = CleaningReport(
        input_rows=2,
        output_rows=1,
        missingness_before={},
        missingness_after={"salary_min": 0.5},
        decisions=[],
        dropped=[
            {"source": "fixture", "source_job_id": "duplicate", "reason": "duplicate ID"}
        ],
        jobs=[],
    )
    document = search_document_factory().model_copy(
        update={"acquired_at": now - timedelta(seconds=300)}
    )

    snapshot = pipeline_snapshot(
        measured_at=now,
        manifests=[manifest],
        cleaning=cleaning,
        documents=[document],
        latency_ms=[10, 20, 30, 40],
    )

    assert snapshot.success_rate == 1.0
    assert snapshot.duplicates_removed == 1
    assert snapshot.freshness_seconds == 300
    assert snapshot.latency_p50_ms == 25
    assert snapshot.latency_p95_ms == pytest.approx(38.5)
