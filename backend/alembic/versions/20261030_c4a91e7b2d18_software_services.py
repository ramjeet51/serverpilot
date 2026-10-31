"""software candidate version and service inventory

Revision ID: c4a91e7b2d18
Revises: fd1776a348f0
Create Date: 2026-10-30 23:15:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a91e7b2d18"
down_revision: str | None = "fd1776a348f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("software_inventory", sa.Column("candidate_version", sa.String(length=128), nullable=True))
    op.alter_column("software_inventory", "version", existing_type=sa.String(length=64), type_=sa.String(length=128),
                    existing_nullable=True)
    op.create_table(
        "service_inventory",
        sa.Column("unit_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("active_state", sa.String(length=32), nullable=False),
        sa.Column("sub_state", sa.String(length=32), nullable=False),
        sa.Column("unit_file_state", sa.String(length=32), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], name=op.f("fk_service_inventory_server_id_servers"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_inventory")),
        sa.UniqueConstraint("server_id", "unit_name", name="uq_service_inventory_server_unit"),
    )
    op.create_index(op.f("ix_service_inventory_server_id"), "service_inventory", ["server_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_service_inventory_server_id"), table_name="service_inventory")
    op.drop_table("service_inventory")
    op.alter_column("software_inventory", "version", existing_type=sa.String(length=128), type_=sa.String(length=64),
                    existing_nullable=True)
    op.drop_column("software_inventory", "candidate_version")
