"""customer accounts

Revision ID: 003_customer_users
Revises: 002_live_tracking
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_customer_users"
down_revision: Union[str, None] = "002_live_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "customer_users" not in tables:
        op.create_table(
            "customer_users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(180), nullable=False),
            sa.Column("phone", sa.String(20), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("email", name="uq_customer_email"),
            sa.UniqueConstraint("phone", name="uq_customer_phone"),
        )
    booking_cols = {col["name"] for col in inspector.get_columns("bookings")}
    if "customer_user_id" not in booking_cols:
        op.add_column("bookings", sa.Column("customer_user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_bookings_customer_user_id",
            "bookings",
            "customer_users",
            ["customer_user_id"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_constraint("fk_bookings_customer_user_id", "bookings", type_="foreignkey")
    op.drop_column("bookings", "customer_user_id")
    op.drop_table("customer_users")
