import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from jobsift.search.gateway import ElasticsearchGateway
from jobsift.search.models import JobSearchRequest, SearchDocument
from jobsift.search.service import JobIndexService, JobSearchService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("JOBSIFT_RUN_ELASTICSEARCH_INTEGRATION") != "1",
        reason="set JOBSIFT_RUN_ELASTICSEARCH_INTEGRATION=1 for real Elasticsearch",
    ),
]


def _document(
    source_job_id: str,
    title: str,
    location: str,
    description: str,
    skills: list[str],
    posted_at: datetime,
) -> SearchDocument:
    document_id = source_job_id.encode().hex().ljust(64, "0")[:64]
    return SearchDocument(
        document_id=document_id,
        source="integration-fixture",
        source_job_id=source_job_id,
        content_fingerprint=(source_job_id[0] * 64),
        title=title,
        company="Prairie Systems",
        location=location,
        description=description,
        url=f"https://jobs.example.test/{source_job_id}",
        posted_at=posted_at,
        employment_type="Full-time",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        skills=skills,
        organizations=["prairie systems"],
        entity_locations=[location.casefold()],
        acquired_at=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
        nlp_text_sha256="f" * 64,
        nlp_model="core_web_sm",
        nlp_model_version="3.8.0",
        skill_dictionary_version="skills-v1",
    )


def test_real_elasticsearch_mapping_idempotency_alias_search_and_pagination() -> None:
    suffix = uuid4().hex[:10]
    index_name = f"jobs-v1-it-{suffix}"
    alias = f"jobs-it-{suffix}"
    url = os.getenv("JOBSIFT_ELASTICSEARCH_URL", "http://elasticsearch:9200")
    client = httpx.Client(base_url=url, timeout=20.0)
    gateway = ElasticsearchGateway(client)
    index_service = JobIndexService(gateway, alias=alias)
    search_service = JobSearchService(gateway, alias=alias)
    documents = [
        _document(
            "a-job",
            "Backend Engineer",
            "Chicago, IL",
            "Build Python APIs and search services.",
            ["Python", "Docker"],
            datetime(2026, 11, 10, tzinfo=UTC),
        ),
        _document(
            "b-job",
            "Frontend Engineer",
            "Remote, US",
            "Build JavaScript interfaces.",
            ["JavaScript"],
            datetime(2026, 11, 11, tzinfo=UTC),
        ),
        _document(
            "c-job",
            "Backend Software Engineer",
            "Chicago, IL",
            "Develop Java services.",
            ["Java"],
            datetime(2026, 11, 9, tzinfo=UTC),
        ),
    ]

    try:
        result = index_service.rebuild(index_name, documents)
        assert result.alias_switched is True
        assert gateway.alias_indices(alias) == [index_name]
        assert "javascript" in gateway.analyze(index_name, "JS", analyzer="jobs_search")
        assert "engin" in gateway.analyze(index_name, "Engineers", analyzer="jobs_index")

        index_service.index_documents(documents)
        all_jobs = search_service.search(JobSearchRequest(size=10))
        assert all_jobs.total == 3

        filtered = search_service.search(
            JobSearchRequest(
                query="backend engineer",
                locations=["Chicago, IL"],
                skills=["Python"],
                sources=["integration-fixture"],
                posted_from=datetime(2026, 11, 1, tzinfo=UTC),
            )
        )
        assert [hit.document.source_job_id for hit in filtered.hits] == ["a-job"]
        assert {bucket.key: bucket.count for bucket in filtered.skill_facets} == {
            "Docker": 1,
            "Python": 1,
        }
        assert {bucket.key: bucket.count for bucket in filtered.location_facets} == {
            "Chicago, IL": 1
        }

        first_page = search_service.search(JobSearchRequest(size=1))
        second_page = search_service.search(
            JobSearchRequest(size=1, cursor=first_page.next_cursor)
        )
        assert first_page.hits[0].document.document_id != second_page.hits[0].document.document_id
    finally:
        gateway.delete_index(index_name, ignore_missing=True)
        client.close()
