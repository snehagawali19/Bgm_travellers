# BGM Travels

Working bus-ticket booking product for a small Belgaum operator. Launch service is **one bus** on **Belgaum (Belagavi) ↔ Bengaluru**, with a data model that can add buses, cities, routes and trips without rewriting the booking flow.

This is not a landing-page mock. Search, seat holds, checkout, PNR issuance, cancellations and admin operations talk to PostgreSQL through FastAPI.

## Architecture

| Layer | Choice |
| --- | --- |
| Customer + admin UI | Next.js 15 App Router, TypeScript, Tailwind CSS |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2 |
| Database | PostgreSQL 16 |
| Payments | Razorpay hosted checkout (Test Mode) or a labeled `fake` provider for local/dev tests |
| Money | Integer **paise** only |
| Time | UTC in the database, **Asia/Kolkata** on the UI |

```
frontend (Vercel)  →  FastAPI (Render)  →  PostgreSQL
                              ↑
                     Razorpay webhooks
```

## Phase plan

1. **Foundation** — schema, migrations, seed cities/routes/bus/trips, brand shell.
2. **Booking core** — search, seat map, transactional holds, passenger details, pending booking.
3. **Payments** — Razorpay/test provider, signature verification, webhooks, PNR, e-ticket QR.
4. **Admin + refunds** — cities, buses, seat layouts, trips, manifests, cancellation tracking.
5. **Hardening** — auth, CSRF, rate limits, payment edge cases, automated tests.
6. **Live tracking** — GPS pings, schedule estimate, demo replay, customer/admin maps.
7. **Handover** — docs, expansion checks (second bus, new city), desktop/mobile UI.

## Defaults used because they were not in the brief

- Brand name: **BGM Travels**
- Sample bus: `KA-22-N-2201`, 40-seat 2+2 AC seater
- Sample fare: ₹899
- Sample cancellation policy: 100% / 50% / 0% by time window — **not final commercial terms**
- Contact placeholders: `+91 83100 00000`, `support@bgmtravels.in`
- Local payments: `PAYMENT_PROVIDER=fake` until Razorpay test keys are added

## Local setup

