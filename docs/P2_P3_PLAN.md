# P2 + P3 PLAN — Task Orchestration · Knowledge & Secretary

**Version:** 0.1 · **Date:** 2026-11-05
**Trạng thái:** Dung yêu cầu "tiếp tục P2, P3" (2026-11-05). ADR 0015–0020 áp dụng theo đề xuất bên dưới; Dung có thể đổi bất kỳ quyết định nào.
**Phạm vi gốc:** `IMPLEMENTATION_PLAN.md` §2 và §5.

## 0. Mục tiêu

- **P2:** task có phụ thuộc, giao việc, chạy song song, retry có giới hạn, pause/resume/cancel theo capability của runtime, phê duyệt hành động L3. Tất cả là hành vi thật của backend, không phải UI giả.
- **P3:** kho tri thức có nguồn gốc (provenance) và tìm kiếm; Thư ký tóm tắt task; bài học phải được người duyệt trước khi thành tri thức; agent đề xuất đổi vai trò, người quyết định.

## 1. Quyết định (ADR)

| ADR | Câu hỏi | Quyết định | Lý do |
|---|---|---|---|
| 0015 | Task graph và lịch chạy | Task có phụ thuộc kiểu finish-to-start, chặn vòng lặp. Scheduler theo company chạy task gốc sẵn sàng, tối đa `max_parallel_runs` (mặc định 3). Task con do agent giao vẫn do run cha chờ; bước `parallel` chạy nhiều task con cùng lúc. Phụ thuộc thất bại: task sau giữ `pending` (bị chặn), không tự fail. | Thay giới hạn "1 kịch bản/company" của P0; retry task trước sẽ mở khóa task sau. |
| 0016 | Retry | Lỗi có cờ `retryable`. Tự retry khi `retryable` và còn lượt (`max_attempts`, backoff mũ). Mỗi lần thử là một run mới (`attempt`). Người dùng có thể retry thủ công task gốc đã fail/cancel. Hành động bên ngoài đã thực thi mà không rõ kết quả thì không bao giờ tự retry. | RUNTIME §10. |
| 0017 | Pause/resume/cancel | Runtime khai báo capability và cài `cancel/pause/resume(run_id)`. API trả 409 `not_supported` nếu runtime không hỗ trợ; UI chỉ hiện nút khi có capability. Cancel lan xuống task con; run cha nhận `CHILD_TASK_CANCELLED`. Mock runtime hỗ trợ cả ba, kiểm tra giữa các bước. | ARCHITECTURE §8, không hiện nút giả. |
| 0018 | Tool Gateway và phê duyệt | Runtime gọi tool qua cổng `call_tool(key, params)` do orchestrator cấp; không tự chạy tool. Gateway: tìm tool → quyết định quyền (ADR-0013) → kiểm tra input schema → nếu cần duyệt thì tạo approval gắn checksum SHA-256 của payload chuẩn hóa, run chuyển `waiting_approval` → người duyệt phải gửi đúng checksum → thực thi đúng một lần, kết quả gắn vào approval. Tool tích hợp sẵn: `kb.search` (L0), `doc.draft` (L1, tạo artifact), `workspace.write` (L2, chỉ ghi trong thư mục workspace của task, kiểm tra đường dẫn, giới hạn kích thước), `social.publish` (L3, **mô phỏng**: không gọi mạng, ghi bản ghi "outbox" có nhãn mô phỏng). Tool khác trả `TOOL_NOT_IMPLEMENTED`. | SECURITY §5, §7, §8. Kết nối mạng thật để P4/P5. |
| 0019 | Tri thức và tìm kiếm | Bảng `knowledge_items` bắt buộc nguồn (`manual`, `artifact`, `task_summary`, `lesson`) + `source_id`. Tìm kiếm SQLite FTS5 (`unicode61 remove_diacritics 2`, gõ không dấu vẫn tìm được); nếu SQLite không có FTS5 thì dùng LIKE. Sửa nội dung tăng `version`, event mang checksum. Tóm tắt task là tóm tắt **tất định** từ cây task/run/artifact, ghi rõ "không dùng AI". | IMPLEMENTATION_PLAN §5 P3: giữ provenance. Không thêm vector DB/embedding trước P4. |
| 0020 | Bài học và đề xuất đổi vai trò | Agent (qua runtime) hoặc người tạo bài học ở trạng thái `proposed`; chỉ người duyệt mới thành tri thức. Đề xuất đổi vai trò (role, phòng ban, quản lý, chỉ dẫn) do agent hoặc người tạo; duyệt thì áp dụng qua service hiện có (cùng kiểm tra hợp lệ, cùng transaction); áp dụng lỗi thì giữ `proposed` và báo lỗi. | Agent không tự thay đổi tổ chức (SECURITY §4). |

## 2. Task (ước lượng theo buổi 1 giờ)

| ID | Task | Buổi |
|---|---|---|
| L1 | Migration 0004: phụ thuộc task, attempt, trạng thái mới, approvals, workspace | 2 |
| L2 | Scheduler + chạy song song + bước `parallel` | 3 |
| L3 | Retry tự động/thủ công | 2 |
| L4 | Pause/resume/cancel + recovery khi khởi động lại | 3 |
| L5 | Tool Gateway + 4 tool tích hợp + approvals + API | 4 |
| L6 | Kịch bản mock P2 (song song, retry, duyệt, cancel) | 1–2 |
| L7 | UI: tạo task + phụ thuộc, nút điều khiển theo capability, màn Phê duyệt | 3–4 |
| M1 | Knowledge + FTS5 + API + nhập artifact | 2–3 |
| M2 | Tóm tắt task (Thư ký) | 1 |
| M3 | Bài học: đề xuất → duyệt → tri thức | 2 |
| M4 | Đề xuất đổi vai trò | 2 |
| M5 | UI Tri thức: tìm kiếm, bài học, đề xuất | 3 |
| N1 | Kiểm tra trên Windows, README | 1–2 |
| | **Tổng** | **29–35** |

## 3. Ngoài phạm vi (cố ý)

- Gọi mạng thật, mạng xã hội thật, email: P4/P5 (cần quản lý credential).
- Sandbox cấp hệ điều hành cho lệnh tùy ý: không có tool chạy lệnh shell ở P2.
- Embedding/vector search: P4 khi có model.
- Thời hạn approval tự hết hạn theo giờ: chỉ hết hạn khi backend khởi động lại (run đã mất).

## 4. Rủi ro

- [I] Chạy song song trên SQLite: mỗi bước là transaction ngắn, WAL + busy_timeout đã có; cần test đồng thời.
- [I] `workspace.write` là tool đầu tiên ghi file thật: kiểm tra đường dẫn và giới hạn kích thước là bắt buộc, có test path traversal.
- [I] Khối lượng UI lớn; ưu tiên đúng hành vi backend trước, UI gọn.
