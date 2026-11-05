# P5 PLAN — Hybrid-ready Workers · Model Delegation · Backup

**Version:** 0.1 · **Date:** 2026-11-05
**Trạng thái:** Dung yêu cầu làm P5 (2026-11-05, "Cả 2 luôn"). Đề xuất mặc định: worker chạy **cùng máy** bằng giao thức sẵn sàng cho mạng; chạy trên máy khác (LAN/TLS) để sau. ADR 0025–0027 áp dụng theo đề xuất; R1–R10 xong trên `main` (2026-11-05), đã kiểm tra trên Windows; chờ Dung nghiệm thu.
**Phạm vi gốc:** `IMPLEMENTATION_PLAN.md` §2 (P5: remote workers, identity, auth, sandbox, backup/recovery) và §5, `RUNTIME.md` §9–10, `SECURITY.md` §7, §10, `ARCHITECTURE.md` §10.

## 0. Mục tiêu và tiêu chí nghiệm thu

- §5 P5: (1) worker có danh tính, xác thực, heartbeat, thu hồi; (2) mất kết nối **không bao giờ** làm run bị coi là hoàn thành; (3) artifact chuyển an toàn (checksum, giới hạn kích thước).
- Thêm (đã hứa ở P4): agent chạy model thật **tự giao việc** cho cấp dưới.
- Sao lưu/khôi phục dữ liệu cục bộ.

## 1. Quyết định (ADR)

| ADR | Câu hỏi | Quyết định | Lý do |
|---|---|---|---|
| 0025 | Worker và giao thức | Worker là tiến trình riêng (`orchestra-worker`), **chủ động kết nối ra** control plane qua HTTP. Đăng ký bằng mã ghép nối một lần (tạo trên UI, hết hạn 15 phút) → nhận `worker_id` + secret (DB chỉ lưu hash). Mỗi lần gọi dùng access token ngắn hạn (15 phút). Nhận việc bằng long-poll; mỗi việc là một **lease** có hạn, heartbeat gia hạn. Event gửi kèm số thứ tự trong lease (chống gửi lặp/replay). Lease hết hạn hoặc worker bị thu hồi → run `failed` với `WORKER_LOST`/`WORKER_REVOKED` (retryable), không bao giờ `completed`. Artifact gửi kèm SHA-256, server kiểm tra lại, giới hạn 1 MB. Tool vẫn chạy ở control plane qua Tool Gateway (worker gửi yêu cầu, chờ kết quả). Worker P5 chỉ chạy runtime **không cần secret của control plane** (mock, ollama). Backend vẫn chỉ nghe `127.0.0.1` (ADR-0009). | SECURITY §10; không mở mạng khi chưa cần. |
| 0026 | Agent model tự giao việc | Tool nội bộ `team.delegate` {to_role, title, description} chỉ có khi agent có cấp dưới. Orchestrator tạo task con, chạy, trả về tóm tắt + tên artifact cho model. Giới hạn: cấp dưới trực tiếp hoặc vai trò trong company, độ sâu ≤ 8 (như mock), tối đa 5 lần giao mỗi run. | Giữ cùng luật tổ chức với mock; model không tự đổi tổ chức. |
| 0027 | Sao lưu/khôi phục | `POST /backups`: dùng SQLite online backup + artifacts + workspaces → một file zip trong `data/backups/`, kèm manifest checksum; **không** chứa secret (secret ở kho OS). Khôi phục bằng lệnh `orchestra-backend restore <file>` khi app tắt: kiểm tra checksum, giữ bản hiện tại thành `data/pre-restore-<thời gian>/`. UI liệt kê bản sao lưu và nút tạo. | Khôi phục khi đang chạy dễ hỏng dữ liệu; tách thành lệnh riêng. |

Sandbox (SECURITY §7): P5 không thêm tool chạy lệnh. Worker chạy bằng quyền người dùng thường, thư mục làm việc riêng. Rủi ro còn lại ghi trong ADR-0025.

## 2. Task (ước lượng theo buổi 1 giờ)

| ID | Task | Buổi |
|---|---|---|
| R1 | Tùy chọn `think` cho Ollama (xong 0325344; mặc định đổi thành "model tự quyết" và lọc suy luận lẫn vào câu trả lời sau khi đo trên máy Dung) | 1 |
| R2 | Migration 0006: workers, enrollment, leases (xong) | 1 |
| R3 | API worker: ghép nối, token, long-poll lease, heartbeat, event, artifact, tool proxy, thu hồi (xong) | 4–5 |
| R4 | `RemoteWorkerRuntime` trong control plane + quét lease hết hạn (xong) | 2 |
| R5 | Tiến trình `orchestra-worker` (chạy mock/ollama), `pnpm worker` (xong) | 2–3 |
| R6 | Test: mất kết nối, replay, token hết hạn, thu hồi giữa chừng, checksum sai (xong) | 2 |
| R7 | `team.delegate` cho agent model (xong, ADR-0026) | 2 |
| R8 | Sao lưu/khôi phục + UI (xong, ADR-0027) | 2 |
| R9 | UI Worker: ghép nối, trạng thái, heartbeat, thu hồi; chọn chạy trên worker cho agent (xong) | 3 |
| R10 | Kiểm tra trên Windows, README (xong) | 1–2 |
| | **Tổng** | **20–23** |

## 3. Ngoài phạm vi (cố ý)

- Worker trên máy khác qua LAN/Internet (cần TLS, ghép cặp chứng chỉ, mở cổng): bước sau, ADR riêng.
- PostgreSQL cho control plane: chỉ cần khi chạy nhiều người/nhiều máy.
- Worker dùng API key cloud: cần cơ chế cấp secret cho worker; để sau.
- Tool chạy lệnh/thực thi code.

## 4. Rủi ro

- [I] Long-poll + nhiều tiến trình trên SQLite: giữ transaction ngắn, test đồng thời.
- [I] Đồng hồ lệch giữa máy (khi có LAN): lease tính theo đồng hồ server.
- [H] Giao việc đệ quy tốn token: giới hạn số lần và độ sâu, chi phí vẫn ghi theo từng run.
