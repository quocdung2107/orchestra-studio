"""Demo Video Studio organization (RUNTIME.md §5). Real records, created via domain services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from orchestra_backend.agents import service as agents
from orchestra_backend.agents.schemas import AgentCreate, AgentDefinition, RuntimePreference
from orchestra_backend.companies.models import Company
from orchestra_backend.companies.schemas import CompanyCreate
from orchestra_backend.companies.service import create_company

# (role, name, reports_to_role, instructions)
DEMO_AGENTS: list[tuple[str, str, str | None, str]] = [
    ("CEO", "An (CEO)", None, "Chia mục tiêu thành việc cho các bộ phận và chốt kết quả."),
    ("CMO", "Bình (CMO)", "CEO", "Chịu trách nhiệm thông điệp và khán giả."),
    ("Researcher", "Chi (Researcher)", "CMO", "Thu thập và tóm tắt dữ liệu có nguồn."),
    ("Strategist", "Dũng (Strategist)", "CMO", "Đề xuất và so sánh phương án thông điệp."),
    ("Producer", "Em (Producer)", "CEO", "Điều phối sản xuất nội dung."),
    ("Scriptwriter", "Giang (Scriptwriter)", "Producer", "Viết kịch bản theo thông điệp."),
    ("Reviewer", "Hà (Reviewer)", "Producer", "Duyệt nội dung theo tiêu chí rõ ràng."),
    ("Secretary", "Khánh (Secretary)", "CEO", "Tổng hợp kết quả và bài học."),
]


def seed_demo_company(session: Session, known_runtimes: set[str]) -> Company:
    company = create_company(
        session,
        CompanyCreate(
            name="Demo Video Studio",
            description="Tổ chức mẫu chạy bằng Mock Runtime (không gọi AI, không cần API key).",
        ),
    )
    by_role: dict[str, object] = {}
    for role, name, manager_role, instructions in DEMO_AGENTS:
        manager = by_role.get(manager_role) if manager_role else None
        agent = agents.create_agent(
            session,
            company.id,
            AgentCreate(
                name=name,
                role=role,
                reports_to_agent_id=getattr(manager, "id", None),
                definition=AgentDefinition(instructions=instructions),
                runtime=RuntimePreference(runtime_id="mock"),
            ),
            known_runtimes,
            created_by="seed",
        )
        agents.transition(session, agent.id, "activate")
        by_role[role] = agent
    return company
