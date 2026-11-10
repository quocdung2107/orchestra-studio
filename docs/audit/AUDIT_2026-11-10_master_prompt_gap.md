# AUDIT — Orchestra Studio hiện tại so với Master Prompt "AI Council & Multi-Agent Organization Platform"

**Ngày:** 2026-11-10 · **Loại:** audit + gap analysis, không code · **Người yêu cầu:** Dung

**Đối tượng so sánh**
- Master prompt mới: `ORCHESTRA_STUDIO_MASTER_PROMPT.md` (Dung tải lên 2026-11-10), gọi tắt là **MP-mới**.
- Repo `main` (commit `45ac528`, P0–P5 xong): gọi là **main**.
- Nhánh `claude/project-thread-lpp66w` (L1–L12 video pipeline, ADR 0028–0033, chưa merge): gọi là **nhánh video**.
- Các quyết định trước: `MASTER_PROMPT.md` cũ trong repo (**MP-cũ**), ADR 0001–0027 (main) và 0028–0033 (nhánh video), audit 2026-11-06 (production readiness và AI Video Production Company).

**Nhãn bằng chứng**
- `[Code]`: đọc trực tiếp mã nguồn trong phiên này. `[Doc]`: tài liệu/ADR trong repo. `[Web]`: nguồn chính thức đọc trong phiên này, có ngày.
- `[Suy luận]`: rút ra từ dữ kiện, chưa kiểm chứng trực tiếp. `[Đề xuất]`: ý kiến của tôi, cần Dung quyết.

---

## 0. Kết luận trước

1. **MP-mới không phải bản nâng cấp của hệ thống hiện tại. Nó mô tả một sản phẩm khác**: một "AI Council" điều khiển nhiều tài khoản AI miễn phí trên web qua trình duyệt nhúng, với Meeting Room nhiều vòng. Khoảng 40% yêu cầu đã có ở main (tổ chức, agent có version, task graph, approval, usage/KPI, Ollama, credentials, backup). Khoảng 60% còn lại chưa có gì: Meeting Room, Response Envelope và Validator, Context Builder, Model Routing, Browser Session, xử lý file. `[Code]`
2. **Trụ cột "Account-first, Free-first qua trình duyệt" (MP-mới §3.5, §11) mâu thuẫn với chính quy tắc "tuân thủ ToS" của MP-mới (§11.5).** Điều khoản hiện hành của Anthropic, Google và DeepSeek cấm truy cập dịch vụ consumer bằng bot hoặc script (trích dẫn ở §3). Với OpenAI, tôi không tải được trang chính thức trong phiên này nên chưa xác minh. Tự động hóa tài khoản free cũng rất dễ gãy (DOM thay đổi, CAPTCHA, khóa tài khoản) với quỹ thời gian ~1 giờ/ngày. **Khuyến nghị: không xây browser automation.** Thay bằng (a) API free tier hợp lệ (Gemini API, Groq, OpenRouter, DeepSeek API) cộng Ollama, và (b) chế độ **"Manual Relay"**: Orchestra tạo Context Package, Dung tự dán vào web chat rồi dán câu trả lời lại. Cách (b) đúng với lối thoát mà MP-mới §11.5 cho phép.
3. **Phần giá trị nhất của MP-mới là ba engine: Meeting Room, Context Builder và Response Protocol.** Cả ba xây được trên runtime đã có (Claude, OpenAI, Ollama), không cần trình duyệt. Chúng cũng sửa đúng lỗi lớn nhất của audit 2026-11-06 (R1: task "completed" chỉ vì model tự báo xong).
4. **Có một lỗi hiện tại MP-mới làm lộ ra:** skill gắn cho agent (ADR-0012) **không bao giờ được đưa vào prompt của model**. Runtime chỉ dùng role, instructions và goals. `[Code]` `runtime/llm/base.py:95`, `orchestrator/service.py:318-331`. Đây là việc nhỏ, nên sửa trước tiên bất kể chọn hướng nào.
5. **Cần Dung quyết định:** MP-mới **thay thế** hướng "AI Video Production Company" (2026-11-06) hay là **nền tảng** mà video chỉ là use case đầu tiên? Đề xuất của tôi: chọn **nền tảng + video là use case đầu tiên**, giữ nhánh video, bỏ browser automation (xem §7).

---

## 1. MP-mới so với hai định hướng trước

