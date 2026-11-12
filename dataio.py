"""Strict daily sales and point-in-time inventory inputs. No silent gap filling."""
import csv
import hashlib
import io
import json
import math
import re
from datetime import date, timedelta

SALES_COLUMNS = ['date', 'sku', 'units']
INVENTORY_COLUMNS = ['sku', 'as_of', 'stock_on_hand', 'on_order', 'lead_time_days',
                     'review_period_days', 'min_order_qty', 'pack_size', 'unit_cost_vnd']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def parse_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ValueError('Ngày cần có dạng YYYY-MM-DD.') from None


def integer(value, field, minimum=0, maximum=1_000_000_000):
    if not isinstance(value, str) or not re.fullmatch(r'\d+', value):
        raise ValueError(f'{field} cần là số nguyên không âm, không có dấu phân cách.')
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f'{field} phải nằm trong [{minimum}, {maximum}].')
    return result


def records(data, columns):
    if len(data) > 5_000_000:
        raise ValueError('CSV tối đa 5 MB.')
    try:
        reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), strict=True)
        if reader.fieldnames != columns:
            raise ValueError('CSV cần đúng các cột theo thứ tự: ' + ','.join(columns))
        rows = []
        for row in reader:
            if len(rows) >= 30_000 or None in row or any(v is None for v in row.values()):
                raise ValueError('CSV sai số cột hoặc vượt 30.000 dòng.')
            row = {k: v.strip() for k, v in row.items()}
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', row['sku']):
                raise ValueError('SKU cần 1–48 chữ Latin, số, _ hoặc -; phân biệt chữ hoa/thường.')
            rows.append(row)
        if not rows:
            raise ValueError('CSV không có dữ liệu.')
        return rows
    except (UnicodeDecodeError, csv.Error):
        raise ValueError('CSV không hợp lệ; dùng UTF-8 và dấu phẩy phân cột.') from None


def read_sales(data):
    grouped = {}
    for row in records(data, SALES_COLUMNS):
        sku, day = row['sku'], parse_date(row['date'])
        values = grouped.setdefault(sku, {})
        if day in values:
            raise ValueError(f'{sku}: trùng ngày {day}; hãy tổng hợp trước khi nhập.')
        values[day] = integer(row['units'], 'units', maximum=1_000_000)
    if len(grouped) > 20:
        raise ValueError('Tối đa 20 SKU.')
    series, reference_dates = {}, None
    for sku in sorted(grouped):
        ordered = sorted(grouped[sku])
        if not 420 <= len(ordered) <= 1460:
            raise ValueError(f'{sku}: cần 420–1460 ngày lịch sử.')
        expected = [ordered[0] + timedelta(days=i) for i in range(len(ordered))]
        if ordered != expected:
            raise ValueError(f'{sku}: có ngày bị thiếu. Chỉ điền 0 nếu thực sự không có bán hàng.')
        if reference_dates is not None and ordered != reference_dates:
            raise ValueError('Tất cả SKU phải có cùng khoảng ngày đầy đủ.')
        reference_dates = ordered
        series[sku] = [grouped[sku][day] for day in ordered]
    return reference_dates, series


def read_inventory(data, skus, last_day):
    inventory = {}
    for source in records(data, INVENTORY_COLUMNS):
        sku = source['sku']
        if sku in inventory:
            raise ValueError('Inventory có SKU bị trùng.')
        if parse_date(source['as_of']) != last_day:
            raise ValueError('as_of phải bằng ngày cuối của lịch sử bán hàng; snapshot tại cuối ngày.')
        row = {'sku': sku, 'as_of': source['as_of']}
        for field in INVENTORY_COLUMNS[2:]:
            row[field] = integer(source[field], field, minimum=1 if field in ('lead_time_days', 'review_period_days', 'pack_size') else 0,
                                 maximum=28 if field in ('lead_time_days', 'review_period_days') else 1_000_000_000)
        if row['lead_time_days'] + row['review_period_days'] > 28:
            raise ValueError('lead_time_days + review_period_days tối đa 28.')
        inventory[sku] = row
    if set(inventory) != set(skus):
        raise ValueError('Danh sách SKU trong hai CSV phải khớp hoàn toàn.')
    return inventory


def csv_bytes(rows, columns):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        values = {}
        for field in columns:
            value = '' if row.get(field) is None else str(row[field])
            values[field] = "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r')) else value
        writer.writerow(values)
    return out.getvalue().encode('utf-8-sig')
