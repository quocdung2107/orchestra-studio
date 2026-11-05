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


def run_migrations_online() -> None:
    engine = make_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
