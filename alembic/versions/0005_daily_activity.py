"""Daily mission evidence with content-free lesson identities."""

import hashlib
from datetime import UTC

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_daily_activity"
down_revision = "0004_educational_progress"
branch_labels = None
depends_on = None


def upgrade():
    activity = op.create_table(
        "reading_activity_days",
        sa.Column(
            "reading_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reading_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("activity_date", sa.Date(), primary_key=True),
        sa.Column("lesson_key", sa.String(64), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("correct_answer", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("inferred", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint("length(lesson_key) = 64", name="ck_activity_lesson_key"),
    )
    # Prior sessions have only their start/completion date; retain that explicit
    # legacy estimate without reconstructing or reading document contents.
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT r.id,r.document_id,r.category,r.started_at,r.ended_at,r.completed,r.questions_correct,d.content_sha256 FROM reading_sessions r LEFT JOIN documents d ON d.id=r.document_id "
                "WHERE r.completed OR r.reading_time_seconds > 0 OR r.completion_percent > 0 OR r.questions_answered > 0 OR r.comprehension_score IS NOT NULL"
            )
        )
        .mappings()
    )
    batch = []
    for row in rows:
        stamp = row["ended_at"] or row["started_at"]
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        identity = (
            f"document:{row['document_id']}"
            if row["document_id"]
            else f"category:{row['category']}"
        )
        batch.append(
            {
                "reading_id": row["id"],
                "activity_date": stamp.astimezone(UTC).date(),
                "lesson_key": row["content_sha256"]
                or hashlib.sha256(identity.encode()).hexdigest(),
                "completed": row["completed"],
                "correct_answer": row["questions_correct"] > 0,
                "inferred": True,
            }
        )
        if len(batch) == 500:
            op.bulk_insert(activity, batch)
            batch = []
    if batch:
        op.bulk_insert(activity, batch)


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM reading_activity_days WHERE NOT inferred LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot downgrade: daily learning activity requires the current schema")
    op.drop_table("reading_activity_days")
