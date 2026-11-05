# Hướng dẫn cho AI coding agent

Đọc theo thứ tự trước khi làm bất kỳ task nào:
1. `MASTER_PROMPT.md` — mục tiêu và quy tắc bắt buộc.
2. `docs/adr/` — quyết định đã chốt. ADR thắng baseline khi hai bên khác nhau.
3. `docs/P0_PLAN.md` — thứ tự task hiện hành (thay thế thứ tự trong `IMPLEMENTATION_PLAN.md` §3).
4. Tài liệu liên quan trong `docs/`.

Quy tắc ngắn:
- Mỗi thay đổi làm đúng một task, kết thúc ở trạng thái chạy được và test pass.
- Trước khi commit: `uv run pytest` + `uv run ruff check .` (apps/backend), `pnpm typecheck`, `pnpm test`.
- Môi trường dev chính là Windows: script phải đa nền tảng, không dùng cú pháp bash trong `package.json`.
- Quyết định mới ảnh hưởng kiến trúc → thêm ADR trong `docs/adr/`.
- Điền đủ PR template, đặc biệt mục "Làm tiếp từ đâu".
