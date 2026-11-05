# ADR-0005 — Kịch bản mock trong P0 giới hạn ở 4

**Status:** Accepted · **Date:** 2026-11-05

## Context
RUNTIME §5 liệt kê 10 kịch bản, phần lớn cần tính năng P2-P4.

## Decision
P0 chỉ gồm: (1) giao việc tuần tự giữa Agent, (2) lỗi và quan sát lỗi, (3) tạo metadata artifact, (4) chạy lại cho cùng chuỗi event logic. Các kịch bản parallel, retry, approval, lesson, KPI, 50 agents chuyển sang phase tương ứng.

## Alternatives considered
Làm cả 10 trong P0 (cần kéo P2-P4 vào).

## Consequences
Demo P0 hẹp hơn nhưng trung thực: không giả lập tính năng chưa có.

## Migration / compatibility impact
Không có.
