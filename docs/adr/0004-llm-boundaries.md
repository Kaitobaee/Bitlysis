# ADR 0004: Ranh giới LLM (OpenRouter) & minh bạch thống kê

## Trạng thái

Đã chấp nhận (Phase 0 — ràng buộc thiết kế; tích hợp theo phase sau).

## Bối cảnh

Sản phẩm nhắm đối tượng học thuật; [.cursor/.docs/docs.md](../../.cursor/.docs/docs.md) yêu cầu **dashboard minh bạch**, không dùng AI viết narrative che kết quả. Vẫn cần LLM cho **gợi ý giả thuyết / pipeline** (ngầm).

## Quyết định

1. **LLM không** sinh số liệu thống kê thay thế engine Python/R: mọi p-value, hệ số, quyết định reject/fail phải từ tính toán có kiểm chứng.
2. Đầu ra LLM phải khớp **JSON schema** cố định; validate bằng Pydantic; lỗi → **fallback rule-based**.
3. **Secrets**: `OPENROUTER_API_KEY` chỉ env; không log full prompt có PII trong production; timeout và rate limit phía server.
4. UI: có thể hiển thị danh sách hypothesis gợi ý; **không** hiển thị “báo cáo giải thích dài” do AI trên dashboard chính (đúng spec minh bạch).

## Hậu quả

- Cần bộ **eval nhỏ** (golden) để regression khi đổi model.

## Thay thế đã xem xét

- Cho AI tự chọn test và “giải thích” kết quả như văn bản chính: trái với positioning minh bạch.
