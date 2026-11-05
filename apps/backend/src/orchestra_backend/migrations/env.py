from __future__ import annotations

from alembic import context
from sqlalchemy import pool

import orchestra_backend.db.models  # noqa: F401  (populate metadata)
from orchestra_backend.db.base import Base
from orchestra_backend.db.session import make_engine

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        from orchestra_backend.core.config import Settings

        settings = Settings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        url = settings.resolved_database_url
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    # FTS5 shadow tables are created by raw SQL (ADR-0019), not by the ORM.
    return not (type_ == "table" and name and name.startswith("knowledge_fts"))


def run_migrations_online() -> None:
    engine = make_engine(_url(), begin_immediate=False, poolclass=pool.NullPool)
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # Batch migrations recreate tables; with FKs on, dropping a referenced table
            # would cascade-fail. Turn them off for the migration, then verify integrity.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            problems = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            if problems:
                raise RuntimeError(f"foreign key check failed after migration: {problems[:5]}")
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
