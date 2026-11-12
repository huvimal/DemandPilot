# Local validation snapshot — 2026-11-12

32 automated tests passed in the project's Python 3.11 environment. Tests cover strict inputs,
known baseline behavior, constant/zero-series ridge behavior, zero-denominator metrics, temporal
cutoffs, changing final-test labels without changing selection/calibration, inventory arithmetic,
zero-recent-sales holds, report-bound export and Streamlit review/invalidation flows.

Synthetic dataset: eight SKUs, 700 days each, 2024-01-01 to 2025-11-30. No real client data.
Five final-test origins × eight SKUs × 28 days = 1,120 scored daily points per candidate.

| Candidate | Final-test MAE (units/day) | Final-test WAPE |
|---|---:|---:|
| seasonal_naive | 2.5580 | 12.4995% |
| mean_28 | 3.9781 | 19.4382% |
| ridge_1 | 1.7813 | 8.7043% |
| ridge_10 — selected before test | 1.7894 | 8.7435% |

Selection picked `ridge_10`; it remains selected even though `ridge_1` happens to have a slightly
lower final-test error. This prevents the final comparison from becoming another tuning stage.

The selected model's empirical daily interval coverage was 95.54%, mean daily width 18.36 units;
cumulative coverage across scored horizons was 91.34%. Calibration used 56 SKU/origin blocks
from seven overlapping origins. These dependent observations do not establish a formal coverage
or inventory service-level guarantee. Wide intervals can improve coverage without sharper forecasts.

For the demo snapshot, forecasts run 2025-12-01 through 2025-12-28. SKU001's 14-day empirical
upper sales bound is approximately 351.796, yielding target 352. With 25 on hand, no on-order,
MOQ 12 and pack size 6, the shortfall 327 rounds to a suggestion of 330 units. At input unit cost
25,000 VND, the estimated purchase amount is 8,250,000 VND. SKU008 is held for manual review
because its last 84 observed days have no sales.

These are arithmetic and model-development results on a known synthetic generator. They do not
measure real forecast accuracy, purchasing benefit, fewer stockouts, profit or cost savings.

Reproduce with a fresh filename:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 evaluate.py --output reports/reproduce-v1.json
```

Full generated JSON reports include data, inventory and code fingerprints. They are ignored by Git
because custom reports may contain private sales observations.
