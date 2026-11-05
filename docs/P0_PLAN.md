# P0 PLAN — chia theo buổi 1 giờ

**Version:** 0.2 · **Date:** 2026-11-05
**Thay thế:** thứ tự P0-01 → P0-10 trong `IMPLEMENTATION_PLAN.md` §3 (nội dung và tiêu chí hoàn thành ở đó vẫn áp dụng).
**Dựa trên:** ADR-0001 → ADR-0009.

> **Trạng thái 2026-11-05:** toàn bộ task A–G đã được code theo yêu cầu của Dung (làm liền, commit thẳng lên main thay vì 1 PR/task). Còn lại: G2 (chạy P0 acceptance trên Windows). Lệch so với kế hoạch: run status P0 chỉ gồm `queued/running/completed/failed`; artifact hiện chỉ cho phép text/markdown/json.

## Nguyên tắc

- 1 task = 1 PR nhỏ, kết thúc ở trạng thái **chạy được và test pass**.
- Ước lượng tính bằng **buổi** (≈1 giờ). Task > 2 buổi được chia nhỏ khi bắt đầu.
- Mỗi PR có mục "Làm tiếp từ đâu" để buổi sau vào việc nhanh.
- Mỗi milestone kết thúc bằng một kiểm tra trên Windows (bạn chạy, hoặc mình chạy qua Remote Control).

## Milestones

| Mã | Milestone | Kết quả nhìn thấy được | Buổi |
|---|---|---|---|
| A | Repo & backend skeleton | `GET /api/v1/health` chạy trên Windows | 4–5 |
| B | Persistence & events | Tạo Company qua API, event `company.created` được lưu | 5–6 |
| C | Frontend shell | Dashboard trên trình duyệt, tạo/xem Company | 6–7 |
| D | Agents | Tạo Agent, có version, activate/deactivate | 6 |
| E | Execution (mock) | Chạy kịch bản Demo Video Studio qua API | 9–10 |
| F | Live dashboard | Xem event realtime, trạng thái run, lỗi, artifact | 6–7 |
| G | Desktop | App Electron chạy trên Windows, đạt P0 acceptance | 4–5 |
| | **Tổng** | | **40–46** |

**Cập nhật ước tính:** 40–46 buổi ≈ 8–10 tuần với 5 buổi/tuần, chưa tính thời gian xử lý sự cố riêng của Windows. Con số này cao hơn ước tính sơ bộ 25–35 buổi trong REVIEW; con số mới được tính theo từng task nên đáng tin hơn.

**Điểm dừng hợp lý:** sau milestone C (~17 buổi) đã có sản phẩm nhìn thấy được. Sau E là lúc kiểm chứng ý tưởng cốt lõi (orchestration qua mock).

## Danh sách task

### A — Repo & backend skeleton
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| A1 | Khởi tạo repo: README (hướng dẫn Windows), `.gitignore`, `.editorconfig`, chép `docs/` + ADR | 1 | Map P0-01 |
| A2 | Backend skeleton: uv project `apps/backend`, FastAPI app factory, `/api/v1/health`, pytest, ruff | 1 | Map P0-01/P0-03 |
| A3 | Settings + bảo mật local: bind 127.0.0.1, token mỗi lần khởi động, kiểm tra Host/Origin, test | 1–2 | ADR-0009 |
| A4 | Quy ước lỗi có cấu trúc + script xuất OpenAPI vào `packages/contracts` | 1 | ADR-0003, P0-03 |

### B — Persistence & events
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| B1 | SQLAlchemy 2 + Alembic + SQLite (foreign keys, busy_timeout, WAL), fixture DB tạm cho test | 1–2 | P0-02 |
| B2 | Bảng `events` + service append (sequence theo company, cùng transaction), kiểm tra append-only | 2 | ADR-0006/0007, P0-09 |
| B3 | Module Company: model, migration, service phát `company.created`, API CRUD, test | 2 | P0-06 |

### C — Frontend shell
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| C1 | pnpm workspace + Vite/React/TS + Tailwind + Vitest; truyền token dev | 1–2 | ADR-0001/0002 |
| C2 | Sinh TS type từ OpenAPI + TanStack Query client | 1 | ADR-0003 |
| C3 | Layout Control Center: sidebar, workspace, inspector, console; trạng thái loading/empty/error | 2 | P0-05 |
| C4 | UI Company: danh sách, tạo, chi tiết | 2 | P0-06 |

### D — Agents
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| D1 | Model `agents` + `agent_versions`, schema `definition_json` tối thiểu, migration | 2 | P0-07 |
| D2 | API Agent: tạo, liệt kê, chi tiết, tạo version mới, activate/deactivate + event | 2 | P0-07 |
| D3 | UI Agent: danh sách, chi tiết, tạo | 2 | P0-07 |

### E — Execution (mock)
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| E1 | Model `tasks` + `agent_runs` + metadata artifact; kiểm tra chuyển trạng thái | 2 | ADR-0004 |
| E2 | Interface `AgentRuntime`, capabilities, registry, chuẩn hóa `run.*` → `agent.run.*` | 2 | ADR-0007/0008, P0-08 |
| E3 | Mock runtime + nạp kịch bản (YAML) + 4 kịch bản, đồng hồ ảo để test nhanh | 3 | ADR-0005, P0-08 |
| E4 | Orchestrator tuần tự: command start run, chạy asyncio trong process | 2 | ADR-0008 |
| E5 | Seed Demo Video Studio (company + 8 agent + tasks) | 1 | RUNTIME §5 |

### F — Live dashboard
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| F1 | API truy vấn event + SSE stream có `Last-Event-ID` | 2 | P0-09/P0-10 |
| F2 | Activity console + cập nhật trạng thái realtime, chống trùng, reconnect | 2–3 | P0-10 |
| F3 | Run inspector: kết quả, metadata artifact, chi tiết lỗi | 2 | P0 acceptance 8–9 |

### G — Desktop
| ID | Task | Buổi | Ghi chú |
|---|---|---|---|
| G1 | Electron main/preload, cấu hình bảo mật, CSP, khởi động backend (dev: `uv run`), token qua preload | 3 | P0-04, ADR-0009 |
| G2 | Chạy P0 acceptance (IMPLEMENTATION_PLAN §4) trên Windows, sửa lỗi, cập nhật README | 1–2 | |

## Hoãn sang sau P0
- Đóng gói Python vào bản cài Windows (PyInstaller/embedded) — cần ADR riêng trước khi phát hành.
- `@xyflow/react`, Zustand, Playwright E2E — thêm khi task cần.
- Department — P1.
