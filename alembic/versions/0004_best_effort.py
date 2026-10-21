"""Allow truthful best-effort telemetry without weakening data integrity.

Revision ID: 0004_best_effort
Revises: 0003_adult_telemetry
"""

from sqlalchemy import text

from alembic import op

revision = "0004_best_effort"
down_revision = "0003_adult_telemetry"
branch_labels = None
depends_on = None

OLD_CHECK = "(original_szigriszt_score IS NULL AND adapted_szigriszt_score IS NULL AND score_delta IS NULL AND original_word_count IS NULL AND adapted_word_count IS NULL AND original_syllable_count IS NULL AND original_sentence_count IS NULL AND syllable_count IS NULL AND sentence_count IS NULL AND maintenance_exception = false) OR (original_szigriszt_score IS NOT NULL AND adapted_szigriszt_score IS NOT NULL AND score_delta IS NOT NULL AND original_word_count IS NOT NULL AND adapted_word_count IS NOT NULL AND original_syllable_count IS NOT NULL AND original_sentence_count IS NOT NULL AND syllable_count IS NOT NULL AND sentence_count IS NOT NULL AND original_word_count > 0 AND adapted_word_count > 0 AND original_syllable_count > 0 AND original_sentence_count > 0 AND syllable_count > 0 AND sentence_count > 0 AND abs(original_szigriszt_score) < 1000000 AND abs(adapted_szigriszt_score) < 1000000 AND score_delta = adapted_szigriszt_score - original_szigriszt_score AND ((original_szigriszt_score > 128.535 AND maintenance_exception = true AND adapted_szigriszt_score >= 85.0) OR (original_szigriszt_score <= 128.535 AND maintenance_exception = false AND adapted_szigriszt_score >= 65.0 AND score_delta >= 15.0)))"
NEW_CHECK = "(original_szigriszt_score IS NULL AND adapted_szigriszt_score IS NULL AND score_delta IS NULL AND original_word_count IS NULL AND adapted_word_count IS NULL AND original_syllable_count IS NULL AND original_sentence_count IS NULL AND syllable_count IS NULL AND sentence_count IS NULL AND maintenance_exception = false) OR (original_szigriszt_score IS NOT NULL AND adapted_szigriszt_score IS NOT NULL AND score_delta IS NOT NULL AND original_word_count IS NOT NULL AND adapted_word_count IS NOT NULL AND original_syllable_count IS NOT NULL AND original_sentence_count IS NOT NULL AND syllable_count IS NOT NULL AND sentence_count IS NOT NULL AND original_word_count > 0 AND adapted_word_count > 0 AND original_syllable_count > 0 AND original_sentence_count > 0 AND syllable_count > 0 AND sentence_count > 0 AND abs(original_szigriszt_score) < 1000000000000 AND abs(adapted_szigriszt_score) < 1000000000000 AND score_delta = adapted_szigriszt_score - original_szigriszt_score AND ((original_szigriszt_score > 128.535 AND maintenance_exception = true) OR (original_szigriszt_score <= 128.535 AND maintenance_exception = false)))"
TABLES = (
    ("documents", "ck_document_acceptance"),
    ("adaptation_chunks", "ck_chunk_acceptance"),
    ("reading_sessions", "ck_reading_acceptance"),
)


def replace_checks(condition):
    for table, constraint in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_="check")
            batch.create_check_constraint(constraint, condition)


def upgrade():
    replace_checks(NEW_CHECK)


def downgrade():
    # Refuse destructive rollback when real best-effort sessions already exist.
    for table, _ in TABLES:
        if (
            op.get_bind()
            .execute(text(f"SELECT 1 FROM {table} WHERE NOT ({OLD_CHECK}) LIMIT 1"))
            .first()
        ):
            raise RuntimeError(
                "Cannot downgrade: best-effort telemetry requires the current schema"
            )
    replace_checks(OLD_CHECK)
