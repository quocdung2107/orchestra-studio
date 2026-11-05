# ADR-0004 — Thêm Task và AgentRun tối thiểu vào P0

**Status:** Accepted · **Date:** 2026-11-05

## Context
RUNTIME §5 yêu cầu Mock Runtime đi qua Task Engine/Orchestrator, nhưng Tasks thuộc P2. P0 acceptance yêu cầu xem kết quả task/run nhưng P0 không có bảng tasks/agent_runs.

## Decision
P0 có bảng tasks (không có dependency, không có parallel) và agent_runs, kèm metadata artifact tối thiểu. Orchestrator P0 chỉ chạy tuần tự. Approval và Metrics không thuộc yêu cầu của P0 Mock Runtime.

## Alternatives considered
Giữ nguyên baseline (không hoàn thành được P0-08 đúng nghĩa); làm luôn Task Orchestration đầy đủ (kéo P2 vào P0).

## Consequences
P2 mở rộng các bảng có sẵn thay vì tạo mới. RUNTIME §5 được hiểu là mục tiêu cuối, không phải yêu cầu P0.

## Migration / compatibility impact
P2 thêm cột/bảng qua migration mới (task_dependencies, approvals).
