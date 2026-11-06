# Cài engine media trên máy Windows của Dung

**Ngày:** 2026-11-06 · Đi kèm ADR-0029/0030/0031. Mọi engine chạy **ngoài** venv backend, chỉ nghe `127.0.0.1`.
Không cài gì trong số này thì app vẫn chạy được với **giọng giả + ảnh giữ chỗ** (để thử pipeline).

Thứ tự đề xuất: FFmpeg → VieNeu → (tùy chọn) ZeroTTS → (tùy chọn) faster-whisper.
Đĩa: đặt engine ở `D:\OrchestraEngines\` (ổ D còn ~78 GB; ổ C còn ~83 GB).

## 1. FFmpeg (bắt buộc để render)

```powershell
winget install Gyan.FFmpeg
# mở PowerShell mới rồi kiểm tra
ffmpeg -version
ffmpeg -hide_banner -encoders | Select-String nvenc   # có h264_nvenc thì GPU encode được
```
Nếu `ffmpeg` không nằm trong PATH, đặt `ORCHESTRA_FFMPEG` và `ORCHESTRA_FFPROBE` là đường dẫn đầy đủ.

## 2. VieNeu-TTS v3 Turbo (TTS chính, CPU)

Nguồn: https://github.com/pnnbao97/VieNeu-TTS (Apache-2.0). `bonelag/VieNeuTTS` chỉ là bản fork.
Máy Dung: driver NVIDIA 566.07 = CUDA 12.7, nhánh GPU của VieNeu cần cu128 → **dùng nhánh CPU (ONNX)**.
Ryzen 5 5600H không có AVX-VNNI → dùng **fp32**, không dùng int8.

```powershell
cd D:\OrchestraEngines
git clone https://github.com/pnnbao97/VieNeu-TTS.git
cd VieNeu-TTS
uv sync                     # bản CPU, không torch
$env:VIENEU_BACKEND = "onnx"
$env:VIENEU_PRECISION = "fp32"
uv run python -m apps.openai_speech     # nghe http://127.0.0.1:8000
```
Kiểm tra: mở http://127.0.0.1:8000/health và http://127.0.0.1:8000/v1/voices.

Lưu ý đã đọc trong mã nguồn server (`apps/openai_speech.py`, 2026-11-06):
- Tham số `speed` được nhận nhưng **bị bỏ qua**. Orchestra tự đổi tốc độ bằng FFmpeg `atempo`.
- Mặc định **bật watermark âm thanh** (`VIENEU_WATERMARK=1`). Muốn tắt thì đặt `$env:VIENEU_WATERMARK = "0"` trước khi chạy. Đây là quyết định của Dung.
- Không có tham số seed.
- Giọng miền Nam theo README: Adam, Thái Sơn, Thục Đoan, Minh Triết, Mỹ Duyên, Đức Trí, Kim Thanh, Thùy Dung. Profile mặc định của Orchestra là **Thùy Dung** (giới tính suy từ tên, chưa nghe kiểm chứng). Đổi ở "Cài đặt sản xuất → Giọng kênh → Lấy danh sách".

Cũng có thể dùng bộ cài Windows ở vieneu.io, miễn là nó mở server OpenAI-compatible ở cổng 8000 (chưa kiểm chứng bộ cài đó làm vậy).

## 3. ZeroTTS (TTS phụ, CPU nhanh)

Nguồn: https://github.com/zeroweight-ai/ZeroTTS (MIT). Không có server sẵn, nên Orchestra có sidecar nhỏ.
Không clone giọng local được (bộ mã hóa giọng chưa công bố). 8 giọng mẫu không ghi vùng miền; `maichi`, `baotrang`, `kimoanh`, `hamy` là giọng nữ.

```powershell
cd D:\OrchestraEngines
uv venv zerotts-env
.\zerotts-env\Scripts\activate
uv pip install zerotts
# lần chạy đầu tải ~900 MB weights từ Hugging Face
python C:\Users\quocd\orchestra-studio\apps\backend\src\orchestra_backend\media_gateway\sidecars\zerotts_server.py --port 8011
```
Tham số `seed` trong sidecar chỉ đặt `numpy.random.seed`; **chưa kiểm chứng** ZeroTTS dùng nguồn ngẫu nhiên đó.

## 4. faster-whisper (tùy chọn, kiểm tra lời đọc bằng ASR)

```powershell
cd D:\OrchestraEngines
uv venv whisper-env
.\whisper-env\Scripts\activate
uv pip install faster-whisper
python C:\Users\quocd\orchestra-studio\apps\backend\src\orchestra_backend\media_gateway\sidecars\faster_whisper_server.py --port 8012 --model small --compute-type int8
```
Bật trong "Cài đặt sản xuất → Kiểm tra lời đọc bằng ASR".

## 5. Cho Orchestra tự bật/tắt engine (tùy chọn)

Mặc định engine là "tự mở ngoài app": Orchestra chỉ kiểm tra `/health` và báo lỗi rõ nếu engine chưa chạy.
Muốn Orchestra tự bật engine khi cần và **tắt ngay khi xong** (đỡ RAM trên máy 8 GB), tạo `data/engines.json`:

```json
{
  "engines": [
    {
      "id": "vieneu",
      "label": "VieNeu-TTS v3 Turbo",
      "base_url": "http://127.0.0.1:8000",
      "command": ["C:\\Users\\quocd\\.local\\bin\\uv.exe", "run", "python", "-m", "apps.openai_speech"],
      "cwd": "D:\\OrchestraEngines\\VieNeu-TTS",
      "env": {"VIENEU_BACKEND": "onnx", "VIENEU_PRECISION": "fp32"}
    },
    {
      "id": "zerotts",
      "label": "ZeroTTS",
      "base_url": "http://127.0.0.1:8011",
      "command": ["D:\\OrchestraEngines\\zerotts-env\\Scripts\\python.exe",
                  "C:\\Users\\quocd\\orchestra-studio\\apps\\backend\\src\\orchestra_backend\\media_gateway\\sidecars\\zerotts_server.py",
                  "--port", "8011"]
    }
  ]
}
```
Đường dẫn `uv.exe` có thể khác; xem bằng `where.exe uv`. Log engine ở `data/logs/engines/<id>.log`.
`ORCHESTRA_ENGINE_KEEP_WARM_S` (mặc định 0) giữ engine chạy thêm N giây sau việc cuối.

## 6. Tài nguyên trên laptop 8 GB

- `ORCHESTRA_MEDIA_MAX_PARALLEL=1` (mặc định): mỗi lúc một việc media.
- Trước mỗi việc, scheduler so RAM trống với ước tính của engine (VieNeu ~2,5 GB, ZeroTTS ~2 GB, faster-whisper ~1,5 GB, render ~1,2 GB, chừa 512 MB). Thiếu thì tắt engine Orchestra đã bật mà đang rảnh, rồi đo lại. Vẫn thiếu thì việc **chờ**, không chạy liều. Các ước tính này là **giả định**, sẽ chỉnh theo số đo L3.
- Nên tắt Ollama khi render (Ollama giữ RAM của qwen3:4b).
