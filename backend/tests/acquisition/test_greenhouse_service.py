import httpx
from jobsift.acquisition.adapters import HttpSourceAdapter, RateLimiter
from jobsift.acquisition.audit import RunManifestStore, RunStatus
from jobsift.acquisition.models import SourceConfig
from jobsift.acquisition.service import AcquisitionService
from jobsift.acquisition.storage import RawSnapshotStore


def test_greenhouse_api_forms_an_idempotent_json_pipeline(
    tmp_path,
    greenhouse_config: SourceConfig,
    greenhouse_fixture_path,
) -> None:
    content = greenhouse_fixture_path.read_bytes()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = HttpSourceAdapter(
        greenhouse_config,
        client=client,
        rate_limiter=RateLimiter(120, sleeper=lambda _seconds: None),
    )
    manifest_store = RunManifestStore(tmp_path / "manifests")
    service = AcquisitionService(
        RawSnapshotStore(tmp_path / "raw"),
        manifest_store=manifest_store,
        run_id_factory=iter(["run-1", "run-2"]).__next__,
    )

    first = service.collect(adapter)
    second = service.collect(adapter)

    assert first.snapshot.created is True
    assert second.snapshot.created is False
    assert first.snapshot.content_path.suffix == ".json"
    assert first.snapshot.metadata_path.name.endswith(".metadata.json")
    assert len(first.report.jobs) == 2
    assert first.manifest.status is RunStatus.SUCCEEDED
    assert first.manifest.jobs_parsed == 2
    assert first.stored_manifest is not None
    assert len(manifest_store.load_all()) == 2
