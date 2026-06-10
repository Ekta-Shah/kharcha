"""insights cache table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("month", sa.Text, nullable=False, unique=True),
        sa.Column("data_hash", sa.Text, nullable=False),
        sa.Column("insights", sa.Text, nullable=False),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("insights_cache")
