# ADR-0001 — Thứ tự P0: React trên trình duyệt trước, Electron cuối P0

**Status:** Accepted · **Date:** 2026-11-05

## Context
Electron là phần tốn công nhất của P0 nhưng không phải giá trị cốt lõi. Developer có ~1 giờ/ngày. Renderer đã được thiết kế không phụ thuộc Node.

## Decision
Phát triển React (Vite) chạy trên trình duyệt, gọi FastAPI qua HTTP. Bọc Electron ở task cuối của P0. Renderer không được dùng API nào chỉ có trong Electron cho tới khi có preload.

## Alternatives considered
Electron ngay từ P0-04 (baseline cũ): kiểm tra bảo mật Electron sớm hơn, nhưng chậm thấy kết quả và tăng tải ban đầu.

## Consequences
Thấy kết quả sớm hơn; dev loop nhanh hơn. Rủi ro: vấn đề tích hợp Electron (khởi động backend, CSP) phát hiện muộn, chấp nhận vì đã có task riêng cuối P0.

## Migration / compatibility impact
Không có. Renderer giữ nguyên khi bọc Electron.
