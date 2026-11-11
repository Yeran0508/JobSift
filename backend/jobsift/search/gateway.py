import json
import re
from urllib.parse import quote

import httpx

from jobsift.search.mapping import job_index_definition
from jobsift.search.models import SearchDocument

_RESOURCE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,254}$")


class ElasticsearchRequestError(RuntimeError):
    """Raised for a failed Elasticsearch REST request without echoing its body."""


class BulkIndexError(RuntimeError):
    """Raised when a 200 bulk response still contains item-level failures."""


def validate_resource_name(value: str) -> str:
    if not _RESOURCE_NAME.fullmatch(value):
        raise ValueError(f"invalid Elasticsearch resource name: {value!r}")
    return value


class ElasticsearchGateway:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def create_job_index(self, index_name: str) -> None:
        self._request("PUT", self._path(index_name), json_body=job_index_definition())

    def delete_index(self, index_name: str, *, ignore_missing: bool = False) -> bool:
        response = self._client.delete(self._path(index_name))
        if response.status_code == 404 and ignore_missing:
            return False
        self._raise_for_status(response, "DELETE", self._path(index_name))
        return True

    def analyze(self, index_name: str, text: str, *, analyzer: str) -> list[str]:
        payload = self._request(
            "POST",
            f"{self._path(index_name)}/_analyze",
            json_body={"analyzer": analyzer, "text": text},
        )
        return [str(token["token"]) for token in payload["tokens"]]

    def bulk_index(self, index_name: str, documents: list[SearchDocument]) -> int:
        if not documents:
            return 0
        lines: list[str] = []
        for document in documents:
            lines.append(
                json.dumps(
                    {"index": {"_index": index_name, "_id": document.document_id}},
                    separators=(",", ":"),
                )
            )
            lines.append(document.model_dump_json(exclude_none=True))
        response = self._client.post(
            "/_bulk?refresh=wait_for",
            content=("\n".join(lines) + "\n").encode(),
            headers={"Content-Type": "application/x-ndjson"},
        )
        self._raise_for_status(response, "POST", "/_bulk")
        payload = response.json()
        if payload.get("errors"):
            failures = [
                f"{item['index'].get('_id', 'unknown')}:{item['index'].get('status', 'unknown')}"
                for item in payload.get("items", [])
                if item.get("index", {}).get("error")
            ]
            raise BulkIndexError(f"bulk indexing failed for {', '.join(failures)}")
        return len(documents)

    def alias_indices(self, alias: str) -> list[str]:
        path = f"/_alias/{quote(validate_resource_name(alias), safe='')}"
        response = self._client.get(path)
        if response.status_code == 404:
            return []
        self._raise_for_status(response, "GET", path)
        return sorted(response.json())

    def switch_alias(self, alias: str, target_index: str) -> tuple[list[str], bool]:
        alias = validate_resource_name(alias)
        target_index = validate_resource_name(target_index)
        previous = self.alias_indices(alias)
        if previous == [target_index]:
            return previous, False
        actions = [
            {"remove": {"index": index, "alias": alias}}
            for index in previous
        ]
        actions.append({"add": {"index": target_index, "alias": alias}})
        self._request("POST", "/_aliases", json_body={"actions": actions})
        return previous, True

    def search(self, index_or_alias: str, body: dict[str, object]) -> dict[str, object]:
        return self._request(
            "POST",
            f"{self._path(index_or_alias)}/_search",
            json_body=body,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object],
    ) -> dict[str, object]:
        response = self._client.request(method, path, json=json_body)
        self._raise_for_status(response, method, path)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ElasticsearchRequestError(f"{method} {path} returned a non-object response")
        return payload

    @staticmethod
    def _raise_for_status(response: httpx.Response, method: str, path: str) -> None:
        if response.is_error:
            raise ElasticsearchRequestError(
                f"{method} {path} failed with HTTP {response.status_code}"
            )

    @staticmethod
    def _path(resource: str) -> str:
        return f"/{quote(validate_resource_name(resource), safe='')}"
