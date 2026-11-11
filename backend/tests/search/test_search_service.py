"""Unit tests for Elasticsearch query and index services."""

from datetime import UTC, datetime

from jobsift.search.models import JobSearchRequest, SearchCursor
from jobsift.search.service import JobIndexService, JobSearchService


class FakeGateway:
    def __init__(self, payload=None) -> None:
        self.payload = payload or {}
        self.calls: list[tuple] = []

    def create_job_index(self, index_name):
        self.calls.append(("create", index_name))

    def bulk_index(self, target, documents):
        self.calls.append(("bulk", target, documents))
        return len(documents)

    def switch_alias(self, alias, target):
        self.calls.append(("alias", alias, target))
        return ["jobs-v1-old"], True

    def search(self, alias, body):
        self.calls.append(("search", alias, body))
        return self.payload


def test_index_service_rebuilds_before_switching_alias(search_document_factory) -> None:
    gateway = FakeGateway()
    document = search_document_factory()
    service = JobIndexService(gateway, alias="jobs-current")

    result = service.rebuild("jobs-v1-new", [document])
    indexed_again = service.index_documents([document])
    indexed_to_version = service.index_documents([document], index_or_alias="jobs-v1-new")

    assert gateway.calls[:3] == [
        ("create", "jobs-v1-new"),
        ("bulk", "jobs-v1-new", [document]),
        ("alias", "jobs-current", "jobs-v1-new"),
    ]
    assert result.documents_indexed == 1
    assert result.previous_indices == ["jobs-v1-old"]
    assert result.alias_switched is True
    assert indexed_again == 1
    assert indexed_to_version == 1


def test_query_builder_uses_bm25_filters_facets_and_three_part_cursor() -> None:
    request = JobSearchRequest(
        query="backend engineer",
        locations=["Chicago, IL"],
        skills=["Python"],
        sources=["example-fixture"],
        posted_from=datetime(2026, 10, 1, tzinfo=UTC),
        posted_to=datetime(2026, 11, 11, tzinfo=UTC),
        size=10,
        cursor=SearchCursor(values=[1.5, 1_762_819_200_000, "a" * 64]),
    )

    body = JobSearchService.build_query(request)

    boolean = body["query"]["bool"]
    assert boolean["must"][0]["multi_match"]["fields"] == [
        "title^3",
        "company^2",
        "description",
    ]
    assert {next(iter(item)) for item in boolean["filter"]} == {"terms", "range"}
    assert body["sort"][0] == {"_score": "desc"}
    assert body["sort"][-1] == {"document_id": "asc"}
    assert body["search_after"] == request.cursor.values
    assert body["aggs"]["skills"]["terms"]["field"] == "skills"


def test_query_builder_supports_match_all_and_filter_only() -> None:
    match_all = JobSearchService.build_query(JobSearchRequest())
    filter_only = JobSearchService.build_query(JobSearchRequest(skills=["Python"]))

    assert match_all["query"] == {"match_all": {}}
    assert len(match_all["sort"]) == 2
    assert filter_only["query"] == {"bool": {"filter": [{"terms": {"skills": ["Python"]}}]}}


def test_search_service_parses_hits_cursor_and_facets(search_document_factory) -> None:
    document = search_document_factory()
    payload = {
        "took": 7,
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [
                {
                    "_score": 2.5,
                    "sort": [2.5, 1_762_819_200_000, document.document_id],
                    "_source": document.model_dump(mode="json", exclude_none=True),
                }
            ],
        },
        "aggregations": {
            "skills": {"buckets": [{"key": "Python", "doc_count": 2}]},
            "locations": {"buckets": [{"key": "Chicago, IL", "doc_count": 1}]},
        },
    }
    gateway = FakeGateway(payload)

    result = JobSearchService(gateway).search(JobSearchRequest(query="backend", size=1))

    assert result.total == 2
    assert result.took_ms == 7
    assert result.hits[0].document.title == "Backend Engineer"
    assert result.next_cursor.values[-1] == document.document_id
    assert result.skill_facets[0].count == 2
    assert result.location_facets[0].key == "Chicago, IL"


def test_search_service_reports_timeout_and_failed_shards_as_partial() -> None:
    result = JobSearchService.parse_result(
        {
            "took": 12,
            "timed_out": True,
            "_shards": {"failed": 2},
            "hits": {"total": {"value": 0}, "hits": []},
        },
        requested_size=20,
    )

    assert result.is_partial is True
    assert result.warnings == [
        "Elasticsearch timed out; results may be incomplete.",
        "2 search shard(s) failed; results may be incomplete.",
    ]


def test_result_parser_handles_short_page_numeric_total_and_missing_aggregations(
    search_document_factory,
) -> None:
    document = search_document_factory()
    payload = {
        "hits": {
            "total": 1,
            "hits": [
                {
                    "_score": None,
                    "sort": [1_762_819_200_000, document.document_id],
                    "_source": document.model_dump(mode="json", exclude_none=True),
                }
            ],
        },
        "aggregations": [],
    }

    result = JobSearchService.parse_result(payload, requested_size=2)

    assert result.total == 1
    assert result.next_cursor is None
    assert result.skill_facets == []
    assert result.location_facets == []
