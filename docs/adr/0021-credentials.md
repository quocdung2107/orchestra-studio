# ADR-0021 — Credential: secret trong kho của hệ điều hành, DB chỉ giữ tham chiếu

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- Bảng `credentials`: `provider` (`anthropic`, `openai`), `label`, `company_id` (null = mọi company), `store` (`keyring` | `env` | `memory`), `store_ref`, `status` (`active` | `revoked`), thời điểm tạo/xoay/thu hồi/kiểm tra. Không có cột secret.
- `keyring` (service `orchestra-studio`, username = id credential). Nếu backend keyring là `fail` hoặc plaintext thì từ chối lưu (`secret_store_unavailable`).
- `env`: chỉ lưu tên biến môi trường; đọc lúc chạy.
- `memory`: chỉ cho test/dev (`ORCHESTRA_SECRET_STORE=memory`), UI ghi rõ "không bền, không an toàn".
- Secret chỉ được đọc trong backend ngay trước khi gọi provider, truyền qua `RunRequest.credential` (không lưu DB, không vào event).
- API: tạo, xoay, thu hồi (xóa khỏi keyring, giữ dòng để audit), kiểm tra kết nối. Không endpoint nào trả secret.
- Redaction: secret đã nạp được đăng ký vào bộ lọc log; mẫu `sk-…` luôn bị che; lỗi từ adapter đi qua `redact()` trước khi ghi.
- Agent tham chiếu bằng `runtime.settings.credential_id`; kiểm tra provider khớp runtime và phạm vi company.

## Alternatives
- File mã hóa tự quản: phải tự giữ khóa, yếu hơn kho OS.
- Electron `safeStorage`: secret phải đi qua renderer/main, trái SECURITY §6.
