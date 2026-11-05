# ADR-0022 — Adapter model: Ollama, Claude, OpenAI qua một vòng lặp chung

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- `LlmRuntime` chung: system prompt từ role/instructions/goals của agent; user message từ task (+ context); tool = tool đã cấp cho agent (tên `kb.search` → `kb__search`), gọi qua `RunRequest.tools` (Tool Gateway). Tối đa `max_turns` (mặc định 8) lượt model.
- Kết thúc: câu trả lời cuối → `run.message` (rút gọn), artifact `<task>.md`, `run.completed` (dòng đầu). Bị cắt do `max_tokens` vẫn hoàn thành nhưng có cảnh báo.
- Mỗi lần gọi model phát `run.usage` (provider, model, token vào/ra, nguồn).
- Adapter chỉ giữ lịch sử hội thoại dạng gốc của provider bên trong; không có đối tượng SDK nào ra ngoài adapter.
- Claude: SDK `anthropic`, `client.beta.messages.create`, mặc định `claude-opus-5-5`, `output_config.effort` (mặc định `medium`), `max_tokens` 16000, `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) cho model hỗ trợ; `stop_reason == "refusal"` → `PROVIDER_REFUSED`. Khối nội dung trả về được gửi lại nguyên vẹn.
- OpenAI: SDK `openai`, `chat.completions`, `max_completion_tokens`; model bắt buộc (không đoán model mặc định).
- Ollama: `POST /api/chat` (`stream: false`), `GET /api/version|tags|ps` cho health.
- Lỗi: `PROVIDER_RATE_LIMITED`, `PROVIDER_UNAVAILABLE` (retryable); `PROVIDER_AUTH_FAILED`, `PROVIDER_BAD_REQUEST`, `MODEL_NOT_FOUND`, `PROVIDER_REFUSED`, `CREDENTIAL_MISSING`, `CREDENTIAL_REVOKED`, `MAX_TURNS_EXCEEDED` (không retry).
- Capability: `supports_cancel` và `supports_tool_calls` = true; pause/resume/streaming = false (UI ẩn nút, API trả 409).
- Settings của runtime được kiểm tra khi lưu agent (`validate_settings`).
- Contract test (`tests/test_runtime_contract.py`) chạy cùng một bộ kiểm tra cho cả ba adapter với transport giả.

## Not now
Agent model tự giao việc; streaming; pause/resume.
