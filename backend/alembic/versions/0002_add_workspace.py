"""add workspace column to tasks

Revision ID: 0002
Revises: 0001_create_tasks
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_workspace"
down_revision: Union[str, None] = "0001_create_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "workspace",
            sa.String(length=50),
            nullable=False,
            server_default="DevOps Capstone",
        ),
    )
    op.create_index("ix_tasks_workspace", "tasks", ["workspace"])


def downgrade() -> None:
    op.drop_index("ix_tasks_workspace", table_name="tasks")
    op.drop_column("tasks", "workspace")
