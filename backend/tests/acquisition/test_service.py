from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jobsift.acquisition.adapters import FixtureSourceAdapter
from jobsift.acquisition.audit import RunManifestStore, RunStage, RunStatus
from jobsift.acquisition.models import AcquisitionMethod, ParserKind, SourceConfig
from jobsift.acquisition.parser import HtmlJobParser
from jobsift.acquisition.service import AcquisitionService
from jobsift.acquisition.storage import RawSnapshotStore


def test_fixture_adapter_requires_fixture_method(
    source_config: SourceConfig,
    fixture_path: Path,
) -> None:
    invalid = source_config.model_copy(update={"method": AcquisitionMethod.HTTP})

    with pytest.raises(ValueError, match="requires method=fixture"):
        FixtureSourceAdapter(invalid, fixture_path)


def test_acquisition_service_forms_an_idempotent_fixture_pipeline(
    tmp_path,
    source_config: SourceConfig,
    fixture_path: Path,
) -> None:
    times = iter(
        [
            datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
            datetime(2026, 11, 11, 12, 0, tzinfo=UTC) + timedelta(milliseconds=25),
            datetime(2026, 11, 11, 12, 1, tzinfo=UTC),
            datetime(2026, 11, 11, 12, 1, tzinfo=UTC) + timedelta(milliseconds=10),
        ]
    )
    manifest_store = RunManifestStore(tmp_path / "manifests")
    service = AcquisitionService(
        RawSnapshotStore(tmp_path / "raw"),
        {ParserKind.HTML: HtmlJobParser()},
        manifest_store=manifest_store,
        clock=times.__next__,
        run_id_factory=iter(["run-1", "run-2"]).__next__,
    )
    adapter = FixtureSourceAdapter(source_config, fixture_path)

    first = service.collect(adapter)
    second = service.collect(adapter)

    assert first.snapshot.created is True
    assert second.snapshot.created is False
    assert first.snapshot.content_sha256 == second.snapshot.content_sha256
    assert len(first.report.jobs) == 2
    assert first.manifest.status is RunStatus.SUCCEEDED
    assert first.manifest.stage is RunStage.COMPLETED
    assert first.manifest.duration_ms == 25.0
    assert first.manifest.fetch_stats.attempts == 1
    assert first.stored_manifest is not None
    assert second.manifest.snapshot_created is False
    assert len(manifest_store.load_all()) == 2


def test_batch_acquisition_isolates_source_failures(
    tmp_path,
    source_config: SourceConfig,
    fixture_path: Path,
) -> None:
    manifest_store = RunManifestStore(tmp_path / "manifests")
    service = AcquisitionService(
        RawSnapshotStore(tmp_path / "raw"),
        {ParserKind.HTML: HtmlJobParser()},
        manifest_store=manifest_store,
        run_id_factory=iter(["working", "broken"]).__next__,
    )
    working = FixtureSourceAdapter(source_config, fixture_path)
    broken_config = source_config.model_copy(update={"source_id": "broken-fixture"})
    broken = FixtureSourceAdapter(broken_config, tmp_path / "missing.html")

    result = service.collect_many([working, broken])

    assert list(result.successes) == ["example-fixture"]
    assert "broken-fixture" in result.failures
    assert result.failures["broken-fixture"].startswith("FileNotFoundError:")
    manifests = manifest_store.load_all()
    failure = next(manifest for manifest in manifests if manifest.status is RunStatus.FAILED)
    assert failure.stage is RunStage.FETCH
    assert failure.error_type == "FileNotFoundError"
    assert failure.fetch_stats.attempts == 1


def test_acquisition_service_rejects_unregistered_parser(
    tmp_path,
    source_config: SourceConfig,
    fixture_path: Path,
) -> None:
    service = AcquisitionService(RawSnapshotStore(tmp_path), {})
    adapter = FixtureSourceAdapter(source_config, fixture_path)

    with pytest.raises(ValueError, match="no parser registered"):
        service.collect(adapter)


def test_acquisition_service_records_compliance_and_parser_drift_failures(
    tmp_path,
    source_config: SourceConfig,
    fixture_path: Path,
) -> None:
    manifest_store = RunManifestStore(tmp_path / "manifests")
    run_ids = iter(["disabled", "drift"])
    service = AcquisitionService(
        RawSnapshotStore(tmp_path / "raw"),
        manifest_store=manifest_store,
        run_id_factory=run_ids.__next__,
    )

    disabled_config = source_config.model_copy(update={"enabled": False})
    with pytest.raises(ValueError, match="is disabled"):
        service.collect(FixtureSourceAdapter(disabled_config, fixture_path))

    drift_selectors = source_config.selectors.model_copy(update={"card": ".missing"})
    drift_config = source_config.model_copy(update={"selectors": drift_selectors})
    with pytest.raises(ValueError, match="produced no cards"):
        service.collect(FixtureSourceAdapter(drift_config, fixture_path))

    manifests = {manifest.run_id: manifest for manifest in manifest_store.load_all()}
    assert manifests["disabled"].stage is RunStage.COMPLIANCE
    assert manifests["disabled"].error_type == "ValueError"
    assert manifests["drift"].stage is RunStage.PARSE
    assert manifests["drift"].error_type == "ParserDriftError"
    assert manifests["drift"].snapshot_sha256 is not None
