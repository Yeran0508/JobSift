import httpx
from jobsift.acquisition.adapters import HttpSourceAdapter, RateLimiter
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
    service = AcquisitionService(RawSnapshotStore(tmp_path))

    first = service.collect(adapter)
    second = service.collect(adapter)

    assert first.snapshot.created is True
    assert second.snapshot.created is False
    assert first.snapshot.content_path.suffix == ".json"
    assert first.snapshot.metadata_path.name.endswith(".metadata.json")
    assert len(first.report.jobs) == 2
