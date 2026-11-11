from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from jobsift.acquisition.adapters import SourceAdapter
from jobsift.acquisition.audit import (
    AcquisitionRunManifest,
    RunManifestStore,
    RunStage,
    RunStatus,
    StoredManifest,
)
from jobsift.acquisition.models import ParseReport, ParserKind
from jobsift.acquisition.parser import GreenhouseJobParser, HtmlJobParser, JobContentParser
from jobsift.acquisition.storage import RawSnapshotStore, StoredSnapshot


@dataclass(frozen=True)
class AcquisitionRun:
    snapshot: StoredSnapshot
    report: ParseReport
    manifest: AcquisitionRunManifest
    stored_manifest: StoredManifest | None


@dataclass
class BatchAcquisitionResult:
    successes: dict[str, AcquisitionRun] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


class AcquisitionService:
    def __init__(
        self,
        snapshot_store: RawSnapshotStore,
        parsers: Mapping[ParserKind, JobContentParser] | None = None,
        manifest_store: RunManifestStore | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        run_id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._snapshot_store = snapshot_store
        self._manifest_store = manifest_store
        self._clock = clock
        self._run_id_factory = run_id_factory
        self._parsers = (
            parsers
            if parsers is not None
            else {
                ParserKind.HTML: HtmlJobParser(),
                ParserKind.GREENHOUSE: GreenhouseJobParser(),
            }
        )

    def collect(self, adapter: SourceAdapter) -> AcquisitionRun:
        started_at = self._clock()
        run_id = self._run_id_factory()
        stage = RunStage.COMPLIANCE
        snapshot: StoredSnapshot | None = None
        try:
            adapter.config.assert_collection_allowed()
            stage = RunStage.FETCH
            page = adapter.fetch()
            stage = RunStage.SNAPSHOT
            snapshot = self._snapshot_store.save(
                source_id=adapter.config.source_id,
                source_url=page.source_url,
                content=page.content,
                content_type=page.content_type,
                fetched_at=page.fetched_at,
            )
            stage = RunStage.PARSE
            parser = self._parsers.get(adapter.config.parser_kind)
            if parser is None:
                raise ValueError(f"no parser registered for {adapter.config.parser_kind}")
            report = parser.parse(page.content, adapter.config, page.fetched_at)
        except Exception as error:
            manifest = self._failure_manifest(
                adapter=adapter,
                run_id=run_id,
                started_at=started_at,
                stage=stage,
                snapshot=snapshot,
                error=error,
            )
            self._store_manifest(manifest)
            raise

        finished_at = self._clock()
        manifest = AcquisitionRunManifest(
            run_id=run_id,
            source=adapter.config.source_id,
            method=adapter.config.method,
            parser_kind=adapter.config.parser_kind,
            status=RunStatus.SUCCEEDED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=self._duration_ms(started_at, finished_at),
            stage=RunStage.COMPLETED,
            fetch_stats=page.fetch_stats,
            snapshot_sha256=snapshot.content_sha256,
            snapshot_created=snapshot.created,
            jobs_parsed=len(report.jobs),
            missing_rates=report.missing_rates,
        )
        stored_manifest = self._store_manifest(manifest)
        return AcquisitionRun(
            snapshot=snapshot,
            report=report,
            manifest=manifest,
            stored_manifest=stored_manifest,
        )

    def collect_many(self, adapters: list[SourceAdapter]) -> BatchAcquisitionResult:
        result = BatchAcquisitionResult()
        for adapter in adapters:
            try:
                result.successes[adapter.config.source_id] = self.collect(adapter)
            except Exception as error:
                result.failures[adapter.config.source_id] = f"{type(error).__name__}: {error}"
        return result

    def _failure_manifest(
        self,
        *,
        adapter: SourceAdapter,
        run_id: str,
        started_at: datetime,
        stage: RunStage,
        snapshot: StoredSnapshot | None,
        error: Exception,
    ) -> AcquisitionRunManifest:
        finished_at = self._clock()
        message = " ".join(str(error).split())[:200] or type(error).__name__
        return AcquisitionRunManifest(
            run_id=run_id,
            source=adapter.config.source_id,
            method=adapter.config.method,
            parser_kind=adapter.config.parser_kind,
            status=RunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=self._duration_ms(started_at, finished_at),
            stage=stage,
            fetch_stats=adapter.last_stats,
            snapshot_sha256=snapshot.content_sha256 if snapshot else None,
            snapshot_created=snapshot.created if snapshot else None,
            error_type=type(error).__name__,
            error_message=message,
        )

    def _store_manifest(self, manifest: AcquisitionRunManifest) -> StoredManifest | None:
        return self._manifest_store.save(manifest) if self._manifest_store else None

    @staticmethod
    def _duration_ms(started_at: datetime, finished_at: datetime) -> float:
        return max(0.0, (finished_at - started_at).total_seconds() * 1000)
