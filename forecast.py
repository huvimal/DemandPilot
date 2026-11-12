"""Small fitted ridge model with train-only scaling and recursive forecasts."""
import math
from datetime import timedelta
from statistics import fmean

MODELS = ('seasonal_naive', 'mean_28', 'ridge_1', 'ridge_10')
HORIZON = 28
FEATURE_NAMES = ['lag_1', 'lag_7', 'lag_14', 'lag_28', 'mean_7', 'mean_28', 'time_years',
                 'weekday_sin', 'weekday_cos', 'annual_sin', 'annual_cos']


def features(history, day, start):
    if len(history) < 28:
        raise ValueError('Cần 28 giá trị quá khứ cho đặc trưng.')
    week = 2 * math.pi * day.weekday() / 7
    year = 2 * math.pi * (day - start).days / 365.25
    return [history[-1], history[-7], history[-14], history[-28],
            fmean(history[-7:]), fmean(history[-28:]), (day - start).days / 365.25,
            math.sin(week), math.cos(week), math.sin(year), math.cos(year)]


def solve(matrix, target):
    n = len(target)
    augmented = [list(matrix[i]) + [target[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        if abs(divisor) < 1e-12:
            raise ValueError('Ma trận không giải được.')
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(n):
            if row != col:
                factor = augmented[row][col]
                augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[col])]
    return [row[-1] for row in augmented]


def fit_ridge(values, start, alpha):
    if len(values) < 56 or alpha <= 0:
        raise ValueError('Ridge cần ít nhất 56 ngày và alpha > 0.')
    x = [features(values[:i], start + timedelta(days=i), start) for i in range(28, len(values))]
    y = values[28:]
    width = len(x[0])
    means = [fmean(row[j] for row in x) for j in range(width)]
    scales = [math.sqrt(fmean((row[j] - means[j]) ** 2 for row in x)) or 1.0 for j in range(width)]
    normalized = [[(row[j] - means[j]) / scales[j] for j in range(width)] for row in x]
    center = fmean(y)
    xtx = [[sum(row[i] * row[j] for row in normalized) + (alpha if i == j else 0)
            for j in range(width)] for i in range(width)]
    xty = [sum(row[j] * (actual - center) for row, actual in zip(normalized, y)) for j in range(width)]
    return {'means': means, 'scales': scales, 'coefficients': solve(xtx, xty), 'target_mean': center,
            'training_count': len(values), 'alpha': alpha, 'feature_names': FEATURE_NAMES}


def forecast(values, start, horizon=HORIZON, model='seasonal_naive'):
    if model not in MODELS or not 1 <= horizon <= HORIZON or len(values) < 56:
        raise ValueError('Model, horizon hoặc độ dài lịch sử không hợp lệ.')
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Lịch sử cần các số hữu hạn không âm.')
    fitted = fit_ridge(values, start, float(model.split('_')[1])) if model.startswith('ridge_') else None
    history = list(values)
    mean = fmean(values[-28:])
    output = []
    for step in range(horizon):
        if model == 'seasonal_naive':
            value = history[-7]
        elif model == 'mean_28':
            value = mean
        else:
            row = features(history, start + timedelta(days=len(history)), start)
            value = fitted['target_mean'] + sum(weight * (x - mu) / scale for weight, x, mu, scale in
                zip(fitted['coefficients'], row, fitted['means'], fitted['scales']))
        if not math.isfinite(value):
            raise ValueError('Mô hình sinh giá trị không hữu hạn.')
        value = max(0.0, value)
        # Predictions, never future actuals, supply recursive lags.
        history.append(value)
        output.append(value)
    return output


def metrics(actuals, predictions):
    if len(actuals) != len(predictions) or not actuals:
        raise ValueError('Cần hai dãy cùng độ dài và không rỗng.')
    absolute = sum(abs(a - p) for a, p in zip(actuals, predictions))
    return {'mae': absolute / len(actuals),
            'wape': absolute / sum(actuals) if sum(actuals) else None,
            'bias': sum(p - a for a, p in zip(actuals, predictions)) / len(actuals), 'points': len(actuals)}


def blocks(start, end, horizon=HORIZON):
    return list(range(start, end - horizon + 1, horizon))


def backtest(series, dates, origins, models=MODELS):
    results = {model: [] for model in models}
    for origin in origins:
        for sku, values in series.items():
            for model in models:
                predicted = forecast(values[:origin], dates[0], HORIZON, model)
                results[model].append({'sku': sku, 'origin': dates[origin].isoformat(),
                    'train_through': dates[origin - 1].isoformat(), 'origin_index': origin,
                    'actual': values[origin:origin + HORIZON], 'predicted': predicted,
                    'scale': fmean(values[max(0, origin - 28):origin]) + 1.0})
    return results


def summarize(cases):
    return metrics([a for case in cases for a in case['actual']], [p for case in cases for p in case['predicted']])


def quantile(scores, coverage=.9):
    if not scores:
        raise ValueError('Không đủ sai số hiệu chỉnh.')
    ordered = sorted(scores)
    index = min(len(ordered) - 1, math.ceil((len(ordered) + 1) * coverage) - 1)
    return ordered[index]


def calibrate(cases):
    if len(cases) < 8:
        return None
    daily, cumulative = [], []
    for step in range(HORIZON):
        daily.append(quantile([abs(c['actual'][step] - c['predicted'][step]) / c['scale'] for c in cases]))
        cumulative.append(quantile([abs(sum(c['actual'][:step + 1]) - sum(c['predicted'][:step + 1])) / c['scale'] for c in cases]))
    return {'daily': daily, 'cumulative': cumulative, 'calibration_blocks': len(cases),
            'nominal_coverage': .9, 'method': 'pooled scaled absolute errors; empirical, not guaranteed coverage'}


def bounds(predictions, scale, calibration):
    if calibration is None:
        return None
    cumulative = 0.0
    previous_lower, previous_upper = 0.0, 0.0
    output = []
    for i, predicted in enumerate(predictions):
        cumulative += predicted
        daily_radius = calibration['daily'][i] * scale
        cumulative_radius = calibration['cumulative'][i] * scale
        cumulative_lower = max(previous_lower, cumulative - cumulative_radius)
        cumulative_upper = max(previous_upper, cumulative + cumulative_radius)
        output.append({'point': predicted, 'lower': max(0, predicted - daily_radius), 'upper': predicted + daily_radius,
                       'cumulative_point': cumulative, 'cumulative_lower': cumulative_lower,
                       'cumulative_upper': cumulative_upper})
        previous_lower, previous_upper = cumulative_lower, cumulative_upper
    return output
