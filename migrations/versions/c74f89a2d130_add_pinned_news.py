"""add pinned news

Revision ID: c74f89a2d130
Revises: aa5b76fbb0ad
Create Date: 2026-10-30 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c74f89a2d130"
down_revision = "aa5b76fbb0ad"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("news_articles", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_pinned", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.create_index(
            batch_op.f("ix_news_articles_is_pinned"), ["is_pinned"], unique=False
        )


def downgrade():
    with op.batch_alter_table("news_articles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_news_articles_is_pinned"))
        batch_op.drop_column("is_pinned")
