# P4 PLAN — KPI & Multi-Runtime

**Version:** 0.1 · **Date:** 2026-11-05
**Trạng thái:** Dung yêu cầu "tiếp tục" sau khi nhận P2+P3 (2026-11-05). ADR 0021–0024 áp dụng theo đề xuất bên dưới; Dung có thể đổi bất kỳ quyết định nào.
**Phạm vi gốc:** `IMPLEMENTATION_PLAN.md` §2 (P4) và §5 (tiêu chí nghiệm thu P4), `RUNTIME.md` §3, §7, §8, `SECURITY.md` §6, `DATABASE.md` (metrics, credential_refs).

## 0. Mục tiêu và tiêu chí nghiệm thu

- Agent có thể chạy bằng model thật: **Ollama** (máy cục bộ), **Claude** (Anthropic), **OpenAI**. Mock vẫn là mặc định; demo không cần model hay API key.
- Tiêu chí P4 (§5): (1) adapter qua **contract test** chung; (2) số liệu usage/chi phí có nhãn **nguồn** và **độ tin cậy**; (3) giới hạn tài nguyên model cục bộ **nhìn thấy được** trên UI.

## 1. Quyết định (ADR)

| ADR | Câu hỏi | Quyết định | Lý do |
|---|---|---|---|
| 0021 | Lưu credential | Secret nằm trong kho bảo mật của hệ điều hành qua thư viện `keyring` (Windows Credential Manager, macOS Keychain, Secret Service). DB chỉ giữ tham chiếu (`credentials`: provider, nhãn, phạm vi company, `store`, `store_ref`, trạng thái). Tùy chọn thứ hai: tham chiếu biến môi trường (`env:TÊN_BIẾN`). Kho không an toàn (keyring "fail"/plaintext) thì từ chối lưu. API không bao giờ trả secret; có xoay (rotate), thu hồi (revoke), kiểm tra kết nối. Bộ lọc log che secret đã nạp và mẫu `sk-…`. | SECURITY §6 ưu tiên kho của OS. Tránh tự mã hóa file (khó quản lý khóa). |
| 0022 | Adapter model | Ba runtime mới `ollama`, `anthropic`, `openai` dùng chung một vòng lặp hội thoại: gửi chỉ dẫn agent + task, cho phép gọi **tool đã cấp quyền** qua Tool Gateway (ADR-0018), tối đa N lượt; câu trả lời cuối thành artifact Markdown + tóm tắt. Claude dùng SDK chính thức `anthropic` (mặc định `claude-opus-5-5`, effort `medium`, bật fallback phía server khi model hỗ trợ); OpenAI dùng SDK `openai` (Chat Completions, model do người dùng chọn); Ollama gọi HTTP API gốc. Capability: cancel có, pause/resume/streaming không. Lỗi được phân loại retryable (429, 5xx, mạng) hay không (401/403, 400, 404, từ chối). Agent model chưa tự giao việc (delegate) ở P4. Một bộ contract test chạy cho mọi adapter, không gọi mạng. | RUNTIME §3, §8: không để đối tượng SDK lọt vào domain. |
| 0023 | Usage, chi phí, KPI | Bảng `metrics` (theo DATABASE.md) thêm `source` và `confidence`. Token: nguồn `provider_reported` (Claude/OpenAI) hoặc `local_runtime_reported` (Ollama). Chi phí: `price_table_estimate` từ bảng giá có ngày (`pricing.yaml`), độ tin cậy `estimated`; model không có giá thì **không** ghi chi phí và KPI báo "chưa có giá". Ollama: 0 USD phí API, ghi rõ không tính điện/phần cứng. KPI tính từ bản ghi run (nguồn `orchestrator`, `measured`) + metrics. | §5 P4: mọi số có nguồn và độ tin cậy; không bịa giá. |
| 0024 | Tài nguyên model cục bộ | Ollama: giới hạn số run đồng thời (`ollama_max_concurrency`, mặc định 1); run vượt giới hạn chờ ở trạng thái `queued`. Health hiện: kết nối, phiên bản, model có sẵn (dung lượng), model đang nạp (RAM/VRAM), số run đang chạy/chờ, giới hạn. | RUNTIME §7: một model dùng chung + hàng đợi tốt hơn nhiều model nặng cùng lúc. |

## 2. Task (ước lượng theo buổi 1 giờ)

| ID | Task | Buổi |
|---|---|---|
| Q1 | Migration 0005: `credentials`, `metrics` | 1 |
| Q2 | Kho secret (keyring/env/memory), redaction, API credential + event | 3 |
| Q3 | Vòng lặp model chung + adapter Claude/OpenAI/Ollama + phân loại lỗi | 5 |
| Q4 | Contract test chung cho mọi adapter (fake transport) | 2 |
| Q5 | Orchestrator: tool spec, credential lúc chạy, usage → metrics | 2 |
| Q6 | KPI API + bảng giá | 2 |
| Q7 | Health Ollama + giới hạn đồng thời | 1–2 |
| Q8 | UI: Kết nối & model, credential, chọn runtime cho agent, KPI | 4 |
| Q9 | Kiểm tra trên Windows, README | 1–2 |
| | **Tổng** | **21–23** |

## 3. Ngoài phạm vi (cố ý)

- Agent model tự giao việc/song song (delegate): P5, cần thiết kế prompt và giới hạn chi phí.
- Streaming token lên UI; pause/resume giữa chừng cho model thật.
- Embedding/vector search: vẫn hoãn (FTS5 đủ cho P4).
- Ngân sách chi phí cứng theo company: chỉ hiện số liệu, chưa chặn.
- Kết nối mạng thật cho tool `social.publish`: vẫn mô phỏng.

## 4. Rủi ro

- [I] Gọi model thật tốn tiền: mock vẫn mặc định, mỗi run có `max_tokens` và số lượt tối đa.
- [I] Linux CI không có keyring: test dùng kho `memory`; trên Windows dùng Credential Manager thật.
- [I] Giá thay đổi: bảng giá có ngày và nguồn, chi phí luôn gắn nhãn "ước tính".
- [H] SDK mới (`anthropic` 2.x, `openai` 3.x, dùng `httpx2`) có thể đổi API: cố định phiên bản trong `uv.lock`, contract test bắt lỗi khi nâng cấp.
