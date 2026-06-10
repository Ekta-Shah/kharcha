"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("item", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False, server_default="Uncategorized"),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", sa.Text, nullable=False, server_default="voice"),
        sa.Column("raw_text", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("cost >= 0", name="ck_expenses_cost_nonneg"),
    )

    op.create_table(
        "statements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.Text),
        sa.Column("bank", sa.Text),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date),
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("statement_id", UUID(as_uuid=True), sa.ForeignKey("statements.id"), nullable=False),
        sa.Column("txn_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_debit", sa.Boolean, nullable=False),
        sa.Column("hash", sa.String(64), unique=True),
    )

    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_id", UUID(as_uuid=True), sa.ForeignKey("expenses.id"), nullable=True),
        sa.Column("bank_txn_id", UUID(as_uuid=True), sa.ForeignKey("bank_transactions.id"), nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.Column("rationale", sa.Text),
        sa.Column("confirmed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "category_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("item_text", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("category_overrides")
    op.drop_table("matches")
    op.drop_table("bank_transactions")
    op.drop_table("statements")
    op.drop_table("expenses")
