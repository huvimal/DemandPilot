# DemandPilot

Local sales forecasting and inventory review prototype. Fits a small ridge regression model,
compares it with simple baselines using chronological backtests, and produces reviewable
replenishment suggestions. No API key or language model is required.

## Run on Windows (Python 3.11+)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8508
```

Open http://127.0.0.1:8508. Vietnamese walkthrough: [HUONG_DAN.md](HUONG_DAN.md).
Model and business assumptions: [MODEL_CARD.md](MODEL_CARD.md).
Data provenance: [data/DATA_CARD.md](data/DATA_CARD.md).
Local synthetic validation snapshot: [VALIDATION.md](VALIDATION.md).
Portfolio narrative: [CASE_STUDY.md](CASE_STUDY.md).
Vietnamese publication steps: [HUONG_DAN_DANG_DU_AN.md](HUONG_DAN_DANG_DU_AN.md).

## Workflow

```mermaid
flowchart LR
    CSV[Sales and inventory CSV] --> V[Validate daily data]
    V --> S[60% initial history + 10% selection]
    S --> M[Choose one model]
    M --> C[10% interval calibration]
    C --> T[20% rolling final test]
    T --> F[Refit on all observed history]
    F --> R[28-day forecasts and stock suggestions]
    R --> H[Human review]
    H --> E[CSV and report ZIP]
```

## Implemented

- Strict daily CSV validation; missing dates never silently become zero sales.
- Up to 20 aligned SKUs with 420–1460 days each. Integer, nonnegative units.
- Four fixed candidates: weekly seasonal naive, trailing-28-day mean, ridge alpha 1 and ridge alpha 10.
- Ridge is actually fitted per SKU, using only past observations for lags, rolling means and scaling.
  The implementation uses standard-library linear algebra for this small feature set.
- Expanding-window, recursive 28-day forecasts; nonoverlapping selection/test blocks and overlapping weekly calibration origins.
- Separate time ranges for model selection, empirical interval calibration and final comparison.
- MAE, WAPE, signed bias, per-SKU errors, interval coverage and width.
- Empirical daily and cumulative sales bands, pooled across normalized SKU/origin errors.
- Order-up-to scenario using stock + on-order, lead/review period, MOQ, pack size and input unit cost.
- Before-lead warning uses current on-hand stock because arrival dates of on-order stock are unknown.
- No sales in the last 84 days holds purchase suggestions at zero for manual investigation.
- Explanations generated from the actual calculation, not free-form LLM claims.
- Review-bound ZIP export; rerunning or changing input invalidates the prior in-session export.
- Private local report history and reproducible JSON reports with data/inventory/code fingerprints.

## CSV contracts

`sales.csv`:

```csv
date,sku,units
2024-01-01,SKU001,12
2024-01-02,SKU001,15
```

Each SKU/date must occur exactly once; all SKUs must share the same complete daily calendar.
Include `units=0` only when that day genuinely had no recorded sales. Aggregate transactions first.

`inventory.csv`:

```csv
sku,as_of,stock_on_hand,on_order,lead_time_days,review_period_days,min_order_qty,pack_size,unit_cost_vnd
SKU001,2025-11-30,25,0,7,7,12,6,25000
```

The inventory SKU set must match sales. `as_of` is the **end of the final observed sales day**.
Lead time and review period are positive integers summing to at most 28 days. Pack size is positive;
other numeric inputs are nonnegative integers. Costs are VND before taxes and fees.

The sample above illustrates the schema, not a sufficient two-row dataset. Full synthetic inputs
contain 8 SKUs × 700 daily rows (5,600 rows), ending 2025-11-30. Forecasts therefore begin
2025-12-01, not the machine's current date.

## Evaluation

```powershell
.\.venv\Scripts\python.exe evaluate.py --output reports/evaluation-v1.json
```

Choose a fresh filename; the CLI refuses to overwrite reports. Exit 0 indicates successful execution,
not business benefit or a required accuracy threshold. Uploaded/custom CSV paths can be passed with
`--sales` and `--inventory`.

For 700 days, the first 420 days supply initial history. Days 420–489 select the model;
490–559 calibrate bands; 560–699 form the final test. Only complete 28-day blocks are scored.
Selection/test origins advance 28 days; calibration origins advance seven days, so calibration
windows overlap and must not be counted as independent observations.
The leftover days in a range are not scored but can enter later origins as already observed history.
At every origin, refitting uses observations strictly before that origin. Test labels from earlier
completed test blocks can be used at later origins, matching sequential operation. Candidate family
and regularization selection remain fixed from the selection stage.

WAPE = sum(abs(actual - prediction)) / sum(actual); lower is better. WAPE is undefined for an
all-zero denominator and is reported as null; MAE still applies. WAPE is **not** forecast accuracy
and should not be rewritten as `100% - WAPE`. Global WAPE favors high-volume SKUs; inspect the
per-SKU results as well.

The seeded synthetic demo is useful for verifying the workflow, not external evidence of forecasting
quality, reduced stockouts or cost savings. The author knows the generator. Keep real evaluation data
separate and freeze model choices before checking it.

## Replenishment calculation

For protection period `P = lead_time_days + review_period_days`:

1. Target = ceil(empirical cumulative upper sales bound at P).
2. Inventory position = stock_on_hand + on_order (no backorders modeled).
3. Shortfall = max(0, target - position).
4. If shortfall is positive: order = pack_size × ceil(max(shortfall, MOQ) / pack_size).
5. If the last 84 observed days have zero sales: hold the suggestion at zero for manual review.
6. Estimated purchase cost = suggested quantity × supplied unit cost.

All on-order stock is assumed to arrive before the protection period ends. This is a planning
assumption, not validated by the input schema. Check actual inbound dates before acting.
An excess flag is a demo heuristic: position > 2 × max(1, cumulative upper bound at P).

## Limitations

- Forecasts observed sales, not latent demand suppressed by stockouts. No stockout censoring correction.
- No promotion, holiday, returns, price elasticity or supplier uncertainty inputs.
- Empirical bands use pooled, dependent time-series errors. Nominal 90% does not guarantee 90%
  coverage or a 90% stock service level. Cumulative bounds are made nondecreasing across horizons.
- At least eight SKU/origin calibration blocks are needed; otherwise point forecasts remain available
  but no interval-based order suggestions are produced. Few-SKU datasets may need more history/SKUs.
- No automatic purchasing, budget optimization, authenticated approval or multi-user isolation.
- Local reviewer labels and report hashes do not provide an immutable or authenticated audit.
- Historical accuracy is not an inventory-policy simulation: no claim of fewer stockouts or higher profit.

## Method reference

The evaluation follows the general principle of forecasting from past observations and checking
future periods, as discussed in [Forecasting: Principles and Practice — The forecaster's toolbox](https://otexts.com/fpp3/toolbox.html).
The small ridge model, pooled calibration and planning rules here are this project's implementation;
they should not be interpreted as methods guaranteed or endorsed by that reference.
