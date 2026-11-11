from pathlib import Path

import pytest
from jobsift.acquisition.adapters import FixtureSourceAdapter
from jobsift.acquisition.models import AcquisitionMethod, SourceConfig
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
    service = AcquisitionService(RawSnapshotStore(tmp_path), HtmlJobParser())
    adapter = FixtureSourceAdapter(source_config, fixture_path)

    first = service.collect(adapter)
    second = service.collect(adapter)

    assert first.snapshot.created is True
    assert second.snapshot.created is False
    assert first.snapshot.content_sha256 == second.snapshot.content_sha256
    assert len(first.report.jobs) == 2


def test_batch_acquisition_isolates_source_failures(
    tmp_path,
    source_config: SourceConfig,
    fixture_path: Path,
) -> None:
    service = AcquisitionService(RawSnapshotStore(tmp_path), HtmlJobParser())
    working = FixtureSourceAdapter(source_config, fixture_path)
    broken_config = source_config.model_copy(update={"source_id": "broken-fixture"})
    broken = FixtureSourceAdapter(broken_config, tmp_path / "missing.html")

    result = service.collect_many([working, broken])

    assert list(result.successes) == ["example-fixture"]
    assert "broken-fixture" in result.failures
    assert result.failures["broken-fixture"].startswith("FileNotFoundError:")
