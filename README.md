# Orchestra Studio

Ứng dụng desktop điều hành các tổ chức AI (AI Organization Control Center): tạo Company, Agent, giao việc, theo dõi thực thi và phê duyệt hành động. Bắt đầu local trên Windows với Mock Agent, mở rộng sang nhiều runtime và hybrid sau này.

**Trạng thái:** P0 và P1 xong, đã kiểm tra trên Windows. P2 (điều phối task, phê duyệt) và P3 (tri thức, Thư ký) xong phần code, đang kiểm tra trên Windows. Kế hoạch: `docs/P2_P3_PLAN.md`.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [`MASTER_PROMPT.md`](MASTER_PROMPT.md) | Mục tiêu sản phẩm và quy tắc bắt buộc cho AI coding agent |
| [`docs/P0_PLAN.md`](docs/P0_PLAN.md) | **Thứ tự task hiện hành** của P0 |
| [`docs/adr/`](docs/adr/) | Quyết định kiến trúc đã chốt |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Kiến trúc tổng thể, module boundaries |
| [`docs/DATABASE.md`](docs/DATABASE.md) | Mô hình dữ liệu |
| [`docs/EVENTS.md`](docs/EVENTS.md) | Event contract, SSE |
| [`docs/RUNTIME.md`](docs/RUNTIME.md) | Agent runtime, adapter, mock |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model, quyền hạn |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Roadmap P0–P5, tiêu chí hoàn thành |
| [`docs/reviews/`](docs/reviews/) | Các bản rà soát baseline |

Khi ADR và baseline khác nhau, **ADR thắng**.

## Cài đặt môi trường dev (Windows)

Cần cài một lần (PowerShell):

```powershell
# Git
winget install --id Git.Git -e
# Python toolchain (ADR-0002)
winget install --id astral-sh.uv -e
# Node.js LTS, rồi cài pnpm (ADR-0002)
winget install --id OpenJS.NodeJS.LTS -e
npm install -g pnpm
```

Mở terminal mới rồi kiểm tra:

```powershell
git --version
uv --version
node --version
pnpm --version
```

Node.js từ bản 25 không còn kèm Corepack, nên không dùng `corepack enable`. Nếu `pnpm` vẫn chưa nhận sau khi cài, đóng và mở lại terminal.

## Chạy ứng dụng

Lần đầu, trong thư mục repo:

```powershell
pnpm install
```

**Ứng dụng desktop (Electron):** tự khởi động backend, không cần API key.

```powershell
pnpm desktop
```

Lần chạy đầu `uv` sẽ tải Python và thư viện nên có thể mất 1–2 phút.

**Chế độ phát triển (trình duyệt, tự reload khi sửa code):** mở 2 terminal.

```powershell
pnpm backend   # terminal 1: API tại http://127.0.0.1:8765
pnpm dev       # terminal 2: mở http://127.0.0.1:5173
```

Muốn xem trong Electron với hot reload: giữ 2 terminal trên, dùng `pnpm desktop:dev` ở terminal thứ 3 nhưng **tắt `pnpm backend`** trước, vì Electron tự khởi động backend riêng.

Dữ liệu (SQLite, artifact, token) nằm trong `data/` ở gốc repo. Xóa thư mục này để bắt đầu lại từ đầu.

## Kiểm tra

```powershell
cd apps/backend; uv run pytest; uv run ruff check .; cd ../..
pnpm typecheck
pnpm test        # gồm kiểm tra openapi.json còn khớp với backend
```

Đổi API backend thì chạy `pnpm contracts` để sinh lại type TypeScript (ADR-0003).

## P0 acceptance (IMPLEMENTATION_PLAN §4)

1. `pnpm desktop` mở được app, không cần API key.
2. Tạo company (màn hình Bắt đầu).
3. Tạo vài agent (Agents → Tạo agent), kích hoạt trong Inspector.
4. Tạo Demo Video Studio (màn hình Bắt đầu → Tạo từ template).
5. Tasks & Runs → chạy "sản xuất video giới thiệu sản phẩm".
6. Xem sự kiện chạy trong Activity Console.
7. Trạng thái task/run đổi theo backend.
8. Bấm một task → Inspector hiện kết quả và artifact (bấm để xem nội dung).
9. Chạy "kịch bản lỗi khi duyệt" → thấy `QUALITY_CHECK_FAILED` lan lên Producer và CEO.
10. Đóng app, mở lại → company, agent và lịch sử sự kiện vẫn còn.

## P1 acceptance (IMPLEMENTATION_PLAN §5)

1. Tạo company từ template "Demo Video Studio" → mở Sơ đồ tổ chức, thấy 8 agent, 4 phòng ban, cạnh báo cáo.
2. Kéo một node, chuyển màn hình rồi quay lại → vị trí còn nguyên.
3. Kéo từ chấm dưới của quản lý xuống chấm trên của nhân viên → đổi người quản lý. Tạo vòng lặp (CEO báo cáo cho nhân viên) → backend từ chối, hiện lỗi.
4. Tạo/đổi trần quyền/lưu trữ phòng ban ở cột phải.
5. Skills & Tools: tạo skill, thêm version; khai báo tool với mức L0–L3.
6. Bấm một agent → Inspector: đổi phòng ban/quản lý, gắn skill (ghim version, có nút nâng version), cấp/thu hồi tool (tool vượt trần không cấp được), sửa định nghĩa thành version mới và so sánh 2 version.
7. Tổng quan: đổi trần quyền của company → quyền tool của agent đổi theo.
8. Agents → Tạo agent: điền nhanh từ mẫu agent, chọn phòng ban.
9. Mọi thay đổi trên xuất hiện trong Activity Console và còn sau khi mở lại app.

