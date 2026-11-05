# Orchestra Studio

Ứng dụng desktop điều hành các tổ chức AI (AI Organization Control Center): tạo Company, Agent, giao việc, theo dõi thực thi và phê duyệt hành động. Bắt đầu local trên Windows với Mock Agent, mở rộng sang nhiều runtime và hybrid sau này.

**Trạng thái:** P0 đã xong phần code (backend, dashboard, mock runtime, Electron). Đang chờ kiểm tra P0 acceptance trên Windows.

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
4. Tạo Demo Video Studio (màn hình Bắt đầu).
5. Tasks & Runs → chạy "sản xuất video giới thiệu sản phẩm".
6. Xem sự kiện chạy trong Activity Console.
7. Trạng thái task/run đổi theo backend.
8. Bấm một task → Inspector hiện kết quả và artifact (bấm để xem nội dung).
9. Chạy "kịch bản lỗi khi duyệt" → thấy `QUALITY_CHECK_FAILED` lan lên Producer và CEO.
10. Đóng app, mở lại → company, agent và lịch sử sự kiện vẫn còn.

## Giới hạn hiện tại (có chủ đích)

- Chỉ có Mock Runtime (L0). Ollama/Claude/OpenAI ở P4.
- Chạy tuần tự, mỗi company một kịch bản tại một thời điểm (ADR-0004/0008).
- Chưa có pause/resume/cancel: runtime mock không hỗ trợ nên UI không hiển thị nút.
- App desktop chạy từ mã nguồn và cần `uv`; chưa có bản cài đặt (cần ADR riêng).

## Quy trình làm việc

1. Chọn task tiếp theo trong `docs/P0_PLAN.md`.
2. Tạo branch `p0/<task-id>-<mô-tả-ngắn>`.
3. Làm, chạy test, mở PR theo template.
4. Kiểm tra trên Windows trước khi merge.

## Không bao giờ commit

Dữ liệu runtime (`data/`, file SQLite), file `.env`, API key, khóa riêng. Xem `.gitignore`.
