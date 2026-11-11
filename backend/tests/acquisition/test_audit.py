from datetime import UTC, datetime, timedelta

import pytest
from jobsift.acquisition.audit import (
    AcquisitionRunManifest,
    RunManifestStore,
    RunStage,
    RunStatus,
    aggregate_source_metrics,
)
from jobsift.acquisition.models import AcquisitionMethod, FetchStats, ParserKind

STARTED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def _manifest(
    run_id: str,
    *,
    status: RunStatus = RunStatus.SUCCEEDED,
    snapshot_created: bool | None = True,
    retries: int = 0,
    error_type: str | None = None,
) -> AcquisitionRunManifest:
    return AcquisitionRunManifest(
        run_id=run_id,
        source="example-source",
        method=AcquisitionMethod.API,
        parser_kind=ParserKind.GREENHOUSE,
        status=status,
        started_at=STARTED_AT,
        finished_at=STARTED_AT + timedelta(seconds=1),
        duration_ms=1000,
        stage=RunStage.COMPLETED if status is RunStatus.SUCCEEDED else RunStage.PARSE,
        fetch_stats=FetchStats(
            attempts=retries + 1,
            retries=retries,
            rate_limit_wait_seconds=0.5,
            backoff_seconds=float(retries),
        ),
        snapshot_sha256="a" * 64,
        snapshot_created=snapshot_created,
        jobs_parsed=2 if status is RunStatus.SUCCEEDED else 0,
        missing_rates={"salary_raw": 1.0} if status is RunStatus.SUCCEEDED else {},
        error_type=error_type,
        error_message="safe failure" if error_type else None,
    )


def test_manifest_store_round_trips_without_overwriting(tmp_path) -> None:
    store = RunManifestStore(tmp_path)
    manifest = _manifest("run-1")

    stored = store.save(manifest)

    assert stored.path.name == "run-1.json"
    assert store.load_all() == [manifest]
    with pytest.raises(FileExistsError):
        store.save(manifest)


def test_manifest_store_loads_empty_root(tmp_path) -> None:
    assert RunManifestStore(tmp_path / "missing").load_all() == []


def test_source_metrics_aggregate_success_failure_and_drift() -> None:
    manifests = [
        _manifest("run-1", retries=1),
        _manifest("run-2", snapshot_created=False),
        _manifest(
            "run-3",
            status=RunStatus.FAILED,
            snapshot_created=None,
            retries=2,
            error_type="ParserDriftError",
        ),
    ]

    metrics = aggregate_source_metrics(manifests)["example-source"]

    assert metrics.runs_total == 3
    assert metrics.succeeded == 2
    assert metrics.failed == 1
    assert metrics.jobs_parsed == 4
    assert metrics.snapshots_created == 1
    assert metrics.snapshots_reused == 1
    assert metrics.attempts == 6
    assert metrics.retries == 3
    assert metrics.rate_limit_wait_seconds == 1.5
    assert metrics.backoff_seconds == 3.0
    assert metrics.parser_drift_failures == 1
    assert metrics.latest_missing_rates == {"salary_raw": 1.0}


def test_source_metrics_empty_input_is_empty() -> None:
    assert aggregate_source_metrics([]) == {}
