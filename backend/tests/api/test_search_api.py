from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from jobsift.api.search import encode_cursor, get_search_service
from jobsift.main import create_app
from jobsift.search.gateway import ElasticsearchRequestError
from jobsift.search.models import (
    FacetBucket,
    JobSearchResult,
    SearchCursor,
    SearchHit,
)


class StubSearchService:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.request = None

    def search(self, request):
        self.request = request
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def client_and_override():
    app = create_app()
    with TestClient(app) as client:
        yield client, app


def test_search_endpoint_validates_filters_and_returns_stable_schema(
    client_and_override, search_document_factory
) -> None:
    client, app = client_and_override
    document = search_document_factory()
    stub = StubSearchService(
        JobSearchResult(
            total=1,
            took_ms=7,
            hits=[
                SearchHit(
                    score=2.4,
                    sort=[2.4, 1_762_752_000_000, document.document_id],
                    document=document,
                )
            ],
            next_cursor=SearchCursor(values=[2.4, 1_762_752_000_000, document.document_id]),
            skill_facets=[FacetBucket(key="Python", count=1)],
            location_facets=[FacetBucket(key="Chicago, IL", count=1)],
            is_partial=True,
            warnings=["1 search shard(s) failed; results may be incomplete."],
        )
    )
    app.dependency_overrides[get_search_service] = lambda: stub

    response = client.get(
        "/api/v1/jobs",
        params=[
            ("q", "backend"),
            ("location", "Chicago, IL"),
            ("skill", "Python"),
            ("source", "example-fixture"),
            ("posted_from", "2026-11-01T00:00:00Z"),
            ("size", "1"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["title"] == "Backend Engineer"
    assert payload["facets"]["skills"] == [{"key": "Python", "count": 1}]
    assert payload["meta"]["is_partial"] is True
    assert payload["next_cursor"]
    assert stub.request.query == "backend"
    assert stub.request.locations == ["Chicago, IL"]
    assert stub.request.posted_from == datetime(2026, 11, 1, tzinfo=UTC)

    follow_up = client.get("/api/v1/jobs", params={"cursor": payload["next_cursor"]})
    assert follow_up.status_code == 200
    assert stub.request.cursor.values == [2.4, 1_762_752_000_000, document.document_id]


def test_search_endpoint_rejects_bad_cursor_and_date_range(client_and_override) -> None:
    client, _ = client_and_override

    bad_cursor = client.get("/api/v1/jobs", params={"cursor": "%%%"})
    bad_range = client.get(
        "/api/v1/jobs",
        params={
            "posted_from": "2026-11-11T00:00:00Z",
            "posted_to": "2026-11-10T00:00:00Z",
        },
    )

    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["detail"]["code"] == "invalid_cursor"
    assert bad_range.status_code == 422
    assert bad_range.json()["detail"]["code"] == "invalid_search"


def test_search_endpoint_returns_safe_retryable_dependency_error(client_and_override) -> None:
    client, app = client_and_override
    stub = StubSearchService(error=ElasticsearchRequestError("secret upstream body"))
    app.dependency_overrides[get_search_service] = lambda: stub

    response = client.get("/api/v1/jobs")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "search_unavailable",
        "message": "Job search is temporarily unavailable. Please retry shortly.",
        "retryable": True,
    }
    assert "secret" not in response.text


def test_web_client_and_assets_are_served(client_and_override) -> None:
    client, _ = client_and_override

    page = client.get("/")
    script = client.get("/assets/app.js")
    stylesheet = client.get("/assets/styles.css")

    assert page.status_code == 200
    assert "Less scrolling" in page.text
    assert "state-loading" in page.text
    assert "partial-banner" in page.text
    assert script.status_code == 200
    assert "/api/v1/jobs" in script.text
    assert stylesheet.status_code == 200
    assert "@media (max-width: 760px)" in stylesheet.text


def test_default_dependency_and_empty_cursor_use_application_state(client_and_override) -> None:
    _, app = client_and_override

    request = type("Request", (), {"app": app})()

    assert get_search_service(request) is app.state.search_service
    assert encode_cursor(None) is None
