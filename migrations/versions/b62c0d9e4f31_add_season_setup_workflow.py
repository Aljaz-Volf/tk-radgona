"""add season setup workflow

Revision ID: b62c0d9e4f31
Revises: f21b3c8d4a90
Create Date: 2026-11-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b62c0d9e4f31"
down_revision = "f21b3c8d4a90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.add_column(sa.Column("promotions_per_boundary", sa.Integer(), nullable=False, server_default="2"))
        batch_op.add_column(sa.Column("setup_pending", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("publish_after_setup", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_check_constraint(
            "ck_seasons_valid_promotions_per_boundary",
            "promotions_per_boundary between 0 and 8",
        )

    with op.batch_alter_table("league_groups", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_players", sa.Integer(), nullable=False, server_default="8"))
        batch_op.add_column(sa.Column("source_group_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_league_groups_source_group_id"),
            ["source_group_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_league_groups_source_group_id_league_groups"),
            "league_groups",
            ["source_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_league_groups_valid_max_players",
            "max_players between 1 and 64",
        )


def downgrade():
    with op.batch_alter_table("league_groups", schema=None) as batch_op:
        batch_op.drop_constraint("ck_league_groups_valid_max_players", type_="check")
        batch_op.drop_constraint(
            batch_op.f("fk_league_groups_source_group_id_league_groups"),
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_league_groups_source_group_id"))
        batch_op.drop_column("source_group_id")
        batch_op.drop_column("max_players")

    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.drop_constraint("ck_seasons_valid_promotions_per_boundary", type_="check")
        batch_op.drop_column("publish_after_setup")
        batch_op.drop_column("setup_pending")
        batch_op.drop_column("promotions_per_boundary")
