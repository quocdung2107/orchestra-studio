# ADR-0002 — Công cụ: uv cho Python, pnpm workspaces cho Node

**Status:** Accepted · **Date:** 2026-11-05

## Context
Cần môi trường tái lập được trên Windows, ít dependency, nhanh.

## Decision
Python dùng uv (pyproject.toml + uv.lock). Node dùng pnpm workspaces (pnpm-lock.yaml). Không dùng Turborepo/Nx. Script trong package.json phải đa nền tảng (không dùng cú pháp bash).

## Alternatives considered
pip+venv (chậm, không lock chuẩn), poetry (chậm hơn uv); npm workspaces (đủ dùng nhưng chậm, node_modules lớn); Turborepo/Nx (thừa cho 1 người).

## Consequences
Developer cần cài uv và pnpm (qua corepack). Hướng dẫn cài đặt Windows ghi trong README.

## Migration / compatibility impact
Có thể đổi sang công cụ khác nếu cần; lock file sẽ phải tạo lại.
