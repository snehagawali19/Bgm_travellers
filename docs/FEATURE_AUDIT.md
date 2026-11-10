# Requested feature audit

Audit date: 6 November 2026. Implementation is in the existing FastAPI/PostgreSQL and Next.js project. No hosted deployment or live gateway transaction was performed.

| Module | Existing coverage | Additions / corrections |
| --- | --- | --- |
| Fleet and layouts | Bus creation/status and per-trip status rows | Edit/deactivate UI; reusable named layouts; immutable historical seat versions; seat maps and capacities now use trip inventory rather than the bus's current layout. |
| Routes and stops | Both directional routes, ordered pickup/drop points | Address/landmark/time-offset editor; dated stop times; boarding information captured with the booking; direction changes rejected when trips exist. |
| Schedules and trips | One-off trips, publishing/cancellation, basic overlap check | Recurring weekday templates, atomic dated generation and duplicate prevention; closed status, editable times/fares, per-trip cutoff; bus-row locking for concurrent assignment checks; overnight turnaround remains enforced. |
| Search and fares | Direction/date search, fares and availability | Search excludes departures past cutoff; hold quote is preserved through checkout; booking fares and policy terms are snapshots. |
| Inventory and holds | Available/Held/Booked/Blocked, timed holds | Pending checkout expiry fixed; all selected seats are checked before any are held; consistent trip lock for online/offline/expiry/swap/cancellation; blocking held seats rejected. |
| Bookings and tickets | Multiple passengers, PNR, private token, QR and printable ticket | Boarding address/landmark/time on tickets; single-use holds; duplicate passenger seats rejected; payment retry from ticket. |
| Counter and phone | Missing | Staff UI and API, approved offline methods, payment references, stable request keys, shared transactional inventory, channel attribution. |
| Payments and refunds | Razorpay orders/signatures/webhooks, separate refund table | Order/amount/currency validation; authorized-to-captured update; concurrent webhook deduplication; Razorpay event header support; original capture identity; late/extra capture refund queue; order reconciliation; stable refund idempotency keys; refund status reconciliation and offline return recording. |
| Cancellation and changes | Customer policy estimates, trip cancellation | Enforced customer cutoff even for zero-refund cancellation; full operator refunds; pending checkout/hold release on trip cancellation; no cancelled-ticket revival; bus swaps require explicit unique mappings for every booked/blocked seat; changes queue notices. |
| Notifications | Placeholders | Durable WhatsApp template outbox, worker, bounded retry/backoff, signed delivery callbacks and monotonic status; admin visibility/retry. Requires agency credentials and template approval. |
| Access and reporting | Admin authentication, CSV manifest and stored audit entries | Owner/booking-staff server permissions, account administration, check-in, correctly escaped CSV, occupancy/channel collection/refund reports, audit viewer. |

## Important implementation rules

- Replacing a bus layout creates new active seat records and archives the old ones. Existing trip inventory and booking seats continue referencing their original records. No existing reservation is relabeled by a template edit.
- All operations that sell, release or remap a trip's seats take its PostgreSQL row lock. Bus assignment checks take a bus row lock. Requests commit once; a failed multi-seat sale or schedule generation rolls back its whole transaction.
- Hold expiry is enforced synchronously on reads and reservation attempts, independently of the worker. Quoted fares are stored per hold and per booked passenger.
- A replacement bus must have a configured layout and no assignment conflict. Any live holds block the swap. Staff map booked and blocked seats to distinct target seats before the swap can be committed.
- Confirmed booking/payment identifiers and idempotency records prevent retrying an action from issuing another reservation or refund. External WhatsApp delivery is at least once, as described in the README.
- Refund creation is queued in the booking transaction. The worker processes already-committed records, and retries use the persistent refund UUID. Offline refunds require a recorded receipt/reference after money is returned.
- Notifications include private ticket links. The admin notification list deliberately excludes message bodies and tokens.

## Verification performed

- 33 database-independent regression tests passed: cancellation windows, zero-refund eligibility, overnight turnaround, staff access boundaries, gateway order/amount/currency binding, payment transitions, original-versus-extra capture identity, refund idempotency and processing status, WhatsApp payload/retries/status ordering, and input validation.
- Python source compilation, FastAPI import/OpenAPI generation and TypeScript checks passed.
- PostgreSQL integration cases cover historical layouts, checkout expiry, atomic holds, online/offline inventory competition, counter idempotency, operator refunds, bus mapping, late captures and recurring generation. The existing PostgreSQL booking/concurrency/tracking suite is retained.
- **Database tests and migration execution are not verified in this session.** Neither development nor test PostgreSQL was running; the isolated test server was blocked by the Windows sandbox and its elevation request was declined.
- **Production build is not verified.** Next.js failed to spawn build workers (`EPERM`); its elevation request was declined. TypeScript checking is not a substitute for a production build or browser testing.
- Real Razorpay and WhatsApp account calls were not exercised. Provider contract tests use mocks; live credentials remain outside source control.

## Finish verification on your machine

Use a dedicated PostgreSQL test database: the test fixture drops and recreates its public schema. Do not point `TEST_DATABASE_URL` at the application database.

```powershell
# From backend, with PostgreSQL running and configured:
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q

# From frontend:
npm run build
```

Review real boarding points, landmarks and stop offsets in Admin → Routes, then configure WhatsApp and run the worker as described in the README. Migration `004_operations` preserves old reservations and must be applied before the new API starts. It does not provide a destructive automatic downgrade; use a verified database backup for rollback.
