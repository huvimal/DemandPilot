"""Chronological selection / calibration / test with fixed predefined candidates."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import fmean

from dataio import read_sales, read_inventory, digest
from forecast import MODELS, HORIZON, blocks, backtest, summarize, calibrate, bounds, forecast, fit_ridge
from planning import recommend

ROOT = Path(__file__).resolve().parent


def code_hash():
    return digest({name: (ROOT / name).read_text(encoding='utf-8') for name in ('dataio.py', 'forecast.py', 'planning.py', 'pipeline.py')})


def run(sales_bytes, inventory_bytes):
    dates, series = read_sales(sales_bytes)
    inventory = read_inventory(inventory_bytes, series, dates[-1])
    n = len(dates)
    train_end, selection_end, calibration_end = int(n * .6), int(n * .7), int(n * .8)
    selection_origins = blocks(train_end, selection_end)
    # Weekly origins increase sample availability, but calibration windows overlap.
    calibration_origins = list(range(selection_end, calibration_end - HORIZON + 1, 7))
    test_origins = blocks(calibration_end, n)
    if not all((selection_origins, calibration_origins, test_origins)):
        raise ValueError('Không đủ khối 28 ngày cho các khoảng đánh giá.')
    selection = backtest(series, dates, selection_origins)
    selection_metrics = {model: summarize(cases) for model, cases in selection.items()}
    # Ties prefer simpler earlier candidates; final test labels do not select models.
    selected = min(MODELS, key=lambda model: (selection_metrics[model]['wape'] if
        selection_metrics[model]['wape'] is not None else selection_metrics[model]['mae'], MODELS.index(model)))
    calibration_cases = backtest(series, dates, calibration_origins, (selected,))[selected]
    calibration = calibrate(calibration_cases)
    tested = backtest(series, dates, test_origins)
    test_metrics = {model: summarize(cases) for model, cases in tested.items()}
    daily_hits, cumulative_hits, interval_points, widths = 0, 0, 0, []
    if calibration:
        for case in tested[selected]:
            band = bounds(case['predicted'], case['scale'], calibration)
            actual_sum = 0
            for actual, row in zip(case['actual'], band):
                actual_sum += actual
                daily_hits += row['lower'] <= actual <= row['upper']
                cumulative_hits += row['cumulative_lower'] <= actual_sum <= row['cumulative_upper']
                interval_points += 1
                widths.append(row['upper'] - row['lower'])
    per_sku = {sku: summarize([case for case in tested[selected] if case['sku'] == sku]) for sku in series}
    future, suggestions, fitted = {}, [], {}
    for sku, values in series.items():
        predicted = forecast(values, dates[0], HORIZON, selected)
        band = bounds(predicted, fmean(values[-28:]) + 1.0, calibration)
        if band:
            future[sku] = [{'date': (dates[-1] + timedelta(days=i + 1)).isoformat(), **row} for i, row in enumerate(band)]
            suggestions.append(recommend(sku, inventory[sku], future[sku], recent_sales_total=sum(values[-84:])))
        else:
            future[sku] = [{'date': (dates[-1] + timedelta(days=i + 1)).isoformat(), 'point': value}
                           for i, value in enumerate(predicted)]
        if selected.startswith('ridge_'):
            fitted[sku] = fit_ridge(values, dates[0], float(selected.split('_')[1]))
    warnings = [
        'Dự báo lượng bán quan sát được; không khôi phục nhu cầu bị mất vì hết hàng.',
        'Khoảng thực nghiệm gộp nhiều SKU và phụ thuộc thời gian; nominal 90% không bảo đảm coverage 90%.',
        'Refit ở mỗi rolling origin chỉ dùng lịch sử trước origin; mô hình được chọn trước phần test.',
        'Đề xuất không tối ưu ngân sách, chiết khấu, hư hỏng, công suất kho hoặc lịch về của từng đơn.',
        'Giải thích sinh bằng mẫu từ phép tính; đây không phải chatbot LLM.'
    ]
    if calibration is None:
        warnings.append('Có ít hơn 8 khối SKU/origin để hiệu chỉnh: chỉ dự báo điểm, chưa lập đề xuất nhập hàng.')
    return {
        'project': 'DemandPilot', 'version': '0.1', 'created_at': datetime.now(timezone.utc).isoformat(),
        'dataset_hash': digest({'dates': dates, 'series': series}), 'inventory_hash': digest(inventory),
        'code_hash': code_hash(),
        'data': {'skus': len(series), 'days_per_sku': n, 'start': dates[0].isoformat(), 'end': dates[-1].isoformat()},
        'protocol': {'horizon': HORIZON, 'selection_and_test_step': HORIZON, 'calibration_step': 7,
            'selection_start': dates[train_end].isoformat(),
            'calibration_start': dates[selection_end].isoformat(), 'test_start': dates[calibration_end].isoformat(),
            'selection_origins': [dates[i].isoformat() for i in selection_origins],
            'calibration_origins': [dates[i].isoformat() for i in calibration_origins],
            'test_origins': [dates[i].isoformat() for i in test_origins],
            'selection_rule': 'global minimum selection WAPE; MAE when all actuals are zero; simple-model tie break'},
        'selected_model': selected, 'selection_metrics': selection_metrics, 'test_metrics': test_metrics,
        'selected_test_by_sku': per_sku, 'calibration': calibration,
        'test_intervals': {'daily_coverage': daily_hits / interval_points if interval_points else None,
            'cumulative_coverage': cumulative_hits / interval_points if interval_points else None,
            'mean_daily_width': fmean(widths) if widths else None, 'points': interval_points},
        'future': future, 'recommendations': suggestions,
        'latest_ridge_fits': fitted,
        'selected_test_blocks': tested[selected],
        'warnings': warnings,
    }
