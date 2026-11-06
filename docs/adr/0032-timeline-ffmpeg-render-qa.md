# ADR-0032 — Timeline JSON v1, render bằng FFmpeg CLI, QA tất định

**Status:** Accepted (Dung, 2026-11-06) · **Date:** 2026-11-06
**Liên quan:** plan local AI §10 (L10, L11), audit video §6.5–6.6 (B8)

## Decision
- Timeline JSON v1 (pydantic, lưu cùng mỗi lần render): canvas, scenes (visual ảnh + motion Ken Burns + fade), một track voice (ghép từ các đoạn, có khoảng lặng giữa đoạn/scene), nhạc nền tùy chọn (ducking `sidechaincompress`), `loudnorm` −14 LUFS, phụ đề ASS đốt vào hình, preset xuất.
- Preset là dữ liệu: `fb_reel_1080x1920_h264` (9:16, 30 fps, 30–90 s) và `fb_video_1920x1080_h264` (16:9, 180–600 s). AAC 48 kHz stereo, `+faststart`. Encoder `libx264` mặc định, `h264_nvenc` tùy chọn (chọn sau render benchmark L2).
- Renderer dịch timeline sang danh sách tham số FFmpeg tất định (không qua shell), chạy trong thư mục làm việc riêng (đường dẫn phụ đề tương đối, tránh lỗi escape ổ đĩa Windows). Lưu lệnh, phiên bản FFmpeg, log cùng bản render.
- Phụ đề lấy từ thời lượng thật của từng đoạn TTS; trong một đoạn chia dòng theo số ký tự tối đa của profile và chia thời gian theo tỉ lệ ký tự.
- QA (bắt buộc pass): ffprobe (h264, AAC 48 kHz, kích thước, fps, thời lượng trong dải profile), `volumedetect` (không im, không clip), phụ đề (độ dài dòng, nằm trong thời lượng), mọi asset có license `commercial=true` hoặc là upload của người dùng. ASR QA (WER so với văn bản đã chuẩn hóa) chạy khi có provider ASR, nếu không thì ghi `skipped`.
- FFmpeg do người dùng cài (`ORCHESTRA_FFMPEG`, mặc định tìm trong PATH). Không đóng gói kèm app (tránh vấn đề GPL khi phân phối).

## Consequences
- Chuyển cảnh v1 là fade qua màu đen, chưa có xfade.
- Font phụ đề mặc định "Arial" (có dấu tiếng Việt trên Windows); đổi được trong cấu hình.
