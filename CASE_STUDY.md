# DemandPilot — Sales Forecasting and Inventory Review

## Problem and scope

Retail planning needs both a forecast and an understandable calculation connecting it to inventory.
DemandPilot is a personal, AI-assisted Python project demonstrating that workflow locally. It is not
a paid client delivery, live purchasing service or evidence of measured business savings.

## Workflow

Validate daily sales and an end-of-day inventory snapshot, compare four predefined forecasting
candidates, calibrate empirical bands, evaluate later periods, refit the selected model and produce
28-day forecasts. Translate cumulative forecast bounds into reviewable order-up-to suggestions.
Export requires a human acknowledgement bound to the current report.

## Technical choices

- Ridge regression is fitted per SKU using past lags, rolling means and known calendar/time features.
- Training-only scaling and recursive predictions avoid feeding future actuals into forecast features.
- Time ranges are separated: 60% initial history, 10% model selection, 10% interval calibration,
  20% final testing. Calibration windows overlap; selection/test blocks do not.
- Earlier observed test blocks may enter later rolling-origin fits, but final-test scores do not
  select the model or regularization.
- Stock suggestions account for on-hand and on-order units, lead/review periods, MOQ and pack size.
  No recent sales holds purchase suggestions at zero for manual investigation.
- Explanations are templates populated by the calculation. No LLM API is required.
- No purchase orders are transmitted. Reviewer names are local labels, not authenticated identities.

## Verified development results

32 automated tests passed during local verification. Huni subsequently ran the supplied evaluation
and saved `reports/my-evaluation-v1.json`; the publication preparation inspected that report.

The synthetic dataset has eight SKUs and 700 daily observations per SKU. Each model was scored on
1,120 daily final-test predictions across five forecast origins.

| Candidate | Test MAE (units/day) | Test WAPE |
|---|---:|---:|
| Seasonal naive | 2.5580 | 12.50% |
| Trailing mean, 28 days | 3.9781 | 19.44% |
| Ridge alpha 1 | 1.7813 | 8.70% |
| Ridge alpha 10, selected before test | 1.7894 | 8.74% |

Ridge alpha 10 remains selected despite alpha 1's slightly lower test error. Selecting again from
the final-test scores would turn that comparison into another tuning step.

Daily empirical interval coverage was 95.54%, with mean width 18.36 units; cumulative coverage was
91.34%. These must be interpreted together. Calibration had 56 dependent SKU/origin blocks from
seven overlapping origins, so nominal coverage is not a formal guarantee or inventory service level.

## Limits and next evidence

The creator knows the synthetic generator. The figures do not establish external forecasting
quality, reduced stockouts, saved money or higher profit. Observed sales can understate demand
when products are out of stock; this prototype does not correct that censoring.

Before operational use, evaluate on permitted real data with a frozen protocol, validate inbound
delivery assumptions and simulate an inventory policy against a business baseline. See
[MODEL_CARD.md](MODEL_CARD.md) and [VALIDATION.md](VALIDATION.md) for the full scope.
