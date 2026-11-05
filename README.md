# Orchestra Studio

Ứng dụng desktop điều hành các tổ chức AI (AI Organization Control Center): tạo Company, Agent, giao việc, theo dõi thực thi và phê duyệt hành động. Bắt đầu local trên Windows với Mock Agent, mở rộng sang nhiều runtime và hybrid sau này.

**Trạng thái:** P0 — đang dựng nền tảng. Chưa có code chạy được.

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

Lệnh chạy backend và frontend sẽ được thêm vào đây ở task A2 và C1.

## Quy trình làm việc

1. Chọn task tiếp theo trong `docs/P0_PLAN.md`.
2. Tạo branch `p0/<task-id>-<mô-tả-ngắn>`.
3. Làm, chạy test, mở PR theo template.
4. Kiểm tra trên Windows trước khi merge.

## Không bao giờ commit

Dữ liệu runtime (`data/`, file SQLite), file `.env`, API key, khóa riêng. Xem `.gitignore`.
