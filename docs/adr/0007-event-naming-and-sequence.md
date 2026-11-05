# ADR-0007 — Tên event và phạm vi sequence

**Status:** Accepted · **Date:** 2026-11-05

## Context
RUNTIME dùng run.*, EVENTS dùng agent.run.*. Phạm vi sequence chưa chốt.

## Decision
Runtime adapter phát event nội bộ run.*. Backend kiểm tra, chuẩn hóa thành agent.run.* rồi mới lưu. Chỉ tên đã chuẩn hóa xuất hiện trong DB, API và UI. sequence tăng dần theo company_id, chỉ backend cấp; runtime/worker không bao giờ tự cấp sequence.

## Alternatives considered
Dùng một bộ tên cho cả hai (lộ chi tiết runtime vào contract); sequence toàn cục (đơn giản nhưng khó tách theo company khi lên server).

## Consequences
Cần một bảng ánh xạ run.* → agent.run.* trong runtime manager. SSE resume dùng sequence theo company.

## Migration / compatibility impact
Không có.
