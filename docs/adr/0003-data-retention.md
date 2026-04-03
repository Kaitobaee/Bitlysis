# ADR 0003: Lưu trữ file upload & xóa dữ liệu

## Trạng thái

Đã chấp nhận và **triển khai Phase 2**: `DELETE /v1/jobs/{id}`, sweep định kỳ theo `RETENTION_*`, cấu hình trong [`services/api/.env.example`](../../services/api/.env.example).

## Bối cảnh

File người dùng có thể chứa dữ liệu nhạy cảm; disk trên PaaS hữu hạn; cần **quan sát được** và **xóa theo yêu cầu**.

## Quyết định

1. File upload và artifact nằm dưới `UPLOAD_DIR` (và thư mục artifact sau này), không commit vào git.
2. **`RETENTION_HOURS`** (env): job quá hạn được coi là eligible để xóa (sweep background hoặc on-demand).
3. **`DELETE /v1/jobs/{id}`** (khi API job có mặt): xóa file + meta + artifacts gắn job.
4. README/public policy ghi rõ thời gian lưu mặc định (điều chỉnh theo môi trường).

## Hậu quả

- Cần cron hoặc worker dọn dẹp; tránh “rò” disk trên Render free tier.

## Thay thế đã xem xét

- Lưu vĩnh viễn: không chấp nhận cho MVP cloud.