| Khía cạnh | MP-cũ (baseline, P0–P5) | Hướng video (2026-11-06) | MP-mới (2026-11-10) |
|---|---|---|---|
| Sản phẩm | AI Organization Control Center | Công ty sản xuất video AI cho Facebook Page của Dung | AI Council: tổ chức AI, họp nhiều vòng |
| Trung tâm UX | Dashboard, không lấy chat làm trung tâm | Pipeline sản xuất | CEO/Orchestrator + Meeting Room |
| Cách gọi AI | Runtime qua API (key trong OS keyring) + Ollama | API cloud + engine local (TTS, FFmpeg) | **Tài khoản free trên web qua Electron**, API chỉ là phụ |
| Đơn vị phối hợp | Task graph + delegate theo sơ đồ tổ chức | Job bền + pipeline tất định | Meeting Room + Handoff |
| Đầu ra | Markdown artifact | MP4 qua QA | JSON Envelope đã validate + Markdown |

`[Suy luận]` MP-mới gần MP-cũ hơn hướng video: cả hai đều là nền tảng ngang (horizontal), không gắn với một lĩnh vực. Khác biệt cốt lõi chỉ có hai điểm: Meeting Room và cách truy cập AI qua trình duyệt.

---

## 2. Xung đột với quyết định đã chốt

| # | MP-mới | Quyết định hiện có | Mức | Nhận xét |
|---|---|---|---|---|
| X1 | §3.5 Account-first: dùng tài khoản free trên trình duyệt, API là phụ | ADR-0021/0022: model gọi qua API, key trong keyring | **Cao** | Đảo ngược kiến trúc runtime. Có rủi ro ToS (§3). |
| X2 | §11 Electron `WebContentsView` nạp ChatGPT, Gemini, Claude, DeepSeek | ADR-0009 và `electron/main.ts`: renderer sandbox, `contextIsolation`, chặn điều hướng ra ngoài, không mở cửa sổ mới | **Cao** | Nạp website bên thứ ba có đăng nhập vào app là một mô hình bảo mật mới, cần ADR riêng. Lưu ý: **ADR-0001 không cấm Electron**. Nó chỉ quy định thứ tự (React trên trình duyệt trước, bọc Electron cuối P0), và Electron đã được bọc xong. Xung đột thật là với ADR-0009/SECURITY, không phải ADR-0001. `[Doc][Code]` |
| X3 | §19 Roadmap P0–P6 mới | P0–P5 đã xong theo nghĩa khác | Trung bình | Trùng tên giai đoạn sẽ gây nhầm. Nếu theo MP-mới, nên đặt tên mới (ví dụ "C1–C7", C = Council). |
| X4 | §18 Cấu trúc `packages/` (core, meeting-engine…) kiểu monorepo TS | Backend Python modular monolith, mỗi module là một package Python | Trung bình | MP-mới §21 tự nói "không phá code đang chạy". Nên ánh xạ module mới vào `apps/backend/src/orchestra_backend/<module>`, không tạo `packages/` rỗng. |
| X5 | §4 Layer 3: Skills là file `SKILL.md` | ADR-0012: skill trong DB, có version, agent ghim version | Thấp | Kết hợp được: DB vẫn là nguồn sự thật, thêm import/export theo định dạng `SKILL.md`. |
| X6 | §4 Layer 4: vòng đời `ASSIGNED→ACCEPTED→IN_PROGRESS→REVIEW→APPROVED→HANDED_OFF→COMPLETED` | ADR-0015: `pending, in_progress, waiting_approval, paused, completed, failed, cancelled` | Trung bình | Thiếu bước REVIEW/APPROVED. Đó chính là lỗi R1 của audit 2026-11-06. Nên bổ sung, không thay toàn bộ. |
| X7 | MP-mới không nhắc đến video | Hướng video 2026-11-06, nhánh L1–L12 chờ Dung review | **Cao (chiến lược)** | Cần Dung trả lời (xem §7). |
| X8 | §21 Phase B: 18 tài liệu spec trước khi code | Quy tắc repo: mỗi thay đổi là một task chạy được; ~1 giờ/ngày | Trung bình | Viết 18 tài liệu trước tốn nhiều tuần mà chưa ra phần mềm. Nhiều tài liệu đã có tương đương (ARCHITECTURE, DATABASE, SECURITY, EVENTS, RUNTIME, các ADR). |

---

## 3. Rủi ro điều khoản dịch vụ (ToS) của browser automation

### Dữ kiện `[Web]`, đọc ngày 2026-11-10

