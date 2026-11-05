# ADR-0018 — Tool Gateway và phê duyệt gắn checksum

**Status:** Accepted · **Date:** 2026-11-05

## Context
SECURITY §5/§7/§8: Tool Gateway là điểm thực thi chính sách; approval phải gắn đúng payload, chống chạy lại.

## Decision
- `RunRequest.tools` là cổng `call_tool(key, params) -> ToolResult`. Runtime không chạy tool trực tiếp.
- Gateway: tìm tool active theo key → `decide()` (ADR-0013) → kiểm tra input theo `input_schema` (tập con JSON Schema: object, properties, required, type, maxLength; không thêm dependency) → nếu `requires_approval` hoặc L3 thì tạo approval.
- Approval: `request_json` = {tool_key, tool_version, params}, `checksum` = SHA-256 của JSON chuẩn hóa (sort_keys, không khoảng trắng). Quyết định phải gửi đúng checksum; chỉ chuyển từ `pending`. Sau `approved` gateway thực thi đúng một lần và lưu `execution_status`, `result_json`, `executed_at`.
- Tool tích hợp: `kb.search` (L0), `doc.draft` (L1, artifact), `workspace.write` (L2, ghi trong `data/workspaces/<company>/<task gốc>/`, đường dẫn tương đối, không `..`, phải nằm trong `allowed_paths`, tối đa 1 MB), `social.publish` (L3, mô phỏng, không gọi mạng). Timeout theo `policy.timeout_seconds`.
- Agent không thể duyệt: API duyệt chỉ nhận lệnh từ người dùng (token của app).

## Consequences
Template Demo Video Studio nâng trần company lên L3 và cấp `social.publish` cho Producer để có kịch bản phê duyệt.

## Residual risk
Ghi file là trong process backend, không phải sandbox cấp OS; giới hạn ở kiểm tra đường dẫn và kích thước (SECURITY §7).
