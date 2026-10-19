"""Zero retention, scoped NINO identities and numerical adaptation telemetry."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_zero_retention"
down_revision = "0001_baseline"
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


def metric_columns():
    return [sa.Column(name, kind(), nullable=True) for name, kind in METRICS.items()] + [
        sa.Column("maintenance_exception", sa.Boolean(), nullable=False, server_default=sa.false())
    ]


def upgrade():
    # Enum labels were stored by NAME already; existing role labels are preserved.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'NINO'")
    op.add_column(
        "users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "child_profiles", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_child_user", "child_profiles", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_unique_constraint("uq_child_user", "child_profiles", ["user_id"])
    # Preflight the new limit; never delete legacy records or pretend to extract
    # scores from content that is forbidden to retain.
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM documents WHERE file_size_bytes > 5242880)
      THEN RAISE EXCEPTION 'Resolve legacy document sizes above 5 MB before migration'; END IF; END $$""")
    op.drop_constraint("ck_tamano_max_10mb", "documents", type_="check")
    op.create_check_constraint(
        "ck_tamano_max_5mb", "documents", "file_size_bytes > 0 AND file_size_bytes <= 5242880"
    )
    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "file_name")
    op.add_column("documents", sa.Column("content_sha256", sa.String(64), nullable=True))
    op.add_column(
        "documents", sa.Column("word_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "documents", sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("documents", sa.Column("adaptation_method", sa.String(32), nullable=True))
    op.create_unique_constraint(
        "uq_owner_content_sha256", "documents", ["owner_id", "content_sha256"]
    )
    op.create_check_constraint(
        "ck_document_counts", "documents", "word_count >= 0 AND chunk_count >= 0"
    )
    for column in metric_columns():
        op.add_column("documents", column)
    op.create_check_constraint("ck_document_acceptance", "documents", TELEMETRY_CHECK)
    op.alter_column("reading_sessions", "duration_seconds", new_column_name="reading_time_seconds")
    op.alter_column("reading_sessions", "progress_percentage", new_column_name="completion_percent")
    op.create_check_constraint("ck_reading_time", "reading_sessions", "reading_time_seconds >= 0")
    op.create_check_constraint(
        "ck_completed_progress", "reading_sessions", "NOT completed OR completion_percent = 100"
    )
    op.add_column(
        "refresh_tokens", sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.execute("UPDATE refresh_tokens SET family_id = id, revoked = true")
    op.alter_column("refresh_tokens", "family_id", nullable=False)
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_table(
        "adaptation_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        *metric_columns(),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunk_index"),
        sa.CheckConstraint(TELEMETRY_CHECK, name="ck_chunk_acceptance"),
    )
    op.create_index("ix_adaptation_chunks_document_id", "adaptation_chunks", ["document_id"])


def downgrade():
    # Reintroducing a retained storage path would violate the new privacy policy.
    raise RuntimeError(
        "Forward-only privacy migration; restore an approved metadata backup if required."
    )
