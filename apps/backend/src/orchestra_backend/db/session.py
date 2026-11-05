from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str, *, begin_immediate: bool = True, **kwargs: Any) -> Engine:
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 15}
    engine = create_engine(url, connect_args=connect_args, **kwargs)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn: Any, _: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=15000")
            if ":memory:" not in url:
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
            if begin_immediate:
                # Let SQLAlchemy control transactions so we can BEGIN IMMEDIATE (below).
                dbapi_conn.isolation_level = None

        if begin_immediate:

            @event.listens_for(engine, "begin")
            def _begin_immediate(conn: Any) -> None:
                # Take the write lock up front: concurrent runs (ADR-0015) then wait on
                # busy_timeout instead of failing with SQLITE_BUSY on lock upgrade.
                conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One short write transaction: commit on success, rollback on error."""
    with factory() as session, session.begin():
        yield session
