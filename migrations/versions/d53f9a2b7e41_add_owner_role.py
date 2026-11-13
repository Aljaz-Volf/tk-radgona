"""add owner role

Revision ID: d53f9a2b7e41
Revises: c42e8f1a6d30
Create Date: 2026-11-13 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d53f9a2b7e41"
down_revision = "c42e8f1a6d30"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    roles = sa.table(
        "roles",
        sa.column("name", sa.String(40)),
        sa.column("description", sa.String(255)),
    )
    exists = connection.execute(
        sa.select(roles.c.name).where(roles.c.name == "owner")
    ).scalar_one_or_none()
    if not exists:
        connection.execute(
            roles.insert().values(
                name="owner",
                description="Najvišji dostop in upravljanje lastnikov",
            )
        )


def downgrade():
    # Owner assignments are durable authorization data and are not deleted.
    pass
