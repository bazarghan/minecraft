"""Add world type to servers.

Revision ID: 0002
"""
import sqlalchemy as sa
from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("minecraft_servers")}
    if "level_type" not in columns:
        op.add_column(
            "minecraft_servers",
            sa.Column(
                "level_type",
                sa.String(length=64),
                nullable=False,
                server_default="minecraft:normal",
            ),
        )


def downgrade() -> None:
    op.drop_column("minecraft_servers", "level_type")
