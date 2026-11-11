import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from jobsift.demo import build_fixture_documents
from jobsift.evaluation.metrics import evaluate_suite
from jobsift.evaluation.models import RelevanceSuite
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


def test_versioned_judgments_against_real_elasticsearch() -> None:
    suite = RelevanceSuite.model_validate_json(
        (REPOSITORY_ROOT / "config/evaluation/m5-relevance-v1.json").read_text()
    )
    documents = build_fixture_documents(
        REPOSITORY_ROOT / "backend/tests/fixtures/example_jobs.html",
        REPOSITORY_ROOT / "config/sources/example-fixture.json",
        REPOSITORY_ROOT / "config/nlp/skills-v1.json",
        acquired_at=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    )
    suffix = uuid4().hex[:10]
    index_name = f"jobs-v1-m5-it-{suffix}"
    alias = f"jobs-m5-it-{suffix}"
    client = httpx.Client(
        base_url=os.getenv("JOBSIFT_ELASTICSEARCH_URL", "http://elasticsearch:9200"),
        timeout=20.0,
    )
    gateway = ElasticsearchGateway(client)

    try:
        JobIndexService(gateway, alias=alias).rebuild(index_name, documents)
        search = JobSearchService(gateway, alias=alias)
        retrieved = {
            case.case_id: [
                hit.document.source_job_id for hit in search.search(case.request).hits
            ]
            for case in suite.cases
        }
        report = evaluate_suite(suite, retrieved, k=1)

        assert report.mean_precision_at_k == 1.0
        assert report.mean_ndcg_at_k == 1.0
    finally:
        gateway.delete_index(index_name, ignore_missing=True)
        client.close()
