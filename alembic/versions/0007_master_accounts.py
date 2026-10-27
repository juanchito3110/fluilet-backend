"""Reserved academic identities, master authority and explicit profile controls."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_master_accounts"
down_revision = "0006_academic_review"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'MASTER_ADMIN'")
    op.add_column("users", sa.Column("demo_identity", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("parental_pin_hash", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_user_demo_identity", "users", ["demo_identity"])
    op.add_column("child_profiles", sa.Column("demo_identity", sa.String(32), nullable=True))
    op.add_column("child_profiles", sa.Column("age_group_override", sa.String(8), nullable=True))
    op.create_unique_constraint(
        "uq_tutor_demo_identity", "child_profiles", ["tutor_id", "demo_identity"]
    )
    op.create_check_constraint(
        "ck_child_age_override",
        "child_profiles",
        "age_group_override IS NULL OR age_group_override IN ('6-8','9-11','12+')",
    )
    op.create_table(
        "profile_controls",
        sa.Column(
            "child_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("child_profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("gems_offset", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("xp_offset", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("level_override", sa.Integer(), nullable=True),
        sa.Column("streak_override", sa.Integer(), nullable=True),
        sa.Column("unlock_all_rewards", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint(
            "level_override IS NULL OR level_override BETWEEN 1 AND 5", name="ck_control_level"
        ),
        sa.CheckConstraint(
            "streak_override IS NULL OR streak_override BETWEEN 0 AND 36500",
            name="ck_control_streak",
        ),
    )


def downgrade():
    bind = op.get_bind()
    if (
        bind.execute(
            sa.text(
                "SELECT 1 FROM users WHERE demo_identity IS NOT NULL OR parental_pin_hash IS NOT NULL OR role::text='MASTER_ADMIN' LIMIT 1"
            )
        ).first()
        or bind.execute(sa.text("SELECT 1 FROM profile_controls LIMIT 1")).first()
        or bind.execute(
            sa.text(
                "SELECT 1 FROM child_profiles WHERE demo_identity IS NOT NULL OR age_group_override IS NOT NULL LIMIT 1"
            )
        ).first()
    ):
        raise RuntimeError("Cannot downgrade: master/demo data requires the current schema")
    op.drop_table("profile_controls")
    op.drop_constraint("ck_child_age_override", "child_profiles", type_="check")
    op.drop_constraint("uq_tutor_demo_identity", "child_profiles", type_="unique")
    op.drop_column("child_profiles", "age_group_override")
    op.drop_column("child_profiles", "demo_identity")
    op.drop_constraint("uq_user_demo_identity", "users", type_="unique")
    op.drop_column("users", "parental_pin_hash")
    op.drop_column("users", "demo_identity")
    # PostgreSQL enum labels are additive; retaining the unused label is lossless.
