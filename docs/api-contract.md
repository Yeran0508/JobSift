# JobSift API Contract

This document records only endpoints that exist in the current codebase.

## `GET /api/v1/health`

Purpose: process liveness. A successful response proves that FastAPI and HTTP routing are available. It does not prove that Elasticsearch or any scraper is ready.

Response `200 OK`:

```json
{
  "status": "ok",
  "service": "JobSift API",
  "version": "0.1.0"
}
```

## `GET /api/v1/jobs`

Purpose: search the current Elasticsearch alias through a stable public schema.

Query parameters:

- `q`: optional full-text query, at most 300 characters;
- repeated `location`, `skill`, and `source`: exact filters, at most 20 values each;
- `posted_from` and `posted_to`: optional ISO 8601 timestamps;
- `size`: 1-100, default 20;
- `cursor`: opaque cursor returned by the previous response.

Response `200 OK` contains `total`, public job summaries, `skills` and `locations` facets, an opaque `next_cursor`, and `meta`. `meta.is_partial` is true only when Elasticsearch reports a timeout or failed shard, and its human-readable warnings are shown by the UI. Public summaries include the original source URL and acquisition timestamp but exclude internal NLP hashes and model provenance.

Validation failures return `422` with a stable `detail.code`; an unavailable Elasticsearch dependency returns retryable `503 search_unavailable`. Upstream response bodies are never forwarded.

The cursor is URL-safe base64 around the complete Elasticsearch sort tuple. Clients must treat it as opaque and must not construct or edit it.
