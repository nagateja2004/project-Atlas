# Project Atlas Evaluation

All metrics are deterministic or directly measured by this command. Synthetic scenarios are not historical predictions.

## Rag

| Metric | Baseline | Advanced |
| --- | ---: | ---: |
| recall at 5 | 0.9231 | 0.9231 |
| recall at 12 | 0.9231 | 1.0 |
| mrr | 0.6269 | 0.7521 |
| correct document rate | 0.6923 | 0.8462 |
| correct page rate | 0.6923 | 0.6923 |
| citation precision | 0.3226 | 0.2432 |
| unsupported claim rate | 0.0 | 0.0 |
| average input tokens | 457.88 | 172.94 |
| average output tokens | 271.44 | 122.75 |
| average latency ms | 41.56 | 123.36 |

## Compliance

| Metric | Value |
| --- | ---: |
| true positive | 6 |
| false positive | 0 |
| false negative | 0 |
| true negative | 6 |
| precision | 1.0 |
| recall | 1.0 |
| f1 | 1.0 |

## Schedule

| Metric | Value |
| --- | ---: |
| case count | 12 |
| mean lead time days | 28.42 |
| mean predicted delay days | 34.67 |
| mean actual or simulated delay days | 33.17 |
| mean prediction error days | 1.5 |
| mean absolute prediction error days | 1.5 |
| cases within 3 days | 12 |

## Supply Chain

| Metric | Value |
| --- | ---: |
| shipments represented | 5 |
| expected shipments | 5 |
| representation rate | 1.0 |
| supplier tiers total | 15 |
| mean supplier tiers per shipment | 3.0 |
| risk events with alert latency | 8 |
| shipments with risk events | 5 |
| mean alert latency minutes | 126.25 |
| events alerted within 2 hours | 6 |
| risky shipments | 3 |
| alternatives generated | 3 |
| alternative generation success | 1.0 |

## Commissioning

| Metric | Value |
| --- | ---: |
| total steps | 21 |
| automatically evaluated steps | 21 |
| automation coverage | 1.0 |
| completion coverage | 1.0 |
| expected ncrs | 1 |
| actual ncrs | 1 |
| ncr correctness | True |

## Manual Effort

| Metric | Value |
| --- | ---: |
| status | NOT_MEASURED |
| measurement count | 0 |
| manual hours | NOT MEASURED |
| atlas hours | NOT MEASURED |
| hours saved | NOT MEASURED |
| note | Add measured manual_hours, atlas_hours, and sample_count values before claiming hours saved. |

## Provenance

| Metric | Value |
| --- | ---: |
| llm calls | none |
| generation | deterministic extractive responder |
| embedding backend | sentence_transformer |
| embedding model | sentence-transformers/all-MiniLM-L6-v2 |
