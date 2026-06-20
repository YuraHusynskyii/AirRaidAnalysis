# AirRaidAnalysis — Evaluation Summary

## Global Baselines

| Model | MAE | RMSE | MAPE (%) |
|---|---:|---:|---:|
| seasonal_naive | 0.000 | 0.000 | 0.000 |
| linear_regression | 0.054 | 0.057 | 5.424 |
| arima | 0.504 | 0.544 | 50.357 |
| sarimax_s24 | 0.000 | 0.000 | 0.000 |
| xgboost | 0.000 | 0.000 | 0.013 |
| lightgbm | 0.219 | 0.219 | 21.875 |

## Regional lightgbm (Holdout)

| Region | MAE | RMSE | MAPE (%) |
|---|---:|---:|---:|
| Dnipro | 0.292 | 0.427 | 29.167 |
| Kharkiv | 0.208 | 0.315 | 20.833 |
| Kyiv | 0.417 | 0.479 | 41.667 |
| Lviv | 0.233 | 0.317 | 23.264 |
| Odesa | 0.292 | 0.427 | 29.167 |

## Regional seasonal_naive (Holdout)

| Region | MAE | RMSE | MAPE (%) |
|---|---:|---:|---:|
| Dnipro | 0.385 | 0.620 | 38.462 |
| Kharkiv | 0.308 | 0.555 | 30.769 |
| Kyiv | 0.692 | 0.832 | 69.231 |
| Lviv | 0.308 | 0.555 | 30.769 |
| Odesa | 0.308 | 0.555 | 30.769 |

## Notes

- Split: chronological holdout (no shuffle).
- Regional metrics use hourly counts per region.
- `sarimax_s24` is tuned on extended dataset when available.
- Boosting models: XGBoost and LightGBM on global feature matrix.
