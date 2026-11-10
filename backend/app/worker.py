"""Run with python -m app.worker [--once]. No external messages are sent by the API process."""
import argparse
import logging
import time
from datetime import timedelta

from sqlalchemy import select
from app.core.security import utcnow
from app.database import SessionLocal
from app.models import Booking, PaymentOrder, PaymentOrderStatus, Refund, RefundStatus
from app.services.booking import load_booking, reconcile_booking
from app.services.cancellations import admin_retry_refund
from app.services.inventory import expire_holds
from app.services.notifications import deliver_one

logger = logging.getLogger(__name__)


def run_once():
    with SessionLocal.begin() as db:
        expire_holds(db)
    with SessionLocal() as db:
        booking_ids = db.execute(select(Booking.id).join(PaymentOrder).where(
            Booking.channel == "online", Booking.created_at >= utcnow() - timedelta(days=7),
            PaymentOrder.status.in_([PaymentOrderStatus.CREATED, PaymentOrderStatus.FAILED, PaymentOrderStatus.EXPIRED]))
            .distinct().limit(100)).scalars().all()
    for booking_id in booking_ids:
        try:
            with SessionLocal.begin() as db:
                reconcile_booking(db, load_booking(db, booking_id))
        except Exception:
            logger.warning("Payment reconciliation deferred for booking %s", booking_id)
    with SessionLocal() as db:
        refund_ids = db.execute(select(Refund.id).where(Refund.status.in_([
            RefundStatus.REQUESTED, RefundStatus.PROCESSING, RefundStatus.FAILED]),
            Refund.updated_at <= utcnow() - timedelta(seconds=30)).order_by(Refund.updated_at).limit(100)).scalars().all()
    for refund_id in refund_ids:
        try:
            with SessionLocal.begin() as db:
                refund = db.get(Refund, refund_id)
                if refund.cancellation.booking.channel == "online":
                    admin_retry_refund(db, refund_id)
                    refund.updated_at = utcnow()
        except Exception:
            logger.warning("Refund reconciliation deferred for refund %s", refund_id)
    for _ in range(100):
        with SessionLocal.begin() as db:
            if not deliver_one(db):
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Worker cycle failed; it will retry")
            if args.once:
                raise
        if args.once:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
