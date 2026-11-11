# M1-C acquisition audit baseline

Date: 2026-11-11

Revision: the M1-C implementation commit containing this report, based on parent `5a44953`

## Purpose

Verify that each acquisition attempt leaves inspectable run evidence and that source metrics can be reconstructed from those manifests. This is a deterministic audit test, not a live traffic, scale, or availability experiment.

## Procedure

The pinned Python 3.12.10 test image ran Ruff and the full pytest suite. Network behavior used `httpx.MockTransport`; fixture reads, HTTP success, rate limiting, retry success, retry exhaustion, compliance rejection, parser drift, idempotent snapshots, and multi-source isolation all executed without contacting a third party.

The audit tests used injected clocks and run IDs. They wrote manifests to pytest temporary directories, loaded them back through the public store, and aggregated mixed successful and failed runs.

## Result

| Check | Result |
| --- | ---: |
| Tests | 46 passed |
| Application statements | 502 |
| Application coverage | 100% |
| Ruff | passed |
| Success manifest round trip | passed |
| Exclusive run-ID collision | passed |
| Compliance failure stage | passed |
| Exhausted HTTP failure stage and attempts | passed |
| Parser-drift failure stage | passed |
| Multi-source failure isolation | passed |
| Source aggregate reconstruction | passed |

The success path records snapshot identity/reuse, job count, missingness, attempts, retries, rate-limit wait, and backoff. Failure manifests preserve the last pipeline stage and available fetch or snapshot evidence while the service still raises the original exception.

## Limitations

- The results establish deterministic behavior for the tested process, not production availability or throughput.
- Manifest storage is local JSON with exclusive file creation; it is not a distributed transaction system.
- Duration tests use injected timestamps and do not claim real latency percentiles.
- No new live request was needed for M1-C. The reviewed M1-B smoke remains the evidence for actual Greenhouse connectivity.
- Metrics are cumulative over the manifest directory supplied to the CLI. Deleting local manifests deletes that local history.

## Conclusion

M1 now has a traceable boundary from compliance decision through fetch, immutable snapshot, parse outcome, and source-level counters. A failed source remains isolated and leaves enough bounded evidence to explain where and why it failed. M2 can consume a specific raw snapshot without confusing acquisition success with cleaning or enrichment quality.
