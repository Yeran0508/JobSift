# M2 Processing Boundary

M2-A converts M1 raw records into typed, explainable clean records without changing the immutable snapshot or discarding the original field values:

```text
ParseReport.jobs
    -> Pandas missingness baseline
    -> required-identity validation
    -> stable source-ID deduplication
    -> text/location/date/employment/salary normalization
    -> normalized-content fingerprint deduplication
    -> guarded missing-value policy
    -> CleaningReport + raw record + transformation reasons
```

## Missing-value decisions

The default is not “fill every null.” Each field has a semantic policy:

| Field | Default | Reason |
| --- | --- | --- |
| title, company, URL | drop invalid row | Identity fields cannot be inferred safely. |
| location | explicit `Unknown` marker | The marker is filterable and does not invent a city. |
| description | no imputation | Job descriptions are independent; forward-fill would copy another job. |
| posted date | no imputation | A missing publication time must remain unknown. |
| employment type | infer explicit phrases, otherwise `Unknown` | Inference is limited to visible evidence. |
| salary | no imputation | Mean and forward-fill would invent compensation. |

Median salary imputation is opt-in. It runs only when the observed missing rate is at or below the configured threshold and every observed range has the same known currency and period. Otherwise, the report records that median imputation was rejected and leaves the values missing. Mean imputation is deliberately absent because salary distributions are commonly skewed and outlier-sensitive.

The policy model rejects incompatible combinations such as median location filling or marker-based salary filling before cleaning starts.

## Normalization and provenance

- Text uses Unicode NFKC, removes replacement characters, collapses whitespace, and preserves case for display.
- Dates use `pandas.to_datetime(..., errors="coerce", utc=True)`; invalid or absent values remain missing.
- Remote locations become `Remote` or `Remote, US`; two-letter state suffixes are uppercased.
- Employment type uses a small explicit phrase set for internship, part-time, contract, and full-time. No model guess is made.
- Salary parsing supports one value or a range, `k` suffixes, USD markers, reversed endpoints, and hourly/yearly periods. The untouched `salary_raw` remains nested in every clean record.
- Every changed, parsed, inferred, or imputed field receives a `TransformationRecord` with an action and reason.

## Deduplication

Deduplication has two different identities:

1. `(source, source_job_id)` removes repeated acquisitions of the same source record and keeps the newest `acquired_at` value.
2. A SHA-256 fingerprint over normalized title, company, location, and description catches equivalent content published under different source IDs or sources and also keeps the newest record.

The fingerprint intentionally excludes URL and acquisition time because mirrors and reruns change those values. Salary and posting date are also excluded from the first M2-A fingerprint; this favors collapsing mirrored content, and the trade-off is documented rather than presented as perfect entity resolution. Every removed record is listed with its reason and retained identity.

## M2-B entity and skill enrichment

M2-B receives `CleanJobPosting` records and runs their title, company, non-marker location, and description through one shared spaCy pipeline with `nlp.pipe`. The runtime pins spaCy 3.8.18 and the compatible `en_core_web_sm` 3.8.0 package. Organizations come from `ORG`; locations come from `GPE`, `LOC`, and `FAC`. Other entity labels are ignored rather than silently reclassified.

Technical skills use a separate case-insensitive `PhraseMatcher`, because general-purpose NER is not trained to recognize the project’s domain taxonomy. The committed [skills-v1.json](../config/nlp/skills-v1.json) maps reviewed aliases such as `JS` to `JavaScript` and `K8s` to `Kubernetes`. Broad aliases such as `Node` and `Spark` are intentionally excluded because they are common English words. Duplicate phrases across canonical skills fail dictionary validation before enrichment.

Each enriched record retains the complete clean record and adds:

- unique organization and location evidence with original text, normalized text, spaCy label, and character offsets;
- unique canonical skills with the exact matched alias and character offsets;
- a SHA-256 digest of the exact text sent to spaCy;
- model name/version plus dictionary version/SHA-256 in the batch report.

Tests inject a deterministic `EntityRuler` so entity assertions do not depend on statistical model changes. A separate test loads the pinned `en_core_web_sm` artifact from the final image, proving that the production model is actually packaged. This follows spaCy’s documented separation between trained pipelines, [rule-based entities](https://spacy.io/api/entityruler), and [phrase terminology matching](https://spacy.io/api/phrasematcher).

## Current limits

- Location normalization is deliberately small and does not geocode or infer countries beyond explicit remote-US text.
- Salary parsing does not convert currencies or annualize hourly compensation.
- Content-fingerprint deduplication can merge legitimately separate openings with identical text. M2-B/M3 evidence may justify adding requisition metadata or a configurable fingerprint.
- The cleaner is an in-process deterministic boundary, not a distributed Pandas job or a throughput claim.
- `en_core_web_sm` outputs are predictions, not ground truth; M2-B does not claim entity accuracy without a labeled evaluation set.
- The skill dictionary favors precision and has finite recall. New aliases require review, a version change, and regression cases.
- Only the first occurrence of each normalized entity or canonical skill is retained per job. Match counts are not treated as relevance scores.

The deterministic baselines are recorded in [experiments/2026-11-11-m2a-cleaning-baseline.md](experiments/2026-11-11-m2a-cleaning-baseline.md) and [experiments/2026-11-11-m2b-enrichment-baseline.md](experiments/2026-11-11-m2b-enrichment-baseline.md).
