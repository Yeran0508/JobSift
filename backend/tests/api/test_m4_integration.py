import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from jobsift.api.search import get_search_service
from jobsift.demo import build_fixture_documents
from jobsift.main import create_app
from jobsift.search.gateway import ElasticsearchGateway
from jobsift.search.service import JobIndexService, JobSearchService

REPOSITORY_ROOT = Path(__file__).parents[3]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("JOBSIFT_RUN_ELASTICSEARCH_INTEGRATION") != "1",
        reason="set JOBSIFT_RUN_ELASTICSEARCH_INTEGRATION=1 for real Elasticsearch",
    ),
]


def test_fixture_to_real_elasticsearch_to_http_api_and_visible_client() -> None:
    suffix = uuid4().hex[:10]
    index_name = f"jobs-v1-m4-it-{suffix}"
    alias = f"jobs-m4-it-{suffix}"
    documents = build_fixture_documents(
        REPOSITORY_ROOT / "backend/tests/fixtures/example_jobs.html",
        REPOSITORY_ROOT / "config/sources/example-fixture.json",
        REPOSITORY_ROOT / "config/nlp/skills-v1.json",
        acquired_at=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    )
    elasticsearch = httpx.Client(
        base_url=os.getenv("JOBSIFT_ELASTICSEARCH_URL", "http://elasticsearch:9200"),
        timeout=20.0,
    )
    gateway = ElasticsearchGateway(elasticsearch)
    app = create_app()
    app.dependency_overrides[get_search_service] = lambda: JobSearchService(
        gateway, alias=alias
    )

    try:
        JobIndexService(gateway, alias=alias).rebuild(index_name, documents)
        with TestClient(app) as browser:
            response = browser.get(
                "/api/v1/jobs",
                params={"q": "backend", "skill": "Python"},
            )
            page = browser.get("/")

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["results"][0]["title"] == "Backend Engineer"
        assert payload["results"][0]["source"] == "example-fixture"
        assert payload["facets"]["skills"] == [{"key": "Python", "count": 1}]
        assert payload["meta"]["is_partial"] is False
        assert page.status_code == 200
        assert "Less scrolling" in page.text
    finally:
        gateway.delete_index(index_name, ignore_missing=True)
        elasticsearch.close()
