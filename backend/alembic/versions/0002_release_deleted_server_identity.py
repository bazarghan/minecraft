"""Release names, slugs, and ports when a server is soft deleted.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("minecraft_servers_name_key", "minecraft_servers", type_="unique")
    op.drop_index("ix_minecraft_servers_slug", table_name="minecraft_servers")
    op.drop_constraint("minecraft_servers_port_key", "minecraft_servers", type_="unique")

    active_only = sa.text("deleted_at IS NULL")
    op.create_index(
        "uq_minecraft_servers_active_name",
        "minecraft_servers",
        ["name"],
        unique=True,
        postgresql_where=active_only,
    )
    op.create_index(
        "uq_minecraft_servers_active_slug",
        "minecraft_servers",
        ["slug"],
        unique=True,
        postgresql_where=active_only,
    )
    op.create_index(
        "uq_minecraft_servers_active_port",
        "minecraft_servers",
        ["port"],
        unique=True,
        postgresql_where=active_only,
    )


def downgrade() -> None:
    op.drop_index("uq_minecraft_servers_active_port", table_name="minecraft_servers")
    op.drop_index("uq_minecraft_servers_active_slug", table_name="minecraft_servers")
    op.drop_index("uq_minecraft_servers_active_name", table_name="minecraft_servers")

    op.create_unique_constraint(
        "minecraft_servers_name_key", "minecraft_servers", ["name"]
    )
    op.create_index(
        "ix_minecraft_servers_slug", "minecraft_servers", ["slug"], unique=True
    )
    op.create_unique_constraint(
        "minecraft_servers_port_key", "minecraft_servers", ["port"]
    )
