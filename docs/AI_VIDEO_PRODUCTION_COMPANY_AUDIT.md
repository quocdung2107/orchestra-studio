# ORCHESTRA STUDIO → AI VIDEO PRODUCTION COMPANY
## Repository Audit, Product Redesign & Architecture Roadmap

**Ngày:** 2026-11-06 · **Repo:** `quocdung2107/orchestra-studio` @ `45ac528` (main chưa thay đổi kể từ audit trước)
**Loại:** audit + thiết kế. Không sửa source, schema, package, cấu hình. Không gọi API trả phí, không đăng Facebook.
**Trạng thái:** chờ Dung duyệt. Chưa bắt đầu triển khai.

Nhãn bằng chứng:
- **[Repo]** đọc trực tiếp từ code · **[Test]** kết quả test chạy hôm nay · **[Doc]** tài liệu chính thức của nhà cung cấp (URL ở mục 13)
- **[Đề xuất]** đề xuất kiến trúc · **[Giả định]** chưa xác minh · **[Câu hỏi]** cần Dung quyết định
- **[S]** số liệu lấy từ bản tóm tắt trang, chưa đọc nguyên văn; cần kiểm tra lại trước khi dựa vào.

Báo cáo liên quan: `docs/audit/AUDIT_2026-11-06_production_readiness.md` (audit tổng quát cùng ngày). Báo cáo này thay phần "vertical đề xuất" của bản đó bằng hướng Dung đã chọn: tự vận hành kênh video trên Facebook.

---

## 0. Trả lời nhanh 5 câu hỏi thành công

| Câu hỏi | Trả lời ngắn |
|---|---|
| 1. Giữ lại được gì? | Phần điều hành: company, agent có version, task graph, approval gắn checksum, Tool Gateway, event, credential trong kho OS, worker, backup, contract OpenAPI. Khoảng 60–70% backend dùng lại được. |
| 2. Cần thay đổi gì? | Thêm hẳn một **Production Engine** (campaign, video, scene, asset, timeline, render job) mà repo hiện **không có gì**. Sửa lại artifact để chứa file nhị phân lớn (hiện chỉ cho văn bản ≤ 1 MB). Thêm Task Contract và verifier. Thêm job bền vững gọi provider bên ngoài. Thêm adapter Meta. |
| 3. Làm sao ra một video hoàn chỉnh? | Pipeline tất định có bước LLM: brief → script (structured output) → scene → ảnh/clip + giọng đọc → timeline JSON → FFmpeg render → QA tự động (ffprobe, độ dài, tỉ lệ, phụ đề, so khớp lời đọc) → người duyệt. Bản MVP dùng ảnh tĩnh có chuyển động, giọng đọc và phụ đề. Clip AI là tùy chọn theo từng scene. |
| 4. Đăng Facebook và lấy số liệu thế nào? | Graph API chính thức: Reels qua `/{page-id}/video_reels` (3–90 giây, 9:16), video dài qua `/{page-id}/videos` với resumable upload. Dùng Page access token lưu trong kho OS. Kiểm tra `status` sau khi đăng. Số liệu lấy qua `video_insights`, lưu snapshot theo thời điểm. |
| 5. Dùng kết quả cũ để cải thiện ra sao? | Mỗi video gắn thuộc tính (hook, độ dài, chủ đề, phong cách). Snapshot số liệu theo mốc cố định. So sánh theo nhóm có cỡ mẫu tối thiểu. CEO đề xuất giả thuyết và thử nghiệm, người dùng duyệt, kết luận ghi kèm độ tin cậy. Chưa làm tự động tối ưu trước khi có dữ liệu. |

---

## 1. Executive Summary

### Sản phẩm hiện tại thực chất là gì?

Một **bảng điều khiển cho tổ chức agent**, điều hành chặt chẽ, trung thực về lỗi. Nó **chưa sản xuất được bất cứ thứ gì ngoài văn bản**. Không có module nào xử lý ảnh, âm thanh hay video. Không có gọi API media, không có FFmpeg, không có kết nối Facebook. `social.publish` chỉ ghi một file JSON mô phỏng. [Repo]

"Demo Video Studio" hiện có chỉ là **kịch bản mock viết sẵn**: các agent CEO, CMO, Scriptwriter… trả về văn bản cố định trong YAML. [Repo] `runtime/mock/scenarios/demo-video-studio.yaml`

### Mức độ sẵn sàng

| Lớp | Mức |
|---|---|
| Control plane (task, event, approval, quyền) | Implemented and tested |
| LLM thật (Claude, OpenAI, Ollama) | Implemented but unverified (chỉ test bằng transport giả) |
| Production (ảnh, video, âm thanh, render) | Not implemented |
| Facebook publishing / analytics | Mock (publish) / Not implemented (analytics) |
| Learning loop | Partially (có lesson cần duyệt, không có số liệu thật) |

### Khoảng cách đến AI Video Production Company

Lớn ở **execution và media**, nhỏ ở **điều hành**. Ước tính thô: Phase 1–3 (video thật → đăng thật → số liệu thật) cần khoảng 90–150 buổi 1 giờ. Đây là ước lượng có độ bất định cao, vì phụ thuộc chất lượng provider và chính sách Meta. [Giả định]

### Ba rủi ro cần biết trước khi duyệt

1. **Chính sách nền tảng chưa xác minh được.** Mình không đọc được trang chính sách gốc của Meta về nhãn AI, "unoriginal content" và điều kiện kiếm tiền (bị chặn hoặc chỉ trả metadata). Một nguồn báo chí (bizhub.vietnamnews.vn, 16/07/2025) thuật lại rằng Meta giảm phân phối và chặn kiếm tiền với tài khoản đăng lại nội dung "without adding meaning". Kênh AI sản xuất hàng loạt có thể bị ảnh hưởng. **Dung nên tự kiểm tra trong Professional Dashboard và trang chính sách trước khi đầu tư lớn.** [Giả định][Câu hỏi]
2. **Provider video thay đổi rất nhanh.** Veo 3.1 Preview trên Gemini API đã bị tắt ngày 22/10/2026, thay bằng Gemini Omni Flash. Sora 2 API bị tắt ngày 24/09/2026 [S]. Thiết kế phải coi mọi provider video là thay thế được, và MVP không nên phụ thuộc vào video AI. [Doc]
3. **Máy của Dung không chạy được model video local.** Wan2.1 T2V-1.3B ghi "requires only 8.19 GB VRAM". RTX 3050 của Dung có 4 GB. ComfyUI chỉ có ích nếu dùng GPU khác hoặc cloud. [Doc]

---

## 2. Repository Reality

### 2.1 Kiểm chứng lại 10 phát hiện của audit trước

`origin/main` vẫn ở `45ac528`, không có commit mới. Mình đọc lại các dòng code liên quan hôm nay và chạy lại test (170 passed). [Repo][Test]

| # | Phát hiện cũ | Trạng thái | Bằng chứng hôm nay |
|---|---|---|---|
| 1 | Control plane khá hoàn chỉnh, deliverable yếu | **Still exists** | Không có module media nào; `tools_builtin.EXECUTORS` vẫn 4 key |
| 2 | Chưa có ingestion tài liệu | **Still exists** | Không có endpoint upload file; knowledge chỉ nhận text |
| 3 | Thiếu Task Contract, schema, acceptance, verifier | **Still exists** | `execution/models.py` `Task`: title, description, context_json; không có cột contract |
| 4 | Completed khi model chỉ trả lời | **Still exists** | `runtime/llm/base.py` khối cuối `_execute` → `run.completed`; `finish_run(ok=True)` → task `completed` |
| 5 | Tool nghiệp vụ hạn chế, có tool mô phỏng | **Still exists** | `social_publish` docstring "Simulated external action… never calls the network" |
| 6 | Delegation không truyền artifact con về cha | **Still exists** | `orchestrator/service.py` `delegate_tool` trả `summary` + danh sách tên artifact |
| 7 | Budget/timeout chưa đủ | **Still exists** | Chỉ `max_turns`, `max_tokens`; `gateway._wait_decision` chờ vô hạn |
| 8 | Thiếu evaluation | **Still exists** | Test runtime dùng `httpx2.MockTransport` (`tests/fake_providers.py`) |
| 9 | Security / prompt injection | **Still exists** | `base.user_prompt` ghép context JSON; tool result trả thẳng cho model; Electron không có CSP |
| 10 | Chưa có installer | **Still exists** | README: app chạy từ mã nguồn, cần `uv` |

Phát hiện mới, quan trọng cho hướng video:

| # | Phát hiện | Bằng chứng |
|---|---|---|
| N1 | **Artifact chỉ chứa văn bản, tối đa 1 MB.** Không lưu được ảnh, audio, video. | `runtime/normalize.py`: `MAX_ARTIFACT_BYTES = 1_000_000`, `mime_type` pattern `^(text/(plain|markdown)|application/json)$`; `execution/service.py` `store_artifact(content: str)` encode UTF-8 |
| N2 | Không có chạy tiến trình ngoài (FFmpeg) ở đâu cả | `grep subprocess\|ffmpeg` không có kết quả trong backend |
| N3 | Credential chỉ cho `anthropic`, `openai` | `credentials/schemas.py`: `Provider = Literal["anthropic", "openai"]` |
| N4 | Backup gom toàn bộ `artifacts/` và `workspaces/` vào một zip | `backup/service.py` `TREES = ("artifacts", "workspaces")`. Với video sẽ thành hàng GB |
| N5 | Worker protocol giới hạn artifact 1 MB | `workers/hub.py` → `ARTIFACT_TOO_LARGE` |
| N6 | Không có job bền vững cho tác vụ dài (provider async, render). Restart → mọi run `INTERRUPTED`, task active `failed` | `execution/service.py` `fail_interrupted_runs` |

