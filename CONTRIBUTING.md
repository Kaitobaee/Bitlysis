# Contributing to Bitlysis

Tài liệu này mô tả quy trình đóng góp mã nguồn cho Bitlysis.

## Môi trường phát triển

- Node.js 22+
- pnpm 9.x
- Python 3.11+
- R 4.4+ nếu đụng tới pipeline R

Khuyến nghị đọc thêm:

- [docs/adr/](docs/adr/)
- [docs/bao-cao-doi-chieu-de-tai-va-san-pham.md](docs/bao-cao-doi-chieu-de-tai-va-san-pham.md)

## Quy trình làm việc

1. Tạo nhánh riêng từ `main`.
2. Thực hiện thay đổi nhỏ, rõ phạm vi.
3. Chạy test/lint liên quan.
4. Tạo PR khi mọi kiểm tra đã pass.

Không commit trực tiếp lên `main` trừ khi được yêu cầu rõ ràng.

## Lệnh cần chạy trước khi gửi PR

Frontend:

```bash
pnpm install
pnpm lint:web
pnpm build:web
```

API:

```bash
cd services/api
pip install -e ".[dev]"
ruff check app tests scripts
pytest tests -q
```

Nếu chạm vào luồng AI/web analysis, nên chạy thêm:

```bash
cd services/api
pytest tests/test_web_analysis.py tests/test_jobs.py -q
```

## Quy ước code

- Giữ thay đổi nhỏ và tập trung.
- Không sửa các file không liên quan đến task.
- Ưu tiên giữ nguyên phong cách hiện có của repo.
- Nếu thêm endpoint hoặc schema mới, cập nhật cả frontend type và tài liệu liên quan.

## Kiểm tra chất lượng

Trước khi mở PR, đảm bảo:

- Không còn lỗi lint/type ở phần đã sửa.
- Test liên quan pass.
- UI mới không phá layout hiện tại.
- API response và TypeScript types khớp nhau.

## Gợi ý khi đóng góp

- Mô tả rõ mục tiêu thay đổi trong PR.
- Nếu thay đổi hành vi AI, thêm ví dụ đầu ra trước/sau.
- Nếu thay đổi cấu trúc output, cập nhật README hoặc tài liệu kèm theo.