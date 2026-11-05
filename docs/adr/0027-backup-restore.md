# ADR-0027 — Sao lưu trong app, khôi phục bằng lệnh khi app tắt

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- `POST /api/v1/backups` tạo `data/backups/orchestra-backup-<UTC time>.zip`:
  - `orchestra.db`: bản chụp nhất quán qua SQLite online backup API (an toàn khi app đang chạy, WAL).
  - `artifacts/**`, `workspaces/**`.
  - `manifest.json`: `format` (=1), thời điểm, phiên bản app, revision Alembic, SHA-256 + kích thước từng file.
  - **Không** chứa secret (nằm trong kho OS, ADR-0021) và không chứa `backend-token`.
- Mỗi lúc chỉ một bản sao lưu (`BACKUP_BUSY`). File ghi ra `.part` rồi đổi tên, không để lại zip dở.
- `GET /api/v1/backups` liệt kê; file hỏng vẫn hiện với `files = null`.
- Khôi phục: `pnpm restore <file>` (`orchestra-backend restore`), không có API:
  1. Từ chối nếu có tiến trình nghe ở cổng backend (`BACKEND_RUNNING`).
  2. Kiểm tra manifest, danh sách file khớp, đường dẫn an toàn (không tuyệt đối, không `..`, chỉ `orchestra.db`, `artifacts/`, `workspaces/`), checksum từng file.
  3. Hỏi lại (trừ khi `--yes`), chuyển dữ liệu hiện tại (db, -wal, -shm, artifacts, workspaces) vào `data/pre-restore-<time>/`, rồi giải nén.
- `pnpm backup` tạo bản sao lưu từ dòng lệnh.

## Consequences
- Lần mở app sau khi khôi phục chạy migration như thường; bản sao lưu cũ hơn được nâng schema. Bản sao lưu từ phiên bản app **mới hơn** sẽ không mở được bằng app cũ (Alembic không biết revision); hiện chưa chặn trước, chỉ ghi revision vào manifest.
- Credential trong DB chỉ là tham chiếu; khôi phục sang máy khác cần nhập lại key.
- Chưa có lịch sao lưu tự động hay xóa bản cũ.
