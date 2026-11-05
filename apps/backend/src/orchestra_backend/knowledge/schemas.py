from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orchestra_backend.knowledge.models import MAX_CONTENT

Kind = Literal["note", "document", "summary", "lesson"]
SourceType = Literal["manual", "artifact", "task_summary", "lesson"]


class KnowledgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=MAX_CONTENT)
    kind: Kind = "note"


class KnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT)


class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    content: str
    kind: Kind
    source_type: SourceType
    source_id: str | None
    created_by: str
    version: int
    status: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SearchHit(BaseModel):
    id: uuid.UUID
    title: str
    kind: Kind
    source_type: SourceType
    source_id: str | None
    snippet: str


class SearchResult(BaseModel):
    engine: Literal["fts5", "like"]
    hits: list[SearchHit]


class LessonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    lesson: str = Field(min_length=1, max_length=4000)
    source_task_id: uuid.UUID | None = None


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    lesson: str
    source_task_id: uuid.UUID | None
    source_run_id: uuid.UUID | None
    proposed_by: str
    review_status: Literal["proposed", "approved", "rejected"]
    review_note: str | None
    reviewed_at: datetime | None
    knowledge_item_id: uuid.UUID | None
    created_at: datetime


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2000)


class RoleChanges(BaseModel):
    """Explicit null clears department/manager; omitted fields are unchanged."""

    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(default=None, min_length=1, max_length=100)
    department_id: uuid.UUID | None = None
    reports_to_agent_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, min_length=1, max_length=20000)

    @model_validator(mode="after")
    def _not_empty(self) -> RoleChanges:
        if not self.model_fields_set:
            raise ValueError("at least one change is required")
        return self


class RoleProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: uuid.UUID
    changes: RoleChanges
    rationale: str = Field(default="", max_length=2000)


class RoleProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    agent_id: uuid.UUID
    changes_json: dict[str, Any]
    rationale: str
    proposed_by: str
    source_run_id: uuid.UUID | None
    status: Literal["proposed", "approved", "rejected"]
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
