from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from sqlalchemy.orm import sessionmaker

from app.core.errors import ConflictError
from app.services.inventory import create_hold
from tests.conftest import seat_ids, seed_launch


def test_concurrent_holds_only_one_wins(db, engine):
    data = seed_launch(db)
    db.commit()
    trip, bus = data["trip_out"], data["bus"]
    seats = seat_ids(bus, 1)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)

    def attempt():
        session = SessionFactory()
        try:
            create_hold(session, trip.id, [UUID(item) for item in seats])
            session.commit()
            return "ok"
        except ConflictError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    assert results.count("ok") == 1
    assert results.count("conflict") == 1
