"""video target duration

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-15 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("video_projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("target_duration_s", sa.Float(), nullable=False, server_default="15")
        )


def downgrade() -> None:
    with op.batch_alter_table("video_projects", schema=None) as batch_op:
        batch_op.drop_column("target_duration_s")