## P2 + P3 acceptance (IMPLEMENTATION_PLAN §5)

1. Tạo company từ template "Demo Video Studio" (template mới: trần L3, Producer được xin đăng bài).
2. Tasks & Runs → chạy "chạy song song, retry và phê duyệt đăng bài". Nghiên cứu và Chiến lược chạy cùng lúc; "Duyệt kịch bản" lỗi tạm thời rồi tự chạy lại (2 lần chạy).
3. Thanh bên hiện số yêu cầu chờ ở "Phê duyệt". Mở ra thấy nội dung đăng bài và checksum. Duyệt → bài đăng **mô phỏng** (artifact `outbox-*.json`), task hoàn tất. Chạy lại và chọn Từ chối → Producer và CEO thất bại với `APPROVAL_REJECTED`/`CHILD_TASK_FAILED`.
4. Tạo task tay (+ Tạo task), chọn "chỉ chạy sau" một task khác → task chờ; task trước lỗi thì task sau hiện "bị chặn bởi", bấm "chạy lại" task trước để mở khóa.
5. Bấm một run đang chạy → Inspector có "Tạm dừng"/"Tiếp tục". Nút "hủy" ở task gốc hủy cả cây, kể cả yêu cầu phê duyệt đang chờ.
6. Tổng quan: đổi số task chạy song song tối đa.
7. Task gốc đã xong → "tóm tắt" (tóm tắt tự động, không dùng AI) vào Tri thức. Inspector run → "→ tri thức" để lưu artifact kèm nguồn.
8. Tri thức: tìm không dấu ("thong diep"), sửa ghi chú tăng version; tab Bài học duyệt bài học của Thư ký; tab Đề xuất đổi vai trò duyệt để Reviewer báo cáo cho CMO (xem lại Sơ đồ tổ chức).
9. Đóng app khi đang chờ duyệt, mở lại → yêu cầu chuyển "hết hạn", run báo `INTERRUPTED` (không giả là đã xong).

## P4 acceptance (IMPLEMENTATION_PLAN §5)

1. **Kết nối & model**: thấy 4 runtime (Mock, Ollama, Claude, OpenAI) với capability của từng cái. Ô Ollama hiện trạng thái kết nối, model đã tải (dung lượng, tham số), model đang nạp (RAM/VRAM) và giới hạn chạy đồng thời. Chưa cài Ollama thì báo "Không kết nối được" (không lỗi app).
2. Thêm credential Anthropic hoặc OpenAI: nhập key (lưu vào Windows Credential Manager, mục `orchestra-studio`) hoặc tên biến môi trường. Key không bao giờ hiện lại; bấm "Kiểm tra" để gọi thử provider (liệt kê model, không tốn token). Có "Xoay key" và "Thu hồi".
3. Agents → chọn một agent → "Runtime & model" → "Đổi": chọn Claude + credential (mặc định `claude-opus-5-5`, effort `medium`), hoặc Ollama + model đã tải. Lưu tạo phiên bản agent mới. Thiếu credential hoặc thêm khóa kiểu `api_key` vào settings sẽ bị từ chối.
4. Tasks & Runs → "+ Tạo task" giao cho agent đó. Agent gọi model thật, có thể dùng tool đã được cấp (qua Tool Gateway, L3 vẫn chờ duyệt); kết quả thành artifact Markdown. Inspector run hiện token vào/ra và chi phí **ước tính**. Run model thật hủy được, không có tạm dừng.
5. **Hiệu suất (KPI)**: số run, tỉ lệ thành công, retry, thời gian trung bình, token, chi phí ước tính theo company, agent và runtime. Mỗi số ghi nguồn và độ tin cậy; model không có trong bảng giá (`apps/backend/src/orchestra_backend/metrics/pricing.yaml`) hiện "chưa có giá" thay vì đoán.
6. Thu hồi credential khi agent còn dùng → run tiếp theo thất bại ngay với `CREDENTIAL_REVOKED`, không gọi provider.

Lưu ý chi phí: gọi Claude/OpenAI tính tiền theo token. Mock vẫn là mặc định; mỗi run có giới hạn số lượt gọi model (`max_turns`, mặc định 8) và `max_tokens`.

## Giới hạn hiện tại (có chủ đích)

- Agent chạy model thật giao việc qua tool `team.delegate` (chỉ cho cấp dưới trực tiếp, tối đa 5 lần mỗi run); các task con chạy lần lượt, không song song.
- Model thật: không streaming, không tạm dừng/tiếp tục giữa chừng (chỉ hủy).
- Bảng giá là file tĩnh có ngày; chi phí là ước tính, không phải hóa đơn. Chưa có giá OpenAI.
- Tool tích hợp: `kb.search`, `doc.draft`, `workspace.write` (chỉ ghi trong `data/workspaces/<company>/<task>/`), `social.publish` (**mô phỏng**, không gọi mạng). Kết nối thật ở P4/P5 (ADR-0018).
- Tạm dừng một run chỉ dừng bước của chính run đó; task con đang chạy vẫn chạy tiếp.
- Tìm kiếm tri thức là full-text (SQLite FTS5), chưa có tìm theo ngữ nghĩa.
- App desktop chạy từ mã nguồn và cần `uv`; chưa có bản cài đặt (cần ADR riêng).

## Quy trình làm việc

1. Chọn task tiếp theo trong `docs/P0_PLAN.md`.
2. Tạo branch `p0/<task-id>-<mô-tả-ngắn>`.
3. Làm, chạy test, mở PR theo template.
4. Kiểm tra trên Windows trước khi merge.

## Không bao giờ commit

Dữ liệu runtime (`data/`, file SQLite), file `.env`, API key, khóa riêng. Xem `.gitignore`.
