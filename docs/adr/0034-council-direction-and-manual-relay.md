# ADR-0034 — Định hướng Council, không tự động hóa web của provider, runtime `manual_relay`

**Status:** Proposed · **Date:** 2026-11-11

## Context
- Ngày 2026-11-10 Dung đưa master prompt "AI Council" (Meeting Room nhiều vòng, Response Envelope, Context Builder, dùng tài khoản AI free trên trình duyệt). Audit: `docs/audit/AUDIT_2026-11-10_master_prompt_gap.md`.
- Dung chọn (2026-11-10): Orchestra Studio là **nền tảng**, video là **use case đầu tiên**. Nhánh video (ADR 0028–0033) được giữ lại.
- Điều khoản consumer, đọc ngày 2026-11-10: Anthropic mục 3.4 cấm "crawl, scrape, or otherwise harvest data" và mục 3.7 cấm truy cập "through automated or non-human means"; Google cấm "using automated means to access content"; DeepSeek mục 3.5(3) cấm "capturing, copying any content… using any robots". Điều khoản của OpenAI chưa đọc được từ nguồn gốc. Cả ba điều khoản trên cấm cả việc tự gửi lẫn việc tự đọc câu trả lời.
- Dung chọn (2026-11-11): Dung tự dán prompt; câu trả lời được lấy về bằng cách bấm Copy, không đọc DOM. Form phản hồi phải đơn giản hơn JSON Envelope đầy đủ.

## Decision
1. **Định hướng.** Làm ba engine của master prompt (Response Protocol, Context Builder, Meeting Room) trên backend hiện có. Use case đầu tiên là cuộc họp duyệt kịch bản video. Giai đoạn mới đặt tên `C0…C8` (xem audit §8) để không trùng P0–P5.
2. **Không tự động hóa giao diện web của provider.** Orchestra không tự gửi prompt, không đọc DOM, không dùng computer use để thao tác trên ChatGPT/Gemini/Claude/DeepSeek web. Không nhúng trang có đăng nhập của provider vào app. ADR-0009 giữ nguyên.
3. **Có ba đường truy cập AI:** API trả phí (đã có: Claude, OpenAI), API free tier (Gemini API, Groq, OpenRouter, DeepSeek API; quota đo thực tế, không hardcode), Ollama. Tài khoản web free dùng qua runtime `manual_relay`.
4. **Runtime `manual_relay`.**
   - Run ở trạng thái chờ người (giống `waiting_approval`). UI hiện Context Package và nút "Copy prompt".
   - Mỗi yêu cầu có một **mã ngắn** 4 ký tự (ví dụ `7K2Q`), ánh xạ tới (cuộc họp, vòng, thành viên) hoặc (task, run). Mã dùng một lần.
   - Dung dán prompt vào web chat, rồi bấm nút Copy của câu trả lời (của cả tin nhắn hoặc của khối code).
   - **Theo dõi clipboard:** tiến trình main của Electron đọc clipboard dạng text khoảng 1 giây một lần, **chỉ khi có ít nhất một yêu cầu relay đang chờ**. Nội dung không bắt đầu bằng `#OS <mã đang chờ>` bị bỏ qua và không được lưu. Có nút tắt theo dõi; khi tắt, Dung dán tay vào ô nhập.
   - Trên trình duyệt (không có Electron) chỉ có ô dán tay.
5. **Form phản hồi cho relay (dạng text có nhãn, không phải JSON).** Prompt yêu cầu AI trả lời đúng mẫu sau, nên đặt trong một khối code để có nút Copy:

   ```text
   #OS 7K2Q
   SUMMARY: một đến ba câu tóm tắt
   STANCE: agree | disagree | partial | none
   CONFIDENCE: 0.0–1.0
   ---
   Nội dung tự do (Markdown, dài bao nhiêu cũng được).
   Dòng nào bắt đầu bằng RISK:, DISAGREE:, QUESTION:, FACT:, ASSUMPTION: thì được trích ra.
   ```

   - **Bắt buộc:** dòng `#OS <mã>`, `SUMMARY`, và phần nội dung sau `---`.
   - **Tùy chọn:** `STANCE` (chỉ cần ở vòng phản biện hoặc quyết định), `CONFIDENCE`, các dòng có nhãn.
   - Nhãn viết bằng chữ ASCII in hoa để không phụ thuộc dấu tiếng Việt; nội dung viết bằng ngôn ngữ nào cũng được. Parser không phân biệt hoa thường và bỏ qua khoảng trắng hoặc dấu `**` của Markdown quanh nhãn.
   - Nội dung không được chứa ```` ``` ```` (nó sẽ cắt khối code). Nếu thiếu dấu bọc khối code thì vẫn nhận, vì dòng `#OS` mới là thứ quyết định.
6. **Một mô hình dữ liệu bên trong.** Form relay và output có cấu trúc của API đều được chuẩn hóa vào cùng một Response Envelope nội bộ (JSON Schema, định nghĩa ở C2). Form relay chỉ điền một tập con các trường. Luôn lưu cả bản gốc, bản chuẩn hóa, kết quả kiểm tra và lịch sử sửa.
7. **Khi sai mẫu:** lưu nguyên văn, đánh dấu `needs_fix`, và hiện một tin nhắn "trả lời lại theo mẫu" để Dung copy. Sau 2 lần vẫn sai thì đánh dấu `INVALID_RESPONSE`. Dung có thể chấp nhận thủ công phần nội dung tự do, khi đó bản ghi mang nhãn "người duyệt, không theo mẫu".

## Alternatives considered
- **Tự gửi và tự đọc trên web (bản gốc master prompt §11):** vi phạm điều khoản của ít nhất 3 provider; selector DOM gãy liên tục; phải nhúng trang có đăng nhập. Từ chối.
- **Dung gửi tay, Orchestra đọc DOM:** khó bị phát hiện, nhưng vẫn là scrape theo chữ của điều khoản, vẫn phải bảo trì selector và nhúng trang. Từ chối (Dung đồng ý ngày 2026-11-11).
- **Computer use điều khiển chuột:** vẫn là tự động hóa theo điều khoản; tốn token ảnh chụp màn hình cho mỗi bước. Từ chối.
- **Envelope JSON đầy đủ cho relay:** chatbot free hay hỏng JSON (dấu ngoặc kép, xuống dòng, thiếu trường) và bị ép trả lời ngắn. Từ chối cho relay; vẫn dùng cho API có structured output.

## Consequences
- Mỗi lượt relay tốn của Dung: một lần copy prompt, một lần dán và gửi, một lần bấm Copy câu trả lời. Cuộc họp 3 AI × 2 vòng ≈ 6 lượt như vậy.
- Theo dõi clipboard đọc mọi thứ Dung copy trong lúc có yêu cầu đang chờ. Giảm rủi ro bằng cách chỉ xử lý nội dung có `#OS <mã>` đang chờ, không lưu nội dung khác, có nút tắt, và hiện trạng thái "đang theo dõi clipboard" trên UI.
- Trường trích từ form relay ít hơn API (không có key_points có id, evidence có cấu trúc). Snapshot cuộc họp phải chịu được việc thiếu các trường này.
- Chất lượng tuân thủ mẫu của từng chatbot free chưa đo. Cần đo trong C7 trên 4 provider; nếu một provider thường xuyên sai thì sửa prompt mẫu, không nới parser một cách âm thầm.

## Migration / compatibility impact
Không đổi dữ liệu hiện có. `manual_relay` là runtime mới đăng ký vào registry (ADR-0022). Theo dõi clipboard thêm một kênh IPC chỉ đọc vào preload, cần kiểm tra theo ADR-0009.
