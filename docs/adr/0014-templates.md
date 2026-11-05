# ADR-0014 — Template YAML trong repo

**Status:** Accepted · **Date:** 2026-11-05

## Context
Cần tạo nhanh tổ chức và agent theo mẫu, có version.

## Decision
templates/company/*.yaml (company + departments + agents + skills + tools + grants) và templates/agent/*.yaml (preset vai trò). Tạo qua API, đi qua đúng domain service và phát event như thao tác tay. Demo Video Studio chuyển thành template; /demo/seed gọi template này để tương thích.

## Alternatives considered
Template trong DB (sửa trên UI nhưng mất version Git).

## Consequences
Template sai định dạng bị từ chối khi nạp (validate bằng Pydantic). Department template chưa làm.

## Migration / compatibility impact
Không có.
