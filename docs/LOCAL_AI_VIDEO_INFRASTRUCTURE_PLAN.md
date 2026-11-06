# Local-First AI Video Production Infrastructure Plan

**Ngày:** 2026-11-06 · **Loại:** nghiên cứu + lập kế hoạch. Không sửa code, không cài phần mềm, không tải model, không gọi API trả phí.
**Trạng thái:** chờ Dung duyệt.
**Tài liệu đi kèm:** [`LOCAL_AI_BENCHMARK_PLAN.md`](LOCAL_AI_BENCHMARK_PLAN.md) (script kiểm kê phần cứng + benchmark) · [`AI_VIDEO_PRODUCTION_COMPANY_AUDIT.md`](AI_VIDEO_PRODUCTION_COMPANY_AUDIT.md) (audit sản phẩm cùng ngày).

Nhãn bằng chứng:
- **[GH]** README/LICENSE đọc trực tiếp từ GitHub hôm nay · **[HF]** model card Hugging Face đọc hôm nay · **[Meta]** metadata repo (license, lần push cuối, sao) lấy qua GitHub API hôm nay
- **[Đo]** số đo trên máy Dung (chỉ có từ ngày 05/11)
- **[Tác giả]** số liệu do tác giả công bố, **không phải** đo trên máy Dung
- **[Giả định]** suy luận chưa kiểm chứng · **[Đề xuất]** khuyến nghị kiến trúc · **[Câu hỏi]** cần Dung quyết định

Giới hạn của nghiên cứu này:
- Mình không truy cập được máy của Dung hôm nay, nên mục 2 dựa trên lần đo ngày 05/11 cộng một script để Dung chạy.
- Không có số benchmark nào đo trên máy Dung cho media.
- Ngày "push cuối" là lần push gần nhất lên GitHub, không phải ngày release.

---

## 1. Executive Summary

### Kết luận chính

1. **Máy hiện tại là laptop, và nút thắt lớn nhất là RAM 8 GB chứ không phải GPU.** Ryzen 5 5600H + RTX 3050 Laptop 4 GB là cấu hình laptop. GPU laptop không thay được. Với ~7,4 GB RAM thấy được, các kỹ thuật "chạy model lớn trên VRAM nhỏ" (offload sang RAM) gần như không dùng được, vì offload cần nhiều RAM. [Đo 05/11][Giả định: 7,4 GB thấy được thường là 8 GB vật lý, trừ phần GPU tích hợp giữ lại]
2. **Máy hiện tại làm được Mode 1:** TTS tiếng Việt chạy CPU, ảnh tĩnh nhẹ, phụ đề, FFmpeg render 1080p, và LLM nhỏ. **Không làm được video AI ở mức dùng để sản xuất.**
3. **TTS tiếng Việt local đã đủ tốt để thử nghiêm túc**, giấy phép thương mại rõ:
   - **VieNeu-TTS v3 Turbo** (Apache-2.0): clone giọng local, 25 giọng mẫu ba miền, có API tương thích OpenAI.
   - **ZeroTTS** (MIT): chạy nhanh hơn thời gian thực trên CPU, có sẵn chuẩn hóa ngày tháng và số tiếng Việt.

   Cả hai đều là số liệu tác giả tự công bố, cần benchmark trên máy Dung.
4. **Nâng cấp có lợi nhất và rẻ nhất trước tiên là RAM** (lên 32 GB, nếu laptop có khe rời). Nó mở khóa ảnh local tốt hơn (FLUX.2 [klein] 4B, Qwen-Image 4-bit) và cho phép chạy LLM, TTS, ComfyUI mà không phải tắt bật liên tục. Muốn có video AI local thực sự thì cần **một desktop mới với GPU ≥ 16 GB và RAM 64 GB**, vì laptop không nâng GPU được.
5. **Không fork dự án lớn nào.**
   - ComfyUI chạy riêng, Orchestra gọi qua HTTP API.
   - TTS chạy như tiến trình riêng.
   - FFmpeg là subprocess.
   - "Local AI Media Gateway" là một **module trong backend hiện có**, không phải server mới.
6. **LLM là chỗ nên chấp nhận trả phí nhỏ.** qwen3:4b local chạy được (27 tok/s [Đo]), nhưng chất lượng kịch bản tiếng Việt chưa được đo. Một kịch bản bằng Claude ước tính chỉ vài cent. Đề xuất dùng cloud cho bước viết kịch bản và local cho bước rẻ. Benchmark sẽ quyết định. [Giả định][Câu hỏi]

### Năm việc Dung cần biết ngay

| | |
|---|---|
| PC hiện tại làm được | TTS tiếng Việt (CPU), phụ đề, render FFmpeg 1080p, ảnh SD 1.5 hoặc ảnh 4B dạng lượng tử (chậm, chưa đo), LLM 4B |
| Nâng cấp tối thiểu | RAM 32 GB cho laptop (nếu có khe), khoảng vài triệu đồng [Giả định về giá]; một SSD NVMe 1–2 TB cho model và media |
| Cấu hình nên có cho video AI | Desktop: GPU NVIDIA 16 GB, RAM 64 GB, NVMe 2 TB, PSU 750–850 W |
| Cấu hình lý tưởng | Desktop: GPU 24–32 GB, RAM 128 GB, NVMe 4 TB, PSU 1000 W+ |
| Repo đáng tích hợp trực tiếp | ComfyUI (+ ComfyUI-GGUF, Nunchaku), VieNeu-TTS, ZeroTTS, faster-whisper, FFmpeg, Ollama (đã có) |

---

## 2. Actual PC Hardware Inventory

### 2.1 Đã biết (đo ngày 2026-11-05)

| Thành phần | Giá trị | Nguồn |
|---|---|---|
| CPU | AMD Ryzen 5 5600H (6 nhân / 12 luồng, Zen 3, dòng H cho laptop) | [Đo 05/11]; số nhân/luồng theo thông số AMD [Giả định, chưa đọc lại hôm nay] |
| RAM thấy được | 7,4 GB; còn khoảng 1 GB trống khi app Orchestra đang mở | [Đo 05/11] |
| RAM vật lý | **Chưa xác định** (có thể là 8 GB) | Cần script |
| GPU | NVIDIA RTX 3050 Laptop, 4 GB VRAM | [Đo 05/11] |
| Loại máy | **Laptop** (suy ra từ CPU 5600H và GPU "Laptop") | [Giả định mạnh] |
| LLM local | Ollama 0.40.14, qwen3:4b Q4_K_M ≈ 27 tok/s | [Đo 05/11] |
| Hệ điều hành | Windows | [Đo] |
| Mainboard, ổ đĩa, dung lượng trống, driver/CUDA, số khe RAM, adapter sạc | **Chưa có** | Cần script |

### 2.2 Cần Dung chạy

Script PowerShell chỉ đọc ở [`LOCAL_AI_BENCHMARK_PLAN.md` §1](LOCAL_AI_BENCHMARK_PLAN.md). Nó ghi model máy, loại máy, từng thanh RAM, số khe và dung lượng tối đa, GPU qua `nvidia-smi`, ổ đĩa (NVMe/SATA), dung lượng trống và pagefile.

Các thứ cần tự kiểm tra: RAM hàn hay khe rời, khe M.2 trống, công suất adapter sạc.

**Mọi khuyến nghị nâng cấp ở mục 12 phụ thuộc vào kết quả này.**

---

## 3. Current Hardware Capability

Nhãn: **OK** chạy được thực tế · **Chậm** chạy được nhưng rất chậm · **Quant** chỉ chạy được nhờ lượng tử hóa/offload · **Không** không đủ phần cứng · **?** chưa có benchmark.

| Công việc | CPU (5600H) | RAM (~7,4 GB) | VRAM (4 GB) | Khả năng | Căn cứ |
|---|---|---|---|---|---|
| Vietnamese TTS | Đủ | Đủ nếu chạy một mình | Không cần | **OK?** | VieNeu: RTF ≈ 0,5–0,62 trên Core i5 thế hệ 12 [Tác giả]. ZeroTTS: RTF 0,5 trên CPU [Tác giả]. 5600H **không có VNNI**, nên VieNeu int8 không dùng được ("on older CPUs int8…" [GH]); còn fp32 hoặc Nano. |
| Voice cloning | Đủ | Đủ | Không cần | **OK?** | VieNeu clone trên CPU/ONNX [GH]. ZeroTTS không có bộ mã hóa giọng local [GH]. |
| Local LLM | Đủ | Chật | 4 GB | **OK (4B)** | qwen3:4b 27 tok/s [Đo]. Model 8B+ không vừa [Đo 05/11]. |
| Image generation | — | **Nút thắt** | 4 GB | **Quant / Chậm / ?** | SD 1.5 vừa VRAM [Giả định]. FLUX.2 [klein] 4B cần "~13GB VRAM" khi chạy gốc [HF], nên cần GGUF hoặc offload, mà offload cần RAM. ComfyUI tự nói "4GB vram + 8GB ram" chạy được model lớn [GH, tuyên bố của dự án, chưa kiểm chứng]. |
| Image editing / inpainting | — | Nút thắt | 4 GB | **Quant / ?** | Như trên |
| Video generation | — | **Không** | **Không** | **Không** (cho sản xuất) | FramePack tối thiểu 6 GB [GH]. Wan2.1 1.3B cần 8,19 GB [GH]. CogVideoX-2B "4GB minimum" chỉ khi dùng diffusers + CPU offload [GH], rất chậm và tốn RAM. |
| Speech recognition | Đủ | Đủ | Tùy chọn | **OK** | faster-whisper small int8 trên CPU dùng 1477 MB RAM [GH, đo trên máy khác] |
| FFmpeg rendering | Đủ | Đủ | NVENC | **OK?** | Ampere có NVENC H.264/HEVC [Giả định]; cần benchmark R1–R4 |
| Video upscaling | — | Nút thắt | 4 GB | **Chậm / ?** | Real-ESRGAN theo từng frame chạy được nhưng chậm [Giả định]. Không cần cho Mode 1 vì ảnh được upscale trước khi dựng. |

**Ràng buộc vận hành quan trọng:** không thể chạy cùng lúc Orchestra (Electron + FastAPI), Ollama qwen3:4b (~3 GB), TTS (~1–2 GB) và ComfyUI với 8 GB RAM. Resource scheduler (mục 14) phải **chạy tuần tự và giải phóng engine** sau mỗi bước. [Giả định có căn cứ]

---

## 4. Open-Source Repository Catalog

Metadata lấy qua GitHub API ngày 2026-11-06 [Meta]. "Push" là ngày push gần nhất.

