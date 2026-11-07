"""Independent-reader administration, without adding fictitious children."""

import sqlalchemy as sa

from alembic import op

revision = "0010_reader_controls"
down_revision = "0009_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reader_controls",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("gems_offset", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("xp_offset", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("level_override", sa.Integer()),
        sa.Column("streak_override", sa.Integer()),
        sa.Column("age_group_override", sa.String(8)),
        sa.Column("unlock_all_rewards", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint(
            "level_override IS NULL OR level_override BETWEEN 1 AND 5", name="ck_reader_level"
        ),
        sa.CheckConstraint(
            "streak_override IS NULL OR streak_override BETWEEN 0 AND 36500",
            name="ck_reader_streak",
        ),
        sa.CheckConstraint(
            "age_group_override IS NULL OR age_group_override IN ('6-8','9-11','12+')",
            name="ck_reader_age",
        ),
    )
    # Existing adult accounts become administrable immediately, without a login.
    connection = op.get_bind()
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, autoload_with=connection)
    controls = sa.Table("reader_controls", metadata, autoload_with=connection)
    connection.execute(
        controls.insert().from_select(
            ["user_id"], sa.select(users.c.id).where(users.c.role == "ADULTO_INDEPENDIENTE")
        )
    )


def downgrade():
    op.drop_table("reader_controls")
