import json

import httpx
import pytest
from jobsift.search.gateway import (
    BulkIndexError,
    ElasticsearchGateway,
    ElasticsearchRequestError,
    validate_resource_name,
)


def _gateway(handler):
    client = httpx.Client(
        base_url="http://elasticsearch.test:9200",
        transport=httpx.MockTransport(handler),
    )
    return ElasticsearchGateway(client)


def test_gateway_creates_analyzes_bulk_indexes_and_searches(search_document_factory) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/jobs-v1-test/_analyze":
            return httpx.Response(200, json={"tokens": [{"token": "engin"}]})
        if request.url.path == "/_bulk":
            return httpx.Response(200, json={"errors": False, "items": []})
        if request.url.path == "/jobs-current/_search":
            return httpx.Response(200, json={"hits": {"total": {"value": 0}, "hits": []}})
        return httpx.Response(200, json={"acknowledged": True})

    gateway = _gateway(handler)
    document = search_document_factory()

    gateway.create_job_index("jobs-v1-test")
    tokens = gateway.analyze("jobs-v1-test", "Engineers", analyzer="jobs_search")
    indexed = gateway.bulk_index("jobs-v1-test", [document])
    payload = gateway.search("jobs-current", {"query": {"match_all": {}}})

    assert tokens == ["engin"]
    assert indexed == 1
    assert payload["hits"]["total"]["value"] == 0
    bulk_request = next(request for request in requests if request.url.path == "/_bulk")
    lines = bulk_request.content.decode().splitlines()
    assert json.loads(lines[0])["index"]["_id"] == document.document_id
    assert json.loads(lines[1])["title"] == "Backend Engineer"
    assert bulk_request.url.params["refresh"] == "wait_for"
    assert gateway.bulk_index("jobs-v1-test", []) == 0


def test_gateway_reports_bulk_item_failures_without_document_bodies(
    search_document_factory,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "errors": True,
                "items": [
                    {"index": {"_id": "bad-id", "status": 400, "error": {"type": "x"}}},
                    {"index": {"_id": "ok-id", "status": 201}},
                ],
            },
        )

    with pytest.raises(BulkIndexError, match="bad-id:400"):
        _gateway(handler).bulk_index("jobs-v1-test", [search_document_factory()])


def test_gateway_switches_alias_atomically_and_detects_noop() -> None:
    alias_reads = 0
    alias_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal alias_reads
        if request.method == "GET":
            alias_reads += 1
            indices = {"jobs-v1-old": {}} if alias_reads == 1 else {"jobs-v1-new": {}}
            return httpx.Response(200, json=indices)
        alias_payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"acknowledged": True})

    gateway = _gateway(handler)

    previous, switched = gateway.switch_alias("jobs-current", "jobs-v1-new")
    current, second_switched = gateway.switch_alias("jobs-current", "jobs-v1-new")

    assert previous == ["jobs-v1-old"]
    assert switched is True
    assert alias_payloads == [
        {
            "actions": [
                {"remove": {"index": "jobs-v1-old", "alias": "jobs-current"}},
                {"add": {"index": "jobs-v1-new", "alias": "jobs-current"}},
            ]
        }
    ]
    assert current == ["jobs-v1-new"]
    assert second_switched is False


def test_gateway_handles_missing_alias_and_targeted_delete() -> None:
    delete_reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal delete_reads
        if request.method == "GET":
            return httpx.Response(404, json={"error": "missing"})
        delete_reads += 1
        return httpx.Response(404 if delete_reads == 1 else 200, json={"acknowledged": True})

    gateway = _gateway(handler)

    assert gateway.alias_indices("jobs-current") == []
    assert gateway.delete_index("jobs-v1-test", ignore_missing=True) is False
    assert gateway.delete_index("jobs-v1-test") is True


def test_gateway_sanitizes_http_and_shape_errors() -> None:
    def http_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"secret": "must not appear"})

    def shape_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with pytest.raises(ElasticsearchRequestError, match="HTTP 500") as captured:
        _gateway(http_error).create_job_index("jobs-v1-test")
    assert "secret" not in str(captured.value)
    with pytest.raises(ElasticsearchRequestError, match="non-object"):
        _gateway(shape_error).search("jobs-current", {})
    with pytest.raises(ValueError, match="invalid Elasticsearch"):
        validate_resource_name("INVALID NAME")
