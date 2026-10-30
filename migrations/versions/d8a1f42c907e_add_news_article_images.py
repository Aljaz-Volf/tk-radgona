"""add news article images

Revision ID: d8a1f42c907e
Revises: c74f89a2d130
Create Date: 2026-10-30 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d8a1f42c907e"
down_revision = "c74f89a2d130"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "news_article_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["news_articles.id"],
            name=op.f("fk_news_article_images_article_id_news_articles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_article_images")),
    )
    with op.batch_alter_table("news_article_images", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_news_article_images_article_id"), ["article_id"], unique=False
        )

    op.execute(
        sa.text(
            """
            INSERT INTO news_article_images
                (article_id, storage_key, sort_order, width, height, created_at, updated_at)
            SELECT id, image_key, 0, NULL, NULL, created_at, updated_at
            FROM news_articles
            WHERE image_key IS NOT NULL
            """
        )
    )
    op.execute(sa.text("UPDATE news_articles SET image_key = NULL WHERE image_key IS NOT NULL"))


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE news_articles
            SET image_key = (
                SELECT storage_key
                FROM news_article_images
                WHERE news_article_images.article_id = news_articles.id
                ORDER BY sort_order, id
                LIMIT 1
            )
            WHERE image_key IS NULL
              AND EXISTS (
                SELECT 1 FROM news_article_images
                WHERE news_article_images.article_id = news_articles.id
              )
            """
        )
    )
    with op.batch_alter_table("news_article_images", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_news_article_images_article_id"))
    op.drop_table("news_article_images")
