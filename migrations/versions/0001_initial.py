"""Create Telegram users and durable update inbox."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "telegram_users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(256), nullable=False),
        sa.Column("language_code", sa.String(16), nullable=True),
        sa.Column("preferred_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "inbox_updates",
        sa.Column("update_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(128), nullable=True),
    )
    op.create_index("ix_inbox_pending", "inbox_updates", ["status", "available_at", "update_id"])


def downgrade():
    op.drop_index("ix_inbox_pending", table_name="inbox_updates")
    op.drop_table("inbox_updates")
    op.drop_table("telegram_users")
