# L1–L12: báo cáo trạng thái (2026-11-06)

Branch: `claude/project-thread-lpp66w`. Lượt chạy dừng ở L12 để Dung đánh giá một lần.

## 1. Quyết định

**2026-11-06: Dung chốt cả D1–D6 theo cột khuyến nghị.** ADR 0028–0033 chuyển sang Accepted; watermark giữ khi thử; giọng chờ nghe thử; API ảnh Dung tìm; RAM kiểm tra trước khi mua; bench chạy trên máy Dung.

Bảng gốc:

| # | Quyết định | Khuyến nghị | Ảnh hưởng nếu chưa chốt |
|---|---|---|---|
| D1 | Chấp nhận ADR 0028–0033 (đang "Proposed") | Chấp nhận | Chưa merge vào main |
| D2 | Watermark VieNeu (`VIENEU_WATERMARK=1` mặc định) giữ hay tắt | Giữ khi thử nghiệm; quyết lại trước khi đăng | Không chặn |
| D3 | Giọng mặc định "Thùy Dung" (VieNeu, miền Nam): **giới tính suy từ tên, chưa nghe thử** | Nghe 3 giọng nữ miền Nam bằng bench L3 rồi chọn | Có thể là giọng sai |
| D4 | API ảnh cloud: base URL, model, key, và **có cho dùng thương mại không** | Dung tự tìm API free (đã nói). Nhập trong "Cài đặt sản xuất" | Chỉ dùng được ảnh thủ công; ảnh cloud bị chặn bởi license policy cho đến khi tick "thương mại" |
| D5 | Nâng RAM lên 2×16 GB? (chưa biết một thanh có hàn chết không) | Kiểm tra bằng CPU-Z/mở máy trước khi mua | Chỉ 1 engine chạy một lúc |
| D6 | Chạy benchmark L2–L4 trên máy Dung (cần cài FFmpeg + VieNeu) | Qua Remote Control, khoảng 1 giờ | Số đo hiện chỉ có từ VM cloud |

## 2. Đã làm, theo từng bước

| Bước | Nội dung | Trạng thái |
|---|---|---|
| L1 | ADR 0028–0033: media store, durable jobs + resource scheduler, media gateway + license policy, voice profile + TTS theo đoạn, timeline + FFmpeg render + QA, video project + nguồn ảnh | Viết xong, chờ D1 |
| L2 | Bench render `bench/render/` (R1–R4) | Chạy trên VM cloud (`bench/results/reference_cloud_vm_render.csv`): 30 s video render trong 14,5 s, 90 s → 42,5 s, 300 s → 141 s (libx264, khoảng 2,1× thời gian thực). **Chưa chạy trên máy Dung** |
| L3 | Bench TTS `bench/tts/` (T1–T11, file nghe thử ẩn tên + phiếu MOS) | Script xong; **chưa chạy** (HF bị chặn trên cloud) |
| L4 | Bench ASR `bench/asr/` (faster-whisper, PhoWhisper) | Script xong; **chưa chạy** |
| L5 | Media store theo sha256, upload có giới hạn kích thước, kiểm MIME bằng magic bytes, `Range` cho video, đưa vào backup | Xong + test |
| L6 | Bảng jobs bền (lease, retry, idempotency, recover sau restart), resource scheduler (GPU lease, CPU slot, cổng RAM/VRAM), engine manager (khởi động/tắt tiến trình engine, kill cả cây) | Xong + test |
| L7 | Media gateway: provider VieNeu, ZeroTTS, faster-whisper, ảnh kiểu OpenAI; provider giả cho test; license policy chặn `commercial != True` | Xong; adapter thật **chỉ kiểm theo mã nguồn/README**, chưa gọi engine thật |
| L8 | Chuẩn hoá văn bản tiếng Việt (số, tiền, đơn vị, ngày giờ, số La Mã, từ điển phát âm, phương ngữ Nam/Bắc), tách đoạn | Xong + test |
| L9 | Voice profile có phiên bản (đổi giọng = phiên bản mới, không ghi đè); mặc định giọng nữ miền Nam, đổi được trong UI | Xong + test; giọng chờ D3 |
| L10 | Timeline JSON v1 → FFmpeg (Ken Burns, fade, phụ đề ASS, nhạc nền ducking, loudnorm −14 LUFS), QA bằng ffprobe (14 kiểm tra) + WER qua ASR | Xong + test; MP4 thật qua QA |
| L11 | Video project: chọn cách nhận ảnh (thủ công / cloud) bằng nút xác nhận, khung thêm ảnh ở cả hai chế độ, đọc lại một đoạn, render lại chỉ khi nội dung đổi, tiếp tục sau khi restart | Xong + test end-to-end |
| L12 | UI "Sản xuất video" + "Cài đặt sản xuất"; 2 mẫu (`templates/video_samples/`: short ~54 s, long 15 cảnh) | Xong; kiểm bằng Playwright với provider giả |

## 3. Đã kiểm chứng và còn là giả định

**Đã kiểm chứng (trên VM Linux cloud):**
- Toàn bộ suite backend pass, ruff sạch, `pnpm typecheck` + `pnpm test` pass.
- Mẫu short chạy qua UI: chọn nguồn ảnh → upload → sản xuất → MP4 1080×1920, H.264/AAC 48 kHz, 55,6 s, mean −16,3 dB, max −9,3 dB. QA pass 13/14; kiểm tra còn lại cố ý báo "có dữ liệu giả lập, không dùng để đăng".
- Restart backend giữa chừng → job tiếp tục, không mất.

**Giả định chưa kiểm:**
- API thật của VieNeu (đã đọc mã nguồn server), ZeroTTS và faster-whisper (đọc từ README; sidecar chỉ thử với module giả).
- Hiệu năng trên Windows/laptop của Dung; NVENC chưa thử.
- Font phụ đề "Arial" trên Windows hiển thị dấu tiếng Việt tốt (khả năng cao, chưa thấy).
- Giới tính và chất lượng giọng "Thùy Dung".

## 4. Chạy thử trên máy Dung

1. `git fetch && git checkout claude/project-thread-lpp66w`, `pnpm install`, `cd apps/backend && uv sync`.
2. `winget install Gyan.FFmpeg` (bắt buộc để render).
3. `pnpm desktop` → "Sản xuất video" → "Tạo từ mẫu" → chọn "Ảnh thủ công" → xác nhận → thả ảnh vào từng cảnh → "Sản xuất".
4. Giọng thật: cài VieNeu theo `docs/MEDIA_ENGINES.md`, rồi bật engine trong "Cài đặt sản xuất". Nếu chưa cài, chọn provider `fake_tts` để thử luồng.
5. DB migration 0007 tự chạy, chỉ thêm bảng mới.

## 5. Nợ kỹ thuật đã ghi nhận

- Chưa dùng Windows Job Object; engine bị kill bằng `taskkill /T` (ADR-0029).
- Chưa đăng Facebook (đúng phạm vi); chưa có agent viết kịch bản tích hợp vào pipeline (Q4: Claude viết, sẽ là bước sau).
- Thẻ cảnh trong UI: dòng đoạn văn dài bị cắt, đã chỉnh layout nhưng chưa xem lại trên màn hình nhỏ.

## 6. Làm tiếp từ đâu

Sau khi Dung chốt D1–D6: chạy bench L2–L4 trên máy Dung (Remote Control), chọn giọng, ghi kết quả vào `bench/results/`, rồi mở PR vào main.
