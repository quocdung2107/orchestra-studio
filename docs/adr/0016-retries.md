# ADR-0016 — Retry có giới hạn, mỗi lần thử là một run

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- `run.failed` có thêm `retryable` (mặc định false). `agent_runs.attempt` bắt đầu từ 1. `tasks.max_attempts` mặc định 1.
- Orchestrator tự chạy lại khi `retryable` và `attempt < max_attempts`, chờ `retry_backoff_ms * 2^(attempt-1)`. Lịch sử run cũ giữ nguyên.
- Lệnh `POST /tasks/{id}/retry` cho task gốc ở `failed`/`cancelled`: đưa về `pending`, scheduler chạy lại.
- Lỗi do tool đã thực thi mà không rõ kết quả (`TOOL_OUTCOME_UNKNOWN`) luôn không retry.

## Consequences
UI hiện số lần thử; event `task.retry_requested`, `agent.run.retry_scheduled`.
