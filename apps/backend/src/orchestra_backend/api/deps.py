from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from orchestra_backend.core.config import Settings

if TYPE_CHECKING:
    from orchestra_backend.orchestrator.service import Orchestrator


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    extras: dict[str, Any] = field(default_factory=dict)

    @contextmanager
    def tx(self) -> Iterator[Session]:
        with self.session_factory() as session, session.begin():
            yield session

    @property
    def orchestrator(self) -> Orchestrator:
        return self.extras["orchestrator"]


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]
