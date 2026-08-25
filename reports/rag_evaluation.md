# Atlas RAG Evaluation

Synthetic test split; tuning used the development split only. Generation and scoring are deterministic/extractive, not LLM-judged.

| Metric | Baseline | Advanced |
| --- | ---: | ---: |
| recall at 5 | 0.9231 | 0.9231 |
| recall at 12 | 0.9231 | 1.0 |
| mrr | 0.6269 | 0.7521 |
| correct document rate | 0.6923 | 0.8462 |
| correct page rate | 0.6923 | 0.6923 |
| citation precision | 0.3226 | 0.2432 |
| citation precision per citation | 0.3846 | 0.2632 |
| citation completeness | 0.7143 | 0.6429 |
| unsupported claim rate | 0.0 | 0.0 |
| insufficient evidence accuracy | 0.8125 | 0.8125 |
| average latency ms | 39.38 | 105.7 |
| average input tokens | 457.88 | 172.94 |
| average output tokens | 271.44 | 122.75 |
| corrective retry rate | 0.0 | 0.0 |

## Contextual retrieval ablation

Dense retrieval over the held-out test split; the only changed input is original versus contextual chunk text.

| Retrieval metric | Original text | Contextual text |
| --- | ---: | ---: |
| recall at 5 | 0.5385 | 0.9231 |
| recall at 12 | 0.7692 | 1.0 |
| mrr | 0.4918 | 0.6365 |

Result: No improvement claim: advanced RAG did not beat the baseline on the guarded primary metrics.

Selected parameters: `{"bm25_retrieval_limit": 20, "context_max_chunks": 5, "dense_retrieval_limit": 10, "rerank_candidate_limit": 12, "reranker_score_threshold": 0.15, "rrf_bm25_weight": 1.0, "rrf_dense_weight": 1.0}`

Fusion: local_weighted_rrf — BM25 is a local lexical ranking and the collection has no sparse-vector index.
