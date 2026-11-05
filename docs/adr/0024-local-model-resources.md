# ADR-0024 — Giới hạn tài nguyên model cục bộ hiển thị và có hàng đợi

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- `ORCHESTRA_OLLAMA_URL` (mặc định `http://127.0.0.1:11434`), `ORCHESTRA_OLLAMA_MAX_CONCURRENCY` (mặc định 1).
- Adapter Ollama giữ semaphore; run vượt giới hạn ở trạng thái `queued` cho đến khi có chỗ.
- `GET /runtimes/{id}/health`: kết nối, phiên bản, model có sẵn (dung lượng, tham số, lượng tử hóa), model đang nạp (RAM, VRAM, hết hạn), số run đang chạy/chờ và giới hạn.
- UI "Kết nối & model" hiển thị các số này.
