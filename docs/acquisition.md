# M1 Acquisition Boundary

JobSift treats source access, raw evidence, and parsing as separate boundaries:

```text
SourceConfig + compliance gate
        -> SourceAdapter.fetch()
        -> immutable content-addressed snapshot
        -> source-specific parser selected by ParserKind
        -> raw job records + missing-field report
```

## Why fixtures come first

CI must be deterministic and must not create traffic against third-party websites. The committed example is synthetic and exercises the same adapter, snapshot, selector, stable-ID, and parser-drift boundaries that a future live adapter will use.

Before enabling a live source, its configuration must record a parser owner, attribution, request limit, robots.txt review, terms review, public-job-only scope, and a disabled-by-default switch. An official API or public feed is preferred. Selenium is reserved for permitted JavaScript-rendered pages where an equivalent data endpoint is unavailable.

## Current capability

M1-A implements the source contract, compliance gate, fixture adapter, immutable raw snapshots, configuration-driven CSS parsing, stable source IDs, missing-field metrics, parser-drift failure, idempotent reruns, and per-source batch failure isolation.

M1-B adds a shared `httpx.Client` boundary, a thread-safe conservative rate limiter, per-request timeout, bounded retry attempts, numeric `Retry-After` support, capped exponential backoff, identified `User-Agent`, Greenhouse JSON parsing, JSON snapshots, and a CLI for an explicit reviewed-source run. Tests use `httpx.MockTransport`; CI never contacts Greenhouse.

The reviewed source is the official Greenhouse Job Board GET API. Greenhouse documents published Job Board GET data as public and unauthenticated. JobSift uses only the list-jobs endpoint and does not request application questions, authenticate, submit applications, or collect applicant data. See [compliance/greenhouse-job-board-api.md](compliance/greenhouse-job-board-api.md).

Selenium is not implemented in M1-B because the selected source already provides structured public JSON. Adding a browser would increase latency, resource use, and selector fragility without adding data for this source.
