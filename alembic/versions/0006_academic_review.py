"""Authorized lesson retrieval and explicitly synthetic academic history."""

import sqlalchemy as sa

from alembic import op

revision = "0006_academic_review"
down_revision = "0005_daily_activity"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.dialects import postgresql

    op.create_table(
        "adaptation_contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("child_profiles.id", ondelete="CASCADE"),
        ),
        sa.Column("context_key", sa.String(64), nullable=False, unique=True),
        sa.Column("target_level", sa.Integer(), nullable=False),
        sa.Column("age_group", sa.String(8), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("adapted_text", sa.Text(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("target_level BETWEEN 1 AND 5", name="ck_content_level"),
        sa.CheckConstraint("age_group IN ('6-8','9-11','12+')", name="ck_content_age"),
        sa.CheckConstraint(
            "length(original_text)>0 AND length(adapted_text)>0", name="ck_content_nonempty"
        ),
    )
    op.create_index("ix_adaptation_contents_document_id", "adaptation_contents", ["document_id"])
    op.add_column("reading_sessions", sa.Column("demo_slot", sa.String(32), nullable=True))
    op.create_unique_constraint("uq_child_demo_slot", "reading_sessions", ["child_id", "demo_slot"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM adaptation_contents LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade: retained adaptations require the current schema")
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM reading_sessions WHERE demo_slot IS NOT NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot downgrade: academic demo markers require the current schema")
    op.drop_constraint("uq_child_demo_slot", "reading_sessions", type_="unique")
    op.drop_column("reading_sessions", "demo_slot")
    op.drop_index("ix_adaptation_contents_document_id", table_name="adaptation_contents")
    op.drop_table("adaptation_contents")
