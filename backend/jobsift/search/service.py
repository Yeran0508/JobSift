from jobsift.search.gateway import ElasticsearchGateway, validate_resource_name
from jobsift.search.models import (
    FacetBucket,
    IndexBuildResult,
    JobSearchRequest,
    JobSearchResult,
    SearchCursor,
    SearchDocument,
    SearchHit,
)


class JobIndexService:
    def __init__(self, gateway: ElasticsearchGateway, *, alias: str = "jobs-current") -> None:
        self._gateway = gateway
        self._alias = validate_resource_name(alias)

    def rebuild(
        self,
        index_name: str,
        documents: list[SearchDocument],
    ) -> IndexBuildResult:
        index_name = validate_resource_name(index_name)
        self._gateway.create_job_index(index_name)
        indexed = self._gateway.bulk_index(index_name, documents)
        previous, switched = self._gateway.switch_alias(self._alias, index_name)
        return IndexBuildResult(
            index_name=index_name,
            documents_indexed=indexed,
            alias=self._alias,
            previous_indices=previous,
            alias_switched=switched,
        )

    def index_documents(
        self,
        documents: list[SearchDocument],
        *,
        index_or_alias: str | None = None,
    ) -> int:
        target = validate_resource_name(index_or_alias or self._alias)
        return self._gateway.bulk_index(target, documents)


class JobSearchService:
    def __init__(self, gateway: ElasticsearchGateway, *, alias: str = "jobs-current") -> None:
        self._gateway = gateway
        self._alias = validate_resource_name(alias)

    def search(self, request: JobSearchRequest) -> JobSearchResult:
        payload = self._gateway.search(self._alias, self.build_query(request))
        return self.parse_result(payload, request.size)

    @staticmethod
    def build_query(request: JobSearchRequest) -> dict[str, object]:
        filters: list[dict[str, object]] = []
        if request.locations:
            filters.append({"terms": {"location": request.locations}})
        if request.skills:
            filters.append({"terms": {"skills": request.skills}})
        if request.sources:
            filters.append({"terms": {"source": request.sources}})
        if request.posted_from or request.posted_to:
            bounds: dict[str, str] = {}
            if request.posted_from:
                bounds["gte"] = request.posted_from.isoformat()
            if request.posted_to:
                bounds["lte"] = request.posted_to.isoformat()
            filters.append({"range": {"posted_at": bounds}})

        if request.query:
            query: dict[str, object] = {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": request.query,
                                "fields": ["title^3", "company^2", "description"],
                                "type": "best_fields",
                            }
                        }
                    ],
                    "filter": filters,
                }
            }
            sort: list[object] = [
                {"_score": "desc"},
                {"posted_at": {"order": "desc", "missing": "_last"}},
                {"document_id": "asc"},
            ]
        else:
            query = {"bool": {"filter": filters}} if filters else {"match_all": {}}
            sort = [
                {"posted_at": {"order": "desc", "missing": "_last"}},
                {"document_id": "asc"},
            ]

        body: dict[str, object] = {
            "query": query,
            "size": request.size,
            "track_total_hits": True,
            "sort": sort,
            "aggs": {
                "skills": {"terms": {"field": "skills", "size": 25}},
                "locations": {"terms": {"field": "location", "size": 25}},
            },
        }
        if request.cursor:
            body["search_after"] = request.cursor.values
        return body

    @staticmethod
    def parse_result(payload: dict[str, object], requested_size: int) -> JobSearchResult:
        hits_section = payload.get("hits", {})
        raw_hits = hits_section.get("hits", [])
        hits = [
            SearchHit(
                score=hit.get("_score"),
                sort=hit.get("sort", []),
                document=SearchDocument.model_validate(hit["_source"]),
            )
            for hit in raw_hits
        ]
        total_value = hits_section.get("total", 0)
        total = total_value.get("value", 0) if isinstance(total_value, dict) else total_value
        aggregations = payload.get("aggregations", {})
        shards = payload.get("_shards", {})
        failed_shards = int(shards.get("failed", 0)) if isinstance(shards, dict) else 0
        timed_out = bool(payload.get("timed_out", False))
        warnings: list[str] = []
        if timed_out:
            warnings.append("Elasticsearch timed out; results may be incomplete.")
        if failed_shards:
            warnings.append(f"{failed_shards} search shard(s) failed; results may be incomplete.")
        next_cursor = (
            SearchCursor(values=hits[-1].sort)
            if len(hits) == requested_size and hits
            else None
        )
        return JobSearchResult(
            total=int(total),
            took_ms=int(payload.get("took", 0)),
            hits=hits,
            next_cursor=next_cursor,
            skill_facets=JobSearchService._buckets(aggregations, "skills"),
            location_facets=JobSearchService._buckets(aggregations, "locations"),
            is_partial=timed_out or failed_shards > 0,
            warnings=warnings,
        )

    @staticmethod
    def _buckets(aggregations: object, name: str) -> list[FacetBucket]:
        if not isinstance(aggregations, dict):
            return []
        aggregation = aggregations.get(name, {})
        return [
            FacetBucket(key=str(bucket["key"]), count=int(bucket["doc_count"]))
            for bucket in aggregation.get("buckets", [])
        ]
