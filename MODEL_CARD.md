# DemandPilot model and decision card

## Intended use

Single-user local exploration of daily unit sales and reviewable inventory scenarios. Personal
portfolio prototype, not a production purchasing system. Human review is required before export;
the app never sends a purchase order.

## Models

- `seasonal_naive`: repeats the last seven observed days recursively.
- `mean_28`: holds the mean of the last 28 observed days constant.
- `ridge_1`, `ridge_10`: separately fitted ridge regressions per SKU, using the given regularization.

Features: lag 1, 7, 14 and 28; trailing mean 7 and 28; linear time in years; weekly sine/cosine;
annual sine/cosine. Calendar/time values are known in advance. Input scaling and target centering
are fit only from training rows. Intercept is represented by the training target mean, and other
coefficients solve the regularized normal equations. Predictions are floored at zero. Future lags
contain recursive predictions, never hidden future actuals.

The latest selected ridge coefficients, feature names and scaler values are saved in the report
when ridge is selected. If a baseline wins selection, it stays selected; there is no requirement that
the machine-learning candidate outperform a baseline.

## Selection and final comparison

Chronological 60/10/10/20 split; global minimum selection WAPE, or MAE when all selection actuals
are zero. Exact ties favor the simpler earlier candidate. Final test metrics do not select alpha.
Final forecasts are refit on all currently observed data only after the retrospective evaluation.

## Uncertainty

For each forecast horizon, take scaled absolute forecast errors from the calibration range.
Scale = trailing 28-day mean sales at that origin + 1. The empirical order statistic uses
ceil((n+1) × 0.9), capped to the largest available score. Daily and cumulative errors are calibrated
separately. Future radii use the latest SKU scale. Bounds are floored at zero; cumulative bounds
are also nondecreasing across horizons.

This borrows an order-statistic idea but does not establish exchangeability or a formal conformal
coverage guarantee. Calibration blocks share dates/SKUs, temporal dependence remains, and sparse
sales or shifts can make intervals wide or unreliable. Show coverage together with width, and do not
convert it into a service-level promise. Calibration origins advance seven days and their 28-day
windows overlap. Demo calibration has 56 SKU/origin blocks from seven origins, not 56 independent observations.

## Business rules

Protection period is lead time plus review period, bounded by the 28-day forecast horizon. The target
uses the cumulative upper band, not the sum of independent daily upper bands. MOQ and pack sizes
apply only when a shortfall is positive. No sales in the last 84 days holds purchasing at zero and
requests investigation. Quantities and cost estimates are scenario outputs, not purchase commitments.

## Evaluation provenance

Data generated locally with seed 20261112: weekly/annual patterns, trends, a late level shift,
occasional bursts, intermittent demand and a zero-sales SKU. No real client or independent external
benchmark. Time-based tests establish implementation behavior, not future business outcomes.

Before external claims: obtain permitted daily sales and inventory data, clarify missing-day and
stockout semantics, freeze an evaluation plan, and compare both forecasts and an inventory-policy
simulation against an appropriate business baseline. Evaluate SKU segments, horizon errors, bias,
calibration and actual operational costs separately.
