# Hướng dẫn DemandPilot

## 1. Mở dự án

```powershell
cd "C:\Users\LOQ\Documents\Codex\2026-11-06\cj\outputs\DemandPilot"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8508
```

Mở http://127.0.0.1:8508. Giữ PowerShell đang chạy; Ctrl+C để dừng.
Nếu môi trường đã được cài, không cần tạo lại .venv hoặc cài thư viện mỗi lần.
Không cần Groq API key, không cần tải mô hình lớn. Đây là mô hình hồi quy học máy chạy trên CPU.

## 2. Chạy dữ liệu mẫu

1. Giữ **Dữ liệu mẫu** trong thanh bên.
2. Kiểm tra 8 SKU, 700 ngày/SKU, snapshot 2025-11-30.
3. Bấm **Chạy backtest và lập dự báo**. Chờ vài giây.
4. Xem bảng bốn mô hình và mô hình đã chọn bằng dữ liệu selection.
5. Chọn SKU001 để xem lịch sử gần đây, đường dự báo điểm và hai đường cận dưới/cận trên.
6. Xem bảng đề xuất nhập hàng và đoạn giải thích phép tính.

Ngày dự báo của mẫu bắt đầu 2025-12-01 vì đây là tình huống lịch sử giả lập, không phải dự báo cho hôm nay.

Các mô hình:

- seasonal_naive: lặp lại tuần gần nhất.
- mean_28: trung bình 28 ngày.
- ridge_1, ridge_10: hồi quy Ridge được huấn luyện từ lịch sử, khác mức regularization.

Mô hình có điểm tốt nhất trên test có thể khác mô hình đã chọn. Không đổi lựa chọn sau khi xem test;
đó là cách giữ phần kiểm tra cuối độc lập với quyết định chọn mô hình trong lần chạy này.

## 3. Hiểu số liệu

- MAE: sai số tuyệt đối trung bình, đơn vị là số sản phẩm/ngày.
- WAPE: tổng sai số tuyệt đối / tổng lượng bán. 0.10 là 10%, càng thấp càng tốt.
- Bias: dự báo trừ thực tế, trung bình; dương là dự báo cao hơn, âm là thấp hơn.
- Coverage: tỷ lệ quan sát nằm trong khoảng. Xem cùng độ rộng khoảng, không chỉ coverage.
- WAPE của SKU toàn số 0 là null/None; dùng MAE để xem lỗi.

Không gọi 1 − WAPE là “độ chính xác”. Không suy từ kết quả giả lập thành cam kết cho cửa hàng thực.

## 4. Kiểm tra đề xuất nhập hàng

Mẫu có lead time 7 ngày và review period 7 ngày, nên kỳ bảo vệ là 14 ngày.

Phép tính:

1. Mục tiêu tồn kho = làm tròn lên cận trên thực nghiệm của tổng lượng bán 14 ngày.
2. Inventory position = tồn đang có + hàng đang đặt.
3. Thiếu hụt = max(0, mục tiêu − inventory position).
4. Khi thiếu hụt > 0, áp MOQ và làm tròn theo pack_size.
5. Chi phí ước tính = số đề xuất × unit_cost_vnd.

Kiểm tra SKU001: tồn đang có thấp, thường có cảnh báo thiếu trước lead time.
Kiểm tra SKU008: không có lượng bán trong 84 ngày gần đây; giữ đề xuất mua ở 0 để kiểm tra thủ công.

Giả định hàng đang đặt sẽ về trước cuối kỳ bảo vệ. CSV không có ngày về từng đơn, nên cần tự đối chiếu.
Cảnh báo trước lead time chỉ tính tồn đang có; không tự cho rằng hàng đang đặt về kịp.

## 5. Duyệt và xuất

1. Nhập tên/bí danh và ghi chú, ví dụ: “Đã đối chiếu tồn, hàng đang đặt, MOQ và lịch giao mẫu.”
2. Tích xác nhận các giả định.
3. Bấm **Xác nhận rà soát báo cáo hiện tại**.
4. Bấm **Tải ZIP đã rà soát**.

ZIP có:

- replenishment-reviewed.csv: đề xuất nhập hàng.
- forecast.csv: dự báo điểm, khoảng ngày và khoảng tổng tích lũy.
- report.json: mô hình, số liệu, giao thức, fingerprint và kết quả.
- review.json: nhãn người duyệt, ghi chú và hash báo cáo được duyệt.

Chạy lại hoặc đổi dữ liệu làm mất hiệu lực bản xuất trước đó. Ứng dụng không tự mua hàng.
Báo cáo lần chạy lưu trong private/runs; thư mục private được bỏ qua khi đưa lên GitHub.

## 6. Lưu báo cáo từ PowerShell

```powershell
.\.venv\Scripts\python.exe -X utf8 evaluate.py --output reports/my-evaluation-v1.json
Get-Content reports/my-evaluation-v1.json -Encoding utf8
```

Nếu file đã tồn tại, dùng tên mới như my-evaluation-v2.json. Exit code 0 chỉ cho biết chạy hoàn tất,
không phải xác nhận hiệu quả kinh doanh.

## 7. Dữ liệu của bạn

Trong thanh bên chọn **CSV của tôi**, tải cả sales.csv và inventory.csv.
Tải hai CSV mẫu để xem đúng tên cột và thứ tự. Không dùng file rút gọn hai dòng trong README để chạy.

- Cần 420–1460 ngày liên tục cho mỗi SKU, cùng khoảng ngày cho mọi SKU.
- Một dòng cho mỗi SKU/ngày; tổng hợp giao dịch trước khi nhập.
- Không có ngày thiếu. Chỉ ghi 0 nếu thực sự không bán; không tự lấp khoảng mất dữ liệu bằng 0.
- Số lượng là số nguyên không âm; không dùng 1.000 hoặc 1,000 làm phân cách nghìn.
- as_of bằng ngày bán cuối, snapshot tại cuối ngày.
- Tổng lead_time_days + review_period_days tối đa 28.
- Tập SKU hai file phải giống nhau; pack_size > 0.

Nếu ít hơn tám khối SKU/origin trong phần hiệu chỉnh, hệ thống chỉ đưa dự báo điểm, chưa đưa đề xuất nhập hàng.
Đây là giới hạn cố ý để tránh hiển thị khoảng với quá ít dữ liệu. Một SKU với lịch sử ngắn có thể gặp tình huống này.

## 8. Phần cần đọc để hiểu code

- dataio.py: kiểm tra CSV, ngày, khoảng lịch sử và snapshot.
- forecast.py: tạo đặc trưng quá khứ, huấn luyện Ridge, dự báo đệ quy và khoảng thực nghiệm.
- pipeline.py: chia thời gian, chọn mô hình và đánh giá test.
- planning.py: chuyển dự báo thành phép tính tồn kho và ZIP đã duyệt.
- app.py: giao diện, biểu đồ và thao tác duyệt.
- make_demo.py: nguồn tạo dữ liệu giả lập; không phải dữ liệu kinh doanh thật.

Trước khi đăng portfolio: chạy các bước trên, đọc report, chụp biểu đồ/bảng đánh giá và ghi rõ phạm vi giả lập.
Hướng dẫn GitHub, LinkedIn và Upwork sẽ dựa vào kết quả bạn đã kiểm tra, không thêm số liệu kinh doanh chưa đo.
