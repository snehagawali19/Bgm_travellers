from app.models import TrackingStatus, TripLiveState
from tests.conftest import add_trip, seed_launch


def test_schedule_estimate_moves_along_corridor(client, db):
    data = seed_launch(db)
    before = client.get(f"/api/v1/trips/{data['trip_out'].id}/tracking").json()
    assert before["status"] in {"scheduled", "boarding"}
    assert before["progress_percent"] == 0
    assert before["latitude"] == 15.8497

    mid = add_trip(db, data["outbound"], data["bus"], hours_ahead=-4)
    live = client.get(f"/api/v1/trips/{mid.id}/tracking").json()
    assert live["status"] == "in_transit"
    assert 10 < live["progress_percent"] < 90
    assert live["latitude"] < 15.8497
    assert live["source"] == "schedule_estimate"
    assert live["polyline"][0]["name"] == "Belgaum Central"
    assert live["polyline"][-1]["name"] == "Bengaluru"


def test_inbound_corridor_is_reversed(client, db):
    data = seed_launch(db)
    inbound = add_trip(db, data["inbound"], data["bus"], hours_ahead=-4)
    live = client.get(f"/api/v1/trips/{inbound.id}/tracking").json()
    assert live["origin_name"] == "Bengaluru"
    assert live["polyline"][0]["name"] == "Bengaluru"
    assert live["polyline"][-1]["name"] == "Belgaum Central"


def test_admin_gps_overrides_schedule_and_simulator_replays(client, db):
    data = seed_launch(db)
    trip = data["trip_out"]
    login = client.post("/api/v1/admin/auth/login", json={"email": "admin@bgmtravels.in", "password": "ChangeMe_Admin123!"})
    csrf = login.json()["csrf_token"]
    ping = client.post(
        f"/api/v1/admin/trips/{trip.id}/tracking/ping",
        headers={"X-CSRF-Token": csrf},
        json={"latitude": 14.4644, "longitude": 75.9218, "speed_kmh": 70},
    )
    assert ping.status_code == 200
    body = ping.json()
    assert body["source"] in {"gps", "admin"}
    assert body["next_landmark"]

    demo = client.post(
        f"/api/v1/admin/trips/{trip.id}/tracking/simulate",
        headers={"X-CSRF-Token": csrf},
        json={"action": "start", "duration_seconds": 120},
    )
    assert demo.status_code == 200
    assert demo.json()["simulator_active"] is True
    state = db.get(TripLiveState, trip.id)
    assert state is not None
    assert state.status in {TrackingStatus.DEPARTED, TrackingStatus.IN_TRANSIT, TrackingStatus.SCHEDULED}


def test_tracking_list_has_no_passenger_pii(client, db):
    data = seed_launch(db)
    listing = client.get("/api/v1/tracking/trips").json()
    assert listing
    assert "customer_phone" not in listing[0]
    assert listing[0]["trip_id"] == str(data["trip_out"].id) or any(
        item["route_name"].startswith("Belgaum") for item in listing
    )
