import hashlib
import io
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from dataio import read_sales, read_inventory, digest
from pipeline import run, code_hash
from planning import export_reviewed

ROOT = Path(__file__).resolve().parent
PRIVATE = Path(os.environ.get('DEMANDPILOT_DATA_DIR', str(ROOT / 'private')))
st.set_page_config(page_title='DemandPilot', page_icon='📦', layout='wide')
st.title('DemandPilot')
st.caption('Sales forecasting · Temporal backtesting · Inventory review')
st.info('Chạy hoàn toàn trên máy, không cần API key. Phần học máy là Ridge Regression được huấn luyện từ lịch sử. '
        'Giải thích dùng mẫu văn bản từ phép tính. Không tự gửi đơn mua hàng.')

with st.sidebar:
    st.header('Dữ liệu')
    source = st.radio('Chọn nguồn', ['Dữ liệu mẫu', 'CSV của tôi'])
    st.caption('Cần 420–1460 ngày liên tục/SKU; tối đa 20 SKU. Ngày không bán phải có units=0, không tự điền ngày thiếu.')
    if source == 'CSV của tôi':
        uploaded_sales = st.file_uploader('sales.csv', type='csv')
        uploaded_inventory = st.file_uploader('inventory.csv', type='csv')
    st.write('**Giao thức cố định**')
    st.caption('60% đầu cho lịch sử ban đầu; 10% chọn mô hình; 10% hiệu chỉnh khoảng; 20% cuối kiểm tra. '
               'Dự báo 28 ngày; selection/test không chồng lấn, hiệu chỉnh có origin mỗi 7 ngày và chồng lấn. '
               'Mỗi origin huấn luyện lại bằng lịch sử đã biết.')
    st.download_button('Tải CSV bán hàng mẫu', (ROOT / 'data' / 'sales.csv').read_bytes(), 'sales.csv', 'text/csv')
    st.download_button('Tải CSV tồn kho mẫu', (ROOT / 'data' / 'inventory.csv').read_bytes(), 'inventory.csv', 'text/csv')

if source == 'Dữ liệu mẫu':
    sales_bytes = (ROOT / 'data' / 'sales.csv').read_bytes()
    inventory_bytes = (ROOT / 'data' / 'inventory.csv').read_bytes()
    st.warning('Đang dùng 8 SKU × 700 ngày giả lập. Kết quả chỉ mô tả tình huống tổng hợp này.')
else:
    if uploaded_sales is None or uploaded_inventory is None:
        # Existing approvals never remain usable when the source changes.
        st.session_state.pop('report', None)
        st.session_state.pop('reviewed_zip', None)
        st.write('Tải đủ hai CSV để bắt đầu.')
        st.stop()
    sales_bytes, inventory_bytes = uploaded_sales.getvalue(), uploaded_inventory.getvalue()

identity = digest({'sales': hashlib.sha256(sales_bytes).hexdigest(),
                   'inventory': hashlib.sha256(inventory_bytes).hexdigest(), 'code': code_hash()})
if st.session_state.get('input_identity') != identity:
    st.session_state['input_identity'] = identity
    st.session_state.pop('report', None)
    st.session_state.pop('reviewed_zip', None)

try:
    dates, series = read_sales(sales_bytes)
    inventory = read_inventory(inventory_bytes, series, dates[-1])
except ValueError as error:
    st.error(str(error))
    st.stop()

st.subheader('1. Kiểm tra đầu vào')
a, b, c = st.columns(3)
a.metric('SKU', len(series))
b.metric('Ngày / SKU', len(dates))
c.metric('Snapshot cuối ngày', dates[-1].isoformat())
st.dataframe(list(inventory.values()), hide_index=True, width='stretch')
if st.button('Chạy backtest và lập dự báo', type='primary'):
    try:
        with st.spinner('Đang huấn luyện và kiểm tra theo thời gian...'):
            report = run(sales_bytes, inventory_bytes)
        st.session_state['report'] = report
        st.session_state.pop('reviewed_zip', None)
        folder = PRIVATE / 'runs'
        folder.mkdir(parents=True, exist_ok=True)
        filename = folder / (digest(report)[:20] + '.json')
        filename.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    except (ValueError, OSError) as error:
        st.session_state.pop('report', None)
        st.session_state.pop('reviewed_zip', None)
        st.error(str(error))

