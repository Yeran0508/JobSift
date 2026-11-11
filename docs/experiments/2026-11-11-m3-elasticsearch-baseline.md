# M3 Elasticsearch Functional Baseline — 2026-11-11

## Scope

This is a functional integration baseline, not a latency or relevance-quality benchmark. It verifies the committed M3 behavior against a real service before the API layer exists.

- Software: Elasticsearch 8.17.4, Python 3.12 test container
- Data: three synthetic job documents defined in `test_elasticsearch_integration.py`
- Index: one shard, zero replicas, unique test index and alias per run
- Command: opt-in pytest integration test over the Docker Compose network
- Cleanup: the physical test index is deleted in `finally`

## Observations

- The strict mapping and both custom analyzers created successfully.
- `_analyze` expanded `JS` to a token containing `javascript` and stemmed `Engineers` to `engin`.
- Replaying the same three bulk documents left total hits at three because deterministic `_id` values overwrite the same logical records.
- The alias pointed to the newly built versioned index.
- A weighted text query plus location, skill, source, and date filters returned only the expected backend job.
- The filtered result produced `Docker: 1`, `Python: 1`, and `Chicago, IL: 1` facet buckets.
- Two one-item pages produced different document IDs using the returned `search_after` cursor.
- Result: `1 passed` against the real Elasticsearch container.

## Limitations

The sample is synthetic and tiny. It cannot establish recall, NDCG, throughput, p95 latency, shard sizing, concurrent pagination consistency, or production failure recovery. No warm-up, repetition count, or timing metric is reported because performance was not the changed variable. M5 needs labeled search judgments and a reproducible load protocol before any quality or speed claim is made.
