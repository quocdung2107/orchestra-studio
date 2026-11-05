# ADR-0015 — Task graph và scheduler theo company

**Status:** Accepted · **Date:** 2026-11-05

## Context
P0 (ADR-0004) chỉ chạy tuần tự, một kịch bản mỗi company. P2 yêu cầu phụ thuộc, giao việc và chạy song song.

## Decision
- Bảng `task_dependencies(task_id, depends_on_task_id, dependency_type='finish_to_start')`, chặn tự phụ thuộc, vòng lặp và khác company.
- Trạng thái task: `pending`, `in_progress`, `waiting_approval`, `paused`, `completed`, `failed`, `cancelled`.
- Task gốc (không có `parent_task_id`) sẵn sàng khi `pending` và mọi phụ thuộc `completed`. Scheduler của company chạy task sẵn sàng, tối đa `companies.max_parallel_runs` (mặc định 3) cùng lúc, rồi xét lại khi có task xong.
- Task con do agent giao được run cha chờ trực tiếp (không qua giới hạn, tránh deadlock). Bước `parallel` của runtime tạo nhiều task con và chờ tất cả.
- Phụ thuộc fail/cancel: task sau giữ `pending`; API trả thêm `blocked_by` để UI hiển thị.
- Giao việc: `assigned_agent_id` cụ thể hoặc `required_role` (agent active đầu tiên của vai trò).

## Consequences
Bỏ lỗi `company_busy`. Kịch bản là task gốc có `context.scenario_id`.
