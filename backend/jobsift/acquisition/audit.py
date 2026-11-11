from collections import defaultdict
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from jobsift.acquisition.models import AcquisitionMethod, FetchStats, ParserKind


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunStage(StrEnum):
    COMPLIANCE = "compliance"
    FETCH = "fetch"
    SNAPSHOT = "snapshot"
    PARSE = "parse"
    COMPLETED = "completed"


class AcquisitionRunManifest(BaseModel):
    run_id: str = Field(min_length=1)
    source: str
    method: AcquisitionMethod
    parser_kind: ParserKind
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    duration_ms: float = Field(ge=0.0)
    stage: RunStage
    fetch_stats: FetchStats
    snapshot_sha256: str | None = None
    snapshot_created: bool | None = None
    jobs_parsed: int = Field(default=0, ge=0)
    missing_rates: dict[str, float] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


class StoredManifest(BaseModel):
    manifest: AcquisitionRunManifest
    path: Path


class SourceRunMetrics(BaseModel):
    source: str
    runs_total: int
    succeeded: int
    failed: int
    jobs_parsed: int
    snapshots_created: int
    snapshots_reused: int
    attempts: int
    retries: int
    rate_limit_wait_seconds: float
    backoff_seconds: float
    parser_drift_failures: int
    latest_missing_rates: dict[str, float]


class RunManifestStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, manifest: AcquisitionRunManifest) -> StoredManifest:
        source_directory = self._root / manifest.source
        source_directory.mkdir(parents=True, exist_ok=True)
        path = source_directory / f"{manifest.run_id}.json"
        payload = manifest.model_dump_json(indent=2).encode()
        with path.open("xb") as stream:
            stream.write(payload)
        return StoredManifest(manifest=manifest, path=path)

    def load_all(self) -> list[AcquisitionRunManifest]:
        manifests: list[AcquisitionRunManifest] = []
        if not self._root.exists():
            return manifests
        for path in sorted(self._root.glob("*/*.json")):
            manifests.append(AcquisitionRunManifest.model_validate_json(path.read_text()))
        return manifests


def aggregate_source_metrics(
    manifests: list[AcquisitionRunManifest],
) -> dict[str, SourceRunMetrics]:
    grouped: dict[str, list[AcquisitionRunManifest]] = defaultdict(list)
    for manifest in manifests:
        grouped[manifest.source].append(manifest)

    metrics: dict[str, SourceRunMetrics] = {}
    for source, source_manifests in grouped.items():
        ordered = sorted(source_manifests, key=lambda manifest: manifest.finished_at)
        successful = [manifest for manifest in ordered if manifest.status is RunStatus.SUCCEEDED]
        metrics[source] = SourceRunMetrics(
            source=source,
            runs_total=len(ordered),
            succeeded=len(successful),
            failed=len(ordered) - len(successful),
            jobs_parsed=sum(manifest.jobs_parsed for manifest in successful),
            snapshots_created=sum(manifest.snapshot_created is True for manifest in successful),
            snapshots_reused=sum(manifest.snapshot_created is False for manifest in successful),
            attempts=sum(manifest.fetch_stats.attempts for manifest in ordered),
            retries=sum(manifest.fetch_stats.retries for manifest in ordered),
            rate_limit_wait_seconds=sum(
                manifest.fetch_stats.rate_limit_wait_seconds for manifest in ordered
            ),
            backoff_seconds=sum(manifest.fetch_stats.backoff_seconds for manifest in ordered),
            parser_drift_failures=sum(
                manifest.error_type == "ParserDriftError" for manifest in ordered
            ),
            latest_missing_rates=successful[-1].missing_rates if successful else {},
        )
    return metrics
