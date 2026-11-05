# ADR-0013 — Khai báo tool và quyền theo tầng (chưa thực thi)

**Status:** Accepted · **Date:** 2026-11-05

## Context
SECURITY.md yêu cầu tool khai báo policy và quyền theo company/department/agent/tool. Thực thi tool là P2.

## Decision
Tool khai báo: key, input schema, permission_level L0–L3, policy (allowed_paths, allowed_domains, timeout_seconds, network, requires_approval, idempotent). L3 luôn requires_approval. Mỗi lần sửa tool tăng version và phát event chứa định nghĩa mới. Mức trần: company.max_tool_level (mặc định L1), department.max_tool_level (null = kế thừa); trần hiệu lực của agent = min theo chuỗi department lên company. Mặc định từ chối: agent chỉ dùng được tool được cấp (agent_tools) và có level ≤ trần. Cấp vượt trần bị từ chối; hạ trần sau đó làm quyết định trả về 'blocked' chứ không xóa grant. Quyết định quyền trả về principal, action, resource, policy result (SECURITY §4).

## Alternatives considered
Quyền phẳng chỉ ở agent (thiếu kiểm soát theo tổ chức).

## Consequences
P2 Tool Gateway dùng chung hàm quyết định này.

## Migration / compatibility impact
Migration 0003 thêm cột max_tool_level cho companies/departments.
