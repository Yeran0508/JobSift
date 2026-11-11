# JobSift

JobSift is an interview-oriented public job aggregation and search platform. Its V1 data path is planned as:

```text
allowed public source or fixture
    -> API/requests or Selenium source adapter
    -> immutable raw snapshot
    -> Pandas normalization and spaCy enrichment
    -> Elasticsearch mapping and bulk indexing
    -> FastAPI search API and web client
```

## Current status

M0 and M1 are implemented and verified. M1-A adds a compliance-gated source contract, synthetic fixture adapter, immutable content-addressed raw snapshots, configuration-driven HTML parsing, stable source IDs, missing-field metrics, parser-drift detection, idempotent reruns, and per-source failure isolation. M1-B adds an identified HTTP client, reusable sessions, timeouts, conservative rate limiting, bounded retries with `Retry-After` or exponential backoff, Greenhouse JSON parsing, and a reviewed public Greenhouse source. M1-C adds immutable per-run audit manifests and source-level acquisition metrics for outcomes, jobs, snapshots, attempts, retries, waiting, backoff, missingness, and parser drift.

Remote CI status must be checked against the exact pushed commit. Local success is not presented as GitHub Actions evidence.

Selenium acquisition, cookies, browser waits, Pandas cleaning, NLP enrichment, Elasticsearch indexing, job search, evaluation results, and the user interface are not implemented yet. Selenium remains intentionally deferred because the selected source exposes an official public JSON API; explicit browser waits become applicable only if a reviewed JavaScript-only source is added.

## Interview evidence standard

Each milestone follows:

```text
concept -> small implementation -> automated test -> real verification
        -> limitations/trade-offs -> Chinese and English interview answer
```

The repository never treats a target as a measured result. See [requirements.md](requirements.md) for V1 acceptance criteria and [docs/experiments/README.md](docs/experiments/README.md) for experiment evidence rules.

M1 acquisition design and current limitations are documented in [docs/acquisition.md](docs/acquisition.md).

## Reviewed public-source smoke test

The Greenhouse Job Board API configuration is limited to published job-listing GET data, identifies JobSift through its user agent, and defaults to two requests per minute. It does not access application questions or submit applicant data. Review evidence is in [docs/compliance/greenhouse-job-board-api.md](docs/compliance/greenhouse-job-board-api.md).

Run one explicit acquisition into ignored local storage:

```bash
docker build --target runtime -t jobsift-api .
docker run --rm \
  -v "$PWD/data:/data" \
  jobsift-api \
  python scripts/acquire_source.py \
  --config config/sources/greenhouse-anthropic.json \
  --output /data/raw \
  --manifest-output /data/manifests
```

This is an explicit tool command, not an API startup side effect or a CI action. It prints the run ID, manifest path, fetch statistics, and cumulative source metrics. Raw snapshots and manifests are ignored local evidence; current counts can change whenever the source publishes or closes jobs.

## Local development

Requirements: Docker Desktop with Docker Compose.

```bash
cp .env.example .env
docker compose up --build -d api
curl http://localhost:8000/api/v1/health
```

If port `8000` is already in use, set `JOBSIFT_API_PORT` in `.env` to another host port, such as `18080`. The container still listens on `8000`.

Run quality checks in the pinned Python 3.12 test image:

```bash
docker compose --profile test build test
docker compose --profile test run --rm test
docker compose --profile test run --rm test ruff check .
docker compose config --quiet
```

Elasticsearch is declared for M3 and can be started separately when its integration begins:

```bash
docker compose --profile search up -d elasticsearch
```

Declaring or starting the container does not mean that application indexing and search are implemented.
