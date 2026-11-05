# ADR-0026 — Agent chạy model thật giao việc qua tool `team.delegate`

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- Agent có ít nhất một cấp dưới trực tiếp đang hoạt động được thêm tool nội bộ `team.delegate` {`to_role`, `title`, `description`}. `to_role` là enum các vai trò cấp dưới trực tiếp; mô tả tool liệt kê tên từng người. Agent không có cấp dưới không thấy tool này.
- Tool không đi qua Tool Gateway (không phải tool ngoài, không cần cấp quyền hay duyệt). Orchestrator tạo task con (giao thẳng cho cấp dưới đó, kế thừa context của task cha), chạy nó, rồi trả cho model: `task_id`, `status`, tóm tắt run cuối, tên artifact.
- Giới hạn: chỉ cấp dưới **trực tiếp** (chặt hơn đề xuất trong P5_PLAN "hoặc vai trò trong company"; giữ đúng sơ đồ tổ chức), độ sâu ≤ 8, tối đa 5 lần giao mỗi run. Vi phạm trả lỗi cho model (`DELEGATION_NOT_ALLOWED`, `DELEGATION_TOO_DEEP`, `DELEGATION_LIMIT`), không làm hỏng run; model tự quyết làm tiếp.
- Task con thất bại/bị hủy: tool trả `ok=false`, `CHILD_TASK_FAILED`/`CHILD_TASK_CANCELLED`, kèm lỗi tóm tắt. Khác với Mock (thất bại cả run cha): model thật có thể xử lý lỗi.
- Trong lúc chờ task con, run cha **trả lại slot** của runtime (Ollama mặc định 1 slot) rồi xếp hàng lại; nếu không, cha và con cùng Ollama sẽ kẹt nhau mãi.
- Lượt gọi `team.delegate` tính vào `max_turns` của run cha. Usage của task con ghi cho run con.

## Consequences
- Một run cha có thể kéo dài bằng tổng thời gian các task con; timeout model áp dụng từng lượt gọi, không áp cho cả run.
- Giao song song nhiều task trong một lượt chạy tuần tự (model gọi nhiều tool một lượt thì lần lượt).
