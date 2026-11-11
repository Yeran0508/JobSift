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

M0 is implemented and locally verified. The repository contains a Python 3.12/FastAPI liveness endpoint, typed configuration, Docker runtime/test targets, automated tests, a coverage gate, CI, and an Elasticsearch development service declaration. The current local evidence is four passing tests, 100% application coverage, a passing Ruff check, valid Compose configuration, and matching health responses from inside the container and through a host port.

Remote CI status must be checked against the exact pushed commit. Local success is not presented as GitHub Actions evidence.

Selenium acquisition, Pandas cleaning, NLP enrichment, Elasticsearch indexing, job search, evaluation results, and the user interface are not implemented yet.

## Interview evidence standard

Each milestone follows:

```text
concept -> small implementation -> automated test -> real verification
        -> limitations/trade-offs -> Chinese and English interview answer
```

The repository never treats a target as a measured result. See [requirements.md](requirements.md) for V1 acceptance criteria and [docs/experiments/README.md](docs/experiments/README.md) for experiment evidence rules.

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
