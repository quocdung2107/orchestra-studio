# ADR-0029 — Job runner bền vững trong SQLite + resource scheduler cho một PC

**Status:** Accepted (Dung, 2026-11-06) · **Date:** 2026-11-06
**Liên quan:** audit video §5.6 (B2), plan local AI §14 (L6)

## Context
Run hiện tại bị đánh `failed` khi app khởi động lại. Video dài chạy nhiều giờ trên laptop 8 GB RAM / 4 GB VRAM, phải tiếp tục được sau khi tắt máy và không được nạp hai model nặng cùng lúc.

## Decision
- Bảng `jobs`: `kind`, `payload_json`, `status` (`queued|running|succeeded|failed|cancelled`), `priority`, `attempts`, `max_attempts`, `next_run_at`, `lease_until`, `idempotency_key` (unique theo company), `engine`, `result_json`, `error`.
- Một vòng lặp asyncio trong backend (không Redis/Celery). Nhận job bằng `UPDATE … WHERE status='queued'` trong `BEGIN IMMEDIATE`, gia hạn lease định kỳ.
- **Khởi động lại**: job `running` có lease hết hạn được đưa về `queued` (mọi handler hiện tại idempotent vì output là file theo sha256). Handler cloud phải lưu `external_id` trước khi chờ; khi resume thì hỏi trạng thái thay vì gửi lại (quy ước cho adapter, chưa có adapter cloud async).
- **Scheduler**:
  - Một GPU lease độc quyền; `cpu_slots` (mặc định 1 trên máy hiện tại); số job chạy song song `ORCHESTRA_MEDIA_MAX_PARALLEL` (mặc định 1).
  - Cổng bộ nhớ: so `est_ram_mb`/`min_vram_mb` của provider với RAM/VRAM trống (đọc `/proc/meminfo`, `GlobalMemoryStatusEx` qua ctypes, `nvidia-smi`; không thêm `psutil`). Thiếu thì tắt engine nhàn rỗi theo LRU rồi đo lại; vẫn thiếu thì hoãn job, quá số lần hoãn thì `failed: insufficient_resources`.
  - Ưu tiên: `priority` (UI đang chờ > lô), rồi **ưu tiên engine đang nạp** để gom việc theo engine, rồi thứ tự tạo.
  - Retry có backoff; lỗi OOM do adapter báo thì retry ở cấu hình nhẹ hơn nếu adapter hỗ trợ.
- **Engine manager**: mỗi engine là tiến trình riêng (venv riêng, không torch trong backend). `ensure_running` → chờ `/health`; `stop` giết cả cây tiến trình (`taskkill /T /F` trên Windows, process group trên POSIX). Engine "external" (Dung tự mở, ví dụ bộ cài VieNeu) chỉ được kiểm tra health, không bị tắt. `keep_warm_s` mặc định 0 (máy 8 GB).

## Consequences
- Chưa dùng Windows Job Object (kill-on-close). Nếu backend chết đột ngột, tiến trình engine có thể còn chạy; lần khởi động sau phát hiện qua cổng/health. Ghi nhận là nợ kỹ thuật.
- Không phân tán; worker LAN (ADR-0025) là bước sau.
