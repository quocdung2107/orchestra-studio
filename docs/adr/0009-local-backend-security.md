# ADR-0009 — Bảo mật backend local

**Status:** Accepted · **Date:** 2026-11-05

## Context
Backend FastAPI chạy trên localhost không có xác thực; trang web khác hoặc process khác có thể gọi API (CSRF, DNS rebinding).

## Decision
Backend chỉ bind 127.0.0.1. Mỗi lần khởi động sinh token ngẫu nhiên; mọi request /api/v1 (trừ health) phải có token. Kiểm tra header Host (chỉ localhost/127.0.0.1) và Origin (danh sách cho phép). Chế độ dev: token đọc từ file trong thư mục dữ liệu local. Khi có Electron: token truyền qua preload.

## Alternatives considered
Không xác thực (rủi ro thật); OAuth/user account (thừa cho single-user local).

## Consequences
Thêm một bước cấu hình cho frontend dev. Không bảo vệ trước malware cùng user trên máy (ghi nhận là rủi ro còn lại).

## Migration / compatibility impact
P5 thay bằng xác thực thật cho hybrid.
