# ADR-0020 — Bài học và đề xuất đổi vai trò cần người duyệt

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- `lessons`: title, lesson, source task/run, `proposed_by`, `review_status` (`proposed`, `approved`, `rejected`), ghi chú duyệt. Duyệt → tạo knowledge item kind `lesson`, `source_type=lesson`.
- `role_change_proposals`: agent đích, `changes` (role, department_id, reports_to_agent_id, instructions; ít nhất một), lý do, `proposed_by`, trạng thái. Duyệt → áp dụng qua `agents`/`organization` service trong cùng transaction (đổi chỉ dẫn = tạo agent version mới). Lỗi hợp lệ → 422, đề xuất giữ `proposed`.
- Runtime phát `run.lesson.proposed` và `run.role_change.proposed`; orchestrator lưu với `proposed_by=agent:<id>`.
- Chỉ người dùng duyệt được.
