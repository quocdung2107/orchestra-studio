# ADR-0003 — Contract: OpenAPI của FastAPI là nguồn duy nhất, sinh type TypeScript

**Status:** Accepted · **Date:** 2026-11-05

## Context
Cần chia sẻ schema giữa Python và TypeScript mà không viết hai lần.

## Decision
Pydantic model trong backend là nguồn sự thật. OpenAPI xuất từ FastAPI và commit vào repo; TS type sinh bằng openapi-typescript. Event payload là Pydantic model, xuất JSON Schema. Có kiểm tra trong test/CI rằng file sinh ra khớp với code.

## Alternatives considered
Viết type TS bằng tay (dễ lệch); JSON Schema viết tay rồi sinh cả hai phía (tốn công).

## Consequences
Đổi API → phải chạy lệnh sinh lại type. packages/contracts chứa file sinh ra.

## Migration / compatibility impact
Không có.
