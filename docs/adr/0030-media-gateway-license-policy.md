# ADR-0030 — Media gateway là module trong backend; provider khai báo license, chặn non-commercial

**Status:** Proposed · **Date:** 2026-11-06
**Liên quan:** plan local AI §13 (L1, L7), audit video §5.7 (B7)

## Decision
- Module `media_gateway` trong backend FastAPI (không thêm server). Mỗi provider có `ProviderMeta`: `provider_id`, `version`, `kind` (`tts|image|asr|render`), `capabilities`, `hardware` (`device`, `min_vram_mb`, `est_ram_mb`, `exclusive_gpu`, `engine`), `license` (`code`, `weights`, `commercial`, `output_rights`, `source_url`, `checked_at`), `cost` (`local` hoặc `unit/price/currency/checked_at`).
- Pipeline chọn provider theo `kind` + cấu hình company, không gọi tên provider trong code pipeline.
- **License policy**: registry từ chối provider có `commercial != true` (lỗi `license_blocked`). Không có cờ vượt qua trong UI.
- Mỗi provider thật có bản **fake** tạo file thật (WAV, PNG) để test và chạy offline.
- Provider có ở đợt này:
  - TTS: `vieneu` (HTTP tới server OpenAI-compatible `apps/openai_speech.py` của pnnbao97/VieNeu-TTS, Apache-2.0), `zerotts` (sidecar HTTP nhỏ của Orchestra chạy trong venv có `zerotts`, MIT), `fake_tts`.
  - Ảnh: `upload` (người dùng), `openai_images` (cloud, endpoint `POST {base_url}/images/generations` kiểu OpenAI, do Dung cấu hình; license đầu ra theo điều khoản nhà cung cấp, Dung tự xác nhận khi cấu hình), `fake_image`.
  - ASR: `faster_whisper` (sidecar, MIT), `fake_asr`.
  - Render: FFmpeg (ADR-0032).
- Engine chỉ nghe `127.0.0.1`. Không cài custom node ComfyUI (ComfyUI ngoài phạm vi đợt này).

## Consequences
- Provider cloud chỉ chạy khi Dung bấm tạo ảnh; chưa có budget tự động (chi phí ghi `null` khi nhà cung cấp không trả giá).
- Số liệu license được nhập tay vào mã nguồn kèm `checked_at`; phải cập nhật khi đổi phiên bản engine.
