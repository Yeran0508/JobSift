# M4 User-Facing Search Loop

M4 closes the first visible product loop: an approved fixture can travel through parsing, Pandas cleaning, spaCy enrichment, deterministic Elasticsearch indexing, the FastAPI search contract, and a responsive browser result.

## API boundary

`GET /api/v1/jobs` accepts bounded query, repeated location/skill/source filters, an ISO date range, a bounded page size, and an opaque cursor. FastAPI validates primitive query values; `JobSearchRequest` validates cross-field rules such as date ordering. Internal Elasticsearch sort values are base64-encoded before leaving the API.

The public response deliberately does not mirror `_source`. It exposes only job display fields, source URL, acquisition freshness, facets, total, search time, partial status, and the next cursor. NLP hashes, entity internals, physical index names, and Elasticsearch error bodies stay behind the service boundary.

An Elasticsearch transport or response error becomes a safe retryable `503 search_unavailable`. A timeout or failed shard can still return useful hits, so the response marks `meta.is_partial` and carries warnings rather than silently presenting the page as complete.

## Web client

The server ships a dependency-free HTML/CSS/JavaScript client from the same origin. Same-origin delivery avoids a separate CORS and frontend deployment boundary for this interview-sized system. The design is responsive and keyboard-accessible, with semantic search/form controls, visible focus behavior, a modal detail view, and reduced-motion support.

The interface supports:

- keyword search and suggested queries;
- location, canonical-skill, and posted-date filters;
- result and facet counts;
- load-more pagination using the opaque cursor;
- job details, source attribution, posted date, and indexed freshness;
- explicit loading, empty, partial-result, and retryable failure states.

The UI links to the original public listing with `noopener noreferrer`. It never applies to a job, ranks a candidate, sends a message, or hides results behind a recommendation model.

## End-to-end acceptance

`scripts/index_fixture.py` uses the same production parser, cleaner, pinned spaCy model, skill dictionary, search-document conversion, bulk gateway, and alias switch as the application. It only reads the committed synthetic fixture and performs no external acquisition.

The real acceptance run created `jobs-v1-m4-demo`, indexed two documents, switched `jobs-current`, served the web client, and returned one `Backend Engineer` for `q=backend&skill=Python`, including the `Python: 1` and `Chicago, IL: 1` facets and a non-partial metadata result.

## Limitations

The web client is intentionally framework-free, so a larger UI would benefit from component-level tooling. M4 does not add authentication, saved searches, analytics, autocomplete, browser-based automated application, point-in-time pagination, or relevance evaluation. Search timing in a two-document local run is diagnostic metadata, not a performance claim. M5 must add versioned judgments and reproducible performance experiments before resume metrics are stated.
