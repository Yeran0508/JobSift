# JobSift V1 Architecture

## System context

```text
reviewed public API or committed fixture
                 |
                 v
 acquisition adapter -> immutable snapshot + run manifest
                 |
                 v
 Pandas cleaning -> spaCy entities + versioned skill matcher
                 |
                 v
 deterministic SearchDocument -> Elasticsearch versioned index
                                      |
                              atomic jobs-current alias
                                      |
                 browser <- FastAPI search API
```

The system is intentionally a modular monolith around one external search dependency. Python keeps acquisition, Pandas, spaCy, evaluation, and API code in one reproducible runtime. Interfaces still separate source adapters, parsers, storage, enrichment, Elasticsearch transport, search policy, public API schemas, and evaluation.

## Data and control boundaries

Raw snapshots are immutable evidence. Cleaning never overwrites the raw object; every normalized, parsed, inferred, or imputed field carries a reason. NLP adds model and dictionary provenance. Search documents retain source identity and acquisition time but expose only a curated public `JobSummary` through the API.

Full rebuilds create a new physical index and switch the stable alias only after bulk success. Query text contributes BM25 score; exact filters do not. Pagination carries the complete deterministic sort tuple behind an opaque API cursor.

## Failure behavior

- Compliance, source fetch, snapshot, and parser failures are recorded at their exact stage.
- Batch acquisition isolates one source failure from other sources.
- Bulk item failures prevent alias cutover.
- Elasticsearch timeout or shard failure is surfaced as partial data.
- Dependency failure becomes a safe retryable 503; zero hits remains a distinct successful state.
- Old indices are not automatically deleted, preserving an explicit rollback decision.

## Security and compliance

Only approved public job data is in scope. The project does not bypass authentication, CAPTCHAs, robots policy, terms, or rate limits and does not collect applicant data. Source URLs are HTTP(S)-validated, displayed text is escaped, and external links use `noopener noreferrer`. The local unauthenticated Elasticsearch configuration is for development only.

## Scaling path

At higher volume, acquisition workers and scheduled orchestration can move outside the API process; raw snapshots can move to object storage; PostgreSQL can own operational metadata; Elasticsearch can use production security, replicas, shard planning, and point-in-time pagination; the static client can become a component application. These are scaling options, not claims about V1.

## Verified V1 boundary

V1 proves repeatable fixture/API acquisition, raw evidence, deterministic processing, real Elasticsearch indexing/search, a visible search loop, versioned relevance judgments, and reproducible functional/latency baselines. It does not prove production scale, broad relevance quality, high availability, or accessibility conformance.
