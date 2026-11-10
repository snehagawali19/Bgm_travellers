"""Operational booking features; preserve existing trips and reservations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "004_operations"
down_revision = "003_customer_users"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    # The original initial migration creates current metadata on fresh installs.
    tables = set(sa.inspect(bind).get_table_names())
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE trip_status ADD VALUE IF NOT EXISTS 'CLOSED'")
    if "seat_layouts" not in tables:
        op.create_table("seat_layouts", sa.Column("id", UUID, primary_key=True),
                        sa.Column("name", sa.String(120), nullable=False, unique=True),
                        sa.Column("seats", JSONB, nullable=False))
    if "recurring_schedules" not in tables:
        op.create_table("recurring_schedules", sa.Column("id", UUID, primary_key=True),
                        sa.Column("name", sa.String(120), nullable=False),
                        sa.Column("definition", JSONB, nullable=False),
                        sa.Column("active", sa.Boolean, nullable=False))
    additions = {
        "route_stops": [sa.Column("landmark", sa.String(255), nullable=False, server_default=""),
                        sa.Column("offset_minutes", sa.Integer, nullable=False, server_default="0")],
        "trips": [sa.Column("booking_cutoff_minutes", sa.Integer, nullable=False, server_default="60"),
                  sa.Column("schedule_id", UUID, sa.ForeignKey("recurring_schedules.id")),
                  sa.Column("service_date", sa.String(10))],
        "seat_holds": [sa.Column("fare_paise", sa.Integer)],
        "bookings": [sa.Column("channel", sa.String(20), nullable=False, server_default="online"),
                     sa.Column("offline_method", sa.String(30)), sa.Column("confirmed_payment_id", sa.String(80)),
                     sa.Column("staff_request_id", sa.String(64)),
                     sa.Column("policy_snapshot", JSONB), sa.Column("pickup_snapshot", JSONB),
                     sa.Column("dropoff_snapshot", JSONB)],
        "booking_seats": [sa.Column("checked_in_at", sa.DateTime(timezone=True))],
    }
    for table, columns in additions.items():
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
    op.execute("ALTER TABLE bus_seats DROP CONSTRAINT IF EXISTS uq_bus_seat_number")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_active_bus_seat_number ON bus_seats (bus_id, seat_number) WHERE active IS TRUE")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_schedule_date ON trips (schedule_id, service_date)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_request_id ON bookings (staff_request_id)")
    # Legacy data had no per-stop timing. Use route duration for drop-only stops;
    # operators can refine these offsets without altering existing tickets.
    if "notifications" not in tables:
        op.execute("UPDATE route_stops s SET offset_minutes = r.estimated_duration_minutes FROM routes r WHERE s.route_id = r.id AND s.dropoff_allowed AND NOT s.pickup_allowed AND s.offset_minutes = 0")
    op.execute("UPDATE seat_holds h SET fare_paise = t.base_fare_paise FROM trips t WHERE h.trip_id = t.id AND h.fare_paise IS NULL")
    op.execute("""UPDATE bookings b SET policy_snapshot = jsonb_build_object('version', p.version, 'rules', p.rules, 'disclaimer', p.disclaimer)
        FROM trips t JOIN cancellation_policies p ON p.id = t.cancellation_policy_id
        WHERE b.trip_id = t.id AND b.policy_snapshot IS NULL""")
    for column, stop_column in [("pickup_snapshot", "pickup_stop_id"), ("dropoff_snapshot", "dropoff_stop_id")]:
        op.execute(f"""UPDATE bookings b SET {column} = (to_jsonb(s) - 'route_id' - 'city_id') ||
            jsonb_build_object('stop_datetime', t.departure_datetime + s.offset_minutes * interval '1 minute')
            FROM route_stops s, trips t WHERE b.{stop_column} = s.id AND b.trip_id = t.id AND b.{column} IS NULL""")
    op.execute("""UPDATE bookings b SET confirmed_payment_id = (SELECT pt.gateway_payment_id
        FROM payment_orders po JOIN payment_transactions pt ON pt.payment_order_id = po.id
        WHERE po.booking_id = b.id AND pt.status IN ('CAPTURED', 'REFUNDED')
        ORDER BY pt.created_at, pt.id LIMIT 1) WHERE b.pnr IS NOT NULL AND b.confirmed_payment_id IS NULL""")
    if "notifications" not in tables:
        op.create_table("notifications", sa.Column("id", UUID, primary_key=True),
            sa.Column("booking_id", UUID, sa.ForeignKey("bookings.id"), nullable=False),
            sa.Column("event_key", sa.String(160), nullable=False, unique=True),
            sa.Column("kind", sa.String(40), nullable=False), sa.Column("recipient", sa.String(20), nullable=False),
            sa.Column("message", sa.Text, nullable=False), sa.Column("status", sa.String(20), nullable=False),
            sa.Column("attempts", sa.Integer, nullable=False), sa.Column("provider_message_id", sa.String(255), index=True),
            sa.Column("last_error", sa.String(255)), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    raise RuntimeError("This migration preserves layout history. Restore a backup to roll it back safely.")
