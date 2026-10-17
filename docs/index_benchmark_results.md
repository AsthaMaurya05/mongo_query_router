# MongoDB Index Benchmark Results

Generated: 2026-10-16T08:14:20.240431+00:00

- Explain repetitions per query: 5
- Timing: median of executionTimeMillis
- Primary evidence: documents examined and query-plan stages

**Text-search baseline:** Rejected without text index (code 27)

| Query / state | Docs examined | Keys examined | Returned | Median ms | Stages | Notes |
|---|---:|---:|---:|---:|---|---|
| 1a. User orders — no indexes | 50000 | 0 | 71 | 75 | COLLSCAN |  |
| 2a. Latest 10 — no indexes | 50000 | 0 | 10 | 74 | COLLSCAN, SORT |  |
| 3a. September orders — no indexes | 50000 | 0 | 5302 | 76 | COLLSCAN |  |
| 4a. Products by category — no indexes | 200 | 0 | 40 | 0 | COLLSCAN |  |
| 5a. Regex wireless — no indexes | 200 | 0 | 6 | 0 | COLLSCAN |  |
| 2b. Latest 10 — user_id only | 71 | 71 | 10 | 0 | FETCH, IXSCAN, SORT |  |
| 1b. User orders — final indexes | 71 | 71 | 71 | 0 | FETCH, IXSCAN |  |
| 2c. Latest 10 — compound index | 10 | 10 | 10 | 0 | FETCH, IXSCAN, LIMIT |  |
| 3b. September orders — final indexes | 5302 | 5302 | 5302 | 15 | FETCH, IXSCAN |  |
| 4b. Products by category — final indexes | 40 | 40 | 40 | 0 | FETCH, IXSCAN |  |
| 5b. Regex wireless — final indexes | 200 | 0 | 6 | 0 | COLLSCAN | Unanchored regex; text index does not accelerate it |
| 5c. $text wireless — text index | 6 | 6 | 6 | 0 | FETCH, IXSCAN, TEXT_MATCH |  |
| 6. Covered user history query | 0 | 71 | 71 | 0 | IXSCAN, PROJECTION_COVERED | Expect docs examined = 0 |

## Interpretation

- COLLSCAN means MongoDB scanned collection documents.
- IXSCAN means MongoDB scanned index entries.
- A covered query can return results from an index without reading collection documents.
- Execution time is environment-dependent; examined counts are generally more useful for comparing plans.
