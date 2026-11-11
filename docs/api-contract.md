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
