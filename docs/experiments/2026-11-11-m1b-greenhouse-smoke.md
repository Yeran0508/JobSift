# M1-B Greenhouse public API smoke test

Date: 2026-11-11

Revision: the M1-B implementation commit containing this report, based on parent `bae09c4`

## Purpose

Verify that the reviewed public GET source works through the same compliance, HTTP, snapshot, parsing, and reporting boundaries used by tests. This is a connectivity and idempotency smoke test, not a load test or a search-quality evaluation.

## Source and configuration

- Endpoint: `https://boards-api.greenhouse.io/v1/boards/anthropic/jobs`
- Method: unauthenticated GET
- Request rate: at most two per minute per process
- Timeout: 20 seconds
- Maximum attempts: three
- User agent: `JobSift/0.1 (+https://github.com/Yeran0508/JobSift)`
- Environment: Docker Desktop, Python 3.12.10 test image, macOS host

## Procedure

The CLI was run twice against the same endpoint and output directory. No `content=true` parameter was used. The second run tested whether unchanged bytes resolve to the existing content-addressed snapshot.

## Result

| Measurement | First run | Second run |
| --- | ---: | ---: |
| HTTP result | 200 | 200 |
| Parsed jobs | 675 | 675 |
| Response bytes | 483,572 | 483,572 |
| Snapshot created | true | false |
| SHA-256 | `9ca6dad433565da5985cd55568fc1f6a82a62ae270f27ba853436a4ea2e803e7` | same |
| Required-field missingness | 0% | 0% |
| Description missingness | 100% | 100% |
| Salary missingness | 100% | 100% |

The stored metadata recorded `application/json`, the exact endpoint, source ID, fetch time, and content hash. The 675 count is a time-specific observation and must not be presented as a stable scale claim.

## Limitations

- The list endpoint can change immediately as the employer opens or closes jobs.
- Without `content=true`, this baseline intentionally lacks descriptions and salary text.
- The smoke test made only two sequential requests; it does not establish production throughput, availability, or P95 latency.
- The raw response was kept in temporary ignored storage and is not committed. The committed synthetic fixture is the regression-test input.
- No Selenium comparison is claimed because an official structured API already satisfies this source's acquisition need.

## Conclusion

The reviewed API can be acquired through the bounded HTTP adapter, parsed into stable raw records, and rerun idempotently when response bytes are unchanged. M2 must preserve the raw missingness and must not infer descriptions or salaries that the source did not return.
