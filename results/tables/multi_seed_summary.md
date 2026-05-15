# Multi-seed robustness analysis

**Seeds tested:** [7, 13, 23, 42, 71, 101, 137, 211, 313, 911]
**Configurations:** 40 per-attribute outcomes (2 datasets × 2 attributes × 10 seeds)

## Aggregate per (dataset, attribute)

| dataset   | attribute   |   n_seeds |   baseline_eo_mean |   baseline_eo_std |   pre_rollback_eo_mean |   pre_rollback_eo_std |   p2_delta_mean |   p2_delta_std |   p2_delta_min |   p2_delta_max |   rollback_rate |   n_synthesis_mean |   provenance_nodes_mean |
|:----------|:------------|----------:|-------------------:|------------------:|-----------------------:|----------------------:|----------------:|---------------:|---------------:|---------------:|----------------:|-------------------:|------------------------:|
| adult     | race        |        10 |             0.2024 |            0.0134 |                 0.3297 |                0.018  |         -0.1273 |         0.0191 |        -0.1505 |        -0.1022 |               1 |             4066   |                    14.8 |
| adult     | sex         |        10 |             0.0532 |            0.0106 |                 0.0863 |                0.0116 |         -0.033  |         0.0135 |        -0.0545 |        -0.0108 |               1 |             4066   |                    14.8 |
| compas    | race        |        10 |             0.3228 |            0.013  |                 0.3242 |                0.0113 |         -0.0014 |         0.0162 |        -0.029  |         0.0298 |               1 |             1534.5 |                    13.1 |
| compas    | sex         |        10 |             0.0936 |            0.005  |                 0.1226 |                0.0169 |         -0.029  |         0.0159 |        -0.0658 |        -0.0091 |               1 |             1534.5 |                    13.1 |

## Robustness pattern

| Dataset | Attribute | P2 < 0 (seeds) | Rollback executed | Signal |
|---|---|---|---|---|
| ADULT | race | 10/10 | 10/10 | **P2 fails consistently** |
| ADULT | sex | 10/10 | 10/10 | **P2 fails consistently** |
| COMPAS | race | 6/10 | 10/10 | P2 mixed |
| COMPAS | sex | 10/10 | 10/10 | **P2 fails consistently** |