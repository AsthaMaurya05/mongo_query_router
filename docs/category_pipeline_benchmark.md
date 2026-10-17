# Revenue-by-category pipeline benchmark

Date range: 2026-01-01 to 2026-10-01 (end exclusive), delivered orders only.
Time = median of 5 real runs. Counters = one explain(executionStats) run.

| Metric | A: lookup each item | B: group by product first |
|---|---|---|
| Median time (ms) | 9,372 | 366 |
| Docs examined by $match | 47,384 | 47,384 |
| Index used by $match | orders_created_at | orders_created_at |
| $lookup stages | 2 | 2 |
| $lookup docs examined | 83,913 | 209 |
| Identical results | yes | |
| Speed-up | | 25.6x |