report = st.session_state.get('report')
if report is None:
    st.stop()
report_id = digest(report)
st.subheader('2. Đối chiếu mô hình')
st.write('Mô hình đã chọn từ giai đoạn selection:', report['selected_model'])
comparison = []
for model in report['selection_metrics']:
    comparison.append({'model': model, 'selection_MAE': report['selection_metrics'][model]['mae'],
        'selection_WAPE': report['selection_metrics'][model]['wape'],
        'test_MAE': report['test_metrics'][model]['mae'], 'test_WAPE': report['test_metrics'][model]['wape'],
        'selected_before_test': model == report['selected_model']})
st.dataframe(comparison, hide_index=True, width='stretch')
st.caption('WAPE là tỷ lệ sai số tuyệt đối, càng thấp càng tốt; 0.10 nghĩa là 10%, không phải “accuracy 90%”. '
           'Không chọn lại mô hình dựa trên cột test. SKU toàn số 0 có WAPE không xác định; xem MAE.')
with st.expander('Khoảng dự báo và ranh giới thời gian'):
    st.json({'protocol': report['protocol'], 'test_intervals': report['test_intervals'],
             'calibration_blocks': report['calibration']['calibration_blocks'] if report['calibration'] else 0})
    st.caption('Coverage là tỷ lệ quan sát lọt trong khoảng thực nghiệm. Xem cùng độ rộng; khoảng rộng dễ có coverage cao. '
               'Đây không phải cam kết mức dịch vụ tồn kho.')

st.subheader('3. Dự báo theo SKU')
sku = st.selectbox('Chọn SKU', list(series))
past = pd.DataFrame({'date': dates[-84:], 'actual': series[sku][-84:]}).set_index('date')
future = pd.DataFrame(report['future'][sku]).set_index('date')
past.index = pd.to_datetime(past.index)
future.index = pd.to_datetime(future.index)
chart = pd.concat([past, future[[column for column in ('point', 'lower', 'upper') if column in future.columns]]])
st.line_chart(chart, x_label='Ngày', y_label='Đơn vị bán')
st.dataframe(future.reset_index(), hide_index=True, width='stretch')
st.write('Sai số test cho SKU:', report['selected_test_by_sku'][sku])

st.subheader('4. Đề xuất nhập hàng để rà soát')
for warning in report['warnings']:
    st.caption('• ' + warning)
if not report['recommendations']:
    st.warning('Chưa đủ khối hiệu chỉnh để tính cận trên và đề xuất nhập hàng. Vẫn có dự báo điểm.')
else:
    table = [{k: v for k, v in row.items() if k != 'explanation'} for row in report['recommendations']]
    st.dataframe(table, hide_index=True, width='stretch')
    selected = next(row for row in report['recommendations'] if row['sku'] == sku)
    st.write(selected['explanation'])
    st.caption('Cờ excess dùng quy tắc minh họa: inventory_position > 2 × max(1, cận trên kỳ bảo vệ). '
               'Chi phí là số lượng × đơn giá đầu vào, chưa gồm thuế/phí. Tên người duyệt là nhãn cục bộ, không xác thực.')
    with st.form('review_' + report_id):
        reviewer = st.text_input('Tên / bí danh người duyệt', max_chars=100)
        note = st.text_input('Ghi chú điều chỉnh hoặc quyết định vận hành', max_chars=1000)
        acknowledged = st.checkbox('Tôi đã đối chiếu tồn kho, lead time, MOQ, quy cách và giả định hàng đang đặt')
        reviewed = st.form_submit_button('Xác nhận rà soát báo cáo hiện tại')
    if reviewed:
        try:
            st.session_state['reviewed_zip'] = {'report_id': report_id,
                'data': export_reviewed(report, reviewer, note, acknowledged)}
            st.success('Đã tạo bản xuất cho báo cáo hiện tại.')
        except ValueError as error:
            st.error(str(error))
    export = st.session_state.get('reviewed_zip')
    if export and export['report_id'] == report_id:
        st.download_button('Tải ZIP đã rà soát', export['data'], 'demandpilot-reviewed.zip', 'application/zip')

st.download_button('Tải báo cáo đánh giá JSON', json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'),
                   'demandpilot-report.json', 'application/json')
