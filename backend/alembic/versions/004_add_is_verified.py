"""Add is_verified column to users

Revision ID: 004_add_is_verified
Revises: 003_add_urgency_reason
Create Date: 2026-09-03 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_add_is_verified'
down_revision: Union[str, None] = '003_add_urgency_reason'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT TRUE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_verified")
