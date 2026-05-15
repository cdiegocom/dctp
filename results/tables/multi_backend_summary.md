# Multi-backend robustness analysis

**Backends tested:** Gaussian Copula, CTGAN, TVAE
**Seeds tested:** [13, 42, 137]
**Note:** Adult runs used a 5,000-record subsample (with seed-specific subsampling) to make CTGAN and TVAE tractable within typical compute budgets; the COMPAS runs used the full filtered dataset (6,130 records).

## Aggregate per (dataset, backend, attribute)

| dataset   | backend         | attribute   |   n_seeds |   baseline_eo_mean |   p2_delta_mean |   p2_delta_std |   p1_pass_rate |   rollback_rate |   n_p2_valid |
|:----------|:----------------|:------------|----------:|-------------------:|----------------:|---------------:|---------------:|----------------:|-------------:|
| adult     | ctgan           | race        |         3 |             0.4766 |          0.056  |         0.0996 |           0.75 |          1      |            3 |
| adult     | ctgan           | sex         |         3 |             0.0644 |         -0.1388 |         0.0153 |           0.75 |          1      |            3 |
| adult     | gaussian_copula | race        |         3 |             0.1988 |         -0.1204 |         0.0228 |           1    |          1      |            3 |
| adult     | gaussian_copula | sex         |         3 |             0.0515 |         -0.0303 |         0.0102 |           1    |          1      |            3 |
| adult     | tvae            | race        |         3 |             0.4766 |        nan      |       nan      |           0    |          0      |            0 |
| adult     | tvae            | sex         |         3 |             0.0644 |        nan      |       nan      |           0    |          0      |            0 |
| compas    | ctgan           | race        |         3 |             0.33   |          0.0156 |         0.0395 |           1    |          0.6667 |            3 |
| compas    | ctgan           | sex         |         3 |             0.0988 |          0.0308 |         0.0173 |           1    |          0.6667 |            3 |
| compas    | gaussian_copula | race        |         3 |             0.33   |          0.0162 |         0.0144 |           1    |          1      |            3 |
| compas    | gaussian_copula | sex         |         3 |             0.0988 |         -0.0343 |         0.0273 |           1    |          1      |            3 |
| compas    | tvae            | race        |         3 |             0.33   |          0.0389 |         0.0191 |           0.7  |          0      |            3 |
| compas    | tvae            | sex         |         3 |             0.0988 |          0.027  |         0.037  |           0.7  |          0      |            3 |