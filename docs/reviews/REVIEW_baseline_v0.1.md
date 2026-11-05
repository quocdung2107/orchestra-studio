# REVIEW — Baseline kiến trúc v0.1

**Ngày:** 2026-11-05
**Phạm vi:** MASTER_PROMPT.md + 6 tài liệu trong `docs/`
**Bối cảnh:** 1 developer, ~1 giờ/ngày, Windows, chưa có repo/code.
**Trạng thái:** Dung đã chấp nhận cả 9 ADR ngày 2026-11-05 → xem `docs/adr/` và `docs/P0_PLAN.md`.

## 0. Kết luận

Baseline có định hướng tốt và nhất quán ở tầng nguyên tắc (mock-first, backend là source of truth, không giả lập UI, quyền theo capability). Vấn đề chính **không nằm ở định hướng mà ở P0**:

1. **P0 tự mâu thuẫn về phạm vi**: Mock Runtime phải đi qua Task Engine, Orchestrator, Approval, Metrics, nhưng các module đó thuộc P2–P4.
2. **Có 6 quyết định kỹ thuật chưa chốt** sẽ chặn ngay P0-01 → P0-03 (mục 3).
3. **P0 quá nặng cho 1 giờ/ngày**: 10 task, 4 tầng công nghệ (Electron, React, FastAPI, SQLite) phải chạy cùng lúc trước khi thấy kết quả đầu tiên.

Đề xuất: chốt 9 ADR ở mục 3 (đa số chỉ cần bạn chọn A/B), rồi sang bước 2 cắt lại P0.

Quy ước: **[F]** = đọc trực tiếp từ tài liệu, **[I]** = suy luận của mình, **[P]** = đề xuất.

---

## 1. Điểm mạnh nên giữ nguyên

- Tách Agent Definition / Agent Run / Runtime / Worker rõ ràng. [F]
- Capability flags (`supports_pause`, …) để UI không hiển thị nút giả. [F]
- L0 Mock Runtime trước, không cần API key để demo. [F]
- EVENTS §5 đã cho phép P0 dùng "state trong DB + event cho audit/realtime", tránh event sourcing sớm. [F]
- Quy tắc "Create only what the active task needs". [F]

## 2. Mâu thuẫn và lỗ hổng

| # | Vấn đề | Bằng chứng | Mức độ |
|---|---|---|---|
| 1 | Mock Runtime phải đi qua Task Engine, Orchestrator, Approval, Artifact, Metrics, nhưng Tasks/Approvals là P2, Metrics là P4. | RUNTIME §5 vs IMPLEMENTATION_PLAN §2 [F] | **Cao** — không thể hoàn thành P0-08 đúng nghĩa |
| 2 | P0 acceptance yêu cầu "inspect task/run result", nhưng không task P0 nào tạo bảng `tasks` / `agent_runs`. | IMPLEMENTATION_PLAN §4 bước 8 [F] | **Cao** |
| 3 | 10 kịch bản mock (parallel, retry, approval, lesson, KPI, 50 agents) — phần lớn thuộc P2–P4. Không ghi kịch bản nào thuộc P0. | RUNTIME §5 [F] | Trung bình |
| 4 | Hai bộ tên event: `agent.run.started` (EVENTS §3) và `run.started` (RUNTIME §4). Không nói quan hệ giữa chúng. | [F] | Trung bình — ảnh hưởng contract |
| 5 | Nhất quán event: ARCHITECTURE §9 đòi transactional outbox; EVENTS §5 cho phép đơn giản hơn. Chưa chốt cho P0. | [F] | Trung bình |
| 6 | Phạm vi `sequence` của event chưa chốt ("company_id hoặc stream khác"). | DATABASE §2 [F] | Trung bình |
| 7 | **Backend local không có xác thực.** Mọi command phải "authenticate the caller" nhưng P0 không định nghĩa auth. FastAPI chạy trên localhost thì bất kỳ trang web nào đang mở trong trình duyệt hoặc process khác trên máy đều có thể gọi API (CSRF / DNS rebinding). | EVENTS §7, P0-03 out-of-scope [F]; rủi ro [I] | **Cao** — lỗ hổng bảo mật thật |
| 8 | Worker process: kiến trúc nói "Modular Monolith + Worker Process", nhưng P0 không nói mock chạy trong process backend hay process riêng. | ARCHITECTURE §3 [F] | Trung bình |
| 9 | Ai khởi động Python backend khi chạy app desktop? Đóng gói Python cho Windows (PyInstaller/embedded Python) không được nhắc tới. | P0-04 "backend lifecycle strategy" [F] | Thấp trong P0, **cao khi phát hành** |
| 10 | Cách chia sẻ type Python ↔ TypeScript chưa chốt (`packages/contracts` tồn tại nhưng không nói sinh từ đâu). | ARCHITECTURE §6 [F] | Trung bình — dễ trùng lặp schema |
| 11 | Công cụ chưa chọn: quản lý gói Python (uv/pip/poetry), Node (npm/pnpm), có dùng monorepo tool không. | [F] — không có | Chặn P0-01 |
| 12 | `definition_json` của Agent chưa có schema tối thiểu (trường nào là "provider-neutral"?). | DATABASE §2 [F] | Chặn P0-07 |
| 13 | Stack frontend nhiều thư viện cho P0: xyflow, Zustand, shadcn, Playwright-Electron. xyflow chỉ cần ở P1. | MASTER_PROMPT §3 [F]; đánh giá tải [I] | Thấp — chỉ cần hoãn |

## 3. Quyết định cần chốt (ADR)

Mình ghi kèm đề xuất. Bạn chỉ cần trả lời "đồng ý" hoặc chọn phương án khác.

| ADR | Câu hỏi | Đề xuất [P] | Lý do ngắn |
|---|---|---|---|
| 001 | Thứ tự P0: Electron ngay hay sau? | **Chạy React trên trình duyệt + FastAPI trước; bọc Electron ở cuối P0.** | Electron là phần tốn công nhất, không phải giá trị cốt lõi. Kiến trúc đã tách renderer khỏi Node nên đổi sau không tốn thêm. |
| 002 | Công cụ | **uv** (Python), **pnpm workspaces** (Node), không dùng Turborepo/Nx. | Nhanh, chạy tốt trên Windows, ít dependency. |
| 003 | Chia sẻ contract | **OpenAPI do FastAPI sinh là nguồn duy nhất → sinh TS type bằng `openapi-typescript`.** Event schema = Pydantic model, xuất JSON Schema. | Một nguồn sự thật, không viết type 2 lần. |
| 004 | Thêm Task + AgentRun tối thiểu vào P0 | **Có**: bảng `tasks` (không dependency) và `agent_runs`; orchestrator P0 chỉ chạy tuần tự 1 run. Approval/Metrics bỏ khỏi yêu cầu P0-08. | Sửa mâu thuẫn #1, #2. |
| 005 | Kịch bản mock trong P0 | **Chỉ 4**: delegation tuần tự, failure, artifact metadata, chạy lại cho cùng chuỗi event. Còn lại chuyển sang P2+. | Sửa #3. |
| 006 | Nhất quán event | **Ghi state + event trong cùng một transaction SQLite**; bảng `events` chính là outbox; SSE đọc từ bảng `events` theo `sequence`. | Đơn giản, không mất event, đúng EVENTS §5. |
| 007 | Tên event & sequence | **Runtime phát `run.*` (nội bộ), backend chuẩn hóa thành `agent.run.*` trước khi lưu.** `sequence` tăng dần theo `company_id`, do backend cấp. | Sửa #4, #6. Worker không bao giờ tự cấp sequence. |
| 008 | Worker trong P0 | **Mock chạy trong process backend (asyncio task) sau interface `AgentRuntime`.** Tách process riêng khi có Local Python Runtime. | Giữ ranh giới bằng interface, chưa trả giá IPC. |
| 009 | Bảo mật backend local | **Bind `127.0.0.1`, token ngẫu nhiên mỗi lần khởi động, kiểm tra header `Host` và `Origin`.** Khi có Electron, token đi qua preload. | Sửa #7 với chi phí thấp. |

Các điểm có thể để sau, không chặn P0: đóng gói Python cho Windows (#9), schema đầy đủ của `definition_json` (#12, chốt tối thiểu ngay trong P0-07), có dùng Zustand hay không (#13).

## 4. Rủi ro tiến độ

- [I] 1 giờ/ngày phần lớn sẽ là "khởi động lại ngữ cảnh". Mỗi task nên kết thúc bằng trạng thái chạy được + ghi chú "làm tiếp từ đâu".
- [I] Kiểm thử Windows: mình làm việc trên Linux. Mỗi PR cần bạn chạy thử trên máy (hoặc mình chạy qua Remote Control). Ưu tiên lệnh đa nền tảng (không dùng script bash trong `package.json`).
- [I] Ước tính sơ bộ, chưa kiểm chứng: P0 sau khi cắt ≈ 25–35 buổi 1 giờ (5–7 tuần). Bước 2 sẽ cho con số theo từng task.

## 5. Bước tiếp theo

Sau khi bạn chốt mục 3, mình sẽ:
1. Ghi các ADR đã chốt thành file `docs/adr/0001-...md` (sẽ đưa vào repo ở bước 3).
2. Viết lại thứ tự P0 thành các task vừa 1 buổi (bước 2 của kế hoạch).
