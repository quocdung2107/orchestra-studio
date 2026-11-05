# ADR-0019 — Tri thức có nguồn gốc, tìm kiếm FTS5

**Status:** Accepted · **Date:** 2026-11-05

## Decision
- `knowledge_items`: title, content (≤ 100 KB), kind (`note`, `document`, `summary`, `lesson`), `source_type` (`manual`, `artifact`, `task_summary`, `lesson`), `source_id` (bắt buộc trừ `manual`), `created_by`, `version`, `status` (active/archived).
- Tìm kiếm: bảng ảo FTS5 `knowledge_fts` (tokenizer `unicode61 remove_diacritics 2`), cập nhật trong cùng transaction. Không có FTS5 thì LIKE.
- Tóm tắt task: tất định từ cây task/run/artifact, gắn nhãn "tự động, không dùng AI".

## Alternatives
Vector search (cần embedding, để P4).
