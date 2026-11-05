from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ApprovalStatus = Literal["pending", "approved", "rejected", "expired", "cancelled"]


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    run_id: uuid.UUID | None
    task_id: uuid.UUID | None
    requested_by_agent_id: uuid.UUID | None
    tool_id: uuid.UUID | None
    action_type: str
    request_json: dict[str, Any]
    checksum: str
    required_level: int
    status: ApprovalStatus
    decided_by: str | None
    decision_note: str | None
    decided_at: datetime | None
    execution_status: str | None
    result_json: dict[str, Any] | None
    executed_at: datetime | None
    created_at: datetime


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    # Must equal the checksum the user was shown (binds the decision to the payload).
    checksum: str = Field(min_length=10, max_length=100)
    note: str = Field(default="", max_length=2000)
