# M1 Acquisition Boundary

JobSift treats source access, raw evidence, and parsing as separate boundaries:

```text
SourceConfig + compliance gate
        -> SourceAdapter.fetch()
        -> immutable content-addressed snapshot
        -> source-specific parser selected by ParserKind
        -> raw job records + missing-field report
        -> immutable run manifest + source metrics
```

## Why fixtures come first

CI must be deterministic and must not create traffic against third-party websites. The committed example is synthetic and exercises the same adapter, snapshot, selector, stable-ID, and parser-drift boundaries that a future live adapter will use.

Before enabling a live source, its configuration must record a parser owner, attribution, request limit, robots.txt review, terms review, public-job-only scope, and a disabled-by-default switch. An official API or public feed is preferred. Selenium is reserved for permitted JavaScript-rendered pages where an equivalent data endpoint is unavailable.

## Current capability

M1-A implements the source contract, compliance gate, fixture adapter, immutable raw snapshots, configuration-driven CSS parsing, stable source IDs, missing-field metrics, parser-drift failure, idempotent reruns, and per-source batch failure isolation.

M1-B adds a shared `httpx.Client` boundary, a thread-safe conservative rate limiter, per-request timeout, bounded retry attempts, numeric `Retry-After` support, capped exponential backoff, identified `User-Agent`, Greenhouse JSON parsing, JSON snapshots, and a CLI for an explicit reviewed-source run. Tests use `httpx.MockTransport`; CI never contacts Greenhouse.

M1-C closes the audit gap. Every attempted collection can write one exclusive JSON manifest under `data/manifests/<source>/<run_id>.json`. A successful run records its completed stage, timestamps, duration, fetch attempts, retries, rate-limit wait, retry backoff, snapshot digest/reuse, parsed-job count, and field missingness. A failed run records the last entered stage, bounded fetch statistics, snapshot evidence when already created, and a sanitized exception type and message before re-raising the original error.

`aggregate_source_metrics` derives source-level totals from manifests rather than from process memory: success/failure counts, parsed jobs, new/reused snapshots, attempts, retries, wait/backoff seconds, parser-drift failures, and the latest successful missingness report. These are operational counters for the observed manifests, not production SLOs or quality claims.

The reviewed source is the official Greenhouse Job Board GET API. Greenhouse documents published Job Board GET data as public and unauthenticated. JobSift uses only the list-jobs endpoint and does not request application questions, authenticate, submit applications, or collect applicant data. See [compliance/greenhouse-job-board-api.md](compliance/greenhouse-job-board-api.md).

Selenium is not implemented in M1 because the selected source already provides structured public JSON. Adding a browser would increase latency, resource use, and selector fragility without adding data for this source. If a future reviewed source is JavaScript-only, its adapter must add explicit waits, bounded browser resources, and the same manifest boundary before it can be enabled.

## Audit guarantees and limits

- Manifest files use exclusive creation, so a run ID collision fails instead of overwriting evidence.
- Failure stages distinguish compliance, fetch, snapshot, and parse failures. `completed` is reserved for successful runs.
- Fetch statistics are updated before each attempt and after each wait/backoff, so exhausted requests remain auditable.
- Error text is flattened and limited to 200 characters. Manifests must still never receive secrets or response bodies.
- Aggregates are recomputed from local manifests and are not concurrency-safe database counters. A production scheduler would move this contract to durable transactional storage.
- The CLI creates UUID-based run IDs. Injected clocks and IDs keep regression tests deterministic.

The deterministic M1-C evidence is recorded in [experiments/2026-11-11-m1c-audit-baseline.md](experiments/2026-11-11-m1c-audit-baseline.md).
