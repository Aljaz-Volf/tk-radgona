"""add application roles

Revision ID: a31d6e7f9b20
Revises: eb19a2c739de
Create Date: 2026-11-13 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a31d6e7f9b20"
down_revision = "eb19a2c739de"
branch_labels = None
depends_on = None


ROLES = (
    ("superadmin", "Polni skrbniški dostop"),
    ("administrator", "Upravljanje brez pregleda administracije"),
    ("member_news", "Ustvarjanje novic in galerij"),
    ("member", "Član kluba"),
)


def upgrade():
    connection = op.get_bind()
    roles = sa.table(
        "roles",
        sa.column("name", sa.String(40)),
        sa.column("description", sa.String(255)),
    )
    existing = set(connection.execute(sa.select(roles.c.name)).scalars())
    for name, description in ROLES:
        if name in existing:
            connection.execute(
                roles.update().where(roles.c.name == name).values(description=description)
            )
        else:
            connection.execute(roles.insert().values(name=name, description=description))


def downgrade():
    # Roles are durable application data and may already be assigned to users.
    pass
