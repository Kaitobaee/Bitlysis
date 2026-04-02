# ADR 0001: Monorepo & tầng hệ thống Bitlysis

## Trạng thái

Đã chấp nhận (2026-04)

## Bối cảnh

Bitlysis (StatOne) cần: web (Next.js), API tổ chức pipeline phân tích, và R cho các thủ tục kiểu SPSS/PLS-SEM.

## Quyết định

1. **Monorepo** gồm `apps/web` (Next.js), `services/api` (FastAPI), `packages/r-pipeline` (R + `renv`).
2. **Python là orchestrator duy nhất** cho HTTP, upload, điều phối job, tích hợp LLM sau này; gọi R qua `Rscript` / subprocess với contract JSON hoặc file.
3. **C++** (nếu có) không bắt buộc MVP: bổ sung sau khi có benchmark, có thể `pybind11` hoặc binary gọi từ Python.
4. **Triển khai**: API trong Docker (Render); frontend trên Vercel; secrets chỉ qua biến môi trường.

## Hậu quả

- Dockerfile API phải cài **Python + R**; tăng kích thước image và cold start — chấp nhận cho giai đoạn MVP.
- Contract giữa Python ↔ R phải được version (schema JSON) để tránh lệch kiểu dữ liệu.

## Thay thế đã xem xét

- Chỉ Python (bỏ R): đủ cho MVP một phần nhưng yếu PLS-SEM ecosystem so với R.
- R là API trực tiếp (Plumber): thêm lớp vận hành; FastAPI vẫn đơn giản hơn cho file upload và tích hợp Python libs.
