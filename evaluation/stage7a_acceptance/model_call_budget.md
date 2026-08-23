# Model Call Budget Summary

Maximum observed in the three live Agentic smoke runs:

| Call | Ticket maximum | Observed maximum |
|---|---:|---:|
| qwen-plus decomposition | 1 | 1 |
| knowledge query embeddings | 4 | 4 |
| knowledge reranks | 4 | 4 |
| task recall embeddings | 5 | 5 |
| task final rerank | 1 | 1 |
| memory query embedding | 1 when enabled | 0 (reused original query embedding) |
| memory rerank | 1 when enabled | 1 |
| qwen-plus explanation | 1 | 1 |

No loops, retries, replanning, checkpointer calls, web calls, or arbitrary tool calls exist in the graph.

