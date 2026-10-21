"""Educational metadata, comprehension practice and reading achievements.

The deployed 0004_best_effort revision remains intact in the linear history.
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_educational_progress"
down_revision = "0004_best_effort"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("documents", "reading_sessions"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column("category", sa.String(64), nullable=False, server_default="lectura_libre")
            )
            batch.add_column(
                sa.Column("simplification_level", sa.Integer(), nullable=False, server_default="2")
            )
            batch.create_check_constraint(
                "ck_document_educational_level"
                if table == "documents"
                else "ck_reading_educational_level",
                "simplification_level BETWEEN 1 AND 5",
            )
    with op.batch_alter_table("reading_sessions") as batch:
        batch.add_column(sa.Column("comprehension_score", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("questions_answered", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("questions_correct", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("tts_speed_used", sa.Float(), nullable=False, server_default="1.0")
        )
        batch.create_check_constraint(
            "ck_reading_comprehension",
            "comprehension_score IS NULL OR comprehension_score BETWEEN 0 AND 100",
        )
        batch.create_check_constraint(
            "ck_reading_questions",
            "questions_answered BETWEEN 0 AND 10000 AND questions_correct >= 0 AND questions_correct <= questions_answered",
        )
        batch.create_check_constraint(
            "ck_reading_tts_speed", "tts_speed_used > 0 AND tts_speed_used <= 4"
        )


def downgrade():
    # Never silently erase educational history to roll back the schema.
    for table, condition in (
        ("documents", "category <> 'lectura_libre' OR simplification_level <> 2"),
        (
            "reading_sessions",
            "category <> 'lectura_libre' OR simplification_level <> 2 OR comprehension_score IS NOT NULL OR questions_answered <> 0 OR questions_correct <> 0 OR tts_speed_used <> 1.0",
        ),
    ):
        if (
            op.get_bind()
            .execute(sa.text(f"SELECT 1 FROM {table} WHERE {condition} LIMIT 1"))
            .first()
        ):
            raise RuntimeError("Cannot downgrade: educational progress requires the current schema")
    with op.batch_alter_table("reading_sessions") as batch:
        for constraint in (
            "ck_reading_comprehension",
            "ck_reading_questions",
            "ck_reading_tts_speed",
        ):
            batch.drop_constraint(constraint, type_="check")
        for column in (
            "comprehension_score",
            "questions_answered",
            "questions_correct",
            "tts_speed_used",
        ):
            batch.drop_column(column)
    for table in ("reading_sessions", "documents"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(
                "ck_document_educational_level"
                if table == "documents"
                else "ck_reading_educational_level",
                type_="check",
            )
            batch.drop_column("simplification_level")
            batch.drop_column("category")
