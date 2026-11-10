"""live tracking tables and city coordinates

Revision ID: 002_live_tracking
Revises: 001_initial
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_live_tracking"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    city_cols = {col["name"] for col in inspector.get_columns("cities")}
    if "latitude" not in city_cols:
        op.add_column("cities", sa.Column("latitude", sa.Float(), nullable=True))
    if "longitude" not in city_cols:
        op.add_column("cities", sa.Column("longitude", sa.Float(), nullable=True))

    tables = set(inspector.get_table_names())
    if "trip_live_states" not in tables:
        tracking_status = postgresql.ENUM(
            "scheduled",
            "boarding",
            "departed",
            "in_transit",
            "arriving",
            "completed",
            "offline",
            name="tracking_status",
            create_type=True,
        )
        tracking_status.create(bind, checkfirst=True)
        op.create_table(
            "trip_live_states",
            sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id"), primary_key=True),
            sa.Column("status", tracking_status, nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("heading", sa.Float(), nullable=False, server_default="0"),
            sa.Column("speed_kmh", sa.Float(), nullable=False, server_default="0"),
            sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(40), nullable=False, server_default="schedule_estimate"),
            sa.Column("next_landmark", sa.String(160), nullable=False, server_default=""),
            sa.Column("eta_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("simulator_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("simulator_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("simulator_duration_seconds", sa.Integer(), nullable=False, server_default="360"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "trip_location_pings" not in tables:
        op.create_table(
            "trip_location_pings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("heading", sa.Float(), nullable=False, server_default="0"),
            sa.Column("speed_kmh", sa.Float(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(40), nullable=False, server_default="gps"),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_trip_pings_trip_time", "trip_location_pings", ["trip_id", "recorded_at"])


def downgrade() -> None:
    op.drop_table("trip_location_pings")
    op.drop_table("trip_live_states")
    op.drop_column("cities", "longitude")
    op.drop_column("cities", "latitude")
