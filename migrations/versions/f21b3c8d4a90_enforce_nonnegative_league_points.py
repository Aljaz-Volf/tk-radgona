"""enforce nonnegative league points

Revision ID: f21b3c8d4a90
Revises: d8a1f42c907e
Create Date: 2026-10-30 18:00:00.000000

"""
from alembic import op


revision = "f21b3c8d4a90"
down_revision = "d8a1f42c907e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_seasons_nonnegative_win_points", "win_points >= 0"
        )
        batch_op.create_check_constraint(
            "ck_seasons_nonnegative_loss_points", "loss_points >= 0"
        )


def downgrade():
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_seasons_nonnegative_loss_points", type_="check"
        )
        batch_op.drop_constraint(
            "ck_seasons_nonnegative_win_points", type_="check"
        )
