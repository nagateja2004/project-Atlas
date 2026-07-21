# Atlas RAG Evaluation

Synthetic test split; tuning used the development split only. Generation and scoring are deterministic/extractive, not LLM-judged.

| Metric | Baseline | Advanced |
| --- | ---: | ---: |
| recall at 5 | 0.75 | 0.75 |
| recall at 12 | 0.75 | 1.0 |
| mrr | 1.0 | 1.0 |
| correct document rate | 1.0 | 0.0 |
| correct page rate | 1.0 | 0.0 |
| citation precision | 0.8333 | 0.0 |
| citation completeness | 0.6667 | 0.0 |
| unsupported claim rate | 0.0 | 0.0 |
| insufficient evidence accuracy | 0.6667 | 0.3333 |
| average latency ms | 1.45 | 22.06 |
| average input tokens | 413.33 | 94.0 |
| average output tokens | 227.33 | 10.0 |
| corrective retry rate | 0.0 | 1.0 |

## Contextual retrieval ablation

Dense retrieval over the held-out test split; the only changed input is original versus contextual chunk text.

| Retrieval metric | Original text | Contextual text |
| --- | ---: | ---: |
| recall at 5 | 0.5 | 0.75 |
| recall at 12 | 0.5 | 0.75 |
| mrr | 0.5 | 1.0 |

Result: No improvement claim: advanced RAG did not beat the baseline on the guarded primary metrics.

Selected parameters: `{"bm25_retrieval_limit": 10, "context_max_chunks": 5, "dense_retrieval_limit": 20, "rerank_candidate_limit": 8, "reranker_score_threshold": 0.3, "rrf_bm25_weight": 1.5, "rrf_dense_weight": 1.0}`

Fusion: local_weighted_rrf — BM25 is a local lexical ranking and the collection has no sparse-vector index.
