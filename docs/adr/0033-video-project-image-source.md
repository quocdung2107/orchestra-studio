# ADR-0033 — Video project từ kịch bản, nguồn ảnh chọn khi bắt đầu (nhập tay / cloud)

**Status:** Accepted (Dung, 2026-11-06) · **Date:** 2026-11-06
**Liên quan:** plan local AI §20 (L12); câu trả lời của Dung ngày 2026-11-06

## Decision
- `video_projects` (profile `short|long`, voice profile, `image_source`, trạng thái) + `video_scenes` (narration, visual prompt, ảnh) + `voice_segments` + `video_renders` (timeline JSON, asset MP4, QA).
- Tạo project từ **kịch bản JSON** (mẫu trong `templates/video_samples/`). Viết kịch bản bằng Claude là bước sau (B4/B6), Dung đã chọn Claude.
- **Nguồn ảnh phải được xác nhận** trước khi sản xuất: `manual` (Dung tải ảnh) hoặc `cloud` (adapter ảnh cloud Dung cấu hình). Ở **cả hai** chế độ, mỗi scene có ô thêm/thay ảnh. Ở chế độ cloud có thêm nút tạo ảnh từng scene hoặc tất cả scene thiếu ảnh. Đổi nguồn sau đó được, có xác nhận lại.
- Ảnh giữ chỗ (`fake_image`) chỉ dùng khi Dung bấm "dùng ảnh giữ chỗ" để thử pipeline; QA ghi cảnh báo.
- Pipeline điều khiển theo trạng thái: `advance(project)` tạo job còn thiếu (TTS đoạn → render → QA); mỗi job xong gọi lại `advance`. Nhờ vậy tắt app giữa chừng rồi mở lại vẫn chạy tiếp.
- Video AI: chỉ qua cloud, chưa làm trong đợt này (Dung đang tìm API miễn phí). Không đăng Facebook.

## Consequences
- Chưa có Campaign/CEO/duyệt plan; project là đơn vị thấp nhất để kiểm chứng pipeline media trước.
