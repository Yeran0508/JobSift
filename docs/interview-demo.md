# JobSift 8–10 Minute Interview Demo

## 0:00–1:00 — Problem and ownership

JobSift aggregates reviewed public early-career software roles into one explainable search surface. State that this is an individual interview-oriented project and distinguish implemented evidence from planned scale.

## 1:00–2:30 — Acquisition and compliance

Show one source configuration and the immutable snapshot/manifest design. Explain API-first acquisition, bounded retry/rate limits, stable source IDs, parser-drift missingness, and why Selenium is deferred when an official data endpoint exists.

## 2:30–4:00 — Cleaning and NLP

Show raw preservation and transformation reasons. Explain field-specific missingness, why salary defaults to no imputation, two-layer deduplication, spaCy organization/location entities, and the versioned PhraseMatcher skill dictionary.

## 4:00–5:30 — Elasticsearch decisions

Show `text` versus `keyword`, index/search analyzers, deterministic `_id`, bulk item checks, and versioned index plus atomic alias. Explain BM25 `must` versus exact `filter`, facets, and the unique `search_after` tie-breaker.

## 5:30–7:00 — Visible search loop

Seed the fixture, open the page, search `backend`, select Python, open the detail, and point to source and indexed freshness. Demonstrate an empty query and explain loading, partial, and retryable failure states.

## 7:00–8:30 — Evaluation

Open the versioned three-query judgment suite. Define binary Precision@1 and graded nDCG@1. Report only the committed synthetic baseline: both equal 1.0 on three intentionally simple cases. Show the 30-sample local Elasticsearch service latency baseline: P50 12.43 ms and P95 16.98 ms. Immediately state that two documents cannot justify production or broad relevance claims.

## 8:30–9:30 — Failure and improvement

Explain the initial draft judgment failure: it assumed a frontend/JavaScript fixture that did not exist and used the wrong generated ID, producing 0.333. The fix corrected labels against source evidence rather than tuning ranking to the test. Next steps are independently labeled, larger queries, typo/autocomplete evaluation, PIT pagination, and production security.

## Commands

```bash
docker compose --profile search up -d elasticsearch
docker compose up -d api
docker compose exec api python scripts/index_fixture.py --index jobs-v1-demo
docker compose --profile test run --rm test
```

Use alternate host ports through `.env` when 8000 or 9200 is occupied. Do not run live acquisition during an interview; use the committed fixture for a deterministic demo.
