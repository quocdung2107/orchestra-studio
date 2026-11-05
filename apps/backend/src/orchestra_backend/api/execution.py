from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from orchestra_backend.agents.models import Agent
from orchestra_backend.api.deps import ContainerDep
from orchestra_backend.companies.schemas import CompanyOut
from orchestra_backend.companies.service import get_company
from orchestra_backend.core.errors import ErrorResponse
from orchestra_backend.demo.seed import seed_demo_company
from orchestra_backend.execution import service as ex
from orchestra_backend.execution.models import Task
from orchestra_backend.execution.schemas import ArtifactOut, RunDetail, RunOut, TaskOut
from orchestra_backend.runtime.mock.scenarios import load_all

router = APIRouter(
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)


# ----- runtimes & scenarios -----


class RuntimeInfo(BaseModel):
    runtime_id: str
    display_name: str
    capabilities: dict[str, bool]


class ScenarioInfo(BaseModel):
    id: str
    name: str
    description: str
    entry_role: str


class ScenarioStartedOut(BaseModel):
    root_task_id: uuid.UUID


@router.get("/runtimes", response_model=list[RuntimeInfo], tags=["runtime"])
def list_runtimes(c: ContainerDep) -> list[RuntimeInfo]:
    return [
        RuntimeInfo(
            runtime_id=r.runtime_id,
            display_name=r.display_name,
            capabilities=r.capabilities.as_dict(),
        )
        for r in c.extras["registry"].all()
    ]


@router.get("/scenarios", response_model=list[ScenarioInfo], tags=["runtime"])
def list_scenarios() -> list[ScenarioInfo]:
    return [
        ScenarioInfo(id=s.id, name=s.name, description=s.description, entry_role=s.entry.role)
        for s in load_all().values()
    ]


@router.post(
    "/companies/{company_id}/scenarios/{scenario_id}/start",
    response_model=ScenarioStartedOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["runtime"],
)
async def start_scenario(
    c: ContainerDep, company_id: uuid.UUID, scenario_id: str
) -> ScenarioStartedOut:
    root = await c.orchestrator.start_scenario(company_id, scenario_id)
    return ScenarioStartedOut(root_task_id=root)


@router.post(
    "/demo/seed", response_model=CompanyOut, status_code=status.HTTP_201_CREATED, tags=["demo"]
)
def seed_demo(c: ContainerDep) -> CompanyOut:
    with c.tx() as s:
        return CompanyOut.model_validate(
            seed_demo_company(s, c.settings.templates_dir, c.extras["registry"].ids())
        )


# ----- tasks -----


@router.get("/companies/{company_id}/tasks", response_model=list[TaskOut], tags=["tasks"])
def list_tasks(c: ContainerDep, company_id: uuid.UUID) -> list[TaskOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [TaskOut.model_validate(t) for t in ex.list_tasks(s, company_id)]


@router.get("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def get_task(c: ContainerDep, task_id: uuid.UUID) -> TaskOut:
    with c.tx() as s:
        return TaskOut.model_validate(ex.get_task(s, task_id))


# ----- runs -----


@router.get("/companies/{company_id}/runs", response_model=list[RunOut], tags=["runs"])
def list_runs(
    c: ContainerDep,
    company_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
) -> list[RunOut]:
    with c.tx() as s:
        get_company(s, company_id)
        return [
            RunOut.model_validate(r)
            for r in ex.list_runs(s, company_id, task_id=task_id, agent_id=agent_id)
        ]


@router.get("/runs/{run_id}", response_model=RunDetail, tags=["runs"])
def get_run(c: ContainerDep, run_id: uuid.UUID) -> RunDetail:
    with c.tx() as s:
        run = ex.get_run(s, run_id)
        agent = s.get(Agent, run.agent_id)
        task = s.get(Task, run.task_id) if run.task_id else None
        return RunDetail(
            **RunOut.model_validate(run).model_dump(),
            task=TaskOut.model_validate(task) if task else None,
            agent_name=agent.name if agent else "?",
            agent_role=agent.role if agent else "?",
            artifacts=[ArtifactOut.model_validate(a) for a in ex.list_artifacts_for_run(s, run.id)],
        )


# ----- artifacts -----


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut, tags=["artifacts"])
def get_artifact(c: ContainerDep, artifact_id: uuid.UUID) -> ArtifactOut:
    with c.tx() as s:
        return ArtifactOut.model_validate(ex.get_artifact(s, artifact_id))


@router.get(
    "/artifacts/{artifact_id}/content",
    tags=["artifacts"],
    response_class=Response,
    responses={200: {"content": {"text/plain": {}}}},
)
def get_artifact_content(c: ContainerDep, artifact_id: uuid.UUID) -> Response:
    with c.tx() as s:
        artifact = ex.get_artifact(s, artifact_id)
    data = ex.read_artifact(artifact, c.settings.artifacts_dir)
    return Response(
        content=data,
        media_type=f"{artifact.mime_type}; charset=utf-8",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{artifact.id}.txt"',
        },
    )
