"""normalize user email addresses and usernames

Revision ID: c42e8f1a6d30
Revises: a31d6e7f9b20
Create Date: 2026-11-13 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c42e8f1a6d30"
down_revision = "a31d6e7f9b20"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    users = sa.table(
        "users",
        sa.column("email", sa.String(254)),
        sa.column("username", sa.String(80)),
    )
    connection.execute(
        users.update().values(
            email=sa.func.lower(sa.func.trim(users.c.email)),
            username=sa.func.lower(sa.func.trim(users.c.username)),
        )
    )
    op.create_index(
        "uq_users_email_normalized",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index(
        "uq_users_username_normalized",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_users_username_normalized", table_name="users")
    op.drop_index("uq_users_email_normalized", table_name="users")
