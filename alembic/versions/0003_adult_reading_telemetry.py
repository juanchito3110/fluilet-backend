"""Independent adult sessions and immutable numerical readability snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_adult_telemetry"
down_revision = "0002_zero_retention"
branch_labels = None
depends_on = None

TELEMETRY_CHECK = "(original_szigriszt_score IS NULL AND adapted_szigriszt_score IS NULL AND score_delta IS NULL AND original_word_count IS NULL AND adapted_word_count IS NULL AND original_syllable_count IS NULL AND original_sentence_count IS NULL AND syllable_count IS NULL AND sentence_count IS NULL AND maintenance_exception = false) OR (original_szigriszt_score IS NOT NULL AND adapted_szigriszt_score IS NOT NULL AND score_delta IS NOT NULL AND original_word_count IS NOT NULL AND adapted_word_count IS NOT NULL AND original_syllable_count IS NOT NULL AND original_sentence_count IS NOT NULL AND syllable_count IS NOT NULL AND sentence_count IS NOT NULL AND original_word_count > 0 AND adapted_word_count > 0 AND original_syllable_count > 0 AND original_sentence_count > 0 AND syllable_count > 0 AND sentence_count > 0 AND abs(original_szigriszt_score) < 1000000 AND abs(adapted_szigriszt_score) < 1000000 AND score_delta = adapted_szigriszt_score - original_szigriszt_score AND ((original_szigriszt_score > 128.535 AND maintenance_exception = true AND adapted_szigriszt_score >= 85.0) OR (original_szigriszt_score <= 128.535 AND maintenance_exception = false AND adapted_szigriszt_score >= 65.0 AND score_delta >= 15.0)))"
METRICS = {
    "original_szigriszt_score": sa.Float,
    "adapted_szigriszt_score": sa.Float,
    "score_delta": sa.Float,
    "original_word_count": sa.Integer,
    "adapted_word_count": sa.Integer,
    "original_syllable_count": sa.Integer,
    "original_sentence_count": sa.Integer,
    "syllable_count": sa.Integer,
    "sentence_count": sa.Integer,
}


def upgrade():
    op.alter_column(
        "reading_sessions", "child_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )
    op.add_column(
        "reading_sessions",
        sa.Column("reader_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_reading_reader_user",
        "reading_sessions",
        "users",
        ["reader_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_reading_sessions_reader_user_id", "reading_sessions", ["reader_user_id"])
    for name, kind in METRICS.items():
        op.add_column("reading_sessions", sa.Column(name, kind(), nullable=True))
    op.add_column(
        "reading_sessions",
        sa.Column("maintenance_exception", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Legacy child ownership is unchanged. Copy only numeric metrics, never text.
    assignments = ", ".join(f"{name} = d.{name}" for name in [*METRICS, "maintenance_exception"])
    op.execute(
        f"UPDATE reading_sessions r SET {assignments} FROM documents d WHERE r.document_id = d.id"
    )
    op.create_check_constraint(
        "ck_reading_single_owner",
        "reading_sessions",
        "(child_id IS NOT NULL AND reader_user_id IS NULL) OR (child_id IS NULL AND reader_user_id IS NOT NULL)",
    )
    op.create_check_constraint("ck_reading_acceptance", "reading_sessions", TELEMETRY_CHECK)


def downgrade():
    # Never erase adult sessions silently to satisfy the old NOT NULL constraint.
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM reading_sessions WHERE child_id IS NULL)
        THEN RAISE EXCEPTION 'Adult reading sessions prevent lossless downgrade'; END IF; END $$""")
    op.drop_constraint("ck_reading_acceptance", "reading_sessions", type_="check")
    op.drop_constraint("ck_reading_single_owner", "reading_sessions", type_="check")
    op.drop_index("ix_reading_sessions_reader_user_id", table_name="reading_sessions")
    op.drop_constraint("fk_reading_reader_user", "reading_sessions", type_="foreignkey")
    op.drop_column("reading_sessions", "reader_user_id")
    for name in [*METRICS, "maintenance_exception"]:
        op.drop_column("reading_sessions", name)
    op.alter_column(
        "reading_sessions", "child_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False
    )
