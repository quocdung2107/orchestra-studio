# ADR-0025 — Worker là tiến trình riêng, kết nối ra, nhận việc theo lease

**Status:** Accepted (phương án "cùng máy, giao thức sẵn cho mạng"; chạy qua LAN để sau) · **Date:** 2026-11-05

## Decision
**Danh tính**
- UI tạo mã ghép nối (10 ký tự, một lần, hết hạn sau 15 phút, `ORCHESTRA_WORKER_PAIRING_TTL_S`). `orchestra-worker pair <mã>` đổi mã lấy `worker_id` + secret. Secret lưu ở kho OS của máy worker (keyring, như ADR-0021); DB chỉ giữ SHA-256 của secret, mã và token.
- Mỗi lần gọi dùng access token ngắn hạn (`ORCHESTRA_WORKER_TOKEN_TTL_S`, mặc định 15 phút) lấy từ `POST /worker/token`. Worker tự lấy lại khi gần hết hạn hoặc khi gặp 401.
- Thu hồi (`POST /workers/{id}/revoke`): xóa token, chặn cấp token mới (403 `WORKER_REVOKED`), các run đang chạy trên worker đó thất bại `WORKER_REVOKED` (retryable).
- Endpoint `/api/v1/worker/*` không dùng token UI (ADR-0009) mà dùng bearer token của worker; token worker không mở được endpoint UI. Kiểm tra Host loopback vẫn áp dụng; backend vẫn chỉ nghe `127.0.0.1`.

**Giao việc**
- Runtime `worker` với settings `{runtime: "mock"|"ollama", worker_id?: ghim một worker, settings: {...của runtime bên trong}}`. Runtime cần secret của control plane (Claude, OpenAI) không chạy trên worker.
- Mỗi lần chạy tạo một lease (bảng `worker_leases`); trạng thái sống giữ trong `WorkerHub` (một tiến trình control plane). Worker long-poll `GET /worker/lease?wait=` (tối đa `ORCHESTRA_WORKER_POLL_MAX_S`).
- Không có worker phù hợp đang hoạt động → run thất bại ngay `WORKER_UNAVAILABLE`. Có nhưng không ai nhận trong `ORCHESTRA_WORKER_DISPATCH_TIMEOUT_S` (300 s) → `WORKER_UNAVAILABLE`.
- Lease có hạn `ORCHESTRA_WORKER_LEASE_TTL_S` (30 s); heartbeat hoặc gửi event gia hạn. Hết hạn → `WORKER_LOST` (retryable). Backend khởi động lại → lease cũ đánh dấu `lost`, run đã thất bại `INTERRUPTED` (như trước).
- **Bất biến:** run trên worker chỉ `completed` khi worker gửi `run.completed` trên lease còn sống. Sau khi lease đóng, mọi lời gọi nhận 409 `LEASE_CLOSED`.
- Event gửi theo lô có `seq` tăng dần từng lease: `seq` cũ → 409 `SEQ_REPLAY` (worker coi như đã nhận), nhảy cóc → 409 `SEQ_GAP`. Event được kiểm theo cùng schema của runtime cục bộ (ADR-0007); event kết thúc phải ở cuối lô.
- Artifact kèm `sha256`; server tính lại trên nội dung UTF-8 và giới hạn 1 MB (`ARTIFACT_CHECKSUM`, `ARTIFACT_TOO_LARGE`).
- Tool: worker gọi `POST /worker/leases/{id}/tool-calls`; control plane chạy qua Tool Gateway của run (quyền, duyệt L3, `team.delegate`). Worker không có quyền tool riêng.
- Hủy: đóng lease ngay, run `cancelled`; worker biết qua 409 ở heartbeat/event kế tiếp và dừng runtime cục bộ.

## Consequences
- Một control plane, một tiến trình: trạng thái lease sống trong bộ nhớ là đủ; nhiều tiến trình control plane cần lưu trạng thái này vào DB.
- Chạy qua LAN cần TLS và cách đưa URL/chứng chỉ cho worker: ADR riêng. Giao thức không phải đổi.
- Mã ghép nối không có giới hạn số lần thử; chấp nhận được vì chỉ nghe loopback và mã hết hạn sau 15 phút. Mở LAN thì phải thêm.
- KPI theo runtime ghi `worker` cho các run này; usage vẫn ghi provider/model thật của runtime bên trong.