| Provider | Nguồn, ngày hiệu lực | Trích nguyên văn |
|---|---|---|
| Anthropic (Claude.ai) | anthropic.com/legal/consumer-terms, *Effective Oct 8, 2025* | Mục 3.7: "Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it," … "to access the Services through automated or non-human means, whether through a bot, script, or otherwise." Mục 3.4 cấm "crawl, scrape, or otherwise harvest data". |
| Google (Gemini app) | policies.google.com/terms, *Effective July 30, 2026* | Mục "Don't abuse our services": "using automated means to access content from any of our services" (khi vi phạm chỉ dẫn máy đọc như robots.txt). Mục tạm ngưng tài khoản có nêu "scraping content that doesn't belong to you". |
| DeepSeek | cdn.deepseek.com/…/deepseek-terms-of-use.html, *Last Update: March 27, 2026* | Mục 3.5(3) cấm "capturing, copying any content of the Services, including but not limited to" … "using any robots, spiders, or other automatic setups, setting mirrors." |
| OpenAI (ChatGPT) | openai.com/policies/terms-of-use | **Chưa xác minh trong phiên này** (trang không tải được). Nguồn thứ cấp (conductatlas.com) ghi điều khoản cấm "automatically or programmatically extract data or Output". Cần đọc lại trang gốc trước khi kết luận. |

Bối cảnh: The Register (20/2/2026) đưa tin Anthropic làm rõ việc cấm dùng công cụ bên thứ ba với gói Claude Free/Pro/Max, và cho biết mục 3.7 không đổi từ năm 2024.

### Suy luận `[Suy luận]`
- Với ít nhất 3 trong 4 provider MP-mới nêu, việc Orchestra tự gõ prompt và đọc câu trả lời trên web là "automated means", dù người dùng đã tự đăng nhập. Vì vậy MP-mới §3.5 và §11 **không thể đồng thời** thỏa §11.5 ("Tuân thủ điều khoản dịch vụ"). Đây là mâu thuẫn nội tại của MP-mới, không chỉ là rủi ro kỹ thuật.
- Hậu quả thực tế có thể xảy ra: tài khoản cá nhân của Dung bị khóa (gồm cả tài khoản Google dùng cho việc khác), và không thể đóng gói thành sản phẩm để bán.
- Rủi ro kỹ thuật, kể cả khi bỏ qua ToS: selector DOM gãy sau mỗi lần provider đổi giao diện, CAPTCHA hoặc chống bot, phát hiện "đã trả lời xong" không ổn định. Bốn adapter nhân với tốc độ thay đổi UI là gánh nặng bảo trì vượt quỹ ~1 giờ/ngày.
- Tài nguyên: 4 `WebContentsView` của web app nặng cộng backend, Ollama và engine TTS trên máy 7,4 GB RAM sẽ thiếu bộ nhớ. Chưa đo.

### Phương án thay thế `[Đề xuất]`

| Phương án | Hợp ToS | Chi phí | Tự động | Ghi chú |
|---|---|---|---|---|
| A. Browser automation tài khoản free (MP-mới) | **Không** (3/4 provider đã xác minh) | Cao, bảo trì liên tục | Cao | Không khuyến nghị |
| B. API free tier (Gemini API, Groq, OpenRouter `:free`, DeepSeek API) + Ollama | Có (dùng API đúng mục đích) | Thấp | Cao | Quota thay đổi, phải đo thực tế và không hardcode (MP-mới §10.2 cũng yêu cầu vậy). Adapter OpenAI hiện **chưa có `base_url`** `[Code]` `openai_rt.py`, chỉ cần sửa nhỏ để dùng endpoint tương thích OpenAI. |
| C. Manual Relay: Orchestra tạo Context Package, Dung dán vào web chat, rồi dán câu trả lời lại | Có (người thao tác) | Thấp | Thấp | Vẫn dùng được tài khoản free và Meeting Room. Validator xử lý câu trả lời dán vào như mọi runtime khác. |
| D. API trả phí (Claude, OpenAI) | Có | Theo token | Cao | Đã có sẵn |

**Khuyến nghị:** B + C + D, trong đó C là một "runtime" mới tên `manual_relay` (run chờ người dán, giống `waiting_approval`). Ghi quyết định này bằng ADR "Không tự động hóa giao diện web của provider".

---

## 4. Gap analysis theo từng mục của MP-mới

Ký hiệu: ✅ Có · 🟡 Một phần · ❌ Thiếu · ⚠️ Xung đột

### §3 Nguyên tắc kiến trúc

