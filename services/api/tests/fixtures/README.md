# Test fixtures (synthetic)

Dữ liệu **giả lập**, dùng cho pytest và kiểm thử ingestion. **Không** đặt dữ liệu thật có PII vào đây.

| File | Mục đích |
| --- | --- |
| `sample_utf8.csv` | CSV UTF-8 (header + vài dòng) |
| `sample_cp1252.csv` | CSV Windows-1252 (kiểm tra encoding) |
| `sample_clean.xlsx` | Excel một sheet, bảng đơn giản |
| `sample_multi_sheet_merged.xlsx` | Hai sheet, có ô merge (kiểm tra edge case Excel) |

Tạo lại file `.xlsx` (nếu đổi schema):

```bash
cd services/api
python scripts/generate_test_fixtures.py
```
