# Orchestra Studio — Bộ tài liệu nền tảng

Bộ tài liệu này đóng băng định hướng kiến trúc ban đầu cho **Orchestra Studio**: ứng dụng desktop điều hành các tổ chức AI, có thể mở rộng từ local sang hybrid/server và hỗ trợ nhiều AI runtime.

## Tài liệu

- `MASTER_PROMPT.md`: prompt tổng thể để đưa cho Claude Code/AI coding agent.
- `docs/ARCHITECTURE.md`: kiến trúc tổng thể, module boundaries và luồng dữ liệu.
- `docs/DATABASE.md`: mô hình dữ liệu và nguyên tắc lưu trữ.
- `docs/EVENTS.md`: event contract, state projection và API realtime.
- `docs/RUNTIME.md`: Agent definition, runtime adapter, execution tiers và worker.
- `docs/SECURITY.md`: threat model và chính sách quyền hạn.
- `docs/IMPLEMENTATION_PLAN.md`: roadmap, P0 task breakdown và tiêu chí hoàn thành.

## Cách sử dụng

1. Đọc `MASTER_PROMPT.md` để hiểu mục tiêu và các nguyên tắc không được phá vỡ.
2. Đọc các tài liệu trong `docs/` trước khi triển khai.
3. Giao Claude Code thực hiện từng TASK trong `IMPLEMENTATION_PLAN.md`, không giao toàn bộ roadmap trong một lần.
4. Trước mỗi TASK, yêu cầu AI kiểm tra trạng thái repo thực tế và báo cáo file dự kiến sửa.
5. Sau mỗi TASK, chạy test, kiểm tra diff và cập nhật tài liệu nếu có quyết định kiến trúc mới.

## Trạng thái

Đây là **baseline kiến trúc v0.1**, không phải đặc tả đã được kiểm chứng bằng implementation. Những điểm chưa được quyết định phải được ghi thành ADR (Architecture Decision Record), không tự ý suy diễn thành yêu cầu.
