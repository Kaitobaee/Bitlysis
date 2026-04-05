# Eval (Phase 7)

- **`golden/hypothesis_llm_golden.json`** — chuỗi phản hồi LLM giả lập + kỳ vọng `hypothesis_id`; pytest đảm bảo parse/validate Pydantic không regression khi đổi `OPENROUTER_MODEL` (golden không gọi mạng).
