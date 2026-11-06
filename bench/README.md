# Benchmarks (L2–L4)

Chạy trên **máy Dung**, cắm sạc, chế độ hiệu năng cao, đóng app khác (LOCAL_AI_BENCHMARK_PLAN §2).
Script dùng môi trường backend (không torch). Engine chạy riêng theo `docs/MEDIA_ENGINES.md`.
Kết quả ghi vào `bench/results/<ngày>_<máy>_<loại>.csv`.

| Bước | Lệnh (từ thư mục repo) | Cần |
|---|---|---|
| L2 render R1–R4 | `uv run --project apps/backend python bench/render/run_render_bench.py --encoders libx264,h264_nvenc` | FFmpeg |
| L3 TTS T1–T11 | `uv run --project apps/backend python bench/tts/run_tts_bench.py --engines vieneu,zerotts` | VieNeu ở :8000, ZeroTTS sidecar ở :8011 |
| L3 MOS | Nghe `bench/results/tts_listen/<run>/sample_*.wav`, điền `mos_sheet.csv`, sau đó mới mở `key.csv` | tai nghe |
| L4 ASR | `uv run --project apps/backend python bench/asr/run_asr_bench.py --listen bench/results/tts_listen/<run>` | faster-whisper sidecar ở :8012 |
| L4 PhoWhisper | `python bench/asr/phowhisper_transcribe.py <thư mục run> pho.json` trong venv riêng có torch CPU, rồi thêm `--pho-json pho.json` | ~1 GB tải model |

Ngưỡng đề xuất (Dung chỉnh): MOS ≥ 4,0 trên T1/T2/T9/T10; ≤ 1 lỗi đọc trên T3–T6; RTF ≤ 1,0;
R2 ≤ 3 phút, R4 ≤ 20 phút, QA pass 100%.

`results/reference_cloud_vm_render.csv` là số đo trên máy ảo cloud 4 nhân (Linux, không GPU) chỉ để
so sánh thứ tự độ lớn. **Không phải số đo trên máy Dung.**
