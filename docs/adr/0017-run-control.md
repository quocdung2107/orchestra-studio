# ADR-0017 — Pause/resume/cancel theo capability

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- Runtime khai báo `supports_cancel/pause/resume` và cài `cancel(run_id)`, `pause(run_id)`, `resume(run_id)`. Lệnh API cho runtime không hỗ trợ trả 409 `not_supported`.
- Trạng thái run thêm `paused`, `waiting_approval`, `cancel_requested`, `cancelled`.
- Cancel task: hủy run đang chạy của nó và mọi task con; task `pending` bị hủy ngay. Run cha nhận lỗi `CHILD_TASK_CANCELLED`. Approval đang chờ của run bị hủy chuyển `cancelled`.
- Khởi động lại backend: run chưa kết thúc (kể cả paused/waiting_approval) → `failed/INTERRUPTED`; approval đang chờ → `expired`.
- Mock runtime hỗ trợ cả ba, kiểm tra cờ giữa các bước.
