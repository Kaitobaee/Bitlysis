# Methodology — chọn phân tích (user-facing)

Tài liệu mô tả **khi nên dùng** từng loại `kind` trong `POST /v1/jobs/{id}/analyze`,
và **khi không nên**. Sau ADR 0005, toàn bộ engine là Python (không còn Rscript).

## `comprehensive_analysis` (khuyến nghị mặc định)

**Khi dùng:** Mọi tình huống "tải file rồi để hệ thống quyết định". Orchestrator
chạy tuần tự profile → cleaning → hypothesis suggest → engine dispatch
(stats / psychometrics / timeseries) → unified schema → export.

**Output:** `academic_summary`, `hypothesis_table`, `decision_trace`,
`diagnostics`, `evidence`, `charts`, `results`, `cleaning`, `provenance_ref`.

**Toggle:** `enable_psychometrics`, `enable_pls`, `enable_timeseries`,
`enable_llm_hypotheses`, `random_seed`.

## `compare_groups_numeric`

**Khi dùng:** So sánh **một biến định lượng** giữa **hai hoặc nhiều nhóm** xác
định bởi một cột phân loại (vd. điểm theo `treatment`).

**Khi không dùng:** Cả outcome lẫn group đều chỉ là nhãn định tính không có thứ
tự và không có cột số liên quan; dữ liệu phân cấp (country → region) dùng để
"test độc lập" — không mang câu hỏi nghiên cứu đúng.

## `regression_ols`

**Khi dùng:** Mô hình **OLS** một outcome số từ một hoặc nhiều predictor số hoặc
đã mã hóa; muốn ước lượng hệ số / R² / kiểm định chung trên tuyến tính.

**Khi không dùng:** Quan hệ phi tuyến mạnh; nhiễu có cấu trúc phức tạp; dữ liệu
chuỗi thời gian có tự tương quan — xem `timeseries_forecast`.

## `categorical_association`

**Khi dùng:** Hai cột **phân loại** (nominal/ordinal ít mức); bảng contingency
**không quá thưa**; câu hỏi: có bằng chứng liên kết trong mẫu không
(chi-square / Cramér V).

**Khi không dùng:** Một trong hai cột có **cực nhiều cấp** → ô kỳ vọng nhỏ,
p-value không tin cậy.

## `psychometrics` (alias `r_pipeline` cho client cũ)

**Khi dùng:** Cronbach α, EFA, PLS-SEM trên một thang đo cụ thể; cần spec chi
tiết các construct/path. Engine: `services/api/app/services/psychometrics/`
(thuần Python).

**Outputs:**
- Cronbach: `raw_alpha`, `std_alpha`, `item_total_statistics` (item-total corr,
  alpha-if-dropped).
- EFA: PAF + varimax (`factor_analyzer` không còn cần); KMO, Bartlett,
  loadings, communalities, variance_proportion, scree, eigenvalues.
- PLS-SEM: NIPALS reflective; outer_loadings, outer_weights, path_coefficients,
  R²/adj R², AVE, CR, rho_A, HTMT, Fornell-Larcker, Q² (blindfolding), f²,
  Bootstrap CI (`bootstrap_samples` mặc định 500, cấu hình được).

**Gate:** giống bản R cũ (`min_n`, `min_items_per_construct`, `min_constructs`).

## `timeseries_forecast`

**Khi dùng:** Chuỗi thời gian có **cột ngày** và **giá trị số**; mục tiêu dự báo
ngắn hạn / đánh giá MAPE trên holdout.

**Khi không dùng:** Không có cấu trúc thời gian rõ; mẫu quá ngắn; ngoại lệ /
structural break chưa xử lý.

## Mapping đề tài ↔ endpoint ↔ điều kiện kích hoạt

| Mục đề tài | Endpoint/spec | Điều kiện kích hoạt | Engine |
| --- | --- | --- | --- |
| One-click analysis | `comprehensive_analysis` | luôn (mặc định UI) | orchestrator |
| Kiểm định giả thuyết | `compare_groups_numeric`/`regression_ols`/`categorical_association` | spec đơn lẻ hoặc auto qua orchestrator | `stats_engine` |
| Cronbach α | `psychometrics` (`cronbach_alpha`) hoặc auto khi có ≥2 cột Likert | gates `min_items≥2`, `n_complete≥2` | `psychometrics/cronbach.py` |
| EFA | `psychometrics` (`efa`) hoặc auto khi có ≥3 Likert + n≥10 | gates `min_variables`, `min_n` | `psychometrics/efa.py` (PAF + varimax) |
| PLS-SEM | `psychometrics` (`pls_sem`) hoặc auto khi `enable_pls` + ≥6 Likert | gates `min_n`, `min_items_per_construct`, `min_constructs` | `psychometrics/pls_sem.py` (NIPALS + bootstrap/HTMT/Q²/f²) |
| Chuỗi thời gian | `timeseries_forecast` hoặc auto khi `enable_timeseries` + có datetime + numeric | có cột thời gian | `timeseries_engine.py` (ETS/ARIMA/Prophet optional) |
| AI hỗ trợ | `comprehensive_analysis.enable_llm_hypotheses=true` | có `OPENROUTER_API_KEY`/`OPENAI_API_KEY` | rule-based + LLM (chỉ paraphrase) |

## Tham chiếu code

- Spec union: `services/api/app/schemas/stats.py`
- Orchestrator: `services/api/app/services/orchestrator.py`
- Engine stats: `services/api/app/services/stats_engine.py`, `timeseries_engine.py`
- Psychometrics (Python): `services/api/app/services/psychometrics/`
- Cleaning: `services/api/app/services/data_cleaning.py`
- Provenance: `services/api/app/services/provenance.py`
