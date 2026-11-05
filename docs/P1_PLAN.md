# P1 PLAN — Organization & Agent Manager

**Version:** 0.1 (bản nháp, chờ Dung duyệt) · **Date:** 2026-11-05
**Phạm vi gốc:** `IMPLEMENTATION_PLAN.md` §2 (P1): Org Builder, templates, versions, skills, tools.
**Tiêu chí gốc (§5):** sơ đồ tổ chức lưu được, sửa được, có kiểm tra hợp lệ; skill và tool có version và gắn quyền.

## 0. Mục tiêu P1 trong một câu

Người dùng dựng và chỉnh tổ chức AI trực quan (phòng ban, ai báo cáo cho ai, agent dùng skill/tool nào với quyền gì), tạo nhanh từ template, và mọi thay đổi có version và event, nhưng **chưa thực thi tool thật** (đó là P2).

## 1. Quyết định cần chốt (ADR đề xuất)

| ADR | Câu hỏi | Đề xuất | Lý do |
|---|---|---|---|
| 0010 | Mô hình tổ chức | Bảng `departments` dạng cây (`parent_department_id`), thêm `agents.department_id`. Quan hệ báo cáo vẫn là `reports_to_agent_id`. Backend chặn vòng lặp, chặn liên kết khác company. | Đúng DATABASE.md, không thêm khái niệm mới. |
| 0011 | Org Builder | Dùng `@xyflow/react` (đã có trong baseline). Graph chỉ là **cách hiển thị**; mỗi thao tác kéo/nối gửi một command lên API, UI vẽ lại theo kết quả backend. Vị trí node lưu trong bảng `org_layouts` (chỉ là dữ liệu giao diện, không phải nghiệp vụ). | Giữ nguyên tắc backend là source of truth. |
| 0012 | Skill | Skill = định nghĩa có version (tên, mô tả, hướng dẫn markdown, đầu vào gợi ý). Agent gắn skill **ghim một version cụ thể**; skill ra version mới không tự đổi hành vi agent. | Tránh thay đổi ngầm; dễ audit. |
| 0013 | Tool và quyền | Tool khai báo đủ trường theo SECURITY.md §5 (schema, mức L0–L3, phạm vi, timeout, cần duyệt hay không). P1 chỉ **khai báo và cấp quyền**, chưa chạy. Quyền theo tầng: company đặt mức trần, department không vượt company, agent không vượt department. Mặc định từ chối. L3 luôn cần phê duyệt (thực thi ở P2). | Có mô hình quyền trước khi có thực thi; không để agent tự cấp quyền. |
| 0014 | Template | Template là file YAML trong `templates/` (version bằng Git), tạo company/department/agent qua API. Demo Video Studio chuyển thành template đầu tiên thay cho code seed. | Đúng ARCHITECTURE §6; template đọc được, sửa được bằng tay. |

## 2. Danh sách task (ước lượng theo buổi 1 giờ)

| ID | Task | Buổi |
|---|---|---|
| H1 | Departments: model, migration, API CRUD, kiểm tra cây không vòng lặp, event | 2 |
| H2 | Gán agent vào department, đổi người quản lý (reports_to) có kiểm tra vòng lặp | 1–2 |
| H3 | API "org graph" trả cây department + agent + cạnh báo cáo; bảng `org_layouts` | 1–2 |
| H4 | Org Builder UI (xyflow): xem graph, kéo thả lưu vị trí | 2–3 |
| H5 | Org Builder: tạo/sửa department, nối agent ↔ manager, báo lỗi hợp lệ từ backend | 2–3 |
| I1 | Skills: model có version, API, gắn skill vào agent (ghim version) | 2 |
| I2 | Tools: khai báo tool + policy, API, event | 2 |
| I3 | Quyền theo tầng company → department → agent, mặc định từ chối, test | 2–3 |
| I4 | UI Skills & Tools: danh sách, tạo version, cấp/thu quyền trong Inspector | 2–3 |
| J1 | Agent Manager: sửa định nghĩa → tạo version mới, xem khác biệt giữa 2 version | 2 |
| J2 | Templates YAML + API tạo từ template; chuyển Demo Video Studio sang template | 2 |
| J3 | UI tạo company/department/agent từ template | 1–2 |
| K1 | Kiểm tra P1 acceptance trên Windows, cập nhật README/ADR | 1–2 |
| | **Tổng** | **22–31** |

Thứ tự: H (tổ chức) → I (skill/tool/quyền) → J (version, template) → K.
Điểm có kết quả nhìn thấy sớm nhất: sau H4 (~6 buổi) đã thấy sơ đồ tổ chức.

## 3. Ngoài phạm vi P1 (cố ý)

- Thực thi tool thật, Tool Gateway, sandbox → P2.
- Approval flow → P2.
- Kéo thả để tạo workflow/DAG task → không làm (ARCHITECTURE §1 non-goal).
- Marketplace skill, chia sẻ template ra ngoài.

## 4. Rủi ro

- [I] Org Builder là phần UI nặng nhất từ trước tới giờ; xyflow tốt nhưng phần tương tác (nối cạnh, báo lỗi) dễ tốn thời gian hơn ước tính.
- [I] Mô hình quyền 3 tầng dễ phình to. P1 chỉ làm "mức trần" theo L0–L3 + danh sách tool được cấp, chưa làm phạm vi file/domain chi tiết.

## 5. Cách làm

Giống P0: code liền, commit thẳng lên `main` theo nhóm task, CI Windows phải xanh, cuối P1 kiểm tra trên máy Windows của Dung.
