# Methodology — chọn phân tích (user-facing)

Tài liệu mô tả **khi nên dùng** từng loại `kind` trong `POST /v1/jobs/{id}/analyze`, và **khi không nên**. Kết quả server (profiling, cảnh báo ô kỳ vọng chi-square, v.v.) luôn ưu tiên hơn xem trước trình duyệt.

## `compare_groups_numeric`

**Khi dùng:** So sánh **một biến định lượng** (continuous) giữa **hai hoặc nhiều nhóm** xác định bởi một cột phân loại (vd. điểm theo `treatment`).

**Khi không dùng:** Cả outcome lẫn group đều chỉ là nhãn định tính không có thứ tự và không có cột số liên quan; dữ liệu phân cấp (country → region) dùng để “test độc lập” — không mang câu hỏi nghiên cứu đúng.

## `regression_ols`

**Khi dùng:** Mô hình **OLS** một outcome số từ một hoặc nhiều predictor số hoặc đã mã hóa; muốn ước lượng hệ số / R² / kiểm định chung trên tuyến tính.

**Khi không dùng:** Quan hệ phi tuyến mạnh; nhiễu có cấu trúc phức tạp; nhiều quan sát trùng hạng mạnh cần mô hình khác; dữ liệu chuỗi thời gian có tự tương quan — xem timeseries.

## `categorical_association`

**Khi dùng:** Hai cột **phân loại** (nominal/ordinal ít mức); bảng contingency **không quá thưa**; câu hỏi: có bằng chứng liên kết trong mẫu không (chi-square / Fisher tùy engine).

**Khi không dùng:** Một trong hai cột có **cực nhiều cấp** (vd. ngày đầy đủ × sản phẩm) → ô kỳ vọng nhỏ, p-value không tin cậy. Dữ **redundant** (country vs country_code) hoặc **phân cấp** (country vs region) — không phải phát hiện insight, chỉ phù hợp kiểm tra dữ liệu.

## `r_pipeline`

**Khi dùng:** Cronbach α, EFA, PLS-SEM (seminr) và các phân tích đã hỗ trợ trong `packages/r-pipeline`; cần **đúng spec JSON** gửi cho R CLI.

**Khi không dùng:** Môi trường không có R / timeout quá ngắn cho PLS; bộ nhớ thấp (risk OOM) — cân nhắc **worker RAM cao** (Docker/Render service thứ hai, xem `DEPLOY-RENDER-VERCEL.md`).

## `timeseries_forecast`

**Khi dùng:** Chuỗi thời gian có **cột ngày** và **giá trị số**; mục tiêu dự báo ngắn hạn / đánh giá MAPE trên holdout.

**Khi không dùng:** Không có cấu trúc thời gian rõ; mẫu quá ngắn; ngoại lệ / structural break chưa xử lý mà cần mô hình khác.

## Tham chiếu code

- Spec union: `services/api/app/schemas/stats.py`
- Engine Python: `services/api/app/services/stats_engine.py`, `timeseries_engine.py`
- R bridge: `services/api/app/services/r_pipeline.py`
