# JobSift V1 Requirements

## 1. Purpose

JobSift is an interview-oriented platform that aggregates public early-career software jobs, normalizes and enriches their fields, and provides explainable full-text search and filters. Every resume-level feature must have code, automated tests, a reproducible demonstration, and a concise interview explanation.

Milestones define build order. They do not allow an unimplemented feature to be described as complete.

## 2. Evidence and compliance policy

- Collect only public job information from sources whose robots policy and terms permit the planned access.
- Prefer an official public API or data feed over browser automation when both expose equivalent data.
- Never collect credentials, private profiles, applicant data, or other personal information.
- CI uses committed synthetic HTML fixtures instead of live websites.
- Every live source must have a documented request limit, attribution, parser owner, and disable switch.
- No traffic, scale, freshness, quality, or latency number may be claimed before a reproducible measurement exists.

## 3. Milestones

### M0: Reproducible engineering baseline

- Python 3.12 and FastAPI application.
- Typed environment configuration and secret-safe examples.
- Docker runtime and test images.
- Liveness endpoint, OpenAPI contract, Ruff, pytest, coverage gate, and CI.
- Elasticsearch declared for later search work but not presented as integrated.

### M1: Compliant acquisition

- A source-adapter interface and configuration-driven field selectors.
- Requests/API-first acquisition with Selenium only for JavaScript-rendered content.
- Explicit waits, bounded retries with backoff, timeouts, rate limits, and session reuse.
- Raw immutable snapshots, stable source IDs, idempotent reruns, and per-source failure isolation.
- Empty-field and parser-drift monitoring.

### M2: Pandas cleaning and NLP enrichment

- Normalize encoding, location, dates, employment type, and salary ranges.
- Measure missingness before choosing drop, marker, forward-fill, median, or no-imputation behavior.
- Deduplicate by stable source ID and normalized content fingerprint.
- Extract organizations and locations with spaCy; supplement technical skills with a reviewed phrase dictionary.
- Preserve raw values and record transformation reasons.

### M3: Elasticsearch indexing and retrieval

- Explicit mappings with `text` for analyzed search and `keyword` for filtering, sorting, and aggregation.
- A documented English analyzer and inspectable `_analyze` examples.
- Idempotent bulk indexing with a versioned index and safe alias switch.
- BM25 keyword search plus `filter` clauses for location, skills, source, and posting date.
- Skill/location aggregations and pagination with a deterministic tie-breaker.

### M4: User-facing search loop

- Search API with validated query parameters and stable response schemas.
- Responsive UI for query, filters, facets, results, detail, source, and freshness.
- Honest empty, loading, partial-source, and failure states.
- End-to-end acceptance from fixture ingestion through a visible search result.

### M5: Evaluation and interview delivery

- Versioned relevance judgments and retrieval metrics such as Precision@K and nDCG@K.
- Pipeline metrics for success rate, missing fields, duplicates, freshness, and P50/P95 latency.
- Controlled comparisons for requests versus Selenium, mean versus median salary imputation, and analyzer behavior.
- Architecture document, 8-10 minute demo, failure case, limitations, and Chinese/English interview questions.

## 4. V1 completion definition

V1 is complete only when a clean environment can run the stack; an allowed fixture/source can be collected repeatedly without duplicates; normalized jobs can be indexed and searched with filters and aggregations; failure and partial-data behavior are visible; automated and real-infrastructure tests pass; all reported metrics have committed evidence; and CI passes on the default branch.

## 5. Explicitly out of scope

- Applying to jobs or sending messages on a user's behalf.
- Bypassing authentication, CAPTCHAs, rate limits, robots policy, or website terms.
- Collecting applicant profiles or other personal data.
- Claiming production scale or accuracy without measurement.
- Recommendation models, resume ranking, native mobile applications, and high-availability deployment for V1.
