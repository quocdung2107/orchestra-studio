# ADR-0028 — Media store nhị phân theo nội dung (sha256) và bảng Asset

**Status:** Accepted (Dung, 2026-11-06) · **Date:** 2026-11-06
**Liên quan:** audit video §5.8, §6.4 (B1), plan local AI §20 (L5)

## Context
Artifact hiện tại là text ≤ 1 MB (ADR-0004). Sản xuất video cần ảnh, WAV, MP4 hàng trăm MB, có lineage và kiểm tra toàn vẹn.

## Decision
- File nằm ở `data/media/<ab>/<cd>/<sha256>` (content-addressed). Ghi ra `.part` trong cùng ổ rồi đổi tên, nên không có file dở. Cùng nội dung chỉ lưu một lần.
- Bảng `assets`: `company_id`, `kind` (`image|voice|music|subtitle|render|reference_audio|other`), `sha256`, `mime`, `bytes`, `duration_s`, `width`, `height`, `provider`, `model`, `params_json`, `license_json`, `parent_asset_id`, `source` (`upload|provider|render`), `retention` (`temp|keep`), `label`.
- Upload: `PUT /companies/{id}/assets?kind=&filename=` với body thô (stream, giới hạn kích thước theo kind). Không thêm `python-multipart`.
- Đọc: `GET /assets/{id}/content` có `Range` (206) để xem video. UI dùng URL cùng origin trực tiếp trong `<img>`/`<video>`; proxy của shell Electron/Vite gắn token, nên token **không** nằm trong URL.
- Kiểm tra định dạng bằng magic bytes (PNG/JPEG/WebP/WAV/MP3/MP4), không tin đuôi file hay `Content-Type` của client.
- Backup (ADR-0027) thêm cây `media/`.

## Consequences
- Xóa asset chỉ xóa hàng; file chỉ bị dọn khi không còn hàng nào trỏ tới (dọn `temp` để sau).
- Backup có thể lớn; lọc theo `retention` là việc sau.
