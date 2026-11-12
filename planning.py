"""Transparent order-up-to suggestions. Never places an order."""
import io
import json
import math
import zipfile
from datetime import datetime, timezone

from dataio import csv_bytes, digest


def recommend(sku, inventory, forecast_rows, recent_sales_total=None):
    protection = inventory['lead_time_days'] + inventory['review_period_days']
    if len(forecast_rows) < protection:
        raise ValueError('Dự báo không đủ kỳ bảo vệ tồn kho.')
    end = forecast_rows[protection - 1]
    target = math.ceil(end['cumulative_upper'])
    position = inventory['stock_on_hand'] + inventory['on_order']
    shortfall = max(0, target - position)
    order = math.ceil(max(shortfall, inventory['min_order_qty']) / inventory['pack_size']) * inventory['pack_size'] if shortfall else 0
    hold = recent_sales_total == 0
    if hold:
        order = 0
    lead_demand = forecast_rows[inventory['lead_time_days'] - 1]['cumulative_point']
    lead_upper = forecast_rows[inventory['lead_time_days'] - 1]['cumulative_upper']
    point_shortage = inventory['stock_on_hand'] < lead_demand
    if hold:
        risk = 'no_recent_sales_manual_review'
    elif point_shortage:
        risk = 'point_forecast_shortage_before_lead'
    elif inventory['stock_on_hand'] < lead_upper:
        risk = 'uncertainty_exposure_before_lead'
    else:
        risk = 'no_shortage_in_current_scenario'
    result = {'sku': sku, 'protection_days': protection,
        'expected_sales': round(end['cumulative_point'], 3), 'empirical_upper_sales': round(end['cumulative_upper'], 3),
        'target_units': target, 'stock_on_hand': inventory['stock_on_hand'], 'on_order': inventory['on_order'],
        'inventory_position': position, 'suggested_order_units': order,
        'estimated_purchase_vnd': order * inventory['unit_cost_vnd'],
        'lead_time_days': inventory['lead_time_days'], 'lead_expected_sales': round(lead_demand, 3),
        'risk': risk,
        'excess_flag': position > 2 * max(1, end['cumulative_upper'])}
    result['explanation'] = (
        f"{sku}: kỳ bảo vệ {protection} ngày; dự báo bán {result['expected_sales']} đơn vị, "
        f"cận trên thực nghiệm {result['empirical_upper_sales']}. Tồn khả dụng theo giả định "
        f"= {inventory['stock_on_hand']} đang có + {inventory['on_order']} đang đặt = {position}. "
        f"Mục tiêu làm tròn lên {target}; đề xuất {order} đơn vị sau MOQ/quy cách đóng gói. "
        f"Chi phí mua ước tính {result['estimated_purchase_vnd']:,} VND. "
        'Giả định hàng đang đặt về trước cuối kỳ bảo vệ; cảnh báo trước lead time chỉ tính tồn đang có. '
        'Khoảng thực nghiệm không bảo đảm mức dịch vụ; cần người phụ trách duyệt.'
    )
    if hold:
        result['explanation'] += ' Không có lượng bán trong 84 ngày gần nhất: giữ đề xuất mua ở 0 và yêu cầu kiểm tra thủ công.'
    return result


def export_reviewed(report, reviewer, note, acknowledged):
    if not acknowledged or not reviewer.strip() or not note.strip():
        raise ValueError('Cần tên, ghi chú và xác nhận đã xem giả định nhập hàng.')
    if not report['recommendations']:
        raise ValueError('Không đủ dữ liệu hiệu chỉnh để lập đề xuất nhập hàng.')
    approval = {'reviewer': reviewer.strip()[:100], 'note': note.strip()[:1000],
                'at': datetime.now(timezone.utc).isoformat(), 'report_hash': digest(report),
                'scope': 'reviewed simulation only; no purchase order sent'}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        rec_columns = ['sku', 'protection_days', 'expected_sales', 'empirical_upper_sales', 'target_units',
                       'stock_on_hand', 'on_order', 'inventory_position', 'suggested_order_units',
                       'estimated_purchase_vnd', 'risk', 'excess_flag', 'explanation']
        archive.writestr('replenishment-reviewed.csv', csv_bytes(report['recommendations'], rec_columns))
        forecast_rows = [{'sku': sku, **row} for sku, rows in report['future'].items() for row in rows]
        archive.writestr('forecast.csv', csv_bytes(forecast_rows, ['sku', 'date', 'point', 'lower', 'upper',
            'cumulative_point', 'cumulative_lower', 'cumulative_upper']))
        archive.writestr('report.json', json.dumps(report, ensure_ascii=False, indent=2))
        archive.writestr('review.json', json.dumps(approval, ensure_ascii=False, indent=2))
    return out.getvalue()
