"""Knowledge, search, task summaries, lessons and role-change proposals (ADR-0019, ADR-0020)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from orchestra_backend.agents import service as agents_svc
from orchestra_backend.agents.models import Agent, AgentVersion
from orchestra_backend.agents.schemas import (
    AgentDefinition,
    AgentUpdate,
    AgentVersionCreate,
    RuntimePreference,
)
from orchestra_backend.core.errors import DomainValidationError, InvalidStateError, NotFoundError
from orchestra_backend.core.time import utcnow
from orchestra_backend.events.catalog import (
    KnowledgeChanged,
    KnowledgeRef,
    LessonProposed,
    ReviewDecided,
    RoleChangeProposed,
)
from orchestra_backend.events.service import append_event
from orchestra_backend.execution import service as ex
from orchestra_backend.execution.models import AgentRun, Artifact, Task
from orchestra_backend.knowledge.models import KnowledgeItem, Lesson, RoleChangeProposal
from orchestra_backend.knowledge.schemas import (
    KnowledgeCreate,
    KnowledgeUpdate,
    LessonCreate,
    Review,
    RoleProposalCreate,
    SearchHit,
    SearchResult,
)

SOURCE = "knowledge"


def _checksum(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------- search index ----------


def fts_available(session: Session) -> bool:
    return (
        session.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_fts'")
        ).first()
        is not None
    )


def fold(text_: str) -> str:
    """Lowercase, strip accents and map đ→d, one char to one char (keeps positions).

    FTS5's remove_diacritics does not treat Vietnamese 'đ' as d + diacritic, so
    "thong diep" would not find "thông điệp" without this.
    """
    out = []
    for ch in text_:
        if ch in "đĐ":
            out.append("d")
        else:
            out.append(unicodedata.normalize("NFD", ch)[0].lower())
    return "".join(out)


def _snippet(content: str, terms: list[str], width: int = 70) -> str:
    folded = fold(content)
    pos = min((i for t in terms if (i := folded.find(t)) >= 0), default=0)
    start = max(0, pos - width // 2)
    end = min(len(content), start + width * 2)
    return (
        ("…" if start else "")
        + content[start:end].replace("\n", " ")
        + ("…" if end < len(content) else "")
    )


def _index(session: Session, item: KnowledgeItem) -> None:
    if not fts_available(session):
        return
    session.execute(text("DELETE FROM knowledge_fts WHERE item_id = :id"), {"id": str(item.id)})
    if item.status == "active":
        session.execute(
            text(
                "INSERT INTO knowledge_fts(item_id, company_id, title, content) "
                "VALUES (:id, :cid, :title, :content)"
            ),
            {
                "id": str(item.id),
                "cid": str(item.company_id),
                "title": fold(item.title),
                "content": fold(item.content),
            },
        )


def _fts_query(q: str) -> str:
    """Turn user text into a safe FTS5 query: quoted prefix terms joined by AND."""
    words = re.findall(r"\w+", fold(q), flags=re.UNICODE)
    return " ".join(f'"{w}"*' for w in words[:12])


def search(session: Session, company_id: uuid.UUID, q: str, limit: int = 20) -> SearchResult:
    q = q.strip()
    if not q:
        return SearchResult(engine="fts5" if fts_available(session) else "like", hits=[])
    if fts_available(session):
        query = _fts_query(q)
        if not query:
            return SearchResult(engine="fts5", hits=[])
        rows = session.execute(
            text(
                "SELECT item_id FROM knowledge_fts "
                "WHERE knowledge_fts MATCH :q AND company_id = :cid ORDER BY rank LIMIT :lim"
            ),
            {"q": query, "cid": str(company_id), "lim": limit},
        ).all()
        terms = re.findall(r"\w+", fold(q), flags=re.UNICODE)
        hits = []
        for (item_id,) in rows:
            item = session.get(KnowledgeItem, uuid.UUID(item_id))
            if item is not None and item.status == "active":
                hits.append(_hit(item, _snippet(item.content, terms)))
        return SearchResult(engine="fts5", hits=hits)
    # Fallback without FTS5: fold in Python so accents/đ behave like the FTS path.
    terms = re.findall(r"\w+", fold(q), flags=re.UNICODE)
    items = session.scalars(
        select(KnowledgeItem)
        .where(KnowledgeItem.company_id == company_id, KnowledgeItem.status == "active")
        .order_by(KnowledgeItem.updated_at.desc())
    )
    hits = [
        _hit(i, _snippet(i.content, terms))
        for i in items
        if all(t in fold(i.title + " " + i.content) for t in terms)
    ][:limit]
    return SearchResult(engine="like", hits=hits)


def _hit(item: KnowledgeItem, snippet: str) -> SearchHit:
    return SearchHit(
        id=item.id,
        title=item.title,
        kind=item.kind,  # type: ignore[arg-type]
        source_type=item.source_type,  # type: ignore[arg-type]
        source_id=item.source_id,
        snippet=snippet,
    )


# ---------- items ----------


def _create(
    session: Session,
    company_id: uuid.UUID,
    *,
    title: str,
    content: str,
    kind: str,
    source_type: str,
    source_id: str | None,
    created_by: str,
    metadata: dict[str, Any] | None = None,
) -> KnowledgeItem:
    if source_type != "manual" and not source_id:
        raise DomainValidationError("Knowledge from a source must keep its source id")
    item = KnowledgeItem(
        company_id=company_id,
        title=title.strip(),
        content=content,
        kind=kind,
        source_type=source_type,
        source_id=source_id,
        created_by=created_by,
        metadata_json=metadata or {},
    )
    session.add(item)
    session.flush()
    _index(session, item)
    append_event(
        session,
        company_id=company_id,
        event_type="knowledge.created",
        source=SOURCE,
        payload=_changed(item),
    )
    return item


def _changed(item: KnowledgeItem) -> KnowledgeChanged:
    return KnowledgeChanged(
        item_id=item.id,
        title=item.title,
        kind=item.kind,
        source_type=item.source_type,
        source_id=item.source_id,
        version=item.version,
        content_checksum=_checksum(item.content),
    )


def create_note(session: Session, company_id: uuid.UUID, data: KnowledgeCreate) -> KnowledgeItem:
    if data.kind in {"summary", "lesson"}:
        raise DomainValidationError("Summaries and lessons come from tasks and lesson reviews")
    return _create(
        session,
        company_id,
        title=data.title,
        content=data.content,
        kind=data.kind,
        source_type="manual",
        source_id=None,
        created_by="user",
    )


def get_item(session: Session, item_id: uuid.UUID) -> KnowledgeItem:
    item = session.get(KnowledgeItem, item_id)
    if item is None:
        raise NotFoundError("Knowledge item not found")
    return item


def list_items(session: Session, company_id: uuid.UUID) -> list[KnowledgeItem]:
    return list(
        session.scalars(
            select(KnowledgeItem)
            .where(KnowledgeItem.company_id == company_id, KnowledgeItem.status == "active")
            .order_by(KnowledgeItem.updated_at.desc())
        )
    )


def update_item(session: Session, item_id: uuid.UUID, data: KnowledgeUpdate) -> KnowledgeItem:
    item = get_item(session, item_id)
    if item.status != "active":
        raise InvalidStateError("Knowledge item is archived")
    changed = False
    if data.title is not None and data.title.strip() != item.title:
        item.title, changed = data.title.strip(), True
    if data.content is not None and data.content != item.content:
        item.content, changed = data.content, True
    if changed:
        item.version += 1
        session.flush()
        _index(session, item)
        append_event(
            session,
            company_id=item.company_id,
            event_type="knowledge.updated",
            source=SOURCE,
            payload=_changed(item),
        )
    return item


def archive_item(session: Session, item_id: uuid.UUID) -> KnowledgeItem:
    item = get_item(session, item_id)
    if item.status == "archived":
        raise InvalidStateError("Knowledge item is already archived")
    item.status = "archived"
    session.flush()
    _index(session, item)
    append_event(
        session,
        company_id=item.company_id,
        event_type="knowledge.archived",
        source=SOURCE,
        payload=KnowledgeRef(item_id=item.id),
    )
    return item


def import_artifact(
    session: Session, artifact: Artifact, content: str, title: str | None = None
) -> KnowledgeItem:
    return _create(
        session,
        artifact.company_id,
        title=title or artifact.name,
        content=content,
        kind="document",
        source_type="artifact",
        source_id=str(artifact.id),
        created_by="user",
        metadata={"artifact_checksum": artifact.checksum, "run_id": str(artifact.run_id)},
    )


# ---------- task summary (Secretary, deterministic) ----------


def summarize_task(session: Session, task_id: uuid.UUID) -> KnowledgeItem:
    root = ex.get_task(session, task_id)
    if root.status not in {"completed", "failed", "cancelled"}:
        raise InvalidStateError("Summaries are made after the task has finished")
    tasks = [root, *ex.descendants(session, root)]
    lines = [
        f"# Tóm tắt: {root.title}",
        "",
        "_Tóm tắt tự động từ dữ liệu task/run, không dùng AI._",
        "",
        f"- Trạng thái: {root.status}",
        f"- Số task: {len(tasks)}",
        "",
        "## Diễn biến",
    ]
    for t in tasks:
        agent = session.get(Agent, t.assigned_agent_id) if t.assigned_agent_id else None
        runs = ex.list_runs(session, t.company_id, task_id=t.id)
        last = runs[0] if runs else None
        outcome = (
            last.result_summary
            if last and last.status == "completed"
            else (f"{last.error_code}: {last.error_summary}" if last and last.error_code else "")
        )
        who = agent.name if agent else (t.required_role or "?")
        attempts = f" · {len(runs)} lần chạy" if len(runs) > 1 else ""
        lines.append(f"- **{t.title}** ({who}) — {t.status}{attempts}. {outcome or ''}".rstrip())
    artifacts = list(
        session.scalars(
            select(Artifact)
            .where(Artifact.task_id.in_([t.id for t in tasks]))
            .order_by(Artifact.created_at)
        )
    )
    if artifacts:
        lines += ["", "## Artifact", *[f"- {a.name} ({a.size_bytes} byte)" for a in artifacts]]
    return _create(
        session,
        root.company_id,
        title=f"Tóm tắt: {root.title}",
        content="\n".join(lines),
        kind="summary",
        source_type="task_summary",
        source_id=str(root.id),
        created_by="secretary:deterministic",
    )


# ---------- lessons ----------


def propose_lesson(
    session: Session,
    company_id: uuid.UUID,
    data: LessonCreate,
    proposed_by: str,
    source_run_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> Lesson:
    if data.source_task_id is not None:
        t = ex.get_task(session, data.source_task_id)
        if t.company_id != company_id:
            raise DomainValidationError("Task belongs to another company")
    lesson = Lesson(
        company_id=company_id,
        title=data.title.strip(),
        lesson=data.lesson.strip(),
        source_task_id=data.source_task_id,
        source_run_id=source_run_id,
        proposed_by=proposed_by,
    )
    session.add(lesson)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="lesson.proposed",
        source=SOURCE if proposed_by == "user" else "orchestrator",
        run_id=source_run_id,
        correlation_id=correlation_id,
        payload=LessonProposed(lesson_id=lesson.id, title=lesson.title, proposed_by=proposed_by),
    )
    return lesson


def list_lessons(session: Session, company_id: uuid.UUID) -> list[Lesson]:
    return list(
        session.scalars(
            select(Lesson).where(Lesson.company_id == company_id).order_by(Lesson.created_at.desc())
        )
    )


def review_lesson(session: Session, lesson_id: uuid.UUID, data: Review) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFoundError("Lesson not found")
    if lesson.review_status != "proposed":
        raise InvalidStateError("Lesson was already reviewed")
    lesson.review_status = "approved" if data.decision == "approve" else "rejected"
    lesson.review_note = data.note or None
    lesson.reviewed_at = utcnow()
    if lesson.review_status == "approved":
        item = _create(
            session,
            lesson.company_id,
            title=lesson.title,
            content=lesson.lesson,
            kind="lesson",
            source_type="lesson",
            source_id=str(lesson.id),
            created_by="user",
            metadata={
                "proposed_by": lesson.proposed_by,
                "source_task_id": str(lesson.source_task_id) if lesson.source_task_id else None,
            },
        )
        lesson.knowledge_item_id = item.id
    append_event(
        session,
        company_id=lesson.company_id,
        event_type="lesson.reviewed",
        source="api.knowledge",
        payload=ReviewDecided(
            id=lesson.id, status=lesson.review_status, knowledge_item_id=lesson.knowledge_item_id
        ),
    )
    return lesson


# ---------- role-change proposals ----------


def propose_role_change(
    session: Session,
    company_id: uuid.UUID,
    data: RoleProposalCreate,
    proposed_by: str,
    source_run_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> RoleChangeProposal:
    agent = agents_svc.get_agent(session, data.agent_id)
    if agent.company_id != company_id:
        raise DomainValidationError("Agent belongs to another company")
    if agent.status == "archived":
        raise InvalidStateError("Agent is archived")
    changes = data.changes.model_dump(mode="json", exclude_unset=True)
    p = RoleChangeProposal(
        company_id=company_id,
        agent_id=agent.id,
        changes_json=changes,
        rationale=data.rationale,
        proposed_by=proposed_by,
        source_run_id=source_run_id,
    )
    session.add(p)
    session.flush()
    append_event(
        session,
        company_id=company_id,
        event_type="role_change.proposed",
        source="api.knowledge" if proposed_by == "user" else "orchestrator",
        run_id=source_run_id,
        correlation_id=correlation_id,
        payload=RoleChangeProposed(
            proposal_id=p.id, agent_id=agent.id, changes=changes, proposed_by=proposed_by
        ),
    )
    return p


def list_role_proposals(session: Session, company_id: uuid.UUID) -> list[RoleChangeProposal]:
    return list(
        session.scalars(
            select(RoleChangeProposal)
            .where(RoleChangeProposal.company_id == company_id)
            .order_by(RoleChangeProposal.created_at.desc())
        )
    )


def review_role_change(
    session: Session, proposal_id: uuid.UUID, data: Review, known_runtimes: set[str]
) -> RoleChangeProposal:
    p = session.get(RoleChangeProposal, proposal_id)
    if p is None:
        raise NotFoundError("Proposal not found")
    if p.status != "proposed":
        raise InvalidStateError("Proposal was already reviewed")
    if data.decision == "approve":
        changes = dict(p.changes_json)
        instructions = changes.pop("instructions", None)
        if changes:
            # Same validation as a manual edit (cycles, departments, archived agents).
            agents_svc.update_agent(session, p.agent_id, AgentUpdate.model_validate(changes))
        if instructions is not None:
            agent = agents_svc.get_agent(session, p.agent_id)
            current = session.get(AgentVersion, agent.current_version_id)
            assert current is not None
            definition = AgentDefinition.model_validate(current.definition_json)
            definition.instructions = instructions
            agents_svc.create_version(
                session,
                agent.id,
                AgentVersionCreate(
                    definition=definition,
                    runtime=RuntimePreference.model_validate(current.runtime_preference_json),
                ),
                known_runtimes,
            )
        p.status = "approved"
    else:
        p.status = "rejected"
    p.review_note = data.note or None
    p.reviewed_at = utcnow()
    append_event(
        session,
        company_id=p.company_id,
        event_type="role_change.reviewed",
        source="api.knowledge",
        payload=ReviewDecided(id=p.id, status=p.status),
    )
    return p


# ---------- runtime-originated proposals (resolved by role names) ----------


def resolve_runtime_role_change(
    session: Session, run: AgentRun, target_role: str, changes: dict[str, Any]
) -> RoleProposalCreate:
    agent = ex.find_agent_for_role(session, run.company_id, target_role)
    if agent is None:
        raise DomainValidationError(f"No active agent with role {target_role}")
    out: dict[str, Any] = {}
    if changes.get("role"):
        out["role"] = changes["role"]
    if changes.get("instructions"):
        out["instructions"] = changes["instructions"]
    if changes.get("reports_to_role"):
        mgr = ex.find_agent_for_role(session, run.company_id, changes["reports_to_role"])
        if mgr is None:
            raise DomainValidationError(f"No active agent with role {changes['reports_to_role']}")
        out["reports_to_agent_id"] = mgr.id
    if changes.get("department"):
        from orchestra_backend.organization.models import Department

        dept = session.scalar(
            select(Department).where(
                Department.company_id == run.company_id,
                Department.name == changes["department"],
                Department.status == "active",
            )
        )
        if dept is None:
            raise DomainValidationError(f"No department named {changes['department']}")
        out["department_id"] = dept.id
    return RoleProposalCreate.model_validate({"agent_id": agent.id, "changes": out})


def task_of_run(session: Session, run: AgentRun) -> Task | None:
    return session.get(Task, run.task_id) if run.task_id else None
