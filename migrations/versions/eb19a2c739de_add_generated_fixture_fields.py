"""add generated fixture fields and constraints

Revision ID: eb19a2c739de
Revises: b62c0d9e4f31
Create Date: 2026-11-06 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "eb19a2c739de"
down_revision = "b62c0d9e4f31"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("round_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("leg", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("generated", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_index(
            batch_op.f("ix_matches_round_number"), ["round_number"], unique=False
        )
        batch_op.create_check_constraint(
            "ck_matches_positive_round_number",
            "round_number is null or round_number > 0",
        )
        batch_op.create_check_constraint(
            "ck_matches_valid_leg", "leg is null or leg in (1, 2)"
        )
    op.create_index(
        "uq_matches_scheduled_fixture",
        "matches",
        ["season_id", "group_id", "player1_id", "player2_id"],
        unique=True,
        sqlite_where=sa.text("round_number IS NOT NULL"),
        postgresql_where=sa.text("round_number IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_matches_scheduled_fixture", table_name="matches")
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_constraint("ck_matches_valid_leg", type_="check")
        batch_op.drop_constraint("ck_matches_positive_round_number", type_="check")
        batch_op.drop_index(batch_op.f("ix_matches_round_number"))
        batch_op.drop_column("generated")
        batch_op.drop_column("leg")
        batch_op.drop_column("round_number")