### 2.2 Kiến trúc và luồng hiện tại

```text
Electron → React (13 view: Overview, Org, Agents, Capabilities, Runs, Approvals, Knowledge, KPI, Connections, Workers, Backup…)
  ↓ REST + SSE (token mỗi lần khởi động, Host/Origin check)
FastAPI (1 process, SQLite WAL)
  ├─ companies / organization / agents(+versions) / capabilities(skills, tools, grants)
  ├─ orchestrator: scheduler theo company → run → runtime → tool gateway → approval
  ├─ runtime: mock | ollama | anthropic | openai | worker
  ├─ events (cùng transaction với state) → SSE
  └─ knowledge FTS5, lessons, role proposals, metrics/KPI, credentials, backup, workers
```

Runtime flow cho model agent: task → `AgentRun` → `LlmRuntime` gọi model tối đa 8 lượt → tool qua Gateway hoặc `team.delegate` → câu trả lời cuối thành artifact `.md` → `completed`. [Repo]

### 2.3 Thực sự hoạt động vs mock

| Chức năng | Trạng thái |
|---|---|
| Company, department, org graph, agent version | Implemented and tested |
| Task graph, dependency, song song, retry, cancel | Implemented and tested |
| Pause/resume | Implemented and tested (chỉ Mock); model thật trả 409 |
| Approval L3 gắn checksum, exactly-once | Implemented and tested (nhưng chỉ cho tool mô phỏng) |
| Credential trong kho OS, xoay, thu hồi | Implemented and tested |
| Gọi Claude/OpenAI/Ollama | Implemented but unverified |
| `team.delegate` | Implemented and tested (với provider giả) |
| Worker cùng máy, lease, revoke | Implemented and tested |
| Backup/restore | Implemented and tested |
| Knowledge FTS5, lesson cần duyệt | Implemented and tested |
| KPI vận hành, chi phí ước tính | Implemented and tested |
| `social.publish` | Mock / Simulated |
| Demo Video Studio | Mock / Simulated (văn bản viết sẵn) |
| Mọi thứ liên quan media, Facebook, analytics nền tảng | Not implemented |

### 2.4 Bảng năng lực thực tế (yêu cầu mục 9)

