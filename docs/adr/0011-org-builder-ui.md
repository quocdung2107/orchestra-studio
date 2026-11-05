# ADR-0011 — Org Builder dùng @xyflow/react, backend là nguồn sự thật

**Status:** Accepted · **Date:** 2026-11-05

## Context
Cần chỉnh tổ chức trực quan mà không để UI tự quyết định trạng thái.

## Decision
Org Builder vẽ agent là node, quan hệ báo cáo là cạnh. Nối cạnh, xóa cạnh, đổi department đều gửi command lên API; UI vẽ lại theo kết quả. Vị trí node lưu trong bảng org_layouts (dữ liệu giao diện, không phát event). Khi chưa có vị trí, UI tự xếp theo cấp báo cáo.

## Alternatives considered
Lưu cả graph từ client (dễ lệch với backend); thư viện layout như dagre/elk (thêm dependency, chưa cần).

## Consequences
Department hiển thị bằng nhãn màu trên node và danh sách bên cạnh, chưa vẽ thành vùng nhóm.

## Migration / compatibility impact
Không có.
