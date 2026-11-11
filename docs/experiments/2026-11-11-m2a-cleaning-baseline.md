# M2-A cleaning baseline

Date: 2026-11-11

Revision: the M2-A implementation commit containing this report, based on parent `11359f4`

## Purpose

Verify that M1 raw jobs can be normalized and deduplicated with explicit missing-value decisions while preserving the original values and transformation reasons. This is a deterministic correctness baseline, not a production data-quality or throughput claim.

## Procedure

The committed two-job HTML fixture was parsed through the M1 parser and passed directly to `JobCleaner`. Additional synthetic cases covered invalid identity fields, repeated stable IDs, cross-source content duplicates, Unicode and whitespace differences, missing and invalid dates, remote locations, employment phrases, reversed salary ranges, optional median filling, incompatible salary units, and empty input.

All tests ran in the pinned Python 3.12.10 image with Pandas 2.2.3. No live source was contacted.

## Fixture result

| Measurement | Result |
| --- | ---: |
| Input rows | 2 |
| Output rows | 2 |
| Raw salary missingness | 50% |
| Default salary imputation | none |
| First salary range | USD 95,000–120,000; period unknown |
| Second salary | remains missing |
| `Remote - US` normalization | `Remote, US` |
| Parsed dates | 2 UTC timestamps |
| Raw records retained | 2 |

The 50% salary missingness is a property of the synthetic fixture, not a claim about a live job source. The default cleaner left the missing salary untouched.

## Quality gates

| Check | Result |
| --- | ---: |
| Tests | 57 passed |
| Application statements | 755 |
| Application coverage | 100% |
| Ruff | passed |
| Missingness before/after | passed |
| Stable-ID deduplication | passed |
| Cross-source fingerprint deduplication | passed |
| Median policy acceptance/rejection | passed |
| Raw values and transformation reasons | passed |

## Limitations

- The salary parser is a bounded rule set, not a global compensation parser.
- Median filling is demonstrated on synthetic compatible annual USD ranges only.
- No speed, memory, or live-source completeness number is claimed.
- NLP entity and skill extraction remain unimplemented until M2-B.

## Conclusion

M2-A establishes a reproducible cleaning contract: measure first, choose a field-specific strategy, retain the raw record, and explain every mutation. The fixture proves that missing salary data remains missing by default and that optional median filling cannot cross a missingness threshold or mix units.
