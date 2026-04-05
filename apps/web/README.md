# Bitlysis Web (Next.js)

Phase 9 — giao diện tải dữ liệu, tạo job, poll trạng thái, phân tích mặc định, xuất ZIP; i18n tĩnh `messages/vi.json` + `messages/en.json`; toast lỗi kèm hướng dẫn (API URL, CORS, `/docs`).

## Chạy local

```bash
# Từ root monorepo
pnpm install
# API (terminal khác): cd services/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd apps/web
cp .env.example .env.local
# Sửa .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000
cd ../..
pnpm dev:web
```

Mở <http://localhost:3000>. Đảm bảo `API_CORS_ORIGINS` trên API chứa `http://localhost:3000`.

## E2E tay (staging / DoD)

1. Deploy hoặc chạy API staging; đặt `NEXT_PUBLIC_API_URL` trỏ đúng base URL (không có slash cuối).
2. Build hoặc dev frontend với biến đó; hard refresh.
3. Tải file CSV ≥ 2 cột (ví dụ `x,y` + vài dòng).
4. Xác nhận toast thành công, URL có `?job=<uuid>`, trạng thái **Uploaded**, danh sách cột đúng.
5. **Run analysis** — skeleton/pulse khi đang chạy; kết thúc **Succeeded** hoặc **Failed** với thông báo lỗi có cấu trúc.
6. Mở khối **Structured results**: bảng `hypothesis_table` / metrics / engine — không phụ thuộc văn bản AI trên dashboard.
7. (Tuỳ chọn) **Download ZIP** sau khi succeeded; nếu API trả 409 heavy export, UI gọi `export/start` rồi thử lại.
8. Đổi **Vi / En** — nhãn giao diện đổi theo file JSON tĩnh.

## Cấu trúc chính

| Path | Mô tả |
| --- | --- |
| `messages/*.json` | Chuỗi UI (Vi/En) |
| `lib/api.ts` | Client gọi `/v1/upload`, `/v1/jobs/...` |
| `lib/poll-job.ts` | Poll GET job đến terminal |
| `components/home-workspace.tsx` | Luồng chính |
| `components/result-summary.tsx` | Hiển thị `result_summary` dạng dữ liệu (ẩn key narrative/LLM) |

Phân tích mặc định: `categorical_association` với hai cột đầu — đủ cho demo; spec khác dùng API trực tiếp.