| Repo | License code | Push | Phân loại | Vai trò |
|---|---|---|---|---|
| [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | GPL-3.0 | 2026-11-06 | **INTEGRATE** | Engine ảnh/video chạy riêng, gọi qua HTTP |
| [Comfy-Org/Comfy-Desktop](https://github.com/Comfy-Org/Comfy-Desktop) | NOASSERTION | 2026-11-06 | USE DIRECTLY (cài đặt) | Bộ cài ComfyUI chính thức cho Windows. `Comfy-Org/desktop` cũ đã archived. |
| [city96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | Apache-2.0 | 2026-01-12 | USE (custom node) | Chạy model DiT lượng tử GGUF trên VRAM thấp |
| [nunchux-ai/nunchaku](https://github.com/nunchux-ai/nunchaku) + ComfyUI-nunchaku | Apache-2.0 | 2026-09-06 | USE (Tier A thử, Tier B) | 4-bit SVDQuant cho FLUX/Qwen-Image; "as little as 3 GiB" với async offload [GH] |
| [Kosinkadink/ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) | GPL-3.0 | 2026-09-02 | USE (trong ComfyUI) | Đọc/ghi video trong workflow |
| [kijai/ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) | Apache-2.0 | 2026-05-24 | INTEGRATE (Tier B+) | Wan qua ComfyUI, có block swap |
| [kijai/ComfyUI-FramePackWrapper](https://github.com/kijai/ComfyUI-FramePackWrapper) | Apache-2.0 | 2026-01-13 | INTEGRATE (Tier B) | FramePack trong ComfyUI (có API, khác bản Gradio) |
| [Lightricks/ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) | NOASSERTION | 2026-10-20 | INTEGRATE (Tier C) | LTX-2 trong ComfyUI, ghi "32GB+ VRAM" [GH] |
| [lllyasviel/FramePack](https://github.com/lllyasviel/FramePack) | Apache-2.0 | 2025-10-16 | STUDY ONLY | App Gradio, không có API sạch. Dùng wrapper ComfyUI thay thế. |
| [deepbeepmeep/Wan2GP](https://github.com/deepbeepmeep/Wan2GP) | WanGP Community License 2.0 | (README đọc được) | STUDY ONLY | Rất tối ưu VRAM. License **cấm** "embed it in a paid product, or offer paid API" [GH]. App UI, không có API ổn định. |
| [ModelTC/LightX2V](https://github.com/ModelTC/LightX2V) | Apache-2.0 | 2026-11-06 | STUDY (Tier C) | Framework tăng tốc Wan/LTX/Hunyuan, có hướng dẫn Windows |
| [hao-ai-lab/FastVideo](https://github.com/hao-ai-lab/FastVideo) | Apache-2.0 | 2026-11-06 | STUDY | Tăng tốc suy luận video |
| [huggingface/diffusers](https://github.com/huggingface/diffusers) | Apache-2.0 | 2026-11-06 | REUSE (chỉ benchmark) | Dùng trong `bench/`, không đưa vào backend |
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | MIT | 2026-11-06 | **STUDY ONLY** | Xem mục 8 |
| [RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT) | MIT | 2025-02-10 | AVOID | Ít hoạt động, xoay quanh OpenAI, cần Docker |
| [FujiwaraChoki/MoneyPrinter](https://github.com/FujiwaraChoki/MoneyPrinter) | MIT | 2026-03-26 | AVOID | Bản gốc, đơn giản hơn bản Turbo |
| [pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) | Apache-2.0 | 2026-11-05 | **INTEGRATE** | TTS tiếng Việt chính |
| [bonelag/VieNeuTTS](https://github.com/bonelag/VieNeuTTS) | Apache-2.0 | 2026-09-18 | **AVOID** | **Đây là fork** (0 sao) của pnnbao97/VieNeu-TTS, mô tả còn ghi "24kHz" (bản cũ). Dùng repo gốc. |
| [zeroweight-ai/ZeroTTS](https://github.com/zeroweight-ai/ZeroTTS) | MIT | 2026-09-17 | **INTEGRATE** | TTS tiếng Việt thứ hai |
| [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | GPL-3.0 | 2026-11-02 | STUDY (fallback dự phòng) | Có giọng `vi_VN` [GH]. `rhasspy/piper` đã archived. |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | 2026-11-02 | **USE DIRECTLY** | ASR cho QA |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | BSD-2-Clause | 2026-10-22 | STUDY | Timestamp theo từ bằng alignment; nặng hơn cần thiết |
| [MahmoudAshraf97/ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner) | BSD-2-Clause | 2026-09-07 | REUSE (Phase 4) | Forced alignment, có ISO 639-3 `vie`. Giấy phép model MMS mặc định **chưa xác minh**. |
| [VinAIResearch/PhoWhisper](https://github.com/VinAIResearch/PhoWhisper) | BSD-3-Clause | 2024-11-12 | USE (ASR tiếng Việt) | Model `small` BSD-3 [HF] |
| [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | MIT | 2026-11-06 | ALTERNATIVE | ASR không cần Python |
| [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | MIT | 2026-10-22 | REUSE | Cắt khoảng lặng / VAD |
| [ace-step/ACE-Step-1.5](https://github.com/ace-step/ACE-Step-1.5) | MIT | 2026-10-11 | STUDY → thử Phase 4 | Nhạc local; xem mục 9 |
| [facebookresearch/audiocraft](https://github.com/facebookresearch/audiocraft) | MIT (code) | 2026-03-03 | **AVOID** | Weights MusicGen là **CC-BY-NC 4.0** [GH][HF] |
| [Stability-AI/stable-audio-tools](https://github.com/Stability-AI/stable-audio-tools) | MIT (code) | 2026-11-01 | AVOID tới khi đọc license | Weights dùng Stability Community License [HF] |
| [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | NOASSERTION | 2026-11-06 | REUSE (tùy chọn) | Khử ồn audio tham chiếu; license cần đọc |
| [adefossez/demucs](https://github.com/adefossez/demucs) | MIT | 2026-10-26 | STUDY | Tách nguồn âm. Bản facebookresearch đã archived. |
| [danielgatis/rembg](https://github.com/danielgatis/rembg) | MIT | 2026-11-06 | REUSE | Xóa nền ảnh |
| [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | MIT | 2026-10-25 | ALTERNATIVE | Xóa nền chất lượng cao |
| [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | BSD-3-Clause | 2024-08-06 | REUSE | Upscale ảnh (ít bảo trì) |
| [Fannovel16/comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) | Apache-2.0 | 2026-10-11 | USE (Phase 2) | Tiền xử lý ControlNet |
| [cubiq/ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) | GPL-3.0 | 2025-04-14 | STUDY | Ít cập nhật; với FLUX.2 [klein] thì dùng multi-reference sẵn có |
| [mltframework/mlt](https://github.com/mltframework/mlt) / [shotcut](https://github.com/mltframework/shotcut) / [KDE/kdenlive](https://github.com/KDE/kdenlive) | LGPL-2.1 / GPL-3.0 / GPL-3.0 | 2026-11 | STUDY | Có thể xuất dự án để sửa tay (Phase 4+) |
| [Zulko/moviepy](https://github.com/Zulko/moviepy) | MIT | 2026-08-26 | AVOID (cho render chính) | Tự ghi "slower than using ffmpeg directly" [GH] |
| [mifi/editly](https://github.com/mifi/editly) | MIT | 2025-05-12 | STUDY | Spec timeline JSON5 đáng học |
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | Remotion License | 2026-11-06 | AVOID (hiện tại) | "requires obtaining a company license in some cases" [GH]; render qua Chromium, nặng cho 8 GB RAM |
| [ollama/ollama](https://github.com/ollama/ollama) | MIT | 2026-11-06 | KEEP (đã tích hợp) | LLM local |
| [rany2/edge-tts](https://github.com/rany2/edge-tts) | NOASSERTION | 2026-10-14 | **AVOID** | Dùng dịch vụ đọc online của Microsoft Edge một cách không chính thức. Không phải API có điều khoản cho sản xuất. |

---

## 5. Vietnamese TTS Comparison

### 5.1 Bảng so sánh

| | VieNeu-TTS v3 Turbo | ZeroTTS | viXTTS / XTTS-v2 | F5-TTS (+ Vietnamese) | Piper vi_VN | GPT-SoVITS | OmniVoice |
|---|---|---|---|---|---|---|---|
| Repo | pnnbao97/VieNeu-TTS | zeroweight-ai/ZeroTTS | thinhlpg/vixtts-demo | SWivid/F5-TTS, nguyenthienhy/F5-TTS-Vietnamese | OHF-Voice/piper1-gpl | RVC-Boss/GPT-SoVITS | k2-fsa/OmniVoice |
| License weights | **Apache-2.0** [HF]; card: "may be used in commercial and monetized content" | **MIT** [HF][GH] | **Coqui Public Model License** [HF] (non-commercial; Coqui đã đóng cửa [Giả định]) | Base **CC-BY-NC** [GH]; bản Việt: code MIT, weights **chưa xác minh** | Code GPL-3.0; license từng giọng chưa xác minh | MIT code; **không hỗ trợ tiếng Việt** (chỉ EN/JA/KO/Cantonese/ZH [GH]) | Apache-2.0 [Meta] |
| Thương mại | Có | Có | **Không** | **Không** (base) / ? | ? | — | Có [Meta], chưa đọc card |
| Giọng ba miền | 25 giọng mẫu Bắc/Trung/Nam [GH] | 8 giọng mẫu, có thẻ giới tính/tuổi [GH] | Theo mẫu clone | Theo mẫu | Ít giọng | — | Theo mẫu |
| Voice cloning | Có, local; tham chiếu tự cắt ≤ 8 giây và khử ồn [GH] | **Không có local**: "the voice encoder is not published"; phải tải mẫu lên platform.zeroweight.ai [GH] | Có | Có (< 10 giây) | Không | Có | Có |
| Cảm xúc | Thẻ `[cười]`, `[thở dài]` (thử nghiệm) [GH] | Qua giọng mẫu | Hạn chế | Theo mẫu | Không | — | ? |
| Đọc dài | SDK chia đoạn; chế độ podcast [GH] | Phải chia đoạn (`chunk_text`, ≤ 15 giây) [GH] | Kém với câu < 10 từ [GH] | Phải sửa hàm chunk [GH] | Được | — | ? |
| CPU | RTF ≈ 0,5–0,62 fp32 (Core i5 thế hệ 12); int8 cần VNNI [Tác giả] | RTF 0,50, TTFA ~70 ms [Tác giả] | RTF 0,71–0,73 [theo bảng của ZeroTTS] | Chậm [Giả định] | Rất nhanh [Giả định] | — | RTF 6,12× [theo bảng của ZeroTTS] |
| GPU | CUDA ≥ 12.8; RTF 0,02 batched trên RTX 3060 [Tác giả] | Không cần | ≥ 4 GB VRAM, 16 GB RAM [GH] | Cần | Không cần | — | Cần |
| API local | **OpenAI-compatible** `POST /v1/audio/speech` [GH] | Python/CLI/Gradio; không có HTTP API chính thức | Gradio | Gradio/CLI | CLI/HTTP | WebUI/API | Python |
| Windows | Có bộ cài riêng [GH] | pip, onnxruntime [GH] | **Chỉ Ubuntu/WSL** [GH] | Có | Có | Có | ? |
| Chuẩn hóa số/ngày | Chưa thấy ghi rõ | **Có** `normalize_vi_text` [GH] | Không | Không | ? | — | ? |
| Độ ổn định dự án | Rất hoạt động (push 05/11); v4 chuyển sang đóng, "v3 Turbo remains the latest open-source" [GH] | Hoạt động (09/2026), 325 sao | "not being actively maintained" [GH] | Hoạt động / bản Việt 04/2025 | Hoạt động | — | Hoạt động |
| Kết luận | **Primary** | **Secondary** | AVOID | AVOID | CPU fallback cuối cùng | AVOID (vi) | Theo dõi (GPU desktop) |

Ghi chú về benchmark: bảng của ZeroTTS (WER 1,03% so với viXTTS 18,4%) do **chính ZeroTTS** công bố trên bộ dữ liệu của họ, và **không so với VieNeu** [GH]. Số RTF của VieNeu cũng do tác giả tự đo. Chưa có so sánh độc lập giữa hai bên. Vì vậy cần benchmark ở [`LOCAL_AI_BENCHMARK_PLAN.md` §3](LOCAL_AI_BENCHMARK_PLAN.md).

### 5.2 Lựa chọn

| Vai trò | Chọn | Lý do |
|---|---|---|
| Primary Vietnamese TTS | **VieNeu-TTS v3 Turbo** (CPU fp32 trên máy hiện tại; GPU trên desktop sau này) | Apache, cho phép thương mại, clone local, giọng ba miền, có API sẵn, có bộ cài Windows |
| Secondary | **ZeroTTS** | MIT, CPU nhanh, có chuẩn hóa tiếng Việt, ít phụ thuộc (không cần torch) |
| CPU fallback | VieNeu v3 Nano (nhanh hơn ~3×, chất lượng thấp hơn [GH]) hoặc ZeroTTS int8 | Khi máy quá tải |
| Voice cloning | VieNeu (local) | ZeroTTS buộc tải giọng lên dịch vụ ngoài |
| Chốt cuối | Sau TTS benchmark | Có thể đảo primary/secondary nếu ZeroTTS thắng rõ về phát âm |

### 5.3 Thiết kế giọng đọc cho kênh [Đề xuất]

- **Voice profile** là một asset có version: `voice_id`, engine, version engine, file tham chiếu (sha256) hoặc tên giọng mẫu, tham số (speed, seed, temperature, cfg), **giấy đồng ý của người có giọng** (nếu clone), ngày tạo. Mỗi đoạn audio lưu `voice_profile_version` đã dùng.
- **Nhất quán**: cố định seed, tham số và engine version cho cả kênh. ZeroTTS ghi rằng `voice=None` thì "*not* stable across runs" [GH], nên luôn chỉ định giọng.
- **Số, ngày, tên riêng**: một bước chuẩn hóa riêng, chạy trước TTS và có từ điển phát âm của kênh (ví dụ "AI" đọc là "ây ai", "GPU" đọc là "gi pi u"). Văn bản sau chuẩn hóa được lưu lại để tạo lại đúng y như cũ.
- **Chia đoạn**: theo câu, mỗi đoạn tối đa khoảng 15 giây (khuyến nghị của ZeroTTS [GH]). Đoạn cũng là **đơn vị phụ đề** và **đơn vị tạo lại**.
- **Tốc độ và khoảng nghỉ**: tham số `speed` của engine (VieNeu có [GH]), cộng khoảng lặng chèn giữa đoạn do renderer quản lý (không nhờ model).
- **Tạo lại một đoạn**: chỉ sinh lại đoạn đó, cùng profile và seed. Renderer nối lại, các đoạn khác giữ nguyên file.
- **Timestamp phụ đề**: vì sinh theo đoạn, **thời lượng từng đoạn là chính xác**, nên phụ đề cấp câu có thời gian đúng mà không cần ASR. Nếu muốn phụ đề nhảy theo từng từ thì làm ở Phase 4 bằng forced alignment.

### 5.4 API contract đề xuất

```python
class TtsRequest(BaseModel):
    text: str                    # đã chuẩn hóa
    voice_profile_id: str
    voice_profile_version: int
    speed: float = 1.0
    seed: int
    output_format: Literal["wav"] = "wav"   # 48 kHz mono PCM

class TtsResult(BaseModel):
    asset_id: str                # file wav trong media store
    duration_s: float
    sample_rate: int
    engine: str                  # "vieneu-v3-turbo@<version>"
    rtf: float
    normalized_text: str
    warnings: list[str]          # ví dụ: "trailing silence 0.8s trimmed"

class TtsProvider(Protocol):
    meta: ProviderMeta           # id, version, capabilities, hardware, license
    async def synthesize(self, req: TtsRequest, job: JobContext) -> TtsResult: ...
```

---

## 6. Local Image Model Comparison

| Model | Params | License weights | VRAM (điều kiện) | Chữ trên ảnh | Edit / tham chiếu | Ghi chú |
|---|---|---|---|---|---|---|
| SD 1.5 (và fine-tune) | ~0,9B [Giả định] | CreativeML OpenRAIL-M (cho phép thương mại, có danh sách cấm sử dụng) [Giả định, chưa đọc lại] | ~2–4 GB fp16 512px [Giả định] | Kém | ControlNet, IP-Adapter | Chạy được trên 4 GB. Chất lượng cũ. License của từng fine-tune phải kiểm tra riêng. |
| SDXL base 1.0 | ~3,5B [Giả định] | openrail++ [HF]; card ghi "intended for research purposes only" ở phần Direct Use | Cần `--lowvram` trên 4 GB; checkpoint ~6,5 GB vượt RAM trống [Giả định] | Trung bình | Rất nhiều LoRA | Trên máy hiện tại khó |
| FLUX.1 [schnell] | 12B | **Apache-2.0** [HF] | Gốc lớn; GGUF Q4 qua ComfyUI-GGUF [GH] | Tốt | Hạn chế | Thương mại OK; nặng RAM |
| FLUX.1 [dev] | 12B | **Non-commercial** [HF] | — | — | — | **AVOID** |
| **FLUX.2 [klein] 4B** | 4B | **Apache-2.0** [GH][HF] | "~13GB VRAM" gốc [HF]; 4 GB cần GGUF/offload [Giả định] | Tốt [Tác giả] | **Có edit + multi-reference** [GH], giúp giữ nhân vật | Ứng viên chính cho Tier A+ / B |
| FLUX.2 [klein] 9B, FLUX.2 [dev] | 9B / 32B | **FLUX Non-Commercial** [GH] | — | — | — | **AVOID** |
| Qwen-Image / Qwen-Image-Edit-2511 | 20B | **Apache-2.0** [HF] | Nunchaku 4-bit + async offload: "as little as 3 GiB" [GH] (RAM cần lớn) | **Rất tốt** [Tác giả] | Edit, nhiều ảnh | Tier B (cần RAM 32 GB+) |

Hỗ trợ ảnh:
- **Background removal**: rembg / BiRefNet (MIT).
- **Upscale**: Real-ESRGAN (BSD-3).
- **Inpainting/outpainting**: FLUX.2 [klein] edit hoặc Qwen-Image-Edit; trên 4 GB thì dùng SD 1.5 inpaint.
- **Giữ nhân vật**: Mode 1 dùng một bộ "character sheet" cố định cộng seed và prompt khóa. Tier B dùng multi-reference của FLUX.2 [klein] hoặc Qwen-Image-Edit. Huấn luyện LoRA nhân vật để sau.

### Theo tầng GPU [Đề xuất; mọi mức cần benchmark]

| VRAM | Model nên dùng |
|---|---|
| 4 GB (máy hiện tại, RAM 8 GB) | SD 1.5 fine-tune có license rõ; thử FLUX.2 [klein] 4B GGUF Q4. **Hoặc** dùng ảnh cloud giá $0,02–0,04/ảnh (xem audit cùng ngày) |
| 4 GB + RAM 32 GB | FLUX.2 [klein] 4B GGUF; Qwen-Image Nunchaku 4-bit (thử) |
| 8 GB | FLUX.2 [klein] 4B Q8/fp8; Qwen-Image Nunchaku |
| 12 GB | FLUX.2 [klein] 4B gần gốc; Qwen-Image 4-bit thoải mái |
| 16 GB | FLUX.2 [klein] 4B gốc (~13 GB [HF]); Qwen-Image-Edit 4-bit |
| 24 GB | Qwen-Image fp8; huấn luyện LoRA |

---

## 7. Local Video Model Comparison

### 7.1 Bảng (ghi rõ điều kiện đo)

| Model | Params | License weights | VRAM (điều kiện, nguồn) | Độ phân giải / fps | Độ dài | T2V / I2V / V2V | Windows |
|---|---|---|---|---|---|---|---|
| Wan2.1 T2V-1.3B | 1,3B | Apache-2.0 [Meta] | **8,19 GB**, gốc, 480p; RTX 4090 ~4 phút / 5 giây video [GH] | 480p (720p kém ổn định [GH]) | ~5 giây | T2V (+VACE) | Qua ComfyUI |
| Wan2.1 14B (T2V/I2V/FLF2V) | 14B | Apache-2.0 | Lớn; với WanVideoWrapper block swap: "~16GB used with 20/40 blocks offloaded" [GH] | 480p/720p | ~5 giây | T2V, I2V, FLF2V | ComfyUI |
| **Wan2.2 TI2V-5B** | 5B | Apache-2.0 [HF] | **≥ 24 GB** gốc, 720p, ví dụ RTX 4090 [GH][HF]; ít hơn khi offload hoặc lượng tử [Giả định] | 720p 24 fps [GH] | ~5 giây | T2V + I2V | ComfyUI |
| Wan2.2 A14B (T2V/I2V) | 27B MoE (14B active) | Apache-2.0 | **≥ 80 GB** gốc 720p với offload [GH] | 480p/720p | ~5 giây | T2V, I2V | ComfyUI + quant |
| FramePack (HunyuanVideo 13B) | 13B | Apache-2.0 code; weights theo HunyuanVideo [Giả định] | **≥ 6 GB**, 60 giây 30 fps [GH]. RTX 4090 1,5–2,5 s/frame; laptop 3060/3070ti chậm hơn 4–8 lần [Tác giả] | Theo ảnh đầu vào | **Tới 60 giây** | I2V | Có bản Windows 1-click [GH] |
| LTX-Video 0.9.x (2B/13B) | 2B / 13B | OpenRail-M (cho bản 2B 0.9.5) [GH] | Cộng đồng: "720x480x121 in under a minute on RTX 4060 (8GB)" [GH, dẫn Reddit] | Mặc định 1216×704 30 fps [GH] | Tới 60 giây (0.9.8 distilled) [GH] | T2V, I2V | ComfyUI |
| LTX-2 / 2.3 / 2.5 | lớn | **LTX-2 / LTX-2.x Community License** [GH][HF] (chưa đọc điều khoản) | ComfyUI-LTXVideo ghi "32GB+ VRAM" [GH]; có `fp8-cast` + offload [GH] | Tới 4K, 50 fps [GH] | ~10 giây, có **audio đồng bộ** [GH] | T2V, I2V, A+V | Windows có fallback VAE [GH] |
| HunyuanVideo-1.5 | 8,3B | tencent-hunyuan-community [HF] (điều khoản vùng lãnh thổ chưa xác minh) | **14 GB tối thiểu, có offload** [GH]; Wan2GP nói 6 GB [GH] | 480p/720p + SR 1080p [GH] | ~5 giây | T2V, I2V | ComfyUI |
| CogVideoX-2B / 5B | 2B / 5B | 2B Apache-2.0 [GH]; 5B riêng | 2B: "diffusers FP16: 4GB minimum*" với CPU offload [GH]; A100 ~90 giây / clip [GH] | 720×480 | 6 giây | T2V (5B có I2V) | diffusers |
| Stable Video Diffusion | — | Stability license | — | 576×1024 | ~2–4 giây | I2V | **Không khuyến nghị** (cũ, license hạn chế) |

Lưu ý: mỗi số VRAM ở bảng trên đi kèm điều kiện đo riêng (gốc, offload, quant, độ phân giải). **Không so sánh trực tiếp giữa các dòng.**

### 7.2 Nhận định

- **GPU hiện tại (4 GB, RAM 8 GB): không có model video nào dùng được cho sản xuất.** CogVideoX-2B "chạy được về mặt kỹ thuật" nhờ CPU offload, nhưng cần nhiều RAM và rất chậm. **Phương án thay thế** là chuyển động bằng FFmpeg (Ken Burns, parallax giả, overlay), cộng **clip AI cloud tùy chọn** cho vài cảnh quan trọng ($0,05–0,10/giây theo audit cùng ngày) nếu Dung duyệt chi phí.
- FramePack hấp dẫn nhất về tỉ lệ VRAM/độ dài (I2V tới 60 giây với 6 GB), nhưng **RAM hệ thống thực tế cần cho offload chưa có số**, và tốc độ trên laptop chậm hơn 4–8 lần so với 4090 [Tác giả].

### 7.3 Chọn theo tầng [Đề xuất]

| Tầng | Model | Dùng cho |
|---|---|---|
| 1. GPU hiện tại | **Không dùng video AI**. Motion từ ảnh bằng FFmpeg. | Mode 1 |
| 2. 12 GB + RAM 32–64 GB | FramePack (ComfyUI wrapper) cho I2V; LTX-Video 2B/13B distilled fp8; Wan2.1 1.3B | I2V cảnh quan trọng, 480–720p |
| 3. 16 GB + RAM 64 GB | Wan2.2 TI2V-5B (offload/quant); HunyuanVideo-1.5 480p I2V step-distilled; Wan 14B GGUF + block swap | I2V/T2V 720p |
| 4. 24 GB | Wan2.2 TI2V-5B gốc 720p; Wan 14B fp8 | Chất lượng cao |
| 5. Workstation 32 GB+ | LTX-2.x (A+V đồng bộ), Wan2.2 A14B quant | Chất lượng cao nhất local |

---

## 8. Video Workflow Repository Comparison

| Câu hỏi | MoneyPrinterTurbo | ComfyUI (+VHS, WanVideoWrapper, LTXVideo, FramePackWrapper) | FramePack (bản gốc) | Wan2GP | ShortGPT |
|---|---|---|---|---|---|
| 1. Giải quyết gì | Chủ đề → kịch bản LLM → TTS → footage stock (Pexels/Pixabay) hoặc AI video API → phụ đề → MoviePy → MP4 [GH] | Engine node graph cho ảnh/video/audio, queue, API | I2V dài trên VRAM thấp | App tổng hợp hàng chục model, rất tối ưu VRAM | Tự động hóa short (OpenAI + EdgeTTS + Pexels) |
| 2. Có thực sự local? | **Một phần**: LLM, TTS và footage mặc định đều ở cloud | Có ("Runs fully offline", `--offline` [GH]) | Có | Có | Không hẳn |
| 3. Cần API trả phí? | LLM có (có thể dùng Ollama [Giả định]); nhiều tích hợp tài trợ | Không (API nodes trả phí là tùy chọn) | Không | Không | OpenAI |
| 4. Tiếng Việt | TTS qua Edge TTS / dịch vụ cloud | Không liên quan | Không liên quan | Có TTS đa ngôn ngữ (chưa kiểm vi) | EdgeTTS |
| 5. Windows | Có (gói 1-click) | Có (Desktop/portable) | Có | Có (Manager.exe) | Docker |
| 6. GPU hiện tại | Không cần GPU | Ảnh nhẹ: có; video: không | Không (≥ 6 GB) | "select models as little as 4 GB" [GH], không nói model nào | — |
| 7. API/CLI | WebUI, **API**, CLI [GH] | **HTTP + WebSocket API** | Gradio | Gradio | Gradio |
| 8. Gọi từ Orchestra | Được, nhưng trùng chức năng với Orchestra | **Có**, qua workflow JSON đã lưu version | Khó | Không nên | Không nên |
| 9. Tái sử dụng hay fork | Học cách chia đoạn, phụ đề, cấu hình. **Không fork.** | Chạy riêng, không fork | Dùng qua wrapper ComfyUI | Học kỹ thuật VRAM | — |
| 10. License tích hợp | MIT | GPL-3.0 (chạy tiến trình riêng, giao tiếp HTTP, nên không ràng buộc code Orchestra [Giả định pháp lý thông thường]) | Apache-2.0 | **Cấm nhúng vào sản phẩm trả phí / API trả phí** [GH] | MIT |
| 11. Bảo trì | Rất hoạt động, nhưng README đầy quảng cáo nhà tài trợ | Rất hoạt động | Push cuối 10/2025 | Rất hoạt động | Push cuối 02/2025 |
| 12. Rủi ro | Edge TTS không chính thức; tự đăng TikTok/IG/YouTube (cách làm chưa xác minh); nhiều SDK bên thứ ba | Custom node của bên thứ ba **chạy code tùy ý**, nên cần danh sách node cho phép và cố định phiên bản | Tải > 30 GB model [GH] | License | Bỏ hoang |
| **Phân loại** | **STUDY ONLY** | **INTEGRATE** | STUDY ONLY | STUDY ONLY | AVOID |

Nhận xét: **không có repo nào làm đúng việc của Orchestra** (đa bước, có contract, duyệt, phiên bản, đăng Facebook). MoneyPrinterTurbo gần nhất với Mode 1. Nhưng nếu fork thì Orchestra sẽ phải gánh MoviePy, Edge TTS, footage stock và chuỗi tích hợp tài trợ, trong khi phần thực sự cần chỉ khoảng 300–500 dòng điều phối FFmpeg và TTS. [Giả định về quy mô]

---

## 9. Audio / Music / Subtitle Tools

### 9.1 Audio

| Việc | Đề xuất | License | Ghi chú |
|---|---|---|---|
| Chuẩn hóa âm lượng | FFmpeg `loudnorm` (EBU R128) | FFmpeg LGPL/GPL | Mức LUFS mục tiêu cho Facebook **chưa xác minh**. Đặt cấu hình, mặc định khoảng −14 LUFS [Giả định]. |
| Ducking nhạc dưới giọng | FFmpeg `sidechaincompress` | — | Tham số cố định trong preset |
| Cắt khoảng lặng thừa | FFmpeg `silenceremove` hoặc silero-vad (MIT) | MIT | Chạy sau mỗi đoạn TTS |
| Khử ồn file tham chiếu | VieNeu tự làm khi clone [GH]; DeepFilterNet tùy chọn | Cần đọc | Chỉ cho giọng tham chiếu |
| Tách giọng/nhạc | demucs (MIT) | MIT | Ít cần |

### 9.2 Nhạc

| Lựa chọn | License | Kết luận |
|---|---|---|
| **Thư viện nhạc có giấy phép rõ** (Dung chọn; lưu file license, nguồn, ngày tải cho từng bài) | Theo thư viện | **Mặc định cho Mode 1** |
| ACE-Step 1.5 | Code MIT [Meta]; weights **MIT**; card ghi "You can strictly use the generated music for commercial purposes" và "Runs locally with less than 4GB of VRAM" [HF]; bảng VRAM ≤ 6 GB: "2B turbo, LM disabled… INT8 + full CPU offload" [GH] | **Thử ở Phase 4.** Rủi ro chưa rõ: nguồn dữ liệu huấn luyện, và nhạc AI có thể bị hệ thống bản quyền của nền tảng nhận nhầm. |
| MusicGen (audiocraft) | Weights **CC-BY-NC 4.0** [GH][HF] | **AVOID** |
| Stable Audio Open (1.0 / small) | Stability AI Community License; card: "For commercial use, please refer to stability.ai/license" [HF] | AVOID tới khi đọc điều khoản |
| Suno | Không có API chính thức (audit cùng ngày) | AVOID |

### 9.3 ASR và phụ đề

| Việc | Đề xuất | Căn cứ |
|---|---|---|
| Thời gian phụ đề | **Lấy từ thời lượng từng đoạn TTS** (không cần ASR) | Mục 5.3 |
| Chia dòng | Theo profile: short ≤ 24 ký tự/dòng, long ≤ 42 ký tự/dòng, tối đa 2 dòng, ngắt tại dấu câu/ranh giới cụm từ | [Đề xuất] |
| QA lời đọc | faster-whisper `small` int8 CPU (~1,5 GB RAM [GH]) **hoặc** PhoWhisper-small (BSD-3, fine-tune tiếng Việt; WER công bố 11,08 trên một bộ test [GH]) | Benchmark §7 chọn |
| Phụ đề theo từ (karaoke) | Phase 4: ctc-forced-aligner (`vie`) hoặc whisperX | License model align chưa xác minh |
| Chuẩn hóa / dấu câu | Dùng lại bộ chuẩn hóa của ZeroTTS (dựa trên soe-vinorm, MIT [GH]) cho cả TTS và so khớp WER | [GH] |
| Định dạng | Xuất **SRT** (đăng kèm) và **ASS** (đốt vào hình, có style) | [Đề xuất] |
| Font tiếng Việt | Font OFL hỗ trợ đầy đủ dấu (ví dụ Be Vietnam Pro, Noto Sans), nhúng vào thư mục font của renderer, không phụ thuộc font hệ thống | License OFL [Giả định, cần đọc lại] |

Không dùng `large-v3` mặc định: trên CPU 8 GB RAM sẽ chậm và tốn bộ nhớ. Chỉ dùng model nhỏ để QA, vì đã biết trước văn bản. [Đề xuất]

---

## 10. Rendering Tools

| Tiêu chí | **FFmpeg CLI + timeline JSON riêng** | MoviePy 2 | Remotion | MLT (melt) / Kdenlive / Shotcut | editly |
|---|---|---|---|---|---|
| Điều khiển bằng code | Có | Có (Python) | Có (React) | XML | JSON5 |
| Tái tạo chính xác | Cao (lệnh + phiên bản cố định) | Trung bình | Cao | Cao | Cao |
| Tốc độ | Nhanh nhất | Chậm hơn FFmpeg [GH] | Chậm (Chromium) | Nhanh | Nhanh (stream) |
| Bộ nhớ | Thấp | Trung bình | Cao | Thấp | Trung bình |
| License | LGPL; GPL nếu build có x264 | MIT | Đặc biệt / có thể cần license công ty [GH] | LGPL/GPL | MIT |
| Phụ thuộc mới | Một binary | Python | Node + Chromium | Binary | Node |
| Kết luận | **CHỌN** | Không | Không (hiện tại) | Phase 4+: xuất file dự án để sửa tay | Học spec |

### Timeline schema đề xuất (rút gọn)

```json
{
  "version": 1,
  "profile": "short_reel",
  "canvas": {"w": 1080, "h": 1920, "fps": 30, "bg": "#000000"},
  "scenes": [
    {
      "id": "s03", "start": 7.2, "duration": 5.4,
      "visual": {"asset": "ast_img_91", "kind": "image",
                 "fit": "cover", "crop": null,
                 "motion": {"type": "kenburns", "from": [1.0, 0.5, 0.5], "to": [1.12, 0.55, 0.45], "ease": "inOutSine"},
                 "color": {"brightness": 0, "contrast": 1.05, "saturation": 1.0}},
      "transition_in": {"type": "fade", "duration": 0.3},
      "voice": {"asset": "ast_vo_s03", "offset": 0.1},
      "subtitle_cues": [{"t0": 7.3, "t1": 9.9, "text": "Mặt Trời lớn gấp 109 lần Trái Đất"}]
    }
  ],
  "audio": {
    "music": {"asset": "ast_music_2", "gain_db": -18, "duck": {"threshold": -30, "ratio": 8, "attack_ms": 20, "release_ms": 300}},
    "master": {"loudnorm_lufs": -14}
  },
  "subtitle_style": "short_large_center",
  "export": {"preset": "fb_reel_1080x1920_h264", "container": "mp4"}
}
```

- Scene model cho Mode 1: một visual (ảnh hoặc clip) cùng một voice và nhiều cue phụ đề. Ở Mode 2 và 3, `visual.kind="clip"` có `trim_in` và `trim_out`.
- Export preset là dữ liệu: `fb_reel_1080x1920_h264` (H.264 High, 30 fps, AAC 48 kHz stereo, khớp spec Reels trong audit) và `fb_video_1920x1080_h264`. Có tùy chọn `encoder: libx264|h264_nvenc`, chọn sau render benchmark.
- **Editor có giới hạn** (đã thống nhất trong audit trước) chỉ thao tác trên timeline JSON: sửa narration (sinh lại voice đoạn đó), thay visual, đổi thời lượng, sửa cue phụ đề, đổi thứ tự scene. Mỗi lần sửa tạo `timeline.version + 1`, rồi render lại.
- Renderer dịch JSON sang filtergraph một cách tất định. Mỗi render lưu kèm lệnh đầy đủ, phiên bản FFmpeg và log.

---

## 11. License Matrix

| Thành phần | Code | Weights | Thương mại | Output | Ghi chú |
|---|---|---|---|---|---|
| VieNeu-TTS v3 Turbo | Apache-2.0 | Apache-2.0 [HF] | Có [HF] | Card cho phép nội dung thương mại | "Do not clone real people without their permission" [HF]. v4 là bản đóng. |
| ZeroTTS | MIT | MIT [HF] | Có | — | Dataset benchmark CC-BY-NC (không áp cho weights) [GH]. Clone qua platform bên ngoài. |
| viXTTS / XTTS-v2 | MPL-2.0 | **CPML** [HF] | **Không** | — | AVOID |
| F5-TTS | MIT | **CC-BY-NC** [GH] | **Không** | — | AVOID |
| Piper | GPL-3.0 | Từng giọng riêng | ? | — | Kiểm tra license giọng vi_VN trước khi dùng |
| ComfyUI | GPL-3.0 | — | Có (dùng như tiến trình riêng) | — | Không phân phối kèm Orchestra |
| FLUX.2 [klein] 4B | Apache-2.0 | **Apache-2.0** [HF] | Có [HF] | — | Bản 9B và dev là non-commercial |
| FLUX.1 [schnell] | Apache-2.0 | Apache-2.0 [HF] | Có | — | Gated (phải chấp nhận điều khoản trên HF) |
| FLUX.1 [dev] | — | **Non-commercial** [HF] | **Không** | — | AVOID |
| Qwen-Image | Apache-2.0 | Apache-2.0 [HF] | Có | — | — |
| SDXL base | — | openrail++ [HF] | Có kèm hạn chế sử dụng [Giả định] | — | Card ghi "research purposes" ở phần mục đích sử dụng |
| Wan2.1 / Wan2.2 | Apache-2.0 | Apache-2.0 [HF Wan2.2-TI2V-5B] | Có | "We claim no rights over the your generated contents" [HF] | — |
| LTX-Video 0.9.x | Apache-2.0 | OpenRail-M (2B 0.9.5) [GH] | Có kèm hạn chế [Giả định] | — | — |
| LTX-2.x | Apache-2.0 | **LTX-2 Community License** [HF] | **Chưa đọc điều khoản** | — | Đọc trước Tier C |
| HunyuanVideo-1.5 | — | tencent-hunyuan-community [HF] | **Chưa xác minh** (có thể có giới hạn vùng lãnh thổ) | — | Đọc trước khi dùng |
| CogVideoX-2B | Apache-2.0 | Apache-2.0 [GH] | Có | — | 5B có license riêng |
| ACE-Step 1.5 | MIT | MIT [HF] | Có [HF] | "use the generated music for commercial purposes" [HF] | Rủi ro dữ liệu huấn luyện chưa rõ |
| MusicGen | MIT | **CC-BY-NC 4.0** | **Không** | — | AVOID |
| Stable Audio Open | MIT | Stability Community | Theo điều khoản Stability (chưa đọc) | — | AVOID tạm |
| faster-whisper / Whisper | MIT | MIT | Có | — | — |
| PhoWhisper-small | BSD-3 | BSD-3 [HF] | Có | — | — |
| FFmpeg | LGPL-2.1+; GPL nếu `--enable-gpl` | — | Có | — | Không phân phối kèm installer nếu chưa chọn bản build |
| Wan2GP | WanGP Community License 2.0 | — | Dùng cá nhân được; output được bán | — | Cấm nhúng vào sản phẩm trả phí |
| Edge TTS | — | — | **Không rõ** | — | AVOID |

Quy tắc áp dụng [Đề xuất]:
- Provider registry **từ chối** model có `license.commercial = false` khi chạy cho kênh có mục đích thương mại.
- Mỗi asset lưu `license_ref` của model và tài nguyên đã dùng.
- Clone giọng chỉ với giọng của Dung hoặc người có **văn bản đồng ý**, lưu cùng voice profile.
- Nhạc chỉ từ nguồn có file license.
- Không dùng footage stock khi chưa lưu điều khoản. Pexels/Pixabay có giấy phép riêng [Giả định]. Đăng lại footage không thêm giá trị cũng chạm rủi ro "unoriginal content" đã nêu trong audit trước.

---

## 12. PC Upgrade Options

### 12.1 Giữ hay thay

| Linh kiện | Laptop hiện tại | Giữ lại được? |
|---|---|---|
| GPU 4 GB laptop | Hàn trên mainboard | **Không nâng được** |
| RAM | Chưa biết hàn hay khe | **Có thể nâng** nếu có khe SO-DIMM. 5600H hỗ trợ DDR4-3200 [Giả định; dung lượng tối đa xem script] |
| SSD | Chưa biết | Thường thêm hoặc thay được M.2 |
| CPU | Hàn | Không |
| Nguồn | Adapter | Không |

Nhận xét: không nên mua eGPU cho laptop này trước khi biết máy có Thunderbolt/USB4 hay không. Máy AMD 5600H thường không có [Giả định]. Lựa chọn hợp lý là **giữ laptop làm máy điều khiển** (Orchestra, duyệt, render FFmpeg), và **thêm desktop GPU** làm máy media. Kiến trúc hỗ trợ điều này qua worker (ADR-0025, hiện chỉ cùng máy, cần mở rộng LAN ở Phase 5).

### 12.2 Cấu hình

| | Tier A — Tận dụng máy hiện tại | Tier B — Desktop hợp lý | Tier C — Workstation |
|---|---|---|---|
| GPU | RTX 3050 Laptop 4 GB (giữ) | NVIDIA **16 GB** (12 GB là mức sàn) | NVIDIA **24–32 GB** |
| RAM | **32 GB** nếu có khe (nâng cấp duy nhất) | **64 GB** DDR5 | **128 GB** |
| CPU | 5600H (giữ) | 8 nhân hiện đại | 12–16 nhân |
| Ổ đĩa | Thêm NVMe 1–2 TB nếu có khe | NVMe 2 TB (model) + 2–4 TB (media) | NVMe 4 TB + HDD/NAS lưu trữ |
| PSU | Adapter hiện tại | 750–850 W 80+ Gold [Giả định theo GPU] | 1000 W+ [Giả định cho GPU 32 GB] |
| Tản nhiệt | Đế tản nhiệt; theo dõi throttle | Case thoáng, 3+ quạt | Tản nhiệt CPU tốt, case lớn |
| Làm được | Mode 1 đầy đủ, ảnh 4B lượng tử | Mode 2: ảnh chất lượng cao, I2V 480–720p cho cảnh chính | Mode 3: T2V/I2V 720p+, LTX-2 có audio, huấn luyện LoRA |

Ví dụ GPU hiện có trên thị trường (cần kiểm tra lại giá và tình trạng khi mua; danh sách dòng card có thể đã thay đổi): 16 GB như RTX 5060 Ti 16 GB, 5070 Ti, 5080; 24 GB như RTX 3090 cũ, 4090; 32 GB như RTX 5090. [Giả định; chưa kiểm tra giá hôm nay]

### 12.3 Nâng cấp cải thiện công việc nào

| Công việc | A → A + 32 GB RAM | → Tier B | → Tier C |
|---|---|---|---|
| TTS | Không thay đổi nhiều (đã CPU real-time) | GPU batch nhanh hơn ~25× [Tác giả VieNeu], ít cần | Không cần |
| LLM local | Chạy cùng engine khác được | Model 8–14B chạy được | 30B+ lượng tử |
| Ảnh | **Lớn**: mở khóa offload cho 4B/20B | Lớn | Vừa |
| Video AI | Không | **Từ không thành có** | Chất lượng/độ dài cao hơn |
| Render FFmpeg | Ít | Vừa (NVENC mới hơn, CPU mạnh hơn) | Ít |

Không mặc định GPU mạnh hơn thì video nhanh hơn tuyến tính: thời gian sinh bị chi phối bởi offload (băng thông RAM/PCIe), kích thước VAE decode và số bước. Một card 16 GB phải offload có thể chậm hơn nhiều so với card 24 GB chạy gốc. [Giả định có căn cứ: tài liệu WanVideoWrapper và HunyuanVideo-1.5 đều nói offload làm chậm]

### 12.4 Chi phí

| Workflow | Local / Cloud | Phần mềm | API | Phần cứng |
|---|---|---|---:|---|
| Vietnamese TTS | Local | $0 (Apache/MIT) | $0 | Máy hiện tại |
| LLM kịch bản | Local hoặc cloud | $0 | $0 local; cloud ~$0,02–0,10/video [Giả định từ giá token trong audit] | Máy hiện tại |
| Image Generation | Local hoặc cloud | $0 | $0 local; cloud ~$0,02–0,04/ảnh | A: chậm; A + RAM hoặc B: tốt |
| Video Generation | Cloud (Tier A) / Local (B, C) | $0 | Cloud ~$0,05–0,10/giây; local $0 | Tier B trở lên |
| Music | Thư viện có license / local ACE-Step | $0 hoặc phí thư viện | $0 | — |
| Subtitle | Local | $0 | $0 | Máy hiện tại |
| Rendering | Local | $0 | $0 | Máy hiện tại |
| Điện năng | — | — | — | Laptop thấp; desktop GPU 16–32 GB tốn điện đáng kể khi sinh video [Giả định; cần đo bằng ổ cắm đo điện] |
| Lưu trữ | — | — | — | 5–20 GB/tháng media (audit) + 50–200 GB model [Giả định] |

Không có cấu hình nào là "zero cost" thật sự: luôn có chi phí điện, ổ đĩa và (nếu dùng) LLM cloud.

---

## 13. Local AI Media Gateway Architecture

### 13.1 Ba phương án

| Phương án | Ưu | Nhược | Kết luận |
|---|---|---|---|
| A. Gọi ComfyUI/TTS trực tiếp từ code pipeline | Ít code | Logic tài nguyên rải rác; khó đổi provider | Không |
| **B. Module `media_gateway` trong backend FastAPI**, adapter Python mỏng, **engine chạy tiến trình riêng** | Không thêm server; dùng lại job runner, event, credential; torch không vào backend | Backend quản lý vòng đời tiến trình | **Chọn** |
| C. Gateway server độc lập | Tách biệt, có thể ở máy khác | Thêm một service, auth, deploy | Để Phase 5, khi có desktop GPU (dùng worker hiện có) |

### 13.2 Sơ đồ

```text
Orchestra backend (FastAPI, venv sạch, không torch)
 └─ media_gateway/
     ├─ registry: providers + capabilities + hardware + license + cost
     ├─ scheduler: GPU lease, CPU pool, RAM/VRAM gate          (mục 14)
     ├─ engine_manager: start/stop/health tiến trình engine     (Windows Job Object)
     ├─ adapters/
     │   ├─ tts_vieneu      → HTTP localhost  (VieNeu OpenAI-compatible server)
     │   ├─ tts_zerotts     → sidecar nhỏ trong venv riêng (stdin/stdout JSON hoặc HTTP)
     │   ├─ image_comfyui   → HTTP /prompt, /history, WebSocket progress
     │   ├─ video_comfyui   → như trên (Tier B+)
     │   ├─ asr_fasterwhisper → sidecar venv riêng
     │   ├─ llm_*           → runtime hiện có (Ollama/Claude/OpenAI)
     │   ├─ render_ffmpeg   → subprocess, args list (không shell)
     │   └─ cloud_*         → tùy chọn, có budget + duyệt chi phí
     └─ outputs → media store (sha256), Asset + lineage
```

- **Mỗi engine một thư mục và một môi trường riêng** (`%LOCALAPPDATA%\OrchestraStudio\engines\<engine>\`), có phiên bản cố định. Backend chỉ lưu đường dẫn, phiên bản và checksum.
- **ComfyUI**: workflow JSON là template được **lưu version trong repo** (`media_gateway/workflows/*.json`), chỉ điền tham số qua danh sách trường cho phép. Không cho LLM tự viết workflow. Danh sách custom node cho phép được cố định commit.
- Engine chỉ nghe trên `127.0.0.1`, cổng ngẫu nhiên, có token nếu engine hỗ trợ.

### 13.3 Provider Adapter Contract

```python
class ProviderMeta(BaseModel):
    provider_id: str            # "vieneu-v3-turbo"
    version: str                # engine + model version, ghi vào mọi asset
    kind: Literal["tts","image","video","asr","render","llm","music"]
    capabilities: dict          # ví dụ {"voice_clone": true, "langs": ["vi","en"], "max_chars": 600}
    hardware: HardwareReq       # device: cpu|gpu, min_vram_mb, est_ram_mb, exclusive_gpu: bool
    input_schema: dict          # JSON Schema
    output_schema: dict
    cancellable: Literal["hard","soft","none"]
    default_timeout_s: int
    license: LicenseMeta        # code, weights, commercial: bool, output_rights, source_url, checked_at
    cost: CostMeta              # local: est_kwh?; cloud: unit, price, currency, price_checked_at

class JobContext:               # do scheduler cấp
    job_id: str; deadline: float; cancel_event: asyncio.Event
    def progress(self, pct: float, note: str = "") -> None: ...
    def usage(self, ram_mb: int, vram_mb: int, gpu_s: float) -> None: ...

class TtsProvider(Protocol):    meta: ProviderMeta; async def synthesize(self, req, ctx) -> TtsResult: ...
class ImageProvider(Protocol):  meta: ProviderMeta; async def generate(self, req, ctx) -> list[AssetRef]: ...
class VideoProvider(Protocol):  meta: ProviderMeta; async def generate(self, req, ctx) -> AssetRef: ...
class SpeechProvider(Protocol): meta: ProviderMeta; async def transcribe(self, req, ctx) -> Transcript: ...
class RenderProvider(Protocol): meta: ProviderMeta; async def render(self, timeline, preset, ctx) -> AssetRef: ...
```

Pipeline chỉ phụ thuộc vào `kind` + `capabilities`, không phụ thuộc tên provider. Đổi provider = đổi cấu hình company, không sửa Campaign Pipeline. Mỗi adapter có bản **fake** tạo file thật để test offline (như đã đề xuất trong audit).

---

## 14. Resource Scheduler Architecture

### 14.1 Nguyên tắc cho một PC

- **Một GPU lease độc quyền**: tại mỗi thời điểm chỉ một job GPU nặng (ComfyUI ảnh/video, TTS GPU).
- **CPU pool** giới hạn theo số luồng: TTS CPU và ASR lấy tối đa 6 luồng, FFmpeg lấy phần còn lại. Không chạy TTS CPU song song với FFmpeg trên máy hiện tại.
- **Cổng bộ nhớ**: trước khi chạy, so `est_ram_mb` và `min_vram_mb` của provider với RAM và VRAM trống thực tế. Không đủ thì **giải phóng engine khác** (theo thứ tự LRU), rồi kiểm tra lại. Vẫn không đủ thì job chờ hoặc báo lỗi `insufficient_resources`, không chạy liều.
- **Chính sách nạp model**:
  - Engine được giữ "ấm" trong N phút. Trên máy 8 GB thì N = 0: tắt ngay sau khi xong.
  - Ollama: gọi với `keep_alive` ngắn hoặc 0 để giải phóng. [Giả định: tham số này có trong API Ollama; cần kiểm tra lại với phiên bản đang dùng]
  - ComfyUI: gọi endpoint giải phóng bộ nhớ (`/free`) hoặc tắt tiến trình. [Giả định: endpoint cần xác minh với phiên bản cài]
- **Gom việc theo engine**: sinh tất cả ảnh của video trước, rồi tất cả voice, rồi render. Cách này giảm số lần nạp model. Pipeline là DAG theo scene, nhưng scheduler sắp lại theo engine.
- **OOM**: nhận diện qua mã lỗi hoặc log của engine → retry 1 lần ở cấu hình nhẹ hơn (độ phân giải thấp hơn, bật lowvram, batch = 1) → nếu vẫn lỗi thì `needs_decision`.
- **Ưu tiên**: job người dùng đang chờ (preview, tạo lại 1 scene) cao hơn job hàng loạt.
- **Pause**: chỉ dừng **giữa** các job (giữa scene). Job đang chạy hủy được hay không tùy `cancellable` của adapter.

### 14.2 Windows và NVIDIA

| Việc | Cách làm | Ghi chú |
|---|---|---|
| Đo VRAM | NVML qua `nvidia-ml-py` hoặc `nvidia-smi --query-gpu=memory.used,memory.total --format=csv` | NVML là thư viện của driver [Giả định] |
| Đo RAM | `psutil` (đã phổ biến) | Dependency mới, cần duyệt khi triển khai |
| Tràn VRAM sang RAM | Driver NVIDIA trên Windows có chính sách "CUDA – Sysmem Fallback Policy" [Giả định, cần kiểm tra trong NVIDIA Control Panel]. Khi bật, job có thể không OOM nhưng chậm hơn nhiều lần. | Scheduler đo "shared GPU memory" và cảnh báo. **Mình không đổi cấu hình**, Dung quyết định. |
| Dừng cả cây tiến trình | Windows Job Object (kill-on-close) cho mỗi engine | Tránh tiến trình con Python mồ côi giữ VRAM |
| Laptop nóng / throttle | Đọc nhiệt độ và xung GPU qua NVML; quá ngưỡng thì giãn job | [Đề xuất] |

### 14.3 Luồng

```text
job submitted → queue(kind, priority)
  → scheduler picks: device lease (gpu|cpu slots) + memory gate
     → engine_manager.ensure_running(engine) (start / warm / health)
        → adapter.run(ctx)  ── progress/usage → events (SSE)
     → output → media store → validation → asset.created
  → release lease → policy: unload engine? → next job
on restart: jobs with lease_until < now → reconcile (local engine: rerun if idempotent; cloud: poll external id)
```

Scheduler này là **phần mở rộng của job runner bền vững** đã đề xuất trong audit (B2), không phải một hệ thống riêng.

---

## 15. Short / Long Production Modes

### 15.1 Ba mode

| | Mode 1 — Low Hardware | Mode 2 — Mid Hardware | Mode 3 — High Hardware |
|---|---|---|---|
| Phần cứng | Máy hiện tại (A); tốt hơn với RAM 32 GB | Tier B (12–16 GB VRAM, RAM 64 GB) | Tier C (24–32 GB, RAM 128 GB) |
| Input | Chủ đề, profile, voice profile, style preset | + character sheet | + reference video, character LoRA |
| LLM | Claude hoặc qwen3:4b (benchmark quyết định) | như Mode 1, hoặc local 8–14B | local lớn hơn |
| Ảnh | SD 1.5 / FLUX.2 [klein] 4B GGUF, **hoặc** ảnh cloud | FLUX.2 [klein] 4B, Qwen-Image-Edit 4-bit | như B, chất lượng cao hơn |
| Video | **Không dùng model video**: Ken Burns, parallax, crop động, chuyển cảnh | I2V cho 20–40% cảnh quan trọng (FramePack/LTX/Wan 5B) | T2V + I2V + V2V; LTX-2 có audio |
| Giọng | VieNeu / ZeroTTS CPU | VieNeu GPU | như B |
| Nhạc | Thư viện có license | + ACE-Step thử nghiệm | như B |
| Render | FFmpeg | FFmpeg | FFmpeg |
| Output | MP4 1080p đạt QA | + clip động thật ở cảnh chính | Video AI chủ đạo |
| Thời gian [Giả định, cần benchmark] | Short 60 giây: ~15–40 phút tổng (phần lớn là ảnh); long 8 phút: vài giờ nếu ảnh local trên 4 GB | + vài phút mỗi clip I2V | Tùy model |
| Giới hạn | Hình tĩnh, ít hấp dẫn hơn video động | Nhân vật giữ chưa hoàn hảo; chậm | Chi phí phần cứng |
| License | Chỉ model `commercial=true` | như trên | Đọc kỹ LTX-2/Hunyuan |
| Acceptance | QA tất định pass; MOS giọng ≥ 4; Dung chấm "đủ để đăng" | + clip không méo hình (Dung chấm) | như B |

### 15.2 Short và Long: dùng chung gì, khác gì

| Dùng chung (một engine) | Khác theo profile |
|---|---|
| Pipeline, Task Contract, media store, scheduler | Tỉ lệ, độ phân giải, dải thời lượng |
| Voice profile (một giọng cho kênh) | Cấu trúc: hook-body-CTA hoặc chương |
| Chuẩn hóa văn bản, TTS theo đoạn | Nhịp: số giây tối đa mỗi scene |
| Timeline schema, renderer, QA | Style phụ đề, ký tự/dòng |
| Asset reuse | Nhạc nền: short thường một bài; long có thể đổi theo chương |

Long cần thêm:
- **Kiểm soát nhất quán giọng qua 40+ đoạn** (cố định seed và profile, QA nghe chuyển đoạn).
- **Mạch kể** (outline chương trước, rồi script từng chương).
- **Chạy theo lô nhiều giờ** (resume sau khi tắt máy là bắt buộc).

---

## 16. Benchmark Plan

Chi tiết ở [`LOCAL_AI_BENCHMARK_PLAN.md`](LOCAL_AI_BENCHMARK_PLAN.md):
- §1 script kiểm kê.
- §3 TTS: 10 loại văn bản + bài kiểm tra nhất quán 8 phút; đo MOS, WER, RTF, peak RAM/VRAM, TTFA.
- §4 ảnh.
- §5 video (chỉ khi có GPU ≥ 8 GB).
- §6 render 30 giây / 90 giây / 5 phút / 10 phút, so `libx264` với `h264_nvenc`.
- §7 ASR.

Mọi benchmark chạy **ngoài app**, trong thư mục và venv riêng. Kết quả ghi CSV.

Thứ tự đề xuất: kiểm kê → render (không cần cài model, chỉ cần FFmpeg) → TTS → ASR → ảnh.

---

## 17. Integration Roadmap

Điều chỉnh so với thứ tự trong brief, có lý do:

1. **Thêm Phase 0b "Benchmark trên máy Dung"** trước khi viết adapter thật. Chọn engine từ số đo, không từ README.
2. **Không để "Orchestra Integration" tới Phase 5.** Nếu làm media foundation riêng rồi mới tích hợp, sẽ có hai hệ thống job, asset và cấu hình. Media foundation nên **xây ngay trong backend Orchestra**, dùng chung backlog B1–B3 của audit trước (media store, job runner, Task Contract).
3. Phase 2 (ảnh local) **phụ thuộc quyết định nâng RAM**. Nếu không nâng, Phase 2 dùng adapter ảnh cloud là chính và local là tùy chọn.

| Phase | Objective | Nội dung chính | Phụ thuộc | Exit |
|---|---|---|---|---|
| **0 (xong khi Dung duyệt)** | Hardware & ecosystem audit | Báo cáo này + audit sản phẩm | — | Dung duyệt stack và trả lời câu hỏi mục 18 |
| **0b** | Benchmark | Kiểm kê; render, TTS, ASR, ảnh trên máy Dung; chốt engine | Dung cài engine theo hướng dẫn (hoặc duyệt để mình hướng dẫn qua Remote Control) | CSV kết quả; chốt primary TTS, encoder, ASR, đường ảnh |
| **1** | Local media foundation | Media store, job runner + scheduler, `media_gateway` (registry, engine manager), adapter TTS + ASR + FFmpeg, chuẩn hóa văn bản, voice profile, phụ đề theo đoạn, ảnh **nhập tay hoặc cloud** | ADR mới; audit B1–B3 | Từ script mẫu → MP4 short + long có giọng tiếng Việt, ảnh, phụ đề, pass QA; tạo lại 1 đoạn voice không đổi đoạn khác; tắt app giữa chừng rồi tiếp tục được |
| **2** | Image production | Adapter ComfyUI (workflow version), character sheet, style preset, edit một ảnh, nhiều phiên bản để chọn | Phase 1; quyết định RAM | Bộ ảnh đồng nhất cho 1 video; Dung chấm ≥ 3,5/5 |
| **3** | AI video (nếu có Tier B) | Adapter video qua ComfyUI, I2V từng scene, tạo lại | Tier B **hoặc** adapter cloud có duyệt chi phí | Clip I2V cho cảnh chính được Dung chấp nhận |
| **4** | Advanced production | Long video nhiều chương, mix audio nâng cao, phụ đề theo từ, video QA, lịch sử version, xuất dự án để sửa tay | 1–2 | Video 8 phút pass QA, nghe liền mạch |
| **5** | Orchestra integration (phần còn lại) | Campaign, CEO, duyệt, worker LAN cho desktop GPU | Audit sản phẩm Phase 1 | Chủ đề → video qua giao diện Orchestra |
| **6** | Facebook + analytics | Theo audit sản phẩm Phase 2–4 | 5 | Như audit |

Lưu ý: trong thực tế, Phase 1 ở đây trùng phần lớn với Phase 1 của audit sản phẩm. Đề xuất **gộp làm một** để có một backlog duy nhất (mục 20).

---

## 18. Risks and Unknowns

| Rủi ro / chưa biết | Ảnh hưởng | Cách xử lý |
|---|---|---|
| RAM vật lý và khả năng nâng cấp chưa biết | Quyết định Tier A+ | Script kiểm kê |
| Chất lượng thực tế của VieNeu/ZeroTTS với nội dung kênh | Cốt lõi | TTS benchmark; giữ 2 engine |
| VieNeu chuyển v4 sang đóng; v3 có thể không được cập nhật | Dài hạn | Cố định phiên bản; adapter cho phép đổi engine |
| ZeroTTS cần dịch vụ ngoài để clone giọng | Riêng tư | Dùng giọng mẫu, hoặc clone bằng VieNeu |
| Ảnh local trên 4 GB / 8 GB RAM có thể quá chậm | Thời gian sản xuất | Benchmark; adapter ảnh cloud làm phương án chính nếu cần |
| Driver tràn VRAM sang RAM khiến kết quả benchmark sai | Quyết định sai | Theo dõi "shared GPU memory" |
| Custom node ComfyUI chạy code tùy ý | Bảo mật | Danh sách node cho phép, cố định commit, không cài node theo gợi ý của model |
| License chưa đọc: LTX-2, HunyuanVideo-1.5, Stable Audio, giọng Piper, model align MMS, F5-TTS-Vietnamese | Pháp lý | Đọc trước khi dùng; registry chặn mặc định |
| Nhạc AI bị hệ thống bản quyền nền tảng nhận nhầm | Bài bị chặn | Mặc định thư viện có license |
| Chính sách Meta về nội dung AI / unoriginal (audit trước) | Phân phối | Dung kiểm tra |
| Laptop nóng khi chạy dài | Ổn định | Scheduler giãn job theo nhiệt |
| Tải model lớn (FramePack > 30 GB [GH]) | Ổ đĩa | NVMe riêng cho model |
| Số liệu tác giả khác số thật trên Windows/laptop | Kỳ vọng | Chỉ dùng số đo |

---

## 19. Recommended Stack

### 19.1 Stack tối thiểu chạy được trên máy hiện tại

| Layer | Recommended Tool | Alternative | Why |
|---|---|---|---|
| Local LLM | Ollama + qwen3:4b (đã có) cho bước rẻ; **Claude** cho kịch bản (chi phí nhỏ, cần duyệt) | OpenAI runtime đã có | 8B+ không vừa máy; chất lượng kịch bản quyết định giá trị kênh |
| Vietnamese TTS | **VieNeu-TTS v3 Turbo** CPU fp32 | ZeroTTS | Apache, giọng ba miền, có API, clone local |
| Voice cloning | VieNeu (giọng của Dung hoặc giọng có văn bản đồng ý) | Giọng mẫu của VieNeu/ZeroTTS | Local, license rõ |
| Image generation | **Ảnh cloud qua adapter** (khi Dung duyệt chi phí) hoặc ComfyUI + SD 1.5 / FLUX.2 [klein] 4B GGUF | Ảnh do Dung cung cấp | 4 GB VRAM + 8 GB RAM là nút thắt; chọn sau benchmark |
| Video generation | **Không dùng**; chuyển động bằng FFmpeg | Clip cloud cho cảnh chính (có duyệt) | Không model nào vừa máy |
| Subtitle / ASR | Thời gian từ đoạn TTS; faster-whisper `small` int8 để QA | PhoWhisper-small | Nhẹ, MIT/BSD |
| Audio processing | FFmpeg (`loudnorm`, `sidechaincompress`, `silenceremove`) | silero-vad | Không thêm dependency |
| Music | Thư viện nhạc có license | — | Rủi ro bản quyền thấp nhất |
| Rendering | **FFmpeg CLI** + timeline JSON | — | Nhanh, tất định, kiểm tra bằng ffprobe |
| Workflow engine | Job runner + pipeline của Orchestra | — | Không thêm framework |
| Local gateway | Module `media_gateway` trong backend, engine là tiến trình riêng | — | Không thêm server |

### 19.2 Stack mục tiêu sau nâng cấp (Tier B desktop + laptop làm máy điều khiển)

| Layer | Recommended Tool | Alternative | Why |
|---|---|---|---|
| Local LLM | Ollama, model 8–14B lượng tử (benchmark tiếng Việt) + Claude cho kịch bản | qwen3:4b | Đủ VRAM |
| Vietnamese TTS | VieNeu v3 Turbo GPU | ZeroTTS | Batch nhanh |
| Voice cloning | VieNeu | OmniVoice (sau khi kiểm tra tiếng Việt) | — |
| Image generation | **ComfyUI + FLUX.2 [klein] 4B** (edit + multi-reference) | Qwen-Image-Edit 4-bit (Nunchaku) | Apache, giữ nhân vật |
| Video generation | **ComfyUI + FramePack wrapper / Wan2.2 TI2V-5B** (I2V) | LTX-Video distilled; HunyuanVideo-1.5 | Apache; chạy được với 16 GB + offload |
| Subtitle / ASR | faster-whisper `medium` (GPU) | PhoWhisper | — |
| Audio processing | FFmpeg | DeepFilterNet | — |
| Music | Thư viện + ACE-Step 1.5 thử nghiệm | — | MIT, cần kiểm rủi ro |
| Rendering | FFmpeg (NVENC nếu đạt chất lượng) | — | — |
| Workflow engine | Orchestra job runner; ComfyUI cho đồ thị model | — | — |
| Local gateway | `media_gateway` + **worker trên desktop GPU** (mở rộng ADR-0025 ra LAN) | Gateway server riêng | Dùng lại worker hiện có |

---

## 20. First Implementation Backlog (sau khi Dung duyệt)

Gộp với backlog B0–B12 của audit sản phẩm. Các mục dưới đây được thêm vào hoặc đổi thứ tự.

| # | Task | Phụ thuộc | Kiểm chứng |
|---|---|---|---|
| L0 | Dung chạy script kiểm kê, gửi kết quả; quyết định có nâng RAM không | — | File `hw_inventory.txt` |
| L1 | ADR: Local media gateway (module, engine là tiến trình riêng), resource scheduler, provider license policy, voice profile | B0 | ADR được duyệt |
| L2 | `bench/` ngoài app: render benchmark R1–R4 bằng FFmpeg (ảnh mẫu tự tạo, giọng mẫu) | FFmpeg trên máy Dung | CSV; chọn encoder |
| L3 | TTS benchmark VieNeu vs ZeroTTS (CPU) theo bộ văn bản | Dung cài 2 engine (cần duyệt) | CSV + MOS; chốt primary |
| L4 | ASR benchmark faster-whisper small vs PhoWhisper-small | L3 | Chốt ASR QA |
| L5 | Media store + Asset (= B1) | B0 | Như B1 |
| L6 | Job runner bền vững (= B2) + scheduler: GPU lease, CPU slots, memory gate, engine manager (Job Object) | L5 | Test: hai job GPU không chạy song song; thiếu RAM thì unload rồi chạy; kill giữa chừng rồi tiếp tục |
| L7 | `media_gateway` registry + ProviderMeta + license policy (chặn `commercial=false`) + fake providers | L6 | Test chặn model non-commercial; pipeline chạy offline |
| L8 | Chuẩn hóa văn bản tiếng Việt + từ điển phát âm kênh + chia đoạn | L3 | Test T3–T6 có đáp án |
| L9 | Adapter TTS primary (HTTP) + secondary (sidecar), voice profile có version | L7, L8 | Sinh lại đoạn 17 của T11 không đổi file đoạn khác |
| L10 | Timeline JSON v1 + renderer FFmpeg (Ken Burns, fade, ducking, loudnorm, ASS) + QA ffprobe (= B8) | L5, L2 | MP4 short và long pass QA trên Windows |
| L11 | Phụ đề theo đoạn + ASR QA (WER) | L9, L4 | Phụ đề lệch < 200 ms trên mẫu 20 dòng [ngưỡng đề xuất] |
| L12 | Ảnh: nhập tay + adapter cloud (khi duyệt) **hoặc** ComfyUI nếu benchmark ảnh đạt | L7 | 1 video hoàn chỉnh từ script mẫu |

Không thuộc đợt này: video AI local, ACE-Step, LoRA nhân vật, worker LAN, Facebook.

---

## 21. Quyết định và câu hỏi cho Dung

1. **Chạy script kiểm kê** ([`LOCAL_AI_BENCHMARK_PLAN.md` §1](LOCAL_AI_BENCHMARK_PLAN.md)) và gửi lại kết quả.
2. **Nâng RAM laptop lên 32 GB** (nếu có khe) trước Phase 2? Đây là khuyến nghị của mình.
3. **Có kế hoạch mua desktop GPU không, và khi nào?** Nếu không có kế hoạch, video AI chỉ còn đường cloud.
4. **LLM viết kịch bản**: chấp nhận Claude với chi phí nhỏ cho mỗi video, hay bắt buộc local? Mình khuyến nghị Claude, local làm dự phòng.
5. **Giọng kênh**: giọng mẫu (miền nào, nam hay nữ), hay clone giọng của chính Dung?
6. **Ảnh ở Phase 1**: chấp nhận adapter ảnh cloud có duyệt chi phí, hay chờ benchmark ảnh local?
7. **Gộp roadmap** này với audit sản phẩm thành một backlog duy nhất (đề xuất mục 17 và 20)?

---

## 22. Sources (truy cập 2026-11-06)

- GitHub metadata (license, lần push, archived, fork): GitHub REST search API, cho mọi repo ở mục 4.
- README/LICENSE (raw.githubusercontent.com): ZeroTTS (README, LICENSE, NOTICE), pnnbao97/VieNeu-TTS, thinhlpg/vixtts-demo, SWivid/F5-TTS, nguyenthienhy/F5-TTS-Vietnamese, RVC-Boss/GPT-SoVITS, fishaudio/fish-speech, index-tts/index-tts, resemble-ai/chatterbox, OHF-Voice/piper1-gpl (+ docs/VOICES.md), Comfy-Org/ComfyUI, Comfy-Org/Comfy-Desktop, city96/ComfyUI-GGUF, nunchux-ai/nunchaku, QwenLM/Qwen-Image, black-forest-labs/flux2, Wan-Video/Wan2.1, Wan-Video/Wan2.2, lllyasviel/FramePack, Lightricks/LTX-Video, Lightricks/LTX-2, Lightricks/ComfyUI-LTXVideo, Tencent-Hunyuan/HunyuanVideo-1.5, zai-org/CogVideo, kijai/ComfyUI-WanVideoWrapper, Kosinkadink/ComfyUI-VideoHelperSuite, deepbeepmeep/Wan2GP (+ LICENSE.txt), ModelTC/LightX2V, harry0703/MoneyPrinterTurbo, RayVentura/ShortGPT, ace-step/ACE-Step-1.5, facebookresearch/audiocraft, SYSTRAN/faster-whisper, m-bain/whisperX, MahmoudAshraf97/ctc-forced-aligner, VinAIResearch/PhoWhisper, remotion-dev/remotion, Zulko/moviepy, mifi/editly, Rikorose/DeepFilterNet.
- Hugging Face model cards: coqui/XTTS-v2, capleaf/viXTTS, pnnbao-ump/VieNeu-TTS-v3-Turbo, zeroweight-ai/ZeroTTS, black-forest-labs/FLUX.1-schnell, FLUX.1-dev, FLUX.2-klein-4B, Qwen/Qwen-Image, Lightricks/LTX-2, tencent/HunyuanVideo-1.5 (chỉ đọc được một phần), ACE-Step/Ace-Step1.5, facebook/musicgen-small, stabilityai/stable-audio-open-small, stable-audio-open-1.0, Wan-AI/Wan2.2-TI2V-5B, stabilityai/stable-diffusion-xl-base-1.0, vinai/PhoWhisper-small.
- Máy Dung: số đo ngày 2026-11-05 (project memory).
- Chưa đọc (cần trước khi dùng): coqui.ai/cpml, stability.ai/license, LTX-2 Community License, Tencent Hunyuan Community License, license giọng Piper vi_VN, license model align MMS, điều khoản Pexels/Pixabay, giấy phép font, chính sách Ollama `keep_alive` và ComfyUI `/free` ở phiên bản sẽ cài, giá GPU/RAM hiện tại.
