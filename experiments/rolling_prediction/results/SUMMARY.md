# Rolling Prediction 결과

| Policy | Task | Existing STOPs | Initial Queries | Re-Prediction Queries | Total Prediction Queries | Matched Exec Events | Fallbacks | Reduction |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `executable_only` | Direct1 | 18 | 1 | 10 | 11 | 17 | 1 | 38.9% |
| `executable_only` | Direct2 | 4 | 1 | 2 | 3 | 4 | 0 | 25.0% |
| `executable_only` | Direct3 | 11 | 1 | 5 | 6 | 11 | 0 | 45.5% |
| `executable_only` | Direct4 | 7 | 1 | 5 | 6 | 7 | 0 | 14.3% |
| `executable_only` | **Total** | **40** | **4** | **22** | **26** | **39** | **1** | **35.0%** |
| `executable_args` | Direct1 | 18 | 1 | 18 | 19 | 12 | 6 | -5.6% |
| `executable_args` | Direct2 | 4 | 1 | 2 | 3 | 3 | 1 | 25.0% |
| `executable_args` | Direct3 | 11 | 1 | 9 | 10 | 10 | 1 | 9.1% |
| `executable_args` | Direct4 | 7 | 1 | 7 | 8 | 6 | 1 | -14.3% |
| `executable_args` | **Total** | **40** | **4** | **36** | **40** | **31** | **9** | **0.0%** |

> Reduction = `1 - (Total Prediction Queries / Existing STOPs)`.
> 이 값은 audit latency 또는 security improvement를 의미하지 않는다.
