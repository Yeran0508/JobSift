# M1 Acquisition Boundary

JobSift treats source access, raw evidence, and parsing as separate boundaries:

```text
SourceConfig + compliance gate
        -> SourceAdapter.fetch()
        -> immutable content-addressed snapshot
        -> configuration-driven HTML parser
        -> raw job records + missing-field report
```

## Why fixtures come first

CI must be deterministic and must not create traffic against third-party websites. The committed example is synthetic and exercises the same adapter, snapshot, selector, stable-ID, and parser-drift boundaries that a future live adapter will use.

Before enabling a live source, its configuration must record a parser owner, attribution, request limit, robots.txt review, terms review, public-job-only scope, and a disabled-by-default switch. An official API or public feed is preferred. Selenium is reserved for permitted JavaScript-rendered pages where an equivalent data endpoint is unavailable.

## Current capability

M1-A implements the source contract, compliance gate, fixture adapter, immutable raw snapshots, configuration-driven CSS parsing, stable source IDs, missing-field metrics, parser-drift failure, idempotent reruns, and per-source batch failure isolation.

It does not yet make HTTP requests, start a browser, reuse cookies, retry with backoff, or rate-limit live traffic. Those capabilities remain M1-B and cannot be described as implemented.
