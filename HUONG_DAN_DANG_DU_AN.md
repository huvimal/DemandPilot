# Đăng DemandPilot lên GitHub, LinkedIn và Upwork

## Chuẩn bị demo

Chụp ba ảnh từ dữ liệu mẫu: bảng so sánh mô hình, biểu đồ dự báo SKU001, bảng đề xuất nhập hàng
kèm giải thích. Nếu quay video, dùng 60–90 giây: chạy báo cáo → so sánh baseline → xem dự báo →
đối chiếu phép tính → rà soát → xuất ZIP. Không đưa dữ liệu khách hàng hoặc thông tin liên hệ vào ảnh.

## GitHub

Tạo repo mới tại https://github.com/new:

- Name: DemandPilot
- Public
- Không tạo sẵn README, .gitignore hoặc license trong repo trống.

Description:

Python sales forecasting and inventory review prototype with temporal backtesting, ridge regression, empirical forecast bands, and reviewed replenishment exports.

Topics: python, time-series, forecasting, machine-learning, inventory-management, streamlit, ridge-regression

Chạy trong PowerShell (áp dụng cho thư mục chưa có Git và repo GitHub mới còn trống):

```powershell
cd "C:\Users\LOQ\Documents\Codex\2026-11-06\cj\outputs\DemandPilot"
git init -b main
git add .gitignore .github .streamlit/config.toml data tests app.py dataio.py evaluate.py forecast.py make_demo.py pipeline.py planning.py requirements.txt README.md MODEL_CARD.md VALIDATION.md HUONG_DAN.md CASE_STUDY.md HUONG_DAN_DANG_DU_AN.md
git diff --cached --stat
git status --short
```

Xem danh sách chuẩn bị commit: không có .venv, private, reports, .agents hoặc .claude.
Báo cáo JSON riêng vẫn lưu trên máy; kết quả giả lập công khai đã tóm tắt trong VALIDATION.md và CASE_STUDY.md.

```powershell
git commit -m "Build sales forecasting and inventory review prototype"
git remote add origin https://github.com/huvimal/DemandPilot.git
git push -u origin main
```

Mở Actions và chờ DemandPilot checks xanh. Sau đó bấm bánh răng cạnh About để điền Description và Topics.
Không dùng localhost làm Website. Nếu repo/remote đã được tạo trước, xem git status và git remote -v trước;
không lặp lại lệnh thêm origin.

## LinkedIn

Chỉ đăng link sau khi repo đã truy cập được. Nội dung đề xuất:

I built DemandPilot, a personal Python project for sales forecasting and inventory review.

It compares seasonal naive and trailing-mean baselines with fitted ridge regression using chronological model selection and rolling-origin testing.

The selected model achieved 8.74% test WAPE versus 12.50% for seasonal naive on eight synthetic SKUs. These are development results on generated data, not a real-store performance guarantee.

The workflow also includes empirical forecast bands, MOQ/pack-size calculations, grounded explanations, and human review before exporting replenishment suggestions.

One lesson: the model chosen before testing should remain selected even if another candidate later scores slightly better on the final test.

Includes 32 automated tests covering temporal data handling, inventory arithmetic, and review/export behavior.

Code and case study: https://github.com/huvimal/DemandPilot

#Python #MachineLearning #TimeSeries #Forecasting #DataScience

## Upwork Portfolio

Title: Sales Forecasting & Inventory Planning — DemandPilot

Role: Python Developer

Description:

Personal, AI-assisted Python project for sales forecasting and inventory review. Compares seasonal and mean baselines with fitted ridge regression using chronological selection and rolling-origin tests. Includes empirical forecast bands, MOQ/pack-size calculations, review-bound CSV exports, and 32 automated tests. The selected model recorded 8.74% test WAPE versus 12.50% for seasonal naive on synthetic data; this is not a real-store performance guarantee.

Skills: Python, Machine Learning, Data Analysis, Time Series Forecasting, Streamlit.
Chọn các nhãn tương ứng có sẵn, tối đa năm nhãn. Đính kèm ba ảnh demo, Preview rồi Publish.
Không thêm dự án này thành kinh nghiệm khách hàng có trả phí.

## Phạm vi claim

Có thể ghi: personal/local prototype, trained ridge regression, temporal backtesting, synthetic data,
32 tests, reviewable inventory suggestions.

Không đổi WAPE thành accuracy; không ghi đã giảm tồn kho, tăng lợi nhuận, tiết kiệm chi phí hoặc tự động
mua hàng. Các kết quả vận hành đó chưa được đo. Khoảng dự báo thực nghiệm không bảo đảm mức dịch vụ.
