# ADR-0010 — Mô hình tổ chức: department dạng cây + quan hệ báo cáo giữa agent

**Status:** Accepted · **Date:** 2026-11-05

## Context
P1 cần sơ đồ tổ chức sửa được và có kiểm tra hợp lệ (IMPLEMENTATION_PLAN §5).

## Decision
Bảng departments có parent_department_id (cây). agents có department_id (nullable) và reports_to_agent_id. Backend chặn: vòng lặp ở cả cây department và chuỗi báo cáo, tự báo cáo cho chính mình, liên kết khác company, gắn vào department đã archive. Archive department bị từ chối khi còn department con hoặc agent chưa archive.

## Alternatives considered
Đồ thị tự do (nhiều cha): linh hoạt nhưng khó kiểm tra và khó hiển thị.

## Consequences
Mỗi agent tối đa một department và một người quản lý.

## Migration / compatibility impact
Migration 0003 thêm bảng và cột; dữ liệu cũ có department_id = null.
