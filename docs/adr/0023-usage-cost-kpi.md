# ADR-0023 — Usage, chi phí và KPI có nhãn nguồn và độ tin cậy

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- Bảng `metrics`: company, agent, department, task, run, `metric_name`, `metric_value`, `unit`, `source`, `confidence`, `metadata_json` (provider, model, ngày bảng giá), `source_event_id`, `recorded_at`.
- `source`: `provider_reported`, `local_runtime_reported`, `price_table_estimate`, `local_no_api_fee`, `orchestrator`. `confidence`: `measured`, `reported`, `estimated`.
- Chi phí = token × giá trong `pricing.yaml` (có `as_of`, nguồn). Không có giá → không ghi chi phí; KPI báo số run "chưa có giá".
- KPI (`GET /companies/{id}/kpis?days=N`): theo company, agent, runtime: số run, hoàn thành, lỗi, hủy, tỉ lệ thành công, thời gian trung bình, số lần retry, token, chi phí ước tính và độ phủ giá. Mỗi nhóm số có nhãn nguồn và độ tin cậy.

## Alternatives
Lấy chi phí từ Admin API của provider: cần khóa admin, để sau.
