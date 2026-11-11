# M5 Evaluation Baseline — 2026-11-11

## Reproducibility

- Dataset: `example-fixture-v1`, two synthetic job documents
- Judgment suite: `m5-relevance-v1`, three query/filter cases, grades 0–3
- Search service: Elasticsearch 8.17.4, one shard, zero replicas
- Metric cutoff: K=1
- Latency protocol: five warm-ups followed by 30 sequential service-level repetitions
- Changed variable for analyzer check: `jobs_index` versus `jobs_search` on identical text `JS`

## Retrieval result

All three final cases returned the only source-evidenced relevant document at rank one:

| Case | Retrieved ID | Precision@1 | nDCG@1 |
| --- | --- | ---: | ---: |
| backend-python | eng-101 | 1.0 | 1.0 |
| data-ingestion | 85f2c93e5627d2bf5cd6 | 1.0 | 1.0 |
| remote-role | 85f2c93e5627d2bf5cd6 | 1.0 | 1.0 |

Macro Precision@1 = 1.0 and macro nDCG@1 = 1.0. These numbers describe three trivial synthetic cases, not general search quality.

## Latency result

The same `backend-python` service query produced: minimum 10.19 ms, mean 12.82 ms, P50 12.43 ms, P95 16.98 ms, maximum 19.37 ms. This excludes browser/network rendering and represents a warm local two-document container only.

## Controlled comparisons

### Analyzer

`jobs_index` emitted `[js]`; `jobs_search` emitted `[javascript, js]`. The search-only synonym graph expands recall without duplicating synonym terms in every indexed document.

### Mean versus median salary imputation

For the controlled annual salary sample `[80, 90, 100, 500]` thousand dollars, mean is 192.5 and median is 95. The single 500 outlier pulls mean far from three of four observations. JobSift therefore keeps salary missing by default and permits median only when missingness is below the configured threshold and currency/period agree. This numerical illustration is not a claim about the fixture distribution.

### Requests/API versus Selenium

The selected live source exposes an official public JSON API, so Selenium was not executed merely to produce a favorable timing number. The controlled decision holds required data and compliance scope constant: the API path returns the data directly, while Selenium would add browser startup, rendering, driver, and wait variables without adding fields. Under the project policy and handbook guidance, the API path wins on necessity and reproducibility. No Selenium latency ratio is reported because no compatible browser surface was available and an unnecessary live browser run would not be a fair benchmark.

## Failure case

The first draft suite assumed the second fixture was a frontend JavaScript role and labeled it as `eng-102`. The real run returned macro Precision@1/nDCG@1 of 0.333: one query had no match and another retrieved the parser-generated ID. Inspection showed the source fixture actually says `Software Engineer I` and `Develop data ingestion tools`, with no JavaScript term and no explicit ID attribute. The judgments were corrected against immutable fixture evidence; ranking code and boosts were not changed. This demonstrates why evaluation data requires the same review discipline as application code.

## Limitations

Two documents, three self-authored queries, and one machine cannot establish broad relevance, inter-annotator agreement, production latency, concurrency, or scalability. A resume claim should cite this only as a reproducible functional baseline. The next credible study needs a larger frozen corpus, independently labeled judgments, multiple query intents, repeated end-to-end HTTP load, and hardware metadata.