| Yêu cầu | TT | Hiện trạng và bằng chứng |
|---|---|---|
| 3.1 Provider agnostic | 🟡 | Có runtime `mock`, `anthropic`, `openai`, `ollama` qua `LlmRuntime` chung, có contract test `[Code]` `runtime/llm/`. Chưa có Gemini, DeepSeek, Groq, OpenRouter. OpenAI adapter không có `base_url`. |
| 3.1 Tách Provider / Model / Browser Account / Browser Session / Conversation Session / Agent / Role / Meeting / Task | 🟡 | Có Agent, Task, Run, Provider (runtime) và Model (settings). Role chỉ là chuỗi `agents.role`. Chưa có Browser Account, Browser Session, Conversation Session, Meeting. |
| 3.2 Một vai trò dùng nhiều model | ❌ | Mỗi agent version có đúng một `runtime_preference` `[Code]` `agents/schemas.py`. Chưa có model theo loại việc. |
| 3.3 Một model phục vụ nhiều vai trò | ✅ | Một credential hoặc một runtime dùng chung cho nhiều agent `[Doc]` ADR-0021. |
| 3.4 Role-based, model-flexible | 🟡 | Đổi runtime không phải tạo lại agent (MP-cũ quyết định #8), nhưng vẫn gắn một model cho mỗi agent. |
| 3.5 Account-first, Free-first | ⚠️ | Xem §3. Ollama local miễn phí đã có. |
| 3.6 Traceability | 🟡 | Event append-only, run giữ `agent_version_id`, `run.usage` có provider/model/token `[Doc]` ADR-0007/0022/0023. **Thiếu:** prompt đã ghép không được lưu nguyên văn (chỉ `input_json` = context); thiếu "ai kiểm tra" và "ai phê duyệt" cho đầu ra (approval mới chỉ áp cho tool call). |
| 3.7 Human control | 🟡 | Có: xem trạng thái, cancel cả cây, đổi runtime/model (version mới), duyệt tool L3, xem lịch sử. Pause/resume chỉ có ở Mock `[Doc]` ADR-0022. Chưa có: sửa kết quả của agent, giao lại task đang chạy. |

### §4 Năm tầng tổ chức

| Tầng | TT | Hiện trạng |
|---|---|---|
| L1 Organization Registry | ✅ | Company, department dạng cây, `reports_to`, chặn vòng lặp, template `[Doc]` ADR-0010/0014. "Position" = `role` dạng chuỗi. "Delegation rules" = chỉ giao cho cấp dưới trực tiếp `[Doc]` ADR-0026. |
| L2 Agent Profile | 🟡 | Có: id, name, department, reports_to, instructions, goals, permissions (tool + mức L0–L3, ADR-0013), runtime, version + diff. **Thiếu các trường có cấu trúc:** Mission, Responsibilities, Input Requirements, **Output Contract**, Handoff Rules, Quality Requirements, Model Policy (preferred/fallback). Hiện tất cả dồn vào `instructions` tự do. |
| L3 Skills & SOP | 🟡 ⚠️ | Có bảng skill có version, agent ghim version `[Doc]` ADR-0012, có UI Skills & Tools. **Lỗi:** runtime không đọc skill nào. `system_prompt()` chỉ dùng name/role/instructions/goals `[Code]` `runtime/llm/base.py:95-108`, và orchestrator không truyền skill vào `RunRequest` `[Code]` `orchestrator/service.py:318-331`. Chưa có định dạng `SKILL.md`, chưa có progressive disclosure. |
| L4 Task & Handoff | 🟡 | Có: id, title/objective, assignee, priority, dependency (finish_to_start), retry, task con, status `[Doc]` ADR-0015/0016. "Agents as Tools" ≈ `team.delegate`: cha giữ quyền sở hữu, gọi cấp dưới, nhận tóm tắt `[Doc]` ADR-0026. **Thiếu:** Expected Output, Acceptance Criteria, Deadline, Next Owner, trạng thái REVIEW/APPROVED/HANDED_OFF, **Handoff thật** (chuyển quyền sở hữu). "Completed" vẫn là model tự báo xong (audit 2026-11-06, R1). |
| L5 Knowledge & Memory | 🟡 | Có: knowledge theo company, FTS5, nguồn gốc, version; lesson và đề xuất đổi vai trò cần người duyệt `[Doc]` ADR-0019/0020. Company là đơn vị cô lập dữ liệu (`[Suy luận]` đóng vai "Project"). **Thiếu:** Agent Memory, Meeting Memory, Decision Records, phân tầng Global/Org/Project. |

### §5–§6 Meeting Room và Meeting Protocol

| Yêu cầu | TT | Ghi chú |
|---|---|---|
| Room, Member, Round, Meeting State, lifecycle | ❌ | Không có bảng, API hay UI nào. Gần nhất là task cha có nhiều task con, nhưng không có "vòng", không có chia sẻ kết quả giữa các thành viên. |
| Context Builder cho cuộc họp | ❌ | Xem §9. |
| Protocol 12 quy tắc, workflow 5 vòng | ❌ | `[Suy luận]` Có thể triển khai như "workflow template" chạy trên Task Engine: mỗi vòng là một nhóm task song song, có dependency giữa các vòng. Scheduler song song đã có (ADR-0015). |

### §7 Response Protocol

| Yêu cầu | TT | Ghi chú |
|---|---|---|
| Universal Response Envelope (JSON Schema) | ❌ | Đầu ra model là Markdown tự do, dòng đầu là tóm tắt `[Code]` `base.py:103`. |
| Schema theo loại task | ❌ | |
| Validator: raw → extract → validate → repair → hỏi lại → `INVALID_RESPONSE` | ❌ | `runtime/normalize.py` chỉ validate **sự kiện runtime** (độ dài message, kích thước artifact ≤ 1 MB), không validate **nội dung**. Có sẵn mẫu validator JSON Schema tập con trong Tool Gateway `[Doc]` ADR-0018, có thể tái dùng hoặc thay bằng thư viện `jsonschema`. |
| Structured output của provider | ❌ | Audit 2026-11-06 đã ghi là thiếu ở cả ba adapter. |

### §8 Meeting Memory Engine

| Tầng | TT | Ghi chú |
|---|---|---|
| Raw History bất biến | 🟡 | Event append-only và artifact có checksum. Nhưng prompt gửi đi và response gốc của provider **không được lưu nguyên văn**: adapter giữ lịch sử trong bộ nhớ rồi bỏ `[Doc]` ADR-0022; `run.message` bị rút gọn ≤ 4000 ký tự `[Code]` `normalize.py`. |
| Structured Findings, Snapshot có version | ❌ | |
| Ollama làm memory assistant | 🟡 | Ollama chạy được, có health, hàng đợi concurrency=1 `[Doc]` ADR-0024; qwen3:4b ~27 tok/s trên máy Dung. `[Suy luận]` Chất lượng tóm tắt và giữ bất đồng của model 4B với tiếng Việt chưa đo. Cần chính Test E của MP-mới để quyết định. Máy chỉ chạy được 1 model local, và sẽ tranh RAM với TTS của nhánh video. |

### §9 Context Engineering

| Yêu cầu | TT | Hiện trạng |
|---|---|---|
| Context Assembly 11 thành phần | ❌ | Prompt hiện tại = role + instructions + goals + task + `context_json` (dump JSON cắt cứng 4000 ký tự) `[Code]` `base.py:111-118`. |
| Thứ tự ưu tiên, không cho dữ liệu ghi đè quy tắc | ❌ | Tool result và knowledge được ghép thẳng vào prompt, không đánh dấu "dữ liệu không tin cậy" (audit 2026-11-06, R5). |
| Token estimator, budget, dedup, nén, cắt theo ưu tiên | ❌ | Chỉ có token thực tế sau khi gọi (`run.usage`), không có ước tính trước khi gọi. |

### §10 Model Routing & Quota

| Yêu cầu | TT | Hiện trạng |
|---|---|---|
| Capability/Model Registry | 🟡 | Runtime registry và capability theo runtime (`supports_cancel`…) `[Code]` `runtime/registry.py`; Ollama liệt kê model, quantization, VRAM. Chưa có registry năng lực theo model (reasoning, coding, context window…). |
| Routing theo năng lực, fallback giữa provider | ❌ | Chỉ có server-side fallback của Anthropic `[Doc]` ADR-0022. |
| Usage tracker, đếm request, token, phân biệt ước tính/thực tế | ✅ | Bảng `metrics` có `source` và `confidence` (`provider_reported`, `price_table_estimate`…) `[Doc]` ADR-0023. MP-mới §10.3 yêu cầu đúng như vậy. |
| Phát hiện rate limit, cooldown | 🟡 | Có mã lỗi `PROVIDER_RATE_LIMITED` và retry có giới hạn; chưa có cooldown theo provider. |
| Quota của tài khoản web | ❌ | Phụ thuộc §11. |

### §11 Browser Session & Provider Adapters

| Yêu cầu | TT | Ghi chú |
|---|---|---|
| Toàn bộ §11.1–11.5 | ❌ ⚠️ | Chưa có gì. Electron hiện bị khóa có chủ đích (sandbox, chặn điều hướng) `[Code]` `electron/main.ts:6,96-97`. Xem §3. |

### §12 Files & Knowledge

| Yêu cầu | TT | Ghi chú |
|---|---|---|
| Markdown, JSON, CSV | 🟡 | Knowledge nhận text ≤ 100 KB `[Doc]` ADR-0019. |
| PDF, DOCX, XLSX, ảnh | ❌ trên main / 🟡 trên nhánh video | Nhánh video có media store theo sha256, kiểm MIME bằng magic bytes, giới hạn kích thước (L5, ADR-0028), nhưng chỉ cho ảnh/audio/video, chưa trích xuất văn bản. |
| Chia đoạn, chỉ mục, chỉ lấy phần liên quan, gắn nguồn | 🟡 | Có FTS5 + nguồn gốc theo item; chưa chia đoạn; tool `kb.search` chỉ trả snippet. |

### §13 Task Dispatcher & Handoff

| Yêu cầu | TT | Ghi chú |
|---|---|---|
| CEO phân rã, chọn agent, giao việc | 🟡 | Agent có cấp dưới gọi được `team.delegate`; chỉ giao theo vai trò của cấp dưới trực tiếp, tối đa 5 lần mỗi run, chạy tuần tự `[Doc]` ADR-0026. Chưa chọn model theo task. |
| Handoff Contract; phân biệt người tạo, người chịu trách nhiệm, người kiểm tra, người duyệt, người nhận tiếp | ❌ | Con chỉ trả một dòng tóm tắt và tên artifact; cha không đọc được nội dung artifact (audit 2026-11-06). |

### §14 Giao diện

| Khu vực | TT | Màn hình hiện có `[Code]` `renderer/src/views/` |
|---|---|---|
| Dashboard | 🟡 | `CompanyOverview`, `ActivityConsole`, `KpiView` |
| Organization | ✅ | `OrgView` (graph), `AgentsView`, `CapabilitiesView` (skills/tools), inspector, diff version |
| Meeting Rooms | ❌ | |
| Task Center | 🟡 | `RunsView` (task, dependency, điều khiển); thiếu acceptance criteria và lịch sử handoff |
| Knowledge Center | 🟡 | `KnowledgeView`, lesson; thiếu decisions, memories |
| Model Center | 🟡 | `ConnectionsView` (credential, health Ollama, model); thiếu quota, capability theo model |
| Settings | 🟡 | `BackupView`, `WorkersView`, runtime settings theo agent |

### §15–§16 Công nghệ, bảo mật, độ tin cậy

| Yêu cầu | TT | Ghi chú |
|---|---|---|
| Electron + React + TS + Python + SQLite + JSON Schema + Markdown | ✅ | Khớp với stack hiện có (MP-cũ §3). Câu "Python backend nếu thực sự cần" của MP-mới đã được trả lời: backend Python đã có và đang chạy, không nên viết lại. |
| Tách UI / Application / Domain / Infrastructure / Adapter | 🟡 | Backend tách theo module nghiệp vụ, runtime là adapter riêng, renderer chỉ gọi API. Không có lớp "domain" tách riêng. `[Suy luận]` Không cần tách thêm cho quy mô hiện tại. |
| Không log secret, không đưa secret vào prompt, IPC validation | ✅ | Keyring, `core/redact.py`, kiểm tra key giống secret trong settings, preload giới hạn `[Doc]` ADR-0009/0021. |
| Prompt injection, dữ liệu web/tài liệu không tin cậy | ❌ | Audit 2026-11-06, R5. |
| Audit log, backup/recovery | ✅ | Event log; backup không chứa API key `[Doc]` ADR-0027. |
| Phục hồi sau khi app tắt đột ngột | 🟡 | main: run đang chạy bị đánh dấu thất bại một cách trung thực, không resume. Nhánh video: job bền có lease và tự tiếp tục sau restart (L6, ADR-0029), **chưa áp cho agent run**. |

### §17 Framework cần nghiên cứu

Audit 2026-11-06 §3 đã so sánh LangGraph, Pydantic AI, OpenAI Agents SDK, Microsoft Agent Framework, Claude Agent SDK, n8n, Dify và Claude Cowork bằng nguồn chính thức. Không lặp lại ở đây.

Với các mục MP-mới thêm, đánh giá sơ bộ (`[Suy luận]`, chưa đọc lại repo nguồn trong phiên này):

| Dự án | Dùng trực tiếp | Học ý tưởng | Ghi chú |
|---|---|---|---|
| Agent Skills (`SKILL.md`, progressive disclosure) | Định dạng file để import/export | Chỉ nạp tên và mô tả, đọc toàn văn khi dùng | Khớp với lỗi skill nêu ở §4 L3 |
| `AGENTS.md` | Cho repo này (đang có `CLAUDE.md`) | | Không phải tính năng sản phẩm |
| OpenAI Agents SDK | Không (lock-in Responses API, vẫn 0.x theo audit trước) | Handoff vs Agents-as-tools | Repo đã có tương đương "agents as tools" |
| CrewAI | Không | Role/Goal/Backstory ≈ trường có cấu trúc cho Agent Profile | |
| GitHub Spec Kit | Không | Constitution, Spec, Plan, Tasks | Quy trình docs/ADR hiện tại đã tương tự |
| Cline Memory Bank | Không | Bố cục bộ nhớ dự án | Gần với Project Knowledge |

Cần đọc lại các repo nguồn trước khi chốt ADR nào dựa trên chúng.

### §20 Acceptance Tests: làm được gì hôm nay?

| Test | Hôm nay | Cần gì |
|---|---|---|
| A Agent Identity | 🟡 Một phần (role/instructions có trong prompt; chưa có Response Contract) | Response Envelope |
| B Meeting Room (ChatGPT + Gemini + DeepSeek) | ❌ | Meeting Room + runtime cho các provider (qua API, không qua browser) |
| C Shared Context | ❌ | Context Builder + Round |
| D Response Contract (6 tình huống lỗi) | ❌ | Validator. **Nên làm trước**: kiểm được hoàn toàn bằng transport giả, không tốn quota |
| E Giữ bất đồng khi Ollama tóm tắt | ❌ | Snapshot + bộ test đo |
| F Handoff | 🟡 (delegate có, contract thì chưa) | Handoff Contract |
| G Model Fallback | ❌ | Model Policy |
| H Browser Session Recovery | ❌ | Không áp dụng nếu bỏ browser automation |
| I Quota (toàn bộ lịch sử / snapshot / context lọc) | ❌ | Token estimator + Context Builder |
| J Security | 🟡 (secret, quyền tool, đường dẫn đã test; injection thì chưa) | Đánh dấu dữ liệu không tin cậy trong context |

---

## 5. MP-mới quá rộng hoặc tự mâu thuẫn ở đâu

1. **§3.5 với §11.5:** như §3.
2. **§21 Phase B (18 tài liệu trước khi code):** với ~1 giờ/ngày, phần này ước chừng 3–6 tuần chỉ viết tài liệu `[Suy luận]`. Repo đã có ARCHITECTURE, DATABASE, SECURITY, EVENTS, RUNTIME và 27–33 ADR. `[Đề xuất]` Chỉ viết **3 spec mới** (`MEETING_ROOM_SPEC`, `RESPONSE_CONTRACT_SPEC`, `CONTEXT_ENGINE_SPEC`) cùng ADR cho mỗi quyết định, và cập nhật tài liệu cũ theo kiểu delta.
3. **§18 với §21 "không phá code đang chạy":** cấu trúc `packages/` gợi ý một monorepo TS. Tôi đề nghị bỏ, giữ module Python.
4. **Workflow 5 vòng × N thành viên:** một cuộc họp 3 AI × 5 vòng ≈ 15 lượt gọi model lớn cộng các lượt tóm tắt. Với free tier hoặc Manual Relay, chi phí thời gian và quota lớn `[Suy luận]`. MP-mới cho phép rút vòng; mặc định nên là 2 vòng (độc lập rồi tổng hợp), các vòng khác là tùy chọn.
5. **Ollama là "memory assistant" trên máy 4 GB VRAM:** MP-mới §10.4 tự cảnh báo không dùng model quá lớn. Model 4B có thể làm sai việc khó nhất (giữ bất đồng và nguồn gốc). `[Đề xuất]` Snapshot nên sinh **tất định** từ các Envelope đã validate (gộp `disagreements`, `risks` theo `agent_id`). LLM chỉ viết phần văn xuôi, và kết quả phải qua kiểm tra: không mất mục nào so với dữ liệu gốc.
6. **§23 mục 18 "nền tảng cho nhiều lĩnh vực":** đây là hướng horizontal. Audit 2026-11-06 đã chỉ ra đối thủ mạnh ở đúng vị trí này (Claude Cowork, n8n…). Đó là lý do Dung đã chọn một lĩnh vực cụ thể (video). MP-mới không nói rõ mình đứng ở đâu so với lựa chọn đó.

---

## 6. Điều MP-mới làm tốt hơn hiện trạng (nên giữ)

- Response Envelope + Validator lưu raw, normalized, kết quả validate và lịch sử sửa (§7.3): sửa trực tiếp lỗi R1 và cho phép đo chất lượng.
- Acceptance criteria và vòng REVIEW → REVISION_REQUIRED (§4 L4).
- Context Builder có thứ tự ưu tiên và các phần "không được cắt" (§9.2–9.3), đi cùng việc đánh dấu dữ liệu không tin cậy (§16).
- Một vai trò dùng nhiều model, model policy có fallback và ghi lý do (§3.2, Test G).
- Memory Integrity: không xóa bất đồng, không biến giả định thành sự thật (§8.1).
- Phân biệt người tạo, người chịu trách nhiệm, người kiểm tra, người duyệt, người nhận tiếp (§13).

---

## 7. Câu hỏi chiến lược cho Dung

**Câu hỏi chính:** MP-mới có thay thế hướng "AI Video Production Company" (2026-11-06) không?

| Lựa chọn | Hệ quả |
|---|---|
| 1. MP-mới **thay thế** video | Nhánh L1–L12 giữ nguyên, không merge. Làm Council từ main. Mất định vị theo lĩnh vực mà audit trước đã khuyên. |
| 2. **Nền tảng + video là use case đầu tiên** (khuyến nghị) | Làm ba engine (Response, Context, Meeting) trên main. Cuộc họp đầu tiên là "duyệt kịch bản video": biên kịch, người phản biện, người kiểm tra fact. Nhánh video merge sau khi Dung test trên máy. Có một workload thật để đo chất lượng Council. |
| 3. Chạy song song cả hai | Không khuyến nghị với ~1 giờ/ngày. |

**Các câu hỏi khác, ảnh hưởng kiến trúc:**
- Q2. Đồng ý bỏ browser automation, thay bằng API free tier + Manual Relay (§3)? Nếu Dung vẫn muốn tự động hóa web, cần chấp nhận rủi ro khóa tài khoản và không thương mại hóa được.
- Q3. Provider nào Dung đã có tài khoản API (kể cả free): Gemini API, Groq, OpenRouter, DeepSeek? Cái này quyết định adapter nào làm trước.
- Q4. Nghiệm thu P5 và review nhánh video vẫn đang treo. Có muốn chốt trước khi bắt đầu hướng mới?

---

## 8. Roadmap đề xuất (nếu chọn lựa chọn 2) `[Đề xuất]`

Mỗi bước là một task 1–3 buổi, chạy được và có test, theo đúng quy tắc của repo. Đặt tên "C" để không trùng P0–P5.

| Bước | Nội dung | Phụ thuộc | Test MP-mới | Độ khó |
|---|---|---|---|---|
| C0 | ADR: định hướng Council; không tự động hóa web của provider; Manual Relay; đặt tên giai đoạn | Dung trả lời §7 | — | S |
| C1 | **Sửa lỗi skill:** nạp tên và mô tả các skill đã ghim vào system prompt; nạp toàn văn khi agent cần (progressive disclosure qua tool `skill.read`) | — | A | S |
| C2 | Response Envelope v1 (JSON Schema, phần chung + 3 loại: research, review, decision) + Validator (raw → extract → validate → repair tất định → hỏi lại 1 lần → `INVALID_RESPONSE`); lưu raw/normalized/validation/repair | C0 | **D** (đủ 6 tình huống, bằng transport giả) | M |
| C3 | Task có `expected_output`, `acceptance_criteria`; trạng thái `review`, `revision_required`; reviewer là agent hoặc người | C2 | F (một phần) | M |
| C4 | Context Builder v1: các phần có thứ tự ưu tiên, token estimator (ghi rõ "ước tính"), cắt theo ưu tiên với danh sách không được cắt, bọc dữ liệu không tin cậy; lưu context đã ghép | C1 | I, J (một phần) | M |
| C5 | Meeting Room v1: room, member (agent + runtime), vòng 1 (độc lập, song song) và vòng cuối (moderator tổng hợp); Snapshot tất định từ Envelope, có version; UI phòng họp tối thiểu, tách rõ nội dung gốc và bản tổng hợp | C2, C4 | B, C, E | L |
| C6 | Adapter OpenAI-compatible (`base_url`) cho Groq, OpenRouter, DeepSeek, Gemini (nếu endpoint tương thích); Model Policy per agent (preferred + fallback + ghi lý do); cooldown khi bị rate limit | C0, Q3 | G | M |
| C7 | Runtime `manual_relay`: run chờ người dán, Context Package copy được, câu trả lời dán vào đi qua Validator | C2, C4 | B (với tài khoản web, thủ công) | S–M |
| C8 | Handoff Contract (chuyển quyền sở hữu), lịch sử handoff trong Task Center | C3 | F | M |
| Sau | Vòng 2–4 (thảo luận, phản biện, thương lượng), Structured Findings, Decision Registry, đọc PDF/DOCX, nhiều phòng song song, quality scoring | C5 | | |

**Không nên tự xây:** browser automation cho web app của provider; vector DB khi FTS5 còn đủ; engine durable kiểu Temporal (job bền ở nhánh video đã đủ, có thể dùng lại cho agent run).

**Hoãn:** dynamic team formation, multi-room, dashboard nâng cao (MP-mới P6).

---

## 9. Giới hạn của audit này

- Không chạy test trong phiên này. Số test (170 backend, 22 frontend) lấy từ audit 2026-11-06.
- Điều khoản OpenAI chưa đọc được từ nguồn chính thức.
- Quota free tier của Gemini API, Groq, OpenRouter, DeepSeek chưa tra. Cần xác minh khi làm C6.
- Đánh giá các repo ở §17 phần mới là sơ bộ, chưa đọc lại nguồn.

## Nguồn web
- Anthropic Consumer Terms: https://www.anthropic.com/legal/consumer-terms
- Google Terms of Service: https://policies.google.com/terms
- DeepSeek Terms of Use: https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html
- The Register, 2026-02-20: https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access
- OpenAI (nguồn thứ cấp, chưa xác minh): https://conductatlas.com/platform/openai/openai-terms-of-use/provision/CA-P-078686/no-automated-extraction-of-data-or-output/
