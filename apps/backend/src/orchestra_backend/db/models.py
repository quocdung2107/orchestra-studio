"""Import every ORM model so Base.metadata is complete (Alembic, tests)."""

from orchestra_backend.agents.models import Agent, AgentVersion  # noqa: F401
from orchestra_backend.approvals.models import Approval  # noqa: F401
from orchestra_backend.capabilities.models import (  # noqa: F401
    AgentSkill,
    AgentTool,
    Skill,
    SkillVersion,
    Tool,
)
from orchestra_backend.companies.models import Company  # noqa: F401
from orchestra_backend.credentials.models import Credential  # noqa: F401
from orchestra_backend.events.models import Event, EventStream  # noqa: F401
from orchestra_backend.execution.models import (  # noqa: F401
    AgentRun,
    Artifact,
    Task,
    TaskDependency,
)
from orchestra_backend.knowledge.models import (  # noqa: F401
    KnowledgeItem,
    Lesson,
    RoleChangeProposal,
)
from orchestra_backend.metrics.models import Metric  # noqa: F401
from orchestra_backend.organization.models import Department, OrgLayout  # noqa: F401
from orchestra_backend.workers.models import (  # noqa: F401
    Worker,
    WorkerLease,
    WorkerPairing,
    WorkerToken,
)