Prerequisites: Node 20+, [uv](https://docs.astral.sh/uv/), and PostgreSQL on port 5432. Docker Desktop is optional; on this Windows machine WSL is not installed, so a portable Postgres under `%LOCALAPPDATA%\bgm-postgres` is used instead.

```powershell
# 1. Database
docker compose up -d
# Windows without Docker/WSL:
.\backend\scripts\start_local_postgres.ps1

# 2. API
cd backend
copy .env.example .env   # already created for local dev
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

# 3. Website (new terminal)
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Track a bus at [http://localhost:3000/track](http://localhost:3000/track). API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

Live tracking:

- Customers: **Track Bus** in the header, or **Track this bus** on a confirmed ticket.
- Admin: **Tracking** in the dashboard — push a GPS ping or start a 6-minute demo replay of the corridor.
- Device ingest later: `POST /api/v1/admin/trips/{id}/tracking/ping` with latitude, longitude, heading and speed.

Admin login:

- Email: `admin@bgmtravels.in`
- Password: `Admin123`

## Tests

```powershell
cd backend
uv run pytest -q
```

Tests use the `db_test` Postgres on port 5433 and the fake payment provider. They cover both route directions, empty search, holds/expiry, payment success/failure/delay, duplicate webhooks, duplicate captures, refunds, admin auth, cross-customer access, bus conflicts, a second bus, and a new city/route.

## Razorpay Test Mode

1. Create a Razorpay test account.
2. Put the key id, key secret and webhook secret in `backend/.env`.
3. Set `PAYMENT_PROVIDER=razorpay` and `PAYMENTS_LIVE_ENABLED=false`.
4. Point the webhook to `https://<api-host>/api/v1/payments/webhook`.
5. Keep live charging off until merchant approval, production secrets, webhook verification and acceptance tests are done.

The frontend never receives the Razorpay secret. Amounts are created on the server. A PNR is issued only after the gateway payment is verified **and** the seats are still held.

If a payment is captured after the hold expires, the booking is moved to `exception` and no conflicting ticket is issued.

## Booking workflow

1. Customer searches published trips for a date.
2. Backend holds selected seats with an expiry.
3. Backend calculates fare, creates a pending booking and a payment order.
4. Customer pays (Razorpay hosted checkout or labeled test checkout).
5. Verify endpoint + signed webhook confirm the payment idempotently.
6. Seats become booked, PNR and QR ticket are issued; a WhatsApp update enters the durable outbox.

## Operational features added November 2026

See [the feature audit](docs/FEATURE_AUDIT.md) for coverage of every requested module and verification limits.

Apply the migration before starting the updated API:

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.worker
```

Run the worker alongside FastAPI. It releases expired holds, reconciles uncertain online payments from the last seven days, submits/reconciles refunds, and sends queued WhatsApp messages. Use `python -m app.worker --once` for a scheduler-managed single cycle. Older uncertain payments can be reconciled from Admin → Payments. The API itself also expires holds on availability and reservation requests, so delayed workers cannot keep expired seats locked.

New admin pages:

- **Fleet:** edit/deactivate buses, edit seat labels/types/positions, save and apply reusable layouts. Old seat versions remain linked to existing trips.
- **Routes:** configure ordered stop addresses, landmarks, and times as minutes after departure. Overnight dates are calculated automatically.
- **Trips:** draft/publish/close/cancel, edit fares/times/cutoffs, manage blocked seats, download manifests, check in passengers, and map reservations when replacing a bus.
- **Schedules:** recurring weekdays and IST departures; generate up to 91 dated departures atomically. Repeated generation skips already-generated dates. Schedule changes do not rewrite existing trips.
- **Counter / phone:** multi-passenger cash, UPI or bank-transfer bookings with retry protection and the same inventory as online checkout.
- **Reports:** occupancy, channel-wise gross collections, completed refunds, net collections, and pending refunds.
- **Staff and notifications:** owner/staff access, versioned cancellation rules, WhatsApp delivery/retry status, and the latest 500 audit entries.

Defaults approved for this implementation: 10-minute holds; booking and customer cancellation close 60 minutes before departure; existing 100%/50%/0% refund windows; cash/UPI/bank transfer. Trip booking cutoffs and policy cancellation cutoffs are configurable. The existing 180-minute bus turnaround buffer remains configurable through `BUS_TURNAROUND_MINUTES`.

Operator trip cancellations queue a full refund regardless of customer cutoff. Online refunds run through the gateway; staff must record money returned for an offline refund. Late and extra captures have separate refund records and cannot claim seats from another booking. A payment retry reuses its original order and quoted fare. Existing `operator` accounts retain owner permissions; new restricted accounts use `booking_staff`.

### WhatsApp configuration

Add the `WHATSAPP_*` settings from `.env.example` to your local environment, including a Business phone-number ID, access token, app secret, and your own webhook verification token. Create and approve a utility template named `bgm_booking_update` (or configure another name) in language `en` with **one body text parameter** for the booking update. For example: `BGM Travels update: {{1}}`. Template approval and live delivery require your agency's Meta account; they are not provisioned by this code.

Configure this public HTTPS callback in Meta and subscribe to message events:

```text
https://<api-host>/api/v1/notifications/whatsapp/webhook
```

The GET handshake checks the verification token; POST callbacks verify `X-Hub-Signature-256` using the app secret. Provider acceptance, sent, delivered, read, retries and failure are tracked separately. Missing credentials leave visible retry/failure records rather than reporting delivery. Delivery is at least once: a process crash after provider acceptance but before database commit may cause a duplicate message. No real WhatsApp messages were sent during implementation.

Refund retries use Razorpay's [idempotent refund API](https://github.com/razorpay/markdown-docs/blob/master/api/refunds/normal-refunds-idempotent.md). See Meta's [template-message guide](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates/) for account/template setup.

## Expansion without rewriting the core

From admin:

1. Register Bus 2 and give it its own seat layout.
2. Publish a new trip assigned to Bus 2.
3. Add Mumbai as a city, then Bengaluru → Mumbai / Belgaum → Mumbai routes.
4. Newly published trips appear in search automatically.
5. Existing PNRs, payments and bookings keep working.
6. Overlapping assignments of the same bus are rejected, including turnaround time.

Cities on the homepage come from the database (active routes only). Mumbai is not bookable until a route exists.

## Production checklist

- [ ] Rotate `SECRET_KEY` and admin password
- [ ] Managed PostgreSQL with backups
- [ ] FastAPI on Render (or similar) with HTTPS
- [ ] Frontend on Vercel, `CORS_ORIGINS` limited to the real domain
- [ ] Razorpay production credentials only after Test Mode sign-off
- [ ] Webhook signature verification against the **raw** body
- [ ] `PAYMENTS_LIVE_ENABLED=true` only in production
- [ ] Confirm real bus registration, seat map, boarding points, fares and cancellation policy
- [ ] Replace placeholder phone, email and office address
- [ ] Restore/backup drill documented with the host

## Known limitations

- Customer accounts and private ticket tokens are supported; no OTP verification. Lookup also supports PNR + mobile.
- WhatsApp needs agency credentials, an approved template, a reachable webhook and the background worker. SMS/email adapters are not configured.
- Full-booking cancellation only. No partial cancel, reschedule or offers.
- Recurring schedules are generated explicitly by staff over a selected date range; there is no automatic rolling timetable publication.
- Lounges and loyalty are out of scope.
- Live tracking uses GPS pings when fresh, otherwise a corridor schedule estimate. Connect a device by posting to `/api/v1/admin/trips/{id}/tracking/ping`.

## Recovering a failed payment / hold

1. Check `/api/v1/health` and Postgres connectivity.
2. Inspect `bookings.booking_status`, `payment_orders` and `webhook_events`.
3. Duplicate webhooks are ignored by `provider + event_id`.
4. Duplicate captured payments mark the booking `exception` and queue a refund for the extra capture, while preserving the original reserved seats and ticket.
5. Admin → Payments → Retry refund for failed gateway refunds.
6. Expired holds, including pending-checkout holds, release seats on availability reads and new reservation requests.
