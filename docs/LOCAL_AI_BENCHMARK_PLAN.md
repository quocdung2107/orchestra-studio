# Local AI Benchmark Plan & Hardware Inventory

**Ngày:** 2026-11-06 · Đi kèm `docs/LOCAL_AI_VIDEO_INFRASTRUCTURE_PLAN.md`.
**Trạng thái:** chỉ là kế hoạch. Chưa cài gì, chưa chạy model nào.

## 1. Hardware inventory: script PowerShell chỉ đọc

Hôm nay mình không kết nối được máy của Dung. Script dưới đây chỉ **đọc** thông tin, không cài và không sửa gì. Dung chạy trong PowerShell (không cần quyền admin), rồi gửi lại file `hw_inventory.txt`.

```powershell
# hw_inventory.ps1 — read-only. Output: .\hw_inventory.txt
$o = @()
$cs  = Get-CimInstance Win32_ComputerSystem
$enc = Get-CimInstance Win32_SystemEnclosure
$o += "== System"
$o += "Manufacturer/Model : $($cs.Manufacturer) $($cs.Model)"
$o += "PCSystemType       : $($cs.PCSystemType)  (1=Desktop, 2=Mobile/Laptop)"
$o += "ChassisTypes       : $($enc.ChassisTypes -join ',')  (9/10/14 = laptop/notebook)"
$o += "TotalPhysicalMemory: {0:N1} GB (OS-visible)" -f ($cs.TotalPhysicalMemory/1GB)
$os = Get-CimInstance Win32_OperatingSystem
$o += "Windows            : $($os.Caption) $($os.Version) build $($os.BuildNumber)"
$o += "FreePhysicalMemory : {0:N1} GB" -f ($os.FreePhysicalMemory/1MB)
$o += "== CPU"
Get-CimInstance Win32_Processor | % { $o += "$($_.Name) | cores $($_.NumberOfCores) | threads $($_.NumberOfLogicalProcessors) | max $($_.MaxClockSpeed) MHz" }
$o += "== RAM modules (installed sticks)"
Get-CimInstance Win32_PhysicalMemory | % { $o += "{0} | {1:N0} GB | {2} MT/s | {3} {4}" -f $_.DeviceLocator,($_.Capacity/1GB),$_.ConfiguredClockSpeed,$_.Manufacturer,$_.PartNumber }
Get-CimInstance Win32_PhysicalMemoryArray | % { $o += "Slots: $($_.MemoryDevices) | MaxCapacity: {0:N0} GB" -f ($_.MaxCapacityEx/1MB) }
$o += "== Mainboard"
Get-CimInstance Win32_BaseBoard | % { $o += "$($_.Manufacturer) $($_.Product) $($_.Version)" }
$o += "== GPU (WMI; AdapterRAM caps at 4 GB, use nvidia-smi for the real value)"
Get-CimInstance Win32_VideoController | % { $o += "$($_.Name) | driver $($_.DriverVersion)" }
$o += "== nvidia-smi"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  $o += (nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version,power.limit,pcie.link.gen.max,pcie.link.width.max --format=csv)
  $o += (nvidia-smi | Select-String "CUDA Version")
} else { $o += "nvidia-smi not found" }
$o += "== Disks"
Get-PhysicalDisk | % { $o += "{0} | {1} | {2} | {3:N0} GB | health {4}" -f $_.FriendlyName,$_.MediaType,$_.BusType,($_.Size/1GB),$_.HealthStatus }
Get-Volume | ? DriveLetter | % { $o += "{0}: {1} | free {2:N0} / {3:N0} GB" -f $_.DriveLetter,$_.FileSystemLabel,($_.SizeRemaining/1GB),($_.Size/1GB) }
$o += "== Power/battery (laptop indicator)"
$o += (Get-CimInstance Win32_Battery | Select -ExpandProperty Name)
$o += "== Pagefile"
Get-CimInstance Win32_PageFileUsage | % { $o += "$($_.Name) | alloc $($_.AllocatedBaseSize) MB | peak $($_.PeakUsage) MB" }
$o | Out-File -Encoding utf8 .\hw_inventory.txt
$o
```

