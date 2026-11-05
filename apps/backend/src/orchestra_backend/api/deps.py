from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, TypeVar

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from orchestra_backend.core.config import Settings

T = TypeVar("T")

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

    def run_tx(self, fn: Callable[[Session], T]) -> T:
        with self.tx() as s:
            return fn(s)

    @property
    def orchestrator(self) -> Orchestrator:
        return self.extras["orchestrator"]


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]
