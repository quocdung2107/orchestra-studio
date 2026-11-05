# ADR-0006 — Nhất quán event P0: state và event trong cùng transaction

**Status:** Accepted · **Date:** 2026-11-05

## Context
ARCHITECTURE §9 yêu cầu transactional outbox; EVENTS §5 cho phép đơn giản hơn ở bản local.

## Decision
Domain service ghi thay đổi state và bản ghi events trong cùng một transaction SQLite. Bảng events đóng vai trò outbox. SSE đọc events theo sequence sau khi commit. Không làm event sourcing.

## Alternatives considered
Outbox riêng + dispatcher (thừa khi chỉ có một DB); event sourcing đầy đủ (phức tạp).

## Consequences
Không mất event khi commit thành công. Khi chuyển PostgreSQL/remote worker cần xem lại cơ chế phát (LISTEN/NOTIFY hoặc polling).

## Migration / compatibility impact
Khi lên PostgreSQL vẫn giữ được mô hình này.