**Không xác định được bằng phần mềm** (Dung cần tự kiểm tra): công suất adapter sạc (laptop) hoặc PSU (desktop), RAM hàn trên mainboard hay khe rời, khe M.2 trống, giới hạn TGP thực của GPU laptop (một số máy ghi trong phần mềm của hãng).

## 2. Nguyên tắc chung cho mọi benchmark

- Chạy trên máy Dung, cắm sạc, chế độ điện năng hiệu năng cao, đóng app khác. Ghi lại nhiệt độ GPU (`nvidia-smi -l 1`).
- Mỗi phép đo chạy 3 lần, **bỏ lần đầu** (khởi động lạnh), ghi trung bình và lần tệ nhất. Thời gian load model ghi riêng.
- Đo đỉnh RAM (Task Manager hoặc `Get-Process`), đỉnh VRAM (`nvidia-smi --query-gpu=memory.used --format=csv -lms 500`). Ghi riêng **"Shared GPU memory"** trong Task Manager. Nếu số này tăng thì driver đang tràn VRAM ra RAM, và tốc độ đo được không phải tốc độ thật.
- Mỗi kết quả ghi: phiên bản engine, model, quantization, độ phân giải, số frame, số bước, seed.
- Số liệu của tác giả repo **không** được ghi vào cột "đo trên máy Dung".
- Mọi benchmark chạy **ngoài** app Orchestra (thư mục `bench/` riêng, venv riêng), để không đưa torch/CUDA vào backend.

## 3. TTS benchmark tiếng Việt

### 3.1 Bộ văn bản (10 mục, cố định, lưu `bench/tts/texts.yaml`)

| ID | Loại | Văn bản mẫu |
|---|---|---|
| T1 | Câu ngắn | "Bạn có biết vì sao bầu trời có màu xanh không?" |
| T2 | Đoạn dài (~250 từ) | Một đoạn kể chuyện khoa học, nhiều mệnh đề phụ |
| T3 | Tên riêng | "Nguyễn Thị Minh Khai, Đắk Lắk, Phan Rang–Tháp Chàm, Albert Einstein, Marie Curie" |
| T4 | Ngày tháng, giờ | "Ngày 02/09/1945, lúc 14h30; quý III/2026; thế kỷ XXI" |
| T5 | Số liệu | "1.250.000 đồng; 3,14; 25%; 1/3; 150 km/h; 2.000 m²; −5°C" |
| T6 | Thuật ngữ tiếng Anh | "Mô hình AI dùng GPU NVIDIA và framework PyTorch để chạy deep learning trên laptop" |
| T7 | Câu hỏi | "Nếu Mặt Trời biến mất, sau bao lâu Trái Đất mới tối?" |
| T8 | Câu cảm thán | "Thật không thể tin nổi! Nó lớn gấp một triệu lần Trái Đất!" |
| T9 | Giọng kể chuyện | Đoạn mở đầu một câu chuyện bí ẩn, có ngắt nghỉ |
| T10 | Giọng tin tức | Bản tin 60 giây, nhịp đều |

Thêm **T11 (độ nhất quán)**: một kịch bản 8 phút chia 40 đoạn, sinh toàn bộ, rồi sinh lại riêng đoạn 17. Mục tiêu là kiểm tra giọng có lệch giữa các đoạn và đoạn tạo lại có khớp với phần còn lại không.

### 3.2 Hệ thống cần đo

VieNeu-TTS v3 Turbo (CPU fp32), VieNeu v3 Nano (CPU), ZeroTTS (CPU fp32 và int8). Nếu VRAM cho phép: VieNeu v3 Turbo GPU. Tham chiếu chất lượng (không dùng để sản xuất): một dịch vụ cloud mà Dung đã có tài khoản. Không gọi API trả phí nếu Dung chưa duyệt.

### 3.3 Chỉ số

