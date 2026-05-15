# Multi-seed robustness analysis

**Seeds tested:** [13, 42, 137]
**Configurations:** 12 per-attribute outcomes (2 datasets × 2 attributes × 3 seeds)

## Aggregate per (dataset, attribute)

| dataset   | attribute   |   n_seeds |   baseline_eo_mean |   baseline_eo_std |   pre_rollback_eo_mean |   pre_rollback_eo_std |   p2_delta_mean |   p2_delta_std |   p2_delta_min |   p2_delta_max |   rollback_rate |   n_synthesis_mean |   provenance_nodes_mean |
|:----------|:------------|----------:|-------------------:|------------------:|-----------------------:|----------------------:|----------------:|---------------:|---------------:|---------------:|----------------:|-------------------:|------------------------:|
| adult     | race        |         3 |             0.1988 |            0.0237 |                 0.3192 |                0.018  |         -0.1204 |         0.0228 |        -0.1467 |        -0.1066 |               1 |               3666 |                 14.6667 |
| adult     | sex         |         3 |             0.0515 |            0.005  |                 0.0818 |                0.0152 |         -0.0303 |         0.0102 |        -0.0413 |        -0.021  |               1 |               3666 |                 14.6667 |
| compas    | race        |         3 |             0.33   |            0.0203 |                 0.3137 |                0.0064 |          0.0162 |         0.0144 |         0.0012 |         0.0298 |               1 |               1671 |                 13.3333 |
| compas    | sex         |         3 |             0.0988 |            0.0014 |                 0.1331 |                0.0286 |         -0.0343 |         0.0273 |        -0.0658 |        -0.0172 |               1 |               1671 |                 13.3333 |

## Robustness pattern

| Dataset | Attribute | P2 < 0 (seeds) | Rollback executed | Signal |
|---|---|---|---|---|
| ADULT | race | 3/3 | 3/3 | **P2 fails consistently** |
| ADULT | sex | 3/3 | 3/3 | **P2 fails consistently** |
| COMPAS | race | 0/3 | 3/3 | **P2 passes consistently** |
| COMPAS | sex | 3/3 | 3/3 | **P2 fails consistently** |