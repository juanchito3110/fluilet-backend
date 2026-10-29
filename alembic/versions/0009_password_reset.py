"""Expiring password recovery codes, with keyed digests and bounded attempts."""

import sqlalchemy as sa

from alembic import op

revision = "0009_password_reset"
down_revision = "0007_master_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_password_reset_attempts"),
    )
    op.create_index(
        "ix_password_reset_user_created", "password_reset_requests", ["user_id", "created_at"]
    )


def downgrade():
    # Recovery requests are deliberately ephemeral; rollback invalidates them.
    op.drop_index("ix_password_reset_user_created", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