| Chỉ số | Cách đo |
|---|---|
| Naturalness, Accent, Emotion | Dung nghe mù (file đặt tên ngẫu nhiên), chấm 1–5. Tối thiểu 2 người nghe nếu được. |
| Pronunciation | Đếm lỗi đọc sai trên T3–T6 (từng mục có đáp án đọc đúng) |
| WER tự động | ASR (PhoWhisper-small hoặc faster-whisper small) trên audio, so với văn bản đã chuẩn hóa |
| Voice consistency | T11: nghe chuyển đoạn; tùy chọn độ tương đồng embedding giọng giữa các đoạn |
| RTF | thời gian sinh ÷ độ dài audio |
| Time to first audio | chỉ cho chế độ streaming |
| Peak RAM / VRAM | như mục 2 |

**Ngưỡng đạt đề xuất** (Dung chỉnh): MOS trung bình ≥ 4,0 trên T1, T2, T9, T10; ≤ 1 lỗi đọc trên T3–T6 sau chuẩn hóa; RTF ≤ 1,0 trên CPU; T11 không có chỗ chuyển giọng nghe thấy rõ.

## 4. Image benchmark

- Prompt set: 10 prompt cố định (khoa học, phong cảnh, nhân vật, chữ trên ảnh) + 1 nhân vật tham chiếu xuất hiện trong 5 cảnh.
- Ứng viên trên máy hiện tại: SD 1.5 (512×768, rồi upscale), FLUX.2 [klein] 4B dạng GGUF qua ComfyUI-GGUF. Chỉ thử tiếp khi hai cái đầu chạy: Qwen-Image 4-bit qua Nunchaku có async offload.
- Đo: load time, giây/ảnh, peak VRAM, peak RAM, shared GPU memory, OOM. Chấm chất lượng 1–5 và nhân vật nhất quán 1–5 (người chấm).
- Ngưỡng đề xuất: ≤ 60 giây/ảnh ở 768px cạnh dài; không OOM trong 20 ảnh liên tiếp; chất lượng ≥ 3,5.

## 5. Video benchmark (chỉ khi có GPU ≥ 8 GB)

- 5 prompt I2V + 5 prompt T2V, 3–5 giây, 480p trước rồi 720p.
- Ứng viên theo tầng VRAM: xem bảng 7.3 trong báo cáo chính.
- Đo: thời gian/clip, peak VRAM/RAM, tỉ lệ OOM trong 10 lần, chuyển động (1–5), bám prompt (1–5), giữ nhân vật từ ảnh đầu vào (1–5).
- Trên RTX 3050 4 GB: **không chạy benchmark video**, trừ một phép thử khả thi (CogVideoX-2B với sequential CPU offload, 1 clip) nếu Dung muốn có số đo thực tế để so sánh.

## 6. Render benchmark (FFmpeg)

| Ca | Nội dung |
|---|---|
| R1 | 30 giây 9:16 1080×1920: 6 ảnh có zoom/pan + voice + nhạc ducking + phụ đề ASS |
| R2 | 90 giây 9:16, 15 ảnh |
| R3 | 5 phút 16:9 1920×1080, 40 ảnh, 6 chương |
| R4 | 10 phút 16:9, 80 ảnh |

Mỗi ca render 2 lần: `libx264` (CPU) và `h264_nvenc` (GPU). Đo thời gian, CPU%, RAM, GPU%, kích thước file, rồi chạy QA (ffprobe: codec, fps, độ phân giải, độ dài, AAC 48 kHz; `ebur128` loudness; phụ đề nằm trong thời lượng).

Ngưỡng đề xuất: R2 ≤ 3 phút; R4 ≤ 20 phút; QA pass 100%.

## 7. Phụ đề / ASR benchmark

- Audio: đầu ra TTS của T2, T10, T11 + 1 đoạn giọng thật của Dung.
- Ứng viên: faster-whisper `small` int8 CPU, `medium` int8 CPU; PhoWhisper-small (transformers, CPU).
- Đo: WER, RTF, RAM. Đo độ lệch timestamp của subtitle sinh theo đoạn TTS so với nghe thực tế (lấy mẫu 20 dòng).

## 8. Ghi kết quả

Một file `bench/results/<date>_<machine>.csv`, mỗi dòng một lần chạy, cùng các cột trên. Báo cáo so sánh sinh từ CSV. Kết quả này là căn cứ để chốt stack ở báo cáo chính mục 19.
