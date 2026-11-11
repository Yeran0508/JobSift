# M4 Visible Search Functional Baseline — 2026-11-11

## Environment and path

- Docker runtime: Python 3.12.10 API plus Elasticsearch 8.17.4
- Host ports: API 18081 and Elasticsearch 9201 to avoid other local projects
- Dataset: two committed synthetic cards from `example_jobs.html`
- Pipeline: HTML parser -> Pandas cleaner -> pinned spaCy/skill matcher -> search documents -> bulk -> alias -> FastAPI -> same-origin web client

## Observations

- The fixture script indexed two documents into `jobs-v1-m4-demo` and atomically switched `jobs-current`.
- `GET /api/v1/jobs?q=backend&skill=Python` returned exactly one `Backend Engineer` in `Chicago, IL`.
- The response included the public source URL, acquisition timestamp, salary fields, `Python: 1` and `Chicago, IL: 1` facets, `is_partial: false`, and no warnings.
- `/`, `/assets/app.js`, and `/assets/styles.css` were served by the runtime image.
- Automated contract tests verified validated filters, cursor round-trip, safe 503 handling, and the presence of loading, empty, partial, and failure UI states.

## Limits

This proves functional wiring with synthetic data. It does not measure production browser performance, accessibility conformance, relevance quality, or behavior at scale. Browser automation was unavailable in the execution environment, so visual behavior was verified through responsive CSS review, served-asset checks, and API/UI contract tests rather than a captured browser screenshot.
