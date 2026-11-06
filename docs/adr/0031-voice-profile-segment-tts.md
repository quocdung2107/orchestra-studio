# ADR-0031 — Voice profile có version, chuẩn hóa tiếng Việt riêng, TTS theo đoạn

**Status:** Accepted (Dung, 2026-11-06) · **Date:** 2026-11-06
**Liên quan:** plan local AI §5.3–5.4 (L8, L9); Dung chọn giọng nữ miền Nam, có thể đổi

## Decision
- `voice_profiles` + `voice_profile_versions` (không sửa tại chỗ; sửa = version mới): `engine`, `voice` (tên giọng mẫu của engine), `dialect` (`south|north`), `speed`, `params_json` (temperature, top_k…), `lexicon_json` (từ điển phát âm của kênh), `reference_asset_id` + `consent_note` (khi clone).
- Mặc định tạo profile "Giọng kênh — nữ miền Nam": VieNeu `Thùy Dung` (nằm trong nhóm Southern + editors' pick theo README; giới tính suy từ tên, **chưa nghe kiểm chứng**). Đổi giọng/engine trong UI, không cố định trong code.
- Chuẩn hóa văn bản chạy **trong backend, trước TTS**, lưu `normalized_text`: số, số thập phân, %, tiền, ngày, giờ, đơn vị, số La Mã sau "thế kỷ/quý", từ điển kênh. Phương ngữ: `south` đọc "ngàn", "lẻ"; `north` đọc "nghìn", "linh".
- Chia đoạn theo câu, mỗi đoạn ≤ `max_chars` (mặc định 180 ký tự ≈ 12–15 giây). Đoạn là đơn vị TTS, phụ đề và tạo lại.
- Mọi WAV được chuẩn về 48 kHz mono s16 trước khi lưu. `speed` ≠ 1 áp bằng FFmpeg `atempo` khi engine không hỗ trợ (server VieNeu nhận nhưng **bỏ qua** `speed`).
- Tạo lại một đoạn chỉ sinh lại đoạn đó; các đoạn khác giữ nguyên asset.

## Consequences
- Không có seed trong API VieNeu, nên sinh lại cùng một câu có thể khác nhẹ; nhất quán dựa vào giọng mẫu cố định.
- Server VieNeu mặc định bật watermark âm thanh (`VIENEU_WATERMARK=1`). Dung quyết định giữ hay tắt khi chạy engine.
