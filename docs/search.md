# Elasticsearch Indexing and Search

M3 turns M2 enrichment output into a deterministic search document and tests the entire path against Elasticsearch 8.17.4. It is a library boundary for M4's API, not an HTTP endpoint yet.

## Mapping and analysis

The mapping uses `dynamic: strict` so an accidental field cannot silently choose an unsuitable inferred type. Full-text fields use the custom `jobs_index` analyzer; exact filters and aggregations use `keyword` fields. `title` and `company` are multi-fields so one value can support both behaviors. Dates and salary bounds have native types, while the display URL is stored but not indexed.

Both analyzers tokenize with `standard`, lowercase, ASCII-fold, remove English possessives and stop words, and stem English tokens. Only `jobs_search` expands the reviewed `js/javascript`, `k8s/kubernetes`, and `postgres/postgresql` synonym graph. Keeping expansion at search time avoids rewriting every stored term when the small synonym list changes, but changing an analyzer still requires a versioned index rebuild.

## Deterministic indexing and cutover

`SearchDocument.document_id` is SHA-256 of `source + NUL + source_job_id`. Bulk actions use that value as Elasticsearch `_id`, so replaying the same documents is an upsert rather than a duplicate. The NDJSON response is checked for item-level errors even when the HTTP response is 200.

A rebuild creates a versioned physical index, bulk-loads it, and then switches `jobs-current` with one `_aliases` request. Readers never need to know the physical version. The old index is returned to the caller but is not deleted automatically: rollback and retention policy are operational decisions, not hidden side effects.

## Query contract

Text queries use `multi_match` with `title^3`, `company^2`, and `description`. Elasticsearch's BM25 score decides text relevance. Location, canonical skills, source, and posted-date bounds live in `bool.filter`, where they restrict eligibility without changing relevance score. An empty text query becomes `match_all` or filter-only search.

Every result also contains top skill and location term buckets. These facets describe the already-filtered result set; they are not disjunctive navigation counts.

Pagination uses the last hit's complete sort tuple as `search_after`. Text search sorts by `_score`, then `posted_at`, then unique `document_id`; browsing omits `_score`. The final unique tie-breaker prevents equal-score/equal-date documents from repeating or disappearing within a stable index snapshot. This milestone does not add point-in-time search, so concurrent writes between pages can still move results.

## Failure and security boundaries

Index and alias names accept only a conservative lowercase character set before entering a URL. Gateway exceptions report method, path, and status without echoing Elasticsearch response bodies. Timeouts are configured at the client boundary. Local Elasticsearch has security disabled and must not be exposed as a production configuration.

## Verification and limitations

Unit tests cover query construction, mapping, model validation, alias actions, partial bulk failures, response parsing, and cursors. An opt-in integration test creates a unique physical index and alias on a real Elasticsearch container, validates analyzers with `_analyze`, indexes twice, searches and filters, checks facets and pagination, and deletes its index in `finally`.

M3 does not yet expose search through FastAPI, use point-in-time pagination, implement typo tolerance or autocomplete, tune relevance on labeled judgments, measure production-scale latency, secure Elasticsearch, or define old-index retention. Those claims remain out of scope until measured or implemented.
