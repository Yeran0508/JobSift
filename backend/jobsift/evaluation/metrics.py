import math
from datetime import datetime
from statistics import fmean

from jobsift.acquisition.audit import AcquisitionRunManifest, RunStatus
from jobsift.evaluation.models import (
    CaseMetrics,
    EvaluationReport,
    PipelineMetricSnapshot,
    RelevanceSuite,
)
from jobsift.processing.models import CleaningReport
from jobsift.search.models import SearchDocument


def precision_at_k(retrieved: list[str], relevance: dict[str, int], k: int) -> float:
    _validate_k(k)
    relevant = sum(relevance.get(document_id, 0) > 0 for document_id in retrieved[:k])
    return relevant / k


def ndcg_at_k(retrieved: list[str], relevance: dict[str, int], k: int) -> float:
    _validate_k(k)
    actual = _dcg([relevance.get(document_id, 0) for document_id in retrieved[:k]])
    ideal = _dcg(sorted(relevance.values(), reverse=True)[:k])
    return actual / ideal if ideal else 0.0


def evaluate_suite(
    suite: RelevanceSuite,
    retrieved_by_case: dict[str, list[str]],
    *,
    k: int,
) -> EvaluationReport:
    case_metrics = [
        CaseMetrics(
            case_id=case.case_id,
            retrieved=retrieved_by_case.get(case.case_id, []),
            precision_at_k=precision_at_k(
                retrieved_by_case.get(case.case_id, []), case.relevance, k
            ),
            ndcg_at_k=ndcg_at_k(
                retrieved_by_case.get(case.case_id, []), case.relevance, k
            ),
        )
        for case in suite.cases
    ]
    return EvaluationReport(
        suite_version=suite.version,
        dataset=suite.dataset,
        k=k,
        cases=case_metrics,
        mean_precision_at_k=fmean(metric.precision_at_k for metric in case_metrics),
        mean_ndcg_at_k=fmean(metric.ndcg_at_k for metric in case_metrics),
    )


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    if not 0.0 <= percentile_value <= 100.0:
        raise ValueError("percentile must be between zero and 100")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def pipeline_snapshot(
    *,
    measured_at: datetime,
    manifests: list[AcquisitionRunManifest],
    cleaning: CleaningReport,
    documents: list[SearchDocument],
    latency_ms: list[float],
) -> PipelineMetricSnapshot:
    succeeded = sum(manifest.status is RunStatus.SUCCEEDED for manifest in manifests)
    latest_acquired_at = max((document.acquired_at for document in documents), default=None)
    freshness = (
        max(0.0, (measured_at - latest_acquired_at).total_seconds())
        if latest_acquired_at
        else None
    )
    return PipelineMetricSnapshot(
        measured_at=measured_at,
        runs_total=len(manifests),
        success_rate=succeeded / len(manifests) if manifests else 0.0,
        missing_rates=cleaning.missingness_after,
        duplicates_removed=sum("duplicate" in item.reason for item in cleaning.dropped),
        indexed_documents=len(documents),
        freshness_seconds=freshness,
        latency_samples=len(latency_ms),
        latency_p50_ms=percentile(latency_ms, 50),
        latency_p95_ms=percentile(latency_ms, 95),
    )


def _dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))


def _validate_k(k: int) -> None:
    if k < 1:
        raise ValueError("k must be at least one")
