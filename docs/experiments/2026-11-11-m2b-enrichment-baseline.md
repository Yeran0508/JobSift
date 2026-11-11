# M2-B spaCy enrichment baseline

Date: 2026-11-11

Revision: the M2-B implementation commit containing this report, based on parent `4e1d471`

## Purpose

Verify that cleaned jobs can be enriched with traceable organization/location entities and canonical technical skills while preserving the M2-A record. This is a deterministic integration baseline, not an NER accuracy evaluation.

## Configuration

- Python: 3.12.10
- spaCy: 3.8.18
- packaged English pipeline: `en_core_web_sm` 3.8.0
- skill dictionary: `skills-v1-2026-11-11`
- matching: case-insensitive spaCy `PhraseMatcher`
- entity labels: `ORG` for organizations; `GPE`, `LOC`, and `FAC` for locations

## Procedure

Deterministic tests injected an English spaCy pipeline with `EntityRuler` patterns for one organization, two location labels, and an ignored person. A synthetic cleaned job contained repeated organization and Python mentions plus the `JS` alias and Docker. A separate final-image test loaded the pinned pretrained pipeline and enriched a job without asserting probabilistic entity labels.

## Deterministic result

| Measurement | Result |
| --- | ---: |
| Input/output jobs | 1 / 1 |
| Unique organizations | 1 |
| Unique locations | 2 |
| Unique canonical skills | 3 |
| `JS` canonicalization | `JavaScript` |
| Repeated `Python` mentions | one canonical skill |
| Ignored `PERSON` entity | passed |
| Text/dictionary SHA-256 | recorded |
| Model/dictionary versions | recorded |

## Quality gates

| Check | Result |
| --- | ---: |
| Tests | 63 passed |
| Application statements | 879 |
| Application coverage | 100% |
| Ruff | passed |
| Pinned model load | passed |
| Dictionary alias collision rejection | passed |
| Empty and missing-description input | passed |
| Batched `nlp.pipe` enrichment | passed |

## Limitations

- The deterministic entity counts come from test rules, not from a claim about pretrained-model precision or recall.
- No labeled job-description entity set exists yet, so no NER F1 is reported.
- Skill matches are dictionary evidence; they do not prove candidate proficiency or job importance.
- Case-insensitive matching improves alias recall but can increase false positives, so ambiguous short/common aliases are excluded.
- No latency or throughput number is claimed from this one-record correctness test.

## Conclusion

M2-B provides a reproducible NLP boundary with separate provenance for statistical entities and reviewed terminology rules. The final image contains the actual pinned English model, while deterministic tests keep CI stable. M2 is now complete; M3 can map canonical skills and normalized entity fields into explicit Elasticsearch `keyword` and `text` fields.
