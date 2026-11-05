# ADR-0012 — Skill có version, agent ghim version

**Status:** Accepted · **Date:** 2026-11-05

## Context
Skill thay đổi không được làm agent đổi hành vi ngầm.

## Decision
skills + skill_versions (instructions, input_hints). agent_skills ghim skill_version_id. Version mới không tự cập nhật agent; người dùng chủ động đổi. Trường definition.skills/tools (danh sách chuỗi) trong Agent Definition được giữ để tương thích nhưng không dùng nữa.

## Alternatives considered
Skill không version (đơn giản nhưng mất khả năng audit).

## Consequences
Cần thao tác nâng version cho từng agent.

## Migration / compatibility impact
Migration 0003.
