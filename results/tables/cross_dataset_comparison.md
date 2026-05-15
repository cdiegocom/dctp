# Cross-dataset results

## Pipeline summary

| Dataset   | Protected Attribute   |   N records (validated) |   N records (quarantined) |   Baseline EO gap |   Baseline DP gap |   N synthesis batches |   N synthetic accepted |   Pre-rollback EO gap |   P2 delta (pre-rollback) | Rollback executed   |   Final EO gap |   Provenance nodes |   Lineage completeness |   Decision coverage |
|:----------|:----------------------|------------------------:|--------------------------:|------------------:|------------------:|----------------------:|-----------------------:|----------------------:|--------------------------:|:--------------------|---------------:|-------------------:|-----------------------:|--------------------:|
| ADULT     | race                  |                   30162 |                      2399 |            0.2254 |            0.1813 |                     4 |                   4666 |                0.332  |                   -0.1066 | True                |         0.2254 |                 15 |                      1 |                   1 |
| ADULT     | sex                   |                   30162 |                      2399 |            0.0513 |            0.1562 |                     4 |                   4666 |                0.0799 |                   -0.0286 | True                |         0.0513 |                 15 |                      1 |                   1 |
| COMPAS    | race                  |                    6130 |                         0 |            0.335  |            0.318  |                     4 |                   2061 |                0.3173 |                    0.0177 | True                |         0.335  |                 14 |                      1 |                   1 |
| COMPAS    | sex                   |                    6130 |                         0 |            0.1003 |            0.1264 |                     4 |                   2061 |                0.1661 |                   -0.0658 | True                |         0.1003 |                 14 |                      1 |                   1 |


## Per-batch synthesis outcomes (P1-P4)

| Dataset   | Target                  |   N generated |   N accepted |   P1 JS divergence | P1 passed   |   P2 delta | P2 passed   |   P3 verification rate |   P4 plausibility rate |
|:----------|:------------------------|--------------:|-------------:|-------------------:|:------------|-----------:|:------------|-----------------------:|-----------------------:|
| ADULT     | race=Amer-Indian-Eskimo |           143 |          143 |             0.0795 | True        |    -0.1066 | False       |                      1 |                      1 |
| ADULT     | race=Black              |          1408 |         1408 |             0.0499 | True        |    -0.1066 | False       |                      1 |                      1 |
| ADULT     | race=Other              |           115 |          115 |             0.0476 | True        |    -0.1066 | False       |                      1 |                      1 |
| ADULT     | race=White              |          3000 |         3000 |             0.0245 | True        |    -0.1066 | False       |                      1 |                      1 |
| COMPAS    | race=Caucasian          |          1051 |         1051 |             0.0031 | True        |     0.0177 | True        |                      1 |                      1 |
| COMPAS    | race=Hispanic           |           254 |          254 |             0.0174 | True        |     0.0177 | True        |                      1 |                      1 |
| COMPAS    | race=Other              |           171 |          171 |             0.0117 | True        |     0.0177 | True        |                      1 |                      1 |
| COMPAS    | sex=Female              |           585 |          585 |             0.0035 | True        |    -0.0658 | False       |                      1 |                      1 |