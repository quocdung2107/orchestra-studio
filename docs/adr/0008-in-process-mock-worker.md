# ADR-0008 — Mock runtime chạy trong process backend ở P0

**Status:** Accepted · **Date:** 2026-11-05

## Context
Kiến trúc có Worker Process riêng, nhưng P0 chỉ có mock không chạy code ngoài.

## Decision
Mock runtime chạy như asyncio task trong process backend, sau interface AgentRuntime. Không có IPC worker trong P0. Tách worker process khi có Local Python Runtime hoặc runtime chạy code/model.

## Alternatives considered
Worker process riêng ngay (tốn công IPC, giám sát process trên Windows).

## Consequences
Ranh giới giữ bằng interface; runtime vẫn không được ghi DB trực tiếp mà trả event cho runtime manager.

## Migration / compatibility impact
Thêm transport worker sau mà không đổi interface AgentRuntime.