| Năng lực | Hiện trạng | Bằng chứng | Mức hoàn thiện | Việc cần làm |
|---|---|---|---|---|
| Agent execution | Vòng lặp model + tool, giới hạn lượt | [Repo] base.py | Implemented and tested (với transport giả) | Gắn vào Task Contract; budget |
| Real LLM | Adapter 3 provider | [Repo] llm/*.py | Implemented but unverified | Chạy thử có kiểm soát ở Phase 1 |
| Structured output | Không dùng | [Repo] anthropic_rt.py chỉ gửi `effort` | Not implemented | `output_config.format` (Claude), `response_format` (OpenAI) |
| Task verification | Không có | [Repo] | Not implemented | Task Contract + verifier registry |
| File handling | Văn bản ≤ 1 MB | [Repo] N1 | Partially implemented | Media store nhị phân |
| Image generation | Không có | [Repo] | Not implemented | Image adapter |
| Video generation | Không có | [Repo] | Not implemented | Video adapter (tùy chọn) |
| Video rendering | Không có | [Repo] N2 | Not implemented | FFmpeg render job |
| Audio / TTS | Không có | [Repo] | Not implemented | TTS adapter tiếng Việt |
| Facebook publishing | Mô phỏng | [Repo] `social_publish` | Mock / Simulated | Meta adapter thật |
| Facebook analytics | Không có | [Repo] | Not implemented | Insights collector |
| Learning loop | Lesson do agent đề xuất, người duyệt | [Repo][Test] | Partially implemented | Hypothesis/experiment trên số liệu thật |
| Error recovery | Fail trung thực khi restart, không resume | [Repo] N6 | Partially implemented | Job bền vững, resume theo bước |

### 2.5 Phân loại thành phần: KEEP / EXTEND / REFACTOR / REPLACE / REMOVE

| Thành phần | Quyết định | Lý do (bằng chứng) |
|---|---|---|
| Companies | **KEEP** | Company = một đơn vị vận hành kênh. Đã có trần quyền, `max_parallel_runs`. |
| Organization / Departments | **KEEP, đóng băng** | Dùng để hiển thị phòng ban; không để sơ đồ báo cáo điều khiển sản xuất. Đã test kỹ, không cần sửa. |
| Agents + versions | **EXTEND** | Thêm capability metadata và contract đầu vào/đầu ra. Version đã có. |
| Skills (có version) | **KEEP** | Phù hợp để lưu prompt cho từng bước pipeline có version (ADR-0012). |
| Tools + permission levels | **EXTEND** | Thêm tool/hành động thật: `meta.publish` (L3), gọi provider media (L2, có budget). `decide()` dùng lại. |
| Tool Gateway | **EXTEND** | Thêm kiểm tra budget, idempotency key, kiểm tra input sâu hơn. Điểm thực thi chính sách giữ nguyên. |
| Orchestrator | **REFACTOR** | Thêm **pipeline/job runner** cho bước sản xuất. `team.delegate` chỉ giữ cho lập kế hoạch, không dùng để chạy sản xuất. File 748 dòng đang ôm nhiều trách nhiệm. |
| Runtime LLM (`LlmRuntime`) | **EXTEND** | Thêm structured output, prompt caching. |
| Mock runtime + kịch bản Demo Video Studio | **REPLACE** | Thay bằng provider giả tạo file thật (ảnh, wav, mp4 nhỏ) để test pipeline mà không tốn tiền. Mock runtime giữ cho test orchestration. |
| Worker | **KEEP** (dùng lại sau) | Có thể làm render worker ở Phase 5. Hiện giới hạn 1 MB, không dùng cho media ở Phase 1. |
| Events | **KEEP + EXTEND catalog** | Thêm event cho campaign, asset, render, publish, metrics. Mô hình cùng transaction giữ nguyên. |
| Approvals | **EXTEND** | Thêm loại duyệt: kế hoạch chiến dịch, chi tiêu vượt ngưỡng, bản cuối, đăng bài, chính sách tự đăng. Checksum + exactly-once giữ nguyên. |
| Knowledge | **EXTEND** | Làm nơi lưu research brief, nguồn. Learning memory là bảng riêng (có cấu trúc), không nhét vào knowledge. |
| Lessons | **EXTEND** → nối với Learning | Lesson phải dẫn chiếu số liệu và thử nghiệm. |
| Role-change proposals | **REMOVE khỏi UI chính / đóng băng** | Không phục vụ chuỗi giá trị video. Giữ code, không phát triển. |
| Metrics / KPI | **EXTEND** | Thêm chi phí sản xuất theo video; số liệu nền tảng nằm bảng riêng có nguồn và thời điểm. |
| Credentials | **EXTEND** | Mở rộng provider: `meta`, `elevenlabs`, `google`, `runway`… Cơ chế keyring giữ nguyên. |
| Backup | **REFACTOR** | Tách media khỏi zip mặc định (chỉ backup bản cuối + metadata), nếu không zip sẽ hàng GB. |
| `social.publish` | **REPLACE** | Thay bằng Meta adapter thật. |
| Electron shell | **KEEP + sửa** | Thêm CSP; thêm cách xem video local an toàn. |
| Frontend | **EXTEND** điều hướng mới | Màn hình hiện có chuyển vào "Company Control Room"; thêm CEO Dashboard, Campaign, Production, Distribution, Analytics. |
| SQLite | **KEEP** | Một người dùng, một máy; metadata không lớn. File media ở đĩa, không ở DB. |
| OpenAPI contract → TS types | **KEEP** | ADR-0003 vẫn đúng. |

---

## 3. Gap Analysis

| Loại | Gap | Mức |
|---|---|---|
| Product | Không có Campaign, Video, Scene, Asset, Timeline | Critical |
| Product | Không có Task Contract và nghiệm thu | Critical |
| Technical | Artifact không chứa nhị phân/lớn (N1) | Critical |
| Technical | Không có job bền vững cho provider async và render (N6) | High |
| Technical | Không có structured output | High |
| Technical | Không có budget theo chiến dịch/video | High |
| Integration | Không có adapter ảnh, video, TTS, nhạc, FFmpeg | Critical |
| Integration | Không có Meta Graph API | Critical (Phase 2) |
| Operational | Không đo chi phí theo video; không chính sách lưu trữ media | High |
| Operational | Backup không phù hợp media (N4) | Medium |
| Security | Token Meta là secret mới cần kho OS; nội dung web/comment là untrusted | High |
| Security | Electron thiếu CSP | Medium |
| Security | File media từ provider cần kiểm tra (ffprobe) trước khi xử lý | Medium |
| UX | UI xoay quanh agent/run, không quanh chiến dịch/video | High |
| UX | Không xem được video, timeline, phiên bản | High |

---

## 4. Product Vision

### 4.1 Định vị

Orchestra Studio là **xưởng sản xuất video của chính Dung**: nhận chủ đề, đề xuất chiến dịch, sản xuất video, chờ duyệt, đăng lên Facebook Page, đọc số liệu thật và đề xuất cải tiến. Người dùng nhìn thấy **chiến dịch, video, quyết định đang chờ và hiệu quả kênh**, không phải agent.

Nhận xét thẳng: mô hình A (tự vận hành kênh) giúp tránh phải cạnh tranh bán phần mềm. Nhưng thước đo thành công lúc này là **hiệu quả kênh trên chi phí sản xuất**, và nó phụ thuộc vào chính sách phân phối của Meta (rủi ro 1). [Đề xuất]

### 4.2 User journey

```text
1. Nhập chủ đề + mục tiêu ("bí ẩn vũ trụ, người yêu khoa học")
2. CEO trả Campaign Proposal: đánh giá tiềm năng, khán giả, góc tiếp cận, số video ngắn/dài, lịch, KPI, ngân sách ước tính
   → [Duyệt kế hoạch] (sửa / chấp nhận / từ chối)
3. Với từng video: Content Brief → Script → Storyboard → tài nguyên → render
   → chỉ dừng hỏi người khi: QA thất bại sau N lần, vượt ngân sách, hoặc tới bước duyệt bản cuối
4. [Duyệt bản cuối] xem preview, QA report, chi phí → Duyệt / Yêu cầu sửa (chọn scene)
5. [Duyệt đăng] caption, thời điểm → hệ thống đăng, kiểm tra trạng thái, lưu link
6. Sau 24 giờ / 7 ngày / 28 ngày: thu số liệu → báo cáo video
7. Cuối chiến dịch: báo cáo + đánh giá của CEO + giả thuyết + đề xuất thử nghiệm cho chiến dịch sau
```

### 4.3 Cấu trúc công ty: gộp lại cho vừa sức

Danh sách 10 bộ phận trong brief đúng về **chức năng**, nhưng không cần 10 agent. Đề xuất: **giữ 10 bộ phận làm nhãn hiển thị và nhóm trách nhiệm, nhưng chỉ có 4 agent LLM, còn lại là bước tất định.** [Đề xuất]

| Bộ phận (hiển thị) | Ai làm | Loại |
|---|---|---|
| CEO Office | Agent **CEO/Planner** | LLM: đề xuất chiến dịch, quyết định khi lỗi, đánh giá cuối |
| Research | Agent **Researcher** | LLM + tool nguồn (Phase 1: chỉ dùng kiến thức model và nguồn người dùng đưa, có ghi rõ; web search là Phase 1b) |
| Content Strategy | CEO/Planner (cùng agent) | LLM |
| Creative | Agent **Writer** | LLM: script, scene breakdown, prompt hình ảnh (structured output) |
| AI Production | Bước tất định gọi adapter | Không phải agent |
| Post-production | Bước tất định FFmpeg | Không phải agent |
| Quality Control | Verifier tất định + Agent **Reviewer** cho tiêu chí nội dung | Phần lớn tất định |
| Distribution | Bước tất định gọi Meta API | Không phải agent |
| Analytics | Bước tất định thu số liệu + Agent CEO viết nhận xét | Phần lớn tất định |
| Learning & Optimization | CEO/Planner + bảng hypothesis/experiment | LLM có ràng buộc |

### 4.4 Deliverables theo bộ phận

| Bộ phận | Deliverable | Kiểm tra tất định |
|---|---|---|
| CEO | Campaign Plan (JSON + Markdown) | Schema; tổng ngân sách ≤ trần; số video khớp lịch |
| Research | Research Brief + danh sách nguồn | Schema; mỗi khẳng định chính có nguồn hoặc nhãn "kiến thức chung, chưa kiểm chứng" |
| Writer | Script + Scene list + prompt hình | Schema; tổng thời lượng ước tính trong dải profile; mỗi scene có lời đọc và mô tả hình |
| Production | Asset (ảnh/clip/audio) + metadata | File mở được (ffprobe), đúng kích thước, có provider/prompt/chi phí |
| Post-production | Final MP4 + preview + render metadata | ffprobe: codec, fps, tỉ lệ, độ phân giải, độ dài, có audio |
| QC | QA Report | Danh sách check pass/fail; Reviewer LLM chỉ là một mục, không phải toàn bộ |
| Distribution | Published Post Record | Có `video_id`, trạng thái từ Meta, URL |
| Analytics | Video/Campaign Report | Mỗi số có nguồn, thời điểm, kỳ |

---

## 5. Target Architecture

### 5.1 Sơ đồ

```text
                         ┌──────────────── Electron + React ────────────────┐
                         │ CEO Dashboard · Campaigns · Production · Distribution│
                         │ Analytics · Company Control Room (màn hình cũ)        │
                         └───────────────────────┬──────────────────────────┘
                                                 │ REST + SSE
┌────────────────────────── CONTROL PLANE (FastAPI, SQLite) ─────────────────────────┐
│ Company · Agents · Permissions · Approvals · Events · Credentials   (KEEP/EXTEND)   │
│ Campaign Mgmt · Content (brief/script/scene) · Task Contract + Verifier  (MỚI)      │
│ Media Asset Mgmt (metadata, version, lineage)  · Budget Manager  (MỚI)              │
│ Distribution records · Analytics snapshots · Learning memory  (MỚI)                 │
│ Job Runner bền vững (bảng jobs, lease, retry, resume)  (MỚI, thay một phần orchestrator)│
└──────────────┬───────────────────────────────┬─────────────────────────────────────┘
               │                               │
   EXECUTION PLANE                     MEDIA PROCESSING PLANE
   LLM runtime (Claude/OpenAI/Ollama)  FFmpeg/ffprobe subprocess (render, kiểm tra)
   qua RunRequest + structured output  Media store trên đĩa: data/media/<sha256>
               │                               │
               └────────── EXTERNAL PROVIDERS (qua adapter + Tool Gateway + budget) ───┐
                  Image · Video · TTS · Music · Meta Graph API · (ComfyUI local tùy chọn)│
```

### 5.2 Domain modules (trong cùng monolith)

| # | Module | Trạng thái |
|---|---|---|
| 1 | Company Control Plane | KEEP (companies, agents, organization, approvals, events, credentials) |
| 2 | Campaign Management | MỚI `campaigns/` |
| 3 | Content Intelligence | MỚI `content/` (brief, research, script, scene) |
| 4 | Video Production | MỚI `production/` (pipeline, step contracts) |
| 5 | Media Asset Management | MỚI `media/` (store, metadata, lineage) |
| 6 | Rendering Engine | MỚI `render/` (timeline → FFmpeg) |
| 7 | Distribution Engine | MỚI `distribution/` (Meta adapter) |
| 8 | Analytics Engine | MỚI `analytics/` |
| 9 | Learning Engine | MỚI `learning/` (dùng lại lessons) |
| 10 | Provider Integration | MỚI `providers/` (adapter + capability registry) |
| 11 | Approval & Security | EXTEND approvals, gateway, credentials |
| 12 | Event & Observability | EXTEND events, metrics |

Không tách microservice. Lý do: một người dùng, một máy, một developer. [Đề xuất]

### 5.3 Data model (thực thể chính, tối giản)

```text
Campaign(id, company_id, topic, objective, audience_json, strategy_json, status, budget_usd, plan_version)
CampaignPlan(id, campaign_id, version, content_json, approved_by, approved_at)
Video(id, campaign_id, profile: short|long, title, status, current_script_version, current_timeline_version, final_asset_id)
Script(id, video_id, version, content_json{hook, narration[], cta, est_duration_s}, source_task_id)
Scene(id, video_id, index, script_version, narration, visual_prompt, duration_s, status)
Asset(id, company_id, kind: image|video_clip|voice|music|sfx|subtitle|render|preview,
      storage_ref (sha256 path), mime, bytes, duration_s, width, height,
      provider, model, prompt_hash, seed, cost_usd, license_json,
      parent_asset_id, source_task_id, scene_id, version, validation_status, retention_class: temp|keep)
Timeline(id, video_id, version, spec_json)   -- tracks/clips trỏ tới asset id
RenderJob(id, video_id, timeline_version, preset, status, output_asset_id, ffmpeg_log_ref, error)
QAReport(id, video_id, render_job_id, checks_json, result: pass|fail, reviewer)
ProviderJob(id, provider, external_job_id, idempotency_key, request_hash, status, cost_usd, attempts, last_error)
PublishingJob(id, campaign_id, video_id, page_id, platform, idempotency_key, request_json,
              platform_video_id, platform_post_id, url, status, created_at, published_at, error, retry_count)
MetricSnapshot(id, platform_video_id, metric, value, period, source, collected_at, completeness)
Hypothesis / Experiment / Lesson(…, confidence, evidence_refs)
Task + TaskContract(task_id, objective, input_refs, output_schema, acceptance_checks, budget, timeout_s, verification_json)
```

Lưu ý: Shot và Track **chưa cần** ở Phase 1. Một Scene có một visual (ảnh hoặc clip) và một đoạn lời đọc. Timeline có cố định 4 track: visual, voice, music, subtitle. [Đề xuất]

### 5.4 API contracts (ví dụ, không đầy đủ)

```text
POST /campaigns                         {topic, objective, constraints}
POST /campaigns/{id}/plan               → task CEO tạo CampaignPlan (async)
POST /campaign-plans/{id}/decide        {decision, checksum, edits?}
GET  /campaigns/{id}/videos
POST /videos/{id}/produce               → chạy pipeline
POST /scenes/{id}/regenerate            {what: visual|voice, prompt_override?}
POST /videos/{id}/render                → RenderJob
GET  /assets/{id}/content               (stream, Range header cho video)
POST /videos/{id}/publish               → PublishingJob (luôn tạo approval nếu chính sách yêu cầu)
GET  /videos/{id}/metrics
GET  /campaigns/{id}/report
```

### 5.5 Event flow (ví dụ)

`campaign.created` → `campaign.plan.proposed` → `approval.requested` → `campaign.plan.approved` → `video.created` ×N → `task.started/completed` (script) → `asset.created` → `provider_job.submitted/succeeded/failed` → `render.started/succeeded` → `qa.passed|failed` → `approval.requested` (final) → `publishing.submitted` → `publishing.confirmed|failed` → `metrics.collected` → `campaign.report.generated`.

Event vẫn ghi cùng transaction với state (ADR-0006). Payload chỉ chứa id, không chứa file. [Repo][Đề xuất]

### 5.6 Worker và job design

- **Phase 1–3: không cần worker riêng.** Một **Job Runner bền vững** trong control plane: bảng `jobs` (kind, payload, status, attempts, next_run_at, lease_until, idempotency_key). Mỗi bước pipeline là một job. Khởi động lại thì job `running` có lease hết hạn được chạy lại **nếu bước đó idempotent**, nếu không thì kiểm tra trạng thái bên ngoài trước (ví dụ hỏi provider bằng `external_job_id`). Khác với hành vi hiện tại là fail toàn bộ. [Đề xuất]
- FFmpeg chạy như subprocess với timeout, thư mục làm việc riêng, danh sách tham số cố định (không ghép chuỗi shell). [Đề xuất]
- Phase 5: chuyển render sang worker hiện có sau khi nâng giới hạn artifact (dùng upload theo chunk + checksum). [Đề xuất]

### 5.7 Provider adapters

```python
class ImageProvider(Protocol):
    capabilities: ImageCaps   # sizes, aspect ratios, max_batch, price_per_image, supports_seed
    async def submit(self, req: ImageRequest, idem_key: str) -> ProviderJobRef: ...
    async def poll(self, ref: ProviderJobRef) -> JobStatus: ...
    async def fetch(self, ref: ProviderJobRef) -> list[MediaBlob]: ...

# Tương tự: VideoProvider, TtsProvider (trả kèm timestamps nếu có), MusicProvider, Publisher, InsightsSource
```

- Capability metadata khai báo: giới hạn, giá, có audio không, có timestamps không, async hay sync. Pipeline chọn provider theo capability, không theo tên. [Đề xuất]
- Mọi lần gọi đi qua Tool Gateway (quyền + budget) và ghi `ProviderJob` **trước khi** gửi để chống gửi trùng. [Đề xuất]
- Mỗi adapter có bản giả (fake) tạo file thật để test. [Đề xuất]

### 5.8 Lựa chọn hạ tầng

| Vấn đề | Đề xuất | Lý do |
|---|---|---|
| DB | Giữ SQLite | Một người dùng; metadata nhỏ. PostgreSQL khi có nhiều máy. |
| Lưu file | Đĩa local, content-addressed `data/media/ab/cd/<sha256>` | Không trùng lặp, kiểm tra toàn vẹn. Object storage để sau. |
| Background jobs | Bảng `jobs` trong SQLite + vòng lặp asyncio | Đủ cho 1 máy; không thêm Redis/Celery. |
| Realtime | Giữ SSE | Chỉ cần đẩy trạng thái một chiều. |
| Rendering | FFmpeg CLI | Ổn định, miễn phí, có ffprobe để kiểm tra. |
| Local vs remote worker | Local trước | Phần nặng nhất (sinh video) chạy ở provider cloud. |

---

## 6. Video Production Architecture

### 6.1 Một engine, hai profile

```yaml
profile: short_reel
aspect: "9:16"; resolution: [1080, 1920]; fps: 30
duration_s: {min: 30, max: 90}         # Reels API: 3–90 giây [Doc]
structure: [hook(≤3s), body, cta]
subtitle: {style: large_center, max_chars_per_line: 24}
pace: {max_scene_s: 6}
video: {codec: h264, audio: aac 48kHz stereo ≥128kbps}   # khớp spec Reels [Doc]

profile: long_video
aspect: "16:9"; resolution: [1920, 1080]; fps: 30
duration_s: {min: 180, max: 600}
structure: [intro, chapters[3..6], outro]
subtitle: {style: bottom, max_chars_per_line: 42}
pace: {max_scene_s: 15}
```

Profile là dữ liệu cấu hình. Pipeline, contract và QA đọc giá trị từ profile. [Đề xuất]

### 6.2 Pipeline 13 bước và contract

| # | Bước | Ai | Input | Output (artifact) | Validation | Retry | Timeout | Budget |
|---|---|---|---|---|---|---|---|---|
| 1 | Campaign Brief | CEO (LLM) | topic, objective, lịch sử learning | CampaignPlan JSON | Schema; số video, ngân sách ≤ trần | 2 lần nếu sai schema | 5 phút | LLM ≤ $X |
| 2 | Content Brief | CEO (LLM) | Plan, video slot | ContentBrief JSON | Schema; profile hợp lệ | 2 | 3 phút | nhỏ |
| 3 | Script | Writer (LLM) | Brief, research | Script JSON (hook, narration[], cta) | Schema; ước tính thời lượng trong dải profile (số từ ÷ tốc độ đọc) | 2 | 5 phút | nhỏ |
| 4 | Storyboard | Writer (LLM) | Script | Scene list + visual prompt | Mỗi scene có narration + prompt; tổng thời lượng khớp | 2 | 5 phút | nhỏ |
| 5 | Scene Breakdown | Tất định | Storyboard | Scene rows | Chỉ số liên tục, không trùng | — | — | — |
| 6 | Asset Generation | Adapter ảnh/clip | visual prompt, profile | Asset image/clip | ffprobe/PIL mở được; đúng tỉ lệ; ≥ độ phân giải tối thiểu | 2 / scene, đổi seed | theo provider | theo scene |
| 7 | Voice / Audio | Adapter TTS + nhạc | narration từng scene | voice asset + timestamps; music asset | Độ dài audio hợp lý so với số ký tự; không im lặng | 2 | 2 phút / scene | theo ký tự |
| 8 | Video Generation (tùy chọn) | Adapter video | prompt + ảnh tham chiếu | clip asset | ffprobe; độ dài ≥ scene | 1 | theo provider | trần cứng |
| 9 | Editing | Tất định | scenes + assets | Timeline JSON | Mọi clip trỏ tới asset hợp lệ; tổng thời lượng | — | — | — |
| 10 | Rendering | FFmpeg | Timeline | Final MP4 + preview | Exit code 0; ffprobe khớp profile | 1 | 30 phút | 0 (local) |
| 11 | Quality Control | Verifier + Reviewer | MP4, script, phụ đề | QA Report | Danh sách mục 6.6 | sinh Revision Task | 10 phút | nhỏ |
| 12 | Final Approval | Người | QA report, preview, chi phí | Approval record | — | — | không hết hạn tự động nhưng có nhắc | — |
| 13 | Publishing | Meta adapter | MP4, caption, Page | PublishingJob + Post record | Trạng thái từ Meta | xem mục 7.5 | — | — |

Quy tắc chung: **một bước chỉ `completed` khi output qua validation**. Thất bại sau hết số lần retry → `needs_decision`, CEO đề xuất (đổi prompt, đổi provider, bỏ scene) và người dùng chọn nếu vượt ngân sách. [Đề xuất]

### 6.3 Tạo lại một phần, phiên bản và lịch sử

- **Tạo lại một scene**: tạo asset mới (version+1, `parent_asset_id` = asset cũ), timeline version mới thay đúng clip đó, render lại. Scene khác giữ nguyên asset.
- **Sửa lời thoại**: sửa narration scene → tạo lại voice scene đó → subtitle sinh lại từ timestamps → timeline mới → render.
- **Thay asset**: người dùng chọn asset khác (hoặc upload) → validation → timeline mới.
- **Tái sử dụng**: asset content-addressed theo sha256; cùng prompt+seed+provider+model có thể tra lại (cache) nếu provider tất định. [Giả định: không phải provider nào cũng tất định theo seed.]
- **Tiếp tục sau khi đóng app**: mỗi bước là job có trạng thái trong DB; provider async lưu `external_job_id` trước khi chờ. Khởi động lại thì hỏi trạng thái job ngoài thay vì gửi lại.

### 6.4 Asset và lưu trữ

- Phân loại `temp` (ảnh thử, clip bị loại, file trung gian render) và `keep` (asset dùng trong bản cuối, bản cuối, preview).
- Dọn `temp` sau N ngày; backup mặc định chỉ gồm DB + asset `keep` của video đã đăng. [Đề xuất]
- Ước tính dung lượng [Giả định]: video ngắn 60 giây 1080p H.264 khoảng 30–80 MB; video dài 8 phút khoảng 200–600 MB; asset trung gian có thể gấp 2–5 lần. 20 video/tháng có thể cần 5–20 GB/tháng nếu không dọn.

### 6.5 Rendering

- Timeline JSON → một lệnh FFmpeg filtergraph xác định: ảnh tĩnh có zoom/pan, nối scene, chuyển cảnh đơn giản, trộn voice + nhạc nền (ducking), phụ đề đốt vào hình (ASS/SRT) hoặc file riêng.
- Phụ đề lấy từ timestamps của TTS. ElevenLabs trả "character-level timing information" [Doc]. Gom thành từ và dòng ở phía mình.
- License: FFmpeg là LGPL, nhưng bản dùng `--enable-gpl` (ví dụ libx264) thì GPL áp cho toàn bộ FFmpeg [Doc]. Dùng nội bộ trên máy Dung không có vấn đề phân phối. Nếu sau này phát hành installer có kèm FFmpeg thì phải chọn bản build phù hợp. [Đề xuất]

### 6.6 QA

Tất định (bắt buộc pass):
- ffprobe: codec, fps 24–60, tỉ lệ, độ phân giải ≥ tối thiểu, độ dài trong dải profile, có audio AAC 48 kHz.
- Khớp spec Reels khi profile short: 9:16, 3–90 giây, ≥ 540×960 [Doc].
- Mức âm lượng (không im lặng, không clipping) qua bộ lọc `volumedetect`/`ebur128` của FFmpeg.
- Phụ đề: không dòng nào quá ký tự tối đa; thời gian phụ đề nằm trong thời lượng video.
- Lời đọc khớp script: chạy ASR (faster-whisper, MIT, có word timestamps [Doc]) trên audio rồi tính tỉ lệ lỗi từ so với narration; vượt ngưỡng thì fail. [Đề xuất; Whisper có tiếng Việt trong tokenizer [Doc], chất lượng với giọng TTS tiếng Việt chưa đo.]
- Mọi asset trong bản cuối có `license_json` và provider ghi rõ.

LLM Reviewer (hỗ trợ, không quyết định một mình): kiểm tra nội dung so với brief, khẳng định khoa học có nguồn hay không, nội dung nhạy cảm. Kết quả của Reviewer luôn đi kèm duyệt của người ở bước 12. [Đề xuất]

### 6.7 Khảo sát provider (truy cập 2026-11-06)

**Video**

| Provider | Tích hợp | Giá (theo nguồn) | 9:16 | Audio | Ghi chú |
|---|---|---|---|---|---|
| Google Gemini Omni Flash (`gemini-omni-1.1-flash`) | API chính thức (Gemini API) | ~$0,10/giây 720p [S]; qua Runway: 720p 10 credit/s = $0,10/s | Có ("9:16") | Có, mặc định sinh audio [S] | Thay Veo 3.1 Preview (đã tắt 22/10/2026). Trạng thái GA chưa nêu. SynthID watermark [S]. |
| Runway Dev API | API chính thức, $0,01/credit | gen4_turbo $0,05/s; gen4.5 $0,12/s; veo3.1_fast $0,10–0,15/s; kling3.0_standard $0,09–0,13/s | Chưa đọc | Tùy model | **Một API truy cập nhiều model**, giảm rủi ro provider tắt model. |
| Luma Ray3.2 | API chính thức | 5 giây: $0,15 (540p), $0,30 (720p), $1,20 (1080p) | Có (6 tỉ lệ gồm 9:16) | Chưa nêu | FAQ và bảng giá mâu thuẫn về cách tính 10 giây. |
| OpenAI Sora 2 | **Đã tắt 24/09/2026** [S] | — | — | — | Không dùng. |
| Kling (trực tiếp) | Chưa xác minh (trang dev không hiển thị nội dung) | — | — | — | Có thể dùng qua Runway. |
| Local (Wan2.1 1.3B) | Open weights, Apache-2.0 | $0 | 480p | — | Cần 8,19 GB VRAM; **không chạy trên máy Dung (4 GB)**. |

Ví dụ chi phí [Giả định, tính từ giá trên]: video ngắn 60 giây với 6 clip AI × 5 giây ở $0,10/s = $3,00, cộng tạo lại 50% → khoảng $4,50. Nếu dùng ảnh tĩnh có chuyển động thay cho clip: 12 ảnh × ~$0,04 ≈ $0,50.

**Ảnh**

| Provider | Giá | Ghi chú |
|---|---|---|
| Gemini image (Nano Banana 2.1) | 1K $0,0336/ảnh; batch giảm 50% [S] | Bản trả phí: nội dung "not used to improve our products" [Doc] |
| Runway (gen4_image_turbo / nano_banana_2.1) | $0,02 / $0,04 mỗi ảnh | Cùng API với video |
| Luma uni-1.1 | 2K ~$0,04 | "Prices are approximate" |
| BFL FLUX | 1 credit = $0,01; giá từng model không đọc được | FLUX.2 [klein] 4B "open weights that run on consumer GPUs"; VRAM thực tế chưa xác minh |
| OpenAI gpt-image | Chỉ có giá theo token, không có giá theo ảnh trên trang giá | Chưa xác minh |

**TTS tiếng Việt**

| Provider | Tiếng Việt | Giá | Timestamps | Ghi chú |
|---|---|---|---|---|
| ElevenLabs | Có (eleven_v4, v3, Flash v2.5; **không** có ở multilingual_v2) | v4 $0,08 / 1K ký tự; Flash/Turbo $0,04 | Có, theo ký tự | "commercial usage rights are only available with paid plans" |
| Google Cloud TTS Chirp 3: HD | Có (vi-VN) | $30 / 1M ký tự, miễn phí 1M đầu mỗi tháng | Chưa nêu | Tối đa 5.000 byte mỗi request |
| OpenAI TTS | Có liệt kê [S] | Không thấy giá | Không nêu | **tts-1, tts-1-hd, gpt-4o-mini-tts ngừng ngày 06/01/2027** [S]. Không chọn. |

Ví dụ [Giả định]: video dài 8 phút ≈ 7.000 ký tự lời đọc → ElevenLabs v4 ≈ $0,56; Google Chirp 3 HD ≈ $0,21 (hoặc $0 trong hạn mức miễn phí).

**Nhạc / hiệu ứng**

| Provider | Tích hợp | Giá | Điều khoản |
|---|---|---|---|
| ElevenLabs Music | API chính thức | $0,15 / phút | API từ gói Starter; Starter/Creator/Pro "For Individual Use Only"; Free cấm phát hành |
| ElevenLabs Sound Effects | API chính thức | $0,12 / phút; tối đa 30 giây/lần | "Royalty-free" |
| Stable Audio | API chính thức | 8 credit ($0,08) mỗi lần sinh tối đa 3–6 phút | "You own your outputs" |
| Suno | **Không thấy API chính thức** | — | Không đưa vào thiết kế |

**Local workflow**

- ComfyUI: có server API (`POST /prompt`, `/history/{prompt_id}`, WebSocket), GPL-3.0, chạy như tiến trình riêng qua HTTP. Tài liệu nói raw Server API "has no compatibility guarantee across releases" [Doc]. → Adapter tùy chọn, Phase 5, khi có GPU phù hợp.

### 6.8 Đề xuất provider cho MVP [Đề xuất]

- LLM: Claude (đã có adapter) hoặc Ollama cho bước rẻ; structured output bắt buộc.
- Ảnh: một provider (Gemini image hoặc Runway) sau adapter.
- TTS: ElevenLabs (tiếng Việt + timestamps để làm phụ đề) hoặc Google Chirp 3 HD (rẻ hơn, chưa có timestamps → cần ASR để căn phụ đề). **[Câu hỏi]** Dung muốn chất lượng giọng hay chi phí?
- Video AI: **tắt ở MVP**; bật theo scene ở Phase 1b qua Runway hoặc Gemini Omni.
- Nhạc: thư viện nhạc miễn phí bản quyền có giấy phép rõ ràng do Dung chọn (nhập tay), hoặc Stable Audio.
- Render: FFmpeg local.

---

## 7. Facebook Integration

Nguồn: tài liệu Meta for Developers, truy cập 2026-11-06. Changelog ghi bản mới nhất là v26.0 (29/07/2026). Các hướng dẫn video dùng ví dụ v25.0. [Doc]

### 7.1 Khả năng API đã xác minh

| Khả năng | Có? | Chi tiết |
|---|---|---|
| Đăng video lên Page | Có | `POST graph-video.facebook.com/v25.0/<PAGE_ID>/videos` với file handle từ Resumable Upload API (`POST /<APP_ID>/uploads` → `POST /upload:<SESSION_ID>`; resume bằng `GET` để lấy `file_offset`) |
| Đăng Reels lên Page | Có | `POST /{page-id}/video_reels` `upload_phase=start` → upload lên `rupload.facebook.com` → `upload_phase=finish`, `video_state=PUBLISHED` |
| Spec Reels | Có | .mp4, 9:16, 1080×1920 khuyến nghị (tối thiểu 540×960), 24–60 fps, **3–90 giây**, H.264/H.265, AAC-LC 48 kHz |
| Giới hạn Reels | Có | "limited to 30 API-published posts within a 24-hour moving period" |
| Trạng thái xử lý | Có (tài liệu Reels) | `GET /{video-id}?fields=status` → `video_status`, `uploading_phase`, `processing_phase`, `publishing_phase` |
| Kiểm tra bản quyền | Có | `copyright_check_information` |
| Lên lịch đăng | **Chưa xác minh** | Không thấy `scheduled_publish_time` trên các trang đã đọc. Không thiết kế dựa trên nó; lịch đăng chạy phía Orchestra. |
| Giới hạn dung lượng/thời lượng video thường | Chưa xác minh | Không nêu trên trang đã đọc |
| Insights video | Có | `video_insights`: `total_video_views` (≥ 3 giây), `total_video_avg_time_watched`, `total_video_retention_graph` (40 khoảng), `total_video_complete_views`, `total_video_impressions(_unique)`, `total_video_reactions_by_type_total`, `total_video_10s_views`, `total_video_30s_views` |
| Insights Reels | Có | `blue_reels_play_count`, `fb_reels_total_plays`, `fb_reels_replay_count`, `post_impressions_unique`, `post_video_avg_time_watched`, `post_video_retention_graph`, `post_video_view_time`, `post_video_social_actions`, `post_video_likes_by_reaction_type`, `post_video_followers` |
| Lưu giữ insights | Có | "Data is only available for the past 2 years" |

### 7.2 Quyền, loại tài khoản, xét duyệt

- Quyền đăng (theo tài liệu Reels): `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`. Đọc insights: `pages_manage_engagement`, `read_insights`, token của người có task `ANALYZE`. [Doc]
- Token đăng: "A Page access token requested by a person who can perform the CREATE_CONTENT task on the Page". [Doc]
- Standard Access: "can only be requested from app users who have a role on the requesting app". Advanced Access cần Business Verification. [Doc]
- **Suy luận [Giả định]:** Dung là admin Page của mình và có vai trò trên app của chính mình, nên Standard Access trong Development Mode có thể đủ, không cần App Review. Cần thử thật với một Page thử nghiệm để xác nhận.
- "If your app does not use a permission for 90 days… the app user must regrant". [Doc] → phải nhắc người dùng.

### 7.3 Token

- User token ngắn hạn → long-lived (~60 ngày, `fb_exchange_token`) → lấy **long-lived Page token** qua `/{user-id}/accounts`. Page token loại này "do not have an expiration date and only expire or are invalidated under certain conditions". [Doc]
- Lỗi token: code 190, subcode 463 (hết hạn), 467 (không hợp lệ), 492 (người dùng không còn vai trò trên Page). [Doc]
- Thiết kế [Đề xuất]:
  - Lưu Page token trong kho OS qua credential store hiện có (thêm provider `meta`). DB chỉ giữ tham chiếu, `page_id`, quyền đã cấp, thời điểm kiểm tra.
  - Đăng nhập Facebook diễn ra trong trình duyệt hệ thống. Token không bao giờ tới renderer.
  - Kiểm tra token hằng ngày (`debug_token` hoặc một lời gọi nhẹ); gặp 190/463/467/492 → credential `needs_reauth`, dừng job đăng, báo trên CEO Dashboard.

### 7.4 Hai phương án phê duyệt

| | 1. Duyệt từng bài | 2. Tự đăng theo chính sách |
|---|---|---|
| Rủi ro nội dung sai/nhạy cảm lên công khai | Thấp | Trung bình–cao, nhất là giai đoạn đầu chưa có số liệu QA |
| Rủi ro chính sách Meta (spam, unoriginal) | Thấp hơn: người kiểm soát nhịp đăng | Cao hơn nếu đăng dày |
| Công sức người dùng | Vài phút/bài | Gần như không |
| Yêu cầu kỹ thuật | Approval hiện có (checksum đúng payload: file sha256 + caption + page) | Thêm Policy (trần số bài/ngày, giờ đăng, danh sách chủ đề cho phép, QA phải pass toàn bộ, Reviewer không cảnh báo), có approval cho chính policy đó, nút dừng khẩn cấp |
| Audit | Mỗi bài có quyết định của người | Mỗi bài trỏ tới policy version đã duyệt |

**Khuyến nghị [Đề xuất]:** bắt đầu bằng phương án 1. Chỉ mở phương án 2 khi đã có ít nhất khoảng 20 bài đăng qua phương án 1 mà QA tự động và người duyệt đồng ý ≥ 90%. Ngay cả khi đó vẫn giới hạn số bài/ngày dưới mức 30 Reels/24 giờ của API. Quyết định cuối thuộc Dung. **[Câu hỏi]**

### 7.5 Publishing contract và chống đăng trùng

Record: `campaign_id, video_id, page_id, platform, publishing_job_id, idempotency_key = sha256(video_final_asset_sha256 + page_id + caption_hash), request_json, platform_video_id, platform_post_id, url, status, created_at, published_at, error, retry_count`.

Trạng thái: `draft → awaiting_approval → approved → uploading → processing → published | failed | unknown`.

Quy tắc [Đề xuất]:
1. Tạo PublishingJob và lưu **trước** lời gọi đầu tiên. Không cho tạo job thứ hai cùng `idempotency_key` khi job trước chưa `failed`.
2. Reels: lưu `video_id` ngay sau `upload_phase=start`. Mọi retry sau đó dùng lại `video_id` (resume theo `bytes_transfered`), không gọi `start` lại.
3. Timeout ở bước `finish` → trạng thái `unknown`, **không gửi lại**. Hỏi `GET /{video-id}?fields=status` cho tới khi biết chắc.
4. `published` chỉ khi `status` báo đã xong `publishing_phase` và có id bài đăng/URL. `{"success": true}` từ `finish` chưa đủ.
5. Lỗi duplicate post (code 506), throttle (4, 17, 32, 613, 80001), "Temporarily blocked for policies violations" (368) → dừng, không retry dồn dập; 368 báo người dùng.
6. Đọc header `X-Business-Use-Case-Usage` để giãn nhịp.

### 7.6 Giới hạn cần biết

- Reels tối đa 90 giây, nên profile short là ≤ 90 giây. Video dài đăng qua `/videos`, không phải Reels.
- Chính sách nhãn AI, nội dung gốc và kiếm tiền: **chưa xác minh từ nguồn chính thức** (trang chính sách bị chặn đọc tự động). Nguồn báo chí có nêu Meta giảm phân phối với nội dung đăng lại không thêm giá trị. Thiết kế nên: không dùng nội dung của người khác; ghi provenance từng asset; có trường "đã gắn nhãn AI" trong publishing record; Dung tự kiểm tra trang chính sách và Professional Dashboard. **[Câu hỏi]**
- Tài liệu có chỗ không nhất quán (một ví dụ Reels dùng v18.0 đã ngừng). Adapter cố định một phiên bản API và có test hợp đồng.

---

## 8. Learning & Optimization

### 8.1 Metrics: lấy được đến đâu

| Nhóm | Chỉ số | Nguồn |
|---|---|---|
| Reach | Views (≥ 3 giây), impressions, unique impressions | **Trực tiếp** (`total_video_views`, `total_video_impressions(_unique)`; Reels: `fb_reels_total_plays`, `post_impressions_unique`) |
| Retention | Avg watch time, retention graph, complete views | **Trực tiếp** (`total_video_avg_time_watched`, `total_video_retention_graph`, `total_video_complete_views`; Reels: `post_video_avg_time_watched`, `post_video_retention_graph`) |
| Completion rate | complete_views / views | **Tính** từ dữ liệu trực tiếp |
| Engagement | Reactions | **Trực tiếp** (`total_video_reactions_by_type_total`, `post_video_likes_by_reaction_type`) |
| Engagement | Comments, shares | Reels: `post_video_social_actions` trực tiếp; video thường: **chưa xác minh** endpoint cụ thể |
| Saves | — | **Chưa xác minh** |
| Growth | Follower từ video | Reels: `post_video_followers`; Page follower growth: **chưa xác minh** (Page insights chưa đọc) |
| Conversion | Link clicks, traffic, leads | **Chưa xác minh** / nhập tay hoặc UTM + analytics website |
| Efficiency | Chi phí sản xuất, chi phí/video, thời gian sản xuất, số lần sửa | **Nội bộ** (Orchestra tự đo, chính xác) |
| Cost per engagement | chi phí / (reactions + comments + shares) | **Tính** |

Mỗi `MetricSnapshot` lưu: source (`meta_graph_v25.0`, `internal`, `manual`), collected_at, period (`lifetime@24h`, `lifetime@7d`, `lifetime@28d`), định nghĩa, value, completeness, freshness.

Vì metric là `lifetime`, cần **snapshot theo mốc cố định sau khi đăng** (ví dụ 1 giờ, 24 giờ, 7 ngày, 28 ngày) để so sánh công bằng giữa video. [Đề xuất]

### 8.2 Learning loop

```text
Published → snapshots (24h/7d/28d) → Performance table (đã chuẩn hóa theo mốc)
→ CEO viết phân tích + giả thuyết (có trích số liệu) → người dùng duyệt giả thuyết
→ Experiment: biến thay đổi (hook / độ dài / chủ đề / phong cách), nhóm đối chứng, số video tối thiểu mỗi nhóm, khoảng thời gian
→ chiến dịch mới dùng thiết kế thử nghiệm → so sánh → Lesson (kèm độ tin cậy)
```

Quy tắc ràng buộc [Đề xuất]:
- Mỗi video gắn thuộc tính có cấu trúc (hook_type, duration_bucket, topic, style, giờ đăng) để so sánh được.
- Không kết luận khi mỗi nhóm có ít hơn một ngưỡng tối thiểu (ví dụ 5 video); báo cáo ghi rõ "chưa đủ dữ liệu".
- So sánh trong cùng khoảng thời gian; ghi các yếu tố gây nhiễu đã biết (giờ đăng, sự kiện).
- Không đổi toàn bộ chiến lược từ một video. Thay đổi chiến lược lớn cần duyệt.
- Lesson lưu: campaign, strategy, hypothesis, experiment, performance, kết luận, **confidence** (low/medium/high theo cỡ mẫu và độ chênh), next action.
- CEO **không tự sửa prompt hoặc chiến lược đang chạy**; chỉ đề xuất, người duyệt áp dụng thành version mới (giống cơ chế role proposal hiện có).

### 8.3 Evaluation nội bộ (chất lượng sản xuất)

- Tỉ lệ QA pass lần đầu, số vòng sửa, tỉ lệ người duyệt chấp nhận bản cuối, chi phí/video, thời gian/video. Đây là chỉ số tối ưu được ngay, không chờ số liệu Facebook.
- Bộ "golden brief" 10–20 chủ đề cố định để so sánh prompt/model/provider khi thay đổi.

---

## 9. UX Redesign

### 9.1 Điều hướng

```text
CEO Dashboard        ← màn hình mặc định
Campaigns            ← danh sách + Campaign Workspace
Production           ← hàng đợi video đang sản xuất + Video Production Workspace
Distribution Center
Analytics Center
Decisions (n)        ← gộp approvals + vấn đề cần xử lý
───────────
Company Control Room ← Org, Agents, Skills & Tools, Runs, Knowledge, Workers, Connections, Backup (màn hình hiện có)
```

### 9.2 Màn hình

| Màn hình | Nội dung | Editor hay viewer (Phase 1) |
|---|---|---|
| CEO Dashboard | Chiến dịch đang chạy, video theo trạng thái, lịch đăng, hiệu quả tóm tắt, quyết định chờ, sự cố | Viewer + nút quyết định |
| Campaign Workspace | Mục tiêu, khán giả, chiến lược, kế hoạch nội dung, danh sách video, tiến độ, lịch, hiệu quả | Sửa kế hoạch trước khi duyệt |
| Video Production Workspace | Script, storyboard (lưới scene có ảnh), asset, timeline đơn giản, render, QA, lịch sử version | **Editor có giới hạn**: sửa narration, tạo lại/thay asset từng scene, đổi thứ tự scene. Timeline là viewer. Không làm NLE. |
| Distribution Center | Page đã kết nối và tình trạng token, hàng đợi đăng, đã đăng (link), lỗi, lịch | Viewer + hành động (duyệt, thử lại có kiểm soát) |
| Analytics Center | Hiệu quả theo video/chiến dịch, so sánh theo thuộc tính, xu hướng, insight có độ tin cậy | Viewer |
| Company Control Room | Như hiện tại | Giữ nguyên |

### 9.3 Quyền và mức tự động

| Mức | Ý nghĩa | Áp dụng mặc định |
|---|---|---|
| Draft | AI tạo, chưa dùng | Research, script |
| Review | Cần người duyệt để đi tiếp | Campaign plan, bản cuối, đăng bài, chi tiêu vượt ngưỡng |
| Approved | Được đi tiếp | Sau duyệt |
| Auto Execute | Tự làm trong giới hạn | Tạo asset trong ngân sách đã duyệt; tạo lại scene ≤ N lần |

Pause/Cancel ở cấp chiến dịch và video: dừng job chưa gửi ra ngoài; job đang chạy ở provider được đánh dấu "bỏ kết quả" (không hủy được ở mọi provider). [Đề xuất; khả năng hủy job theo từng provider chưa xác minh.]

---

## 10. Roadmap

Đơn vị độ phức tạp: S (≤ 5 buổi), M (5–15), L (15–30), XL (> 30). Ước tính có độ bất định cao.

### Phase 0 — Audit & Architecture (đang ở đây)
- Objective: duyệt thiết kế, chốt quyết định mục 11 và câu hỏi mục 12.
- Exit: Dung duyệt; ADR cho các quyết định kiến trúc mới được viết (Task Contract, media store, job runner, provider adapter, Meta integration).

### Phase 1 — Production Foundation
- Objective: từ một chủ đề ra **file MP4 ngắn và dài đạt QA**, chưa đăng.
- Scope: Task Contract + verifier; job runner bền vững; media store nhị phân; Campaign/Video/Script/Scene/Asset/Timeline/RenderJob/QAReport; LLM structured output cho plan/brief/script/storyboard; adapter ảnh + TTS (+ fake adapters); FFmpeg render; QA tất định; UI Campaign + Production (bản tối thiểu); duyệt plan và bản cuối.
- Sub-phases: 1a short profile ảnh tĩnh + voice + phụ đề → 1b long profile → 1c clip AI tùy chọn theo scene.
- Files/modules: mới `campaigns/`, `content/`, `production/`, `media/`, `render/`, `providers/`, `jobs/`; sửa `execution/` (contract), `runtime/llm/` (structured output), `credentials/schemas.py` (provider mới), `approvals/` (loại duyệt), `events/catalog.py`, `backup/service.py`, renderer views mới.
- DB: migration 0007+ cho các bảng mục 5.3.
- API: nhóm endpoint mục 5.4; contracts sinh lại TS.
- Tests: contract test cho mỗi adapter (fake transport); pipeline end-to-end với fake adapter tạo file thật; QA với video mẫu lỗi (sai tỉ lệ, im lặng, quá dài); resume sau restart giữa các bước; budget vượt trần.
- Acceptance: từ chủ đề mẫu tạo ra MP4 short 30–90 giây 9:16 và long 3–10 phút pass toàn bộ QA tất định; tạo lại 1 scene không làm thay đổi scene khác; khởi động lại app giữa pipeline thì tiếp tục được; chi phí/video được ghi lại.
- Risks: chất lượng hình/giọng chưa đủ để đăng; FFmpeg trên Windows (đường dẫn, font phụ đề tiếng Việt); máy 7,4 GB RAM khi render 1080p.
- Complexity: **XL** (ước tính thô 50–80 buổi).
- Exit: Dung xem 3 video thật và đánh giá "đủ để đăng thử".

### Phase 2 — Facebook Publishing
- Objective: đăng video thật lên Page, có trạng thái xác minh.
- Scope: app Meta của Dung (Dung tự tạo), kết nối Page (OAuth qua trình duyệt hệ thống, token vào kho OS), Reels + video thường, PublishingJob + idempotency, kiểm tra trạng thái, xử lý lỗi/throttle, duyệt từng bài, Distribution Center.
- DB: `publishing_jobs`, `platform_posts`, credential provider `meta`.
- Tests: contract test với transport giả cho từng nhánh lỗi (timeout ở finish, 506, 190/463, 368, throttle); test thật trên **Page thử nghiệm** trước Page chính.
- Acceptance: 3 bài đăng thật trên Page thử nghiệm, mỗi bài có `platform_video_id`, URL, trạng thái `published` lấy từ `status`; mô phỏng timeout không tạo bài trùng.
- Risks: điều kiện quyền/app mode khác suy luận; chính sách nội dung.
- Complexity: **L** (15–30 buổi).

### Phase 3 — Analytics
- Objective: số liệu thật, có nguồn và thời điểm.
- Scope: collector theo lịch (snapshot 1h/24h/7d/28d), `MetricSnapshot`, báo cáo video/chiến dịch, Analytics Center, chi phí/engagement.
- Acceptance: với ≥ 5 video đã đăng, báo cáo hiển thị đúng số so với Meta Business Suite (đối chiếu tay) và ghi rõ chỉ số nào thiếu.
- Complexity: **M–L** (10–20 buổi).

### Phase 4 — Learning & Optimization
- Objective: dùng dữ liệu cũ để thiết kế chiến dịch mới có kiểm soát.
- Scope: thuộc tính video, hypothesis/experiment/lesson, báo cáo của CEO có trích số, đề xuất thay đổi cần duyệt.
- Điều kiện bắt đầu: có ít nhất ~20–30 video với snapshot 7 ngày. [Giả định]
- Complexity: **M** (8–15 buổi).

### Phase 5 — Expansion
Nền tảng khác, nhiều Page, lịch nâng cao, render worker từ xa, cloud rendering, ComfyUI, phân tích nâng cao. Chỉ làm khi Phase 1–4 ổn định.

---

## 11. Technical Decisions

| Decision | Recommended Option | Alternatives | Reason | Trade-off |
|---|---|---|---|---|
| Kiến trúc tổng | Giữ modular monolith, thêm module mới | Microservices; viết lại | Control plane đã test kỹ; 1 developer | Monolith lớn dần; cần ranh giới module rõ |
| Điều khiển sản xuất | **Pipeline tất định có bước LLM**, CEO lập kế hoạch và xử lý ngoại lệ | CEO giao việc tự do qua `team.delegate` theo sơ đồ tổ chức | Delegation hiện mất thông tin (chỉ trả 1 dòng); sản xuất video cần thứ tự và contract rõ | Ít "tự chủ" hơn hình ảnh "công ty AI" |
| Số agent | 4 agent LLM (CEO/Planner, Researcher, Writer, Reviewer) | 1 agent/bộ phận | Ít chi phí, dễ kiểm thử | Bộ phận chỉ là nhãn hiển thị |
| Chọn agent cho bước | Theo luật: capability phù hợp → chất lượng đo được → chi phí | LLM tự chọn | Tất định, giải thích được | Cần dữ liệu eval để có "chất lượng" |
| Task Contract | Bảng contract gắn task, verifier đăng ký theo key | Chỉ dựa vào prompt | Chặn "completed" giả | Đổi schema + event contract (cần ADR) |
| Job | Bảng `jobs` SQLite + asyncio, lease, idempotency key | Celery/Redis; Temporal | Không thêm hạ tầng | Không phân tán được (chưa cần) |
| Media storage | Đĩa local content-addressed, metadata trong DB | Object storage; lưu BLOB trong SQLite | Đơn giản, toàn vẹn | Phải tự dọn dẹp, backup có chọn lọc |
| Render | FFmpeg CLI + timeline JSON tự định nghĩa | MoviePy; Remotion; ComfyUI | Ổn định, nhanh, kiểm tra được bằng ffprobe | Tự viết filtergraph |
| Visual MVP | Ảnh tĩnh có chuyển động + voice + phụ đề | Clip AI cho mọi scene | Rẻ hơn ~10 lần, ít phụ thuộc provider đang thay đổi | Ít hấp dẫn hơn; có thể ảnh hưởng hiệu quả |
| Provider | Adapter + capability registry; Runway làm cổng đa model cho video | Gắn chặt một provider | Veo preview và Sora đều đã tắt trong 2 tháng qua | Thêm một lớp trừu tượng |
| TTS | ElevenLabs (v4/Flash, có timestamps) hoặc Google Chirp 3 HD | OpenAI TTS | Có tiếng Việt; OpenAI TTS sắp ngừng | Phụ thuộc gói trả phí cho quyền thương mại |
| Phụ đề | Từ timestamps TTS; ASR (faster-whisper) để QA | Chỉ ASR | Chính xác theo script | ASR tiếng Việt cần đo |
| Facebook | Graph API chính thức, Standard Access, Page token trong kho OS | Tự động hóa trình duyệt; công cụ bên thứ ba | Đúng điều khoản, kiểm soát được | Phụ thuộc thay đổi API của Meta |
| Phê duyệt đăng | Duyệt từng bài trước; tự đăng theo policy sau khi có dữ liệu | Tự đăng ngay | Rủi ro công khai và chính sách | Tốn vài phút/bài |
| DB | Giữ SQLite | PostgreSQL | Một máy | Đổi khi có nhiều máy |
| Realtime | Giữ SSE | WebSocket | Đủ dùng | — |
| Local AI | ComfyUI để sau | ComfyUI ngay | Máy 4 GB VRAM không chạy được model video | — |

---

## 12. First Implementation Backlog (sau khi Dung duyệt)

Thứ tự theo phụ thuộc. Mỗi mục kết thúc ở trạng thái chạy được, test pass (theo CLAUDE.md).

| # | Task | Complexity | Kết quả kiểm chứng |
|---|---|---|---|
| B0 | ADR 0028–0032: Task Contract, media store, job runner, provider adapter, hướng sản phẩm video | S | ADR được duyệt |
| B1 | Media store nhị phân + `Asset` (sha256, kind, lineage, retention) + endpoint stream có Range | M | Upload/đọc file 200 MB, checksum đúng, test path traversal |
| B2 | Job runner bền vững (`jobs`, lease, retry, idempotency, resume sau restart) | M | Test: kill giữa job, khởi động lại → job tiếp tục hoặc đối soát, không chạy trùng |
| B3 | Task Contract + verifier registry; task không `completed` khi verifier fail | M | Test 3 trạng thái: passed / failed / needs_decision |
| B4 | Structured output trong `LlmRuntime` (Claude `output_config.format`, OpenAI `response_format`, Ollama JSON) | S–M | Contract test với transport giả cho cả 3 |
| B5 | Campaign + CampaignPlan + duyệt plan (dùng Approvals) | M | API + UI tối thiểu; plan có schema |
| B6 | Video/Script/Scene + bước Content Brief, Script, Storyboard với profile short | M | Script qua schema + kiểm tra thời lượng ước tính |
| B7 | Provider adapter interface + fake image/TTS tạo file thật | S–M | Pipeline chạy hoàn toàn offline |
| B8 | Timeline JSON + FFmpeg render (ảnh + voice + phụ đề), ffprobe QA | M–L | MP4 9:16 30–90 giây pass QA tất định trên Windows |
| B9 | Adapter thật: 1 image provider + 1 TTS tiếng Việt (credential trong kho OS, budget) | M | 1 video thật, chi phí ghi lại; cần Dung duyệt chi phí trước khi chạy |
| B10 | Tạo lại scene / sửa narration / render lại; version history | M | Thay 1 scene không đổi asset scene khác |
| B11 | UI Campaign Workspace + Video Production Workspace (viewer + sửa giới hạn) | M–L | Xem preview, QA, duyệt bản cuối trong app |
| B12 | Long profile | M | MP4 16:9 3–10 phút pass QA |

Không thuộc backlog đầu: Facebook (Phase 2), analytics, learning, clip AI, ComfyUI, worker từ xa.

---

## 13. Quyết định và câu hỏi cần Dung xác nhận

**Quyết định kiến trúc (mình có khuyến nghị):**
1. Pipeline tất định có bước LLM thay vì CEO giao việc tự do theo sơ đồ tổ chức.
2. MVP hình ảnh = ảnh tĩnh có chuyển động + voice + phụ đề; clip AI bật theo scene ở Phase 1c.
3. Duyệt từng bài đăng ở Phase 2; tự đăng theo policy để sau khi có dữ liệu.
4. Giữ SQLite, đĩa local, job runner tự viết; không thêm Redis/Celery/Temporal.

**Câu hỏi:**
5. Ngôn ngữ lời đọc và phụ đề: tiếng Việt? Có cần giọng nam/nữ cố định cho thương hiệu kênh?
6. TTS ưu tiên chất lượng (ElevenLabs, có timestamps) hay chi phí (Google Chirp 3 HD, có hạn mức miễn phí)?
7. Ngân sách trần mỗi video và mỗi tháng (USD)?
8. Đã có Facebook Page và app trên Meta for Developers chưa? Có Page thử nghiệm riêng không?
9. Dung đã kiểm tra chính sách Meta về nội dung AI / nội dung gốc / kiếm tiền cho Page chưa? Mục tiêu kênh là kiếm tiền từ Meta hay mục tiêu khác?
10. Nhạc nền: dùng thư viện miễn phí bản quyền do Dung chọn, hay sinh bằng AI?
11. P5 vẫn chờ nghiệm thu. Có nghiệm thu P5 trước khi bắt đầu Phase 1 không?

---

## 14. Sources

Truy cập 2026-11-06. **[P]** nguồn chính thức, **[C]** bên thứ ba. **[S]** = số liệu từ bản tóm tắt trang.

Repository: `quocdung2107/orchestra-studio` @ `45ac528`; file trích dẫn trong mục 2. Test: `uv run pytest` 170 passed (2026-11-06).

Meta:
- [P] Video publishing: https://developers.facebook.com/docs/video-api/guides/publishing (v25.0)
- [P] Reels publishing: https://developers.facebook.com/docs/video-api/guides/reels-publishing (v25.0)
- [P] Access levels: https://developers.facebook.com/docs/graph-api/overview/access-levels/
- [P] Pages API overview: https://developers.facebook.com/docs/pages-api/overview
- [P] Permissions: https://developers.facebook.com/docs/permissions
- [P] Long-lived tokens: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived
- [P] Error handling: https://developers.facebook.com/docs/graph-api/guides/error-handling
- [P] Video insights: https://developers.facebook.com/docs/graph-api/reference/video/video_insights/
- [P] Rate limiting: https://developers.facebook.com/docs/graph-api/overview/rate-limiting
- [P] Changelog: https://developers.facebook.com/docs/graph-api/changelog
- [P, chỉ đọc được metadata] AI labeling: https://www.meta.com/en-gb/help/artificial-intelligence/1783222608822690/
- [P, không đọc được: robots] Partner/Content Monetization Policies: https://www.facebook.com/business/help/1348682518563619 , https://www.facebook.com/business/help/1409263409529474
- [C] Unoriginal content (Vietnam News BizHub, 16/07/2025): https://bizhub.vietnamnews.vn/facebook-intensifies-crackdown-on-unoriginal-content-to-support-real-creators-post380520.html

Video / ảnh:
- [P] Gemini video & Omni: https://ai.google.dev/gemini-api/docs/video , https://ai.google.dev/gemini-api/docs/omni ; pricing: https://ai.google.dev/gemini-api/docs/pricing [S cho giá]
- [P] OpenAI video guide: https://developers.openai.com/api/docs/guides/video-generation [S]
- [P] Runway pricing: https://docs.dev.runwayml.com/guides/pricing/
- [P] Luma: https://docs.lumalabs.ai/ , https://lumalabs.ai/api/pricing
- [P] BFL: https://docs.bfl.ai/ , https://bfl.ai/pricing
- [P] Wan2.1 T2V-1.3B: https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B ; LTX-Video: https://huggingface.co/Lightricks/LTX-Video
- [P, không đọc được nội dung] Kling developer: https://kling.ai/dev

Âm thanh / xử lý:
- [P] ElevenLabs: https://elevenlabs.io/docs/overview/models , https://elevenlabs.io/pricing/api , https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps , https://elevenlabs.io/music-terms
- [P] OpenAI TTS: https://developers.openai.com/api/docs/guides/text-to-speech [S]
- [P] Google Cloud TTS: https://cloud.google.com/text-to-speech/pricing , https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd , https://docs.cloud.google.com/text-to-speech/quotas
- [P] Stability AI: https://platform.stability.ai/ , https://docs.stability.ai/pricing
- [P] Suno: https://suno.com/pricing (không thấy API)
- [P] ComfyUI: https://docs.comfy.org/development/comfyui-server/comms_routes.md , https://github.com/Comfy-Org/ComfyUI
- [P] FFmpeg legal: https://ffmpeg.org/legal.html
- [P] Whisper: https://github.com/openai/whisper ; faster-whisper: https://github.com/SYSTRAN/faster-whisper

Chưa xác minh (giới hạn): chính sách AI/nội dung gốc/kiếm tiền của Meta từ nguồn gốc; `scheduled_publish_time`; giới hạn kích thước video thường; Page insights (follower growth); giá Kling trực tiếp, giá FLUX từng model, giá gpt-image theo ảnh; rate limit của các provider media; điều khoản sở hữu đầu ra của Runway/Luma/Gemini; giọng vi-VN của Google Standard/WaveNet; chất lượng thực tế của mọi provider với nội dung tiếng Việt (chưa chạy thử vì cần chi phí).
