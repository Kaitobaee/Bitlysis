# ADR 0002: Vòng đời Job & API `/v1`

## Trạng thái

Đã chấp nhận và **triển khai Phase 1** trong repo: prefix `/v1`, `GET /v1/jobs/{id}`, `POST /v1/jobs/{id}/analyze` (202 + background stub), header `X-Request-Id`, body lỗi chuẩn hoá.

## Bối cảnh

Bitlysis cần upload + phân tích nặng + export; HTTP sync dễ timeout (Render/Vercel). Cần mô hình **job** rõ ràng cho client poll và cho observability.

## Quyết định

1. Mọi tài nguyên chạy dài gắn với **`job_id`** (UUID); API công khai dùng prefix **`/v1`**.
2. Trạng thái tối thiểu: `uploaded` → `profiling` → `analyzing` → `exporting` → `succeeded` | `failed` (cho phép gộp bước nhỏ trong MVP miễn **bất biến trong OpenAPI**).
3. Thao tác nặng (`analyze`, `export`) trả **202 Accepted** + poll `GET /v1/jobs/{id}` (hoặc SSE sau này); chế độ dev có thể bật sync qua env.
4. Mỗi response lỗi mang **`request_id`** (header hoặc body) để truy vết log.

## Hậu quả

- Frontend phải xây flow **poll + skeleton**; backend phải persist state (filesystem trước, DB sau nếu cần).

## Thay thế đã xem xét

- Chỉ `POST /analyze` sync: đơn giản nhưng không scale và dễ 504.
