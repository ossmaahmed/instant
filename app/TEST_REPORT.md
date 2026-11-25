# Test Report - Microservices version

Date: 2026-11-24

## What was executed (real runs, not inspection)

### Unit and API test suites (69 tests, all passing)

| Suite | Count | Database |
| ----- | ----- | -------- |
| `booking-api` | 37 | Real PostgreSQL 16.2 (including the two-parallel-requests concurrency test, which exercises the row-lock + unique-occupancy guarantee) |
| `identity-api` | 7 | SQLite (login lockout, token issue/verify/expiry/revocation, password change revoking other tokens) |
| `web` | 25 | SQLite (page rendering, redirects, CSRF enforcement, session handling, HTML escaping; API client layer mocked) |

### End-to-end run of the full system

All three services were run as real processes (gunicorn) against a real
PostgreSQL 16.2 server initialized with the shipped `db/init/01-init.sh`,
with the least-privilege roles (`booking`, `identity`). 24 checks, all passing:

- Home page renders seeded services; CSS served by the web service.
- Guest books through the real form (CSRF included); booking code shown.
- Double-booking the same slot is rejected both at the API and through the UI;
  the taken slot disappears from availability.
- Guest lookup: wrong phone rejected, correct code+phone accepted.
- Owner API refuses missing and garbage bearer tokens (verified directly
  against `booking-api`, not only through the gateway path).
- The init script was re-run on a scratch PostgreSQL with passwords
  containing quotes, double quotes, backslashes, spaces, dollar signs and
  backticks: both roles were created, each connects with its exact
  password, cross-database access stays refused, and an empty password is
  rejected before any database write.
- scripts/smoke-gateway.sh (new) is the standing regression test for this
  path: it POSTs through the gateway with real browser headers and fails
  on a 403. It was run against the local web service (SMOKE OK).
- A browser POST through the gateway was reproduced with curl (Host header
  without port, Origin with :8000, as nginx sends with $host): Django 5.2
  rejected it with 403 CSRF bad-origin. After switching the gateway to
  proxy_set_header Host $http_host (keeps the client Host including port),
  the same POST passes CSRF. This hop was the one path not covered by the
  first end-to-end run, which called web directly.
- Wrong owner password rejected; owner login through the UI works; dashboard
  lists the guest booking.
- Shrinking hours around an existing booking is rejected; the booking is not
  auto-cancelled. Closing a booked day is rejected the same way.
- Owner blocks a free period; the blocked slots stop being offered.
- Guest cancellation releases the slot back into availability.
- Owner session validity follows the identity token (logout/lockout revoke).
- Login then dashboard was stress-tested with 40 fresh sessions: 40/40.
- Database isolation: connecting as the `booking` role to the `identity`
  database and vice versa is refused (`REVOKE CONNECT` in the init script).
- Restart idempotency: after a simulated service restart (migrate + seed
  again), service/schedule/booking counts are unchanged and the site keeps
  working. No duplicated demo data, no data reset.

### Bugs found and fixed during this verification

- Web session records are signed with `SECRET_KEY`; with a random per-process
  key and multiple gunicorn workers, roughly one in four logins lost its
  session. Fixed by persisting a generated key in a private file shared by all
  workers (or set `WEB_SECRET_KEY`).

## What was NOT executed

- `docker compose up --build` and the Dockerfiles were not run: no Docker
  daemon was available in the authoring environment. `compose.yaml` was
  validated by parsing and by reviewing the topology (networks, volumes,
  published ports), and the nginx config was reviewed statically. The first
  real Compose run on a Docker host is still pending and may surface
  container-specific issues (for example base-image or DNS details) that
  process-level execution cannot.

## Known limits

- PostgreSQL concurrency test runs only on PostgreSQL (skipped on SQLite).
- The gateway's runtime behavior (DNS-based upstream resolution) is verified
  only statically until the first Compose run.

## UI revisions (generation 7)

- Customer pages carry no owner-login entry; the owner menu renders only with
  a live owner session. Found and fixed along the way: the owner navigation
  was keyed to Django's `user.is_staff`, which is always false in the web
  service (owner identity lives in identity-api), so the owner menu never
  rendered. It is now keyed to the server-side owner session flag. Tests:
  anonymous pages contain no owner link; a signed-in owner sees the menu.
- Times render as natural Arabic 12-hour text with dayparts (صباحًا، ظهرًا،
  عصرًا، مساءً، ليلًا) across slots, hours, dashboard, blocks and booking
  details, including the dashboard's live-refresh JSON. Unit-tested across
  the daypart boundaries.
- Public copy no longer explains internal rules: the lockout-counter line on
  the owner login page, the "saved in the database" line on the booking
  confirmation, and the "updates automatically" mechanics note on the home
  page are gone.
- Found and fixed: an API outage on an owner page caused an infinite
  redirect loop (ApiError handler redirected the dashboard to itself).
  Owner pages now render a retry-later page with HTTP 503 instead, with a
  regression test.
- Visual re-verification on a live local stack (PostgreSQL + all three
  services): home, booking with slots, owner login and owner dashboard at
  1560px and 390px. No horizontal overflow at either width; slot labels,
  dashboard times and the owner menu render as described above.

## Owner/customer interface split (generation 8)

- Owner pages (login, dashboard, manual booking, hours, services, blocks,
  shop settings, password, booking detail, error page) now render with a
  dedicated owner layout: own header (shop name + لوحة الإدارة), owner-only
  navigation, no customer links, owner footer. Shared templates pick their
  layout from a view-supplied context variable, so the customer booking page
  and the owner manual-booking page keep one codebase with two shells.
- Customer pages never show owner entries, including to a signed-in owner.
- Booking page aside keeps only customer-actionable rules (two-day booking
  window, change/cancel deadline, no online payment); the "availability
  follows the owner's hours" implementation note is removed.
- Tests: customer home stays owner-free after owner sign-in; owner pages
  carry owner nav and no customer links; login page has no customer
  navigation. Suite 22/22.
- Visual re-verification on the live local stack: owner login, dashboard,
  owner manual booking, customer home and booking at 1560px and 390px,
  no horizontal overflow, correct nav on each side, logout returns to the
  customer home page.

## Recurring weekly schedule with per-date exceptions (generation 9)

- New `WeeklyHours` table: one row per weekday (open/close times or day off).
  A per-date `Schedule` row (exception: special hours or a day off) always
  wins over the template for that date. Availability, booking, blocking and
  the public schedule feed all resolve through one shared rule, so every
  surface agrees.
- The owner saves the weekly template once from the hours page (seven rows,
  Saturday first); saving is atomic and is rejected with a clear error if the
  new hours would cut across an existing booking in the coming window on a
  template-governed day. Bookings are never auto-cancelled.
- Days without an exception need no data entry: they become bookable
  automatically as the rolling window reaches them.
- Fresh installs still seed a 10:00-22:00 weekly template. On an existing
  installation the seed never creates or changes schedule data, so the
  owner's saved hours, exceptions and bookings are untouched by upgrades.
- Tests: 10 new booking-api tests (effective-schedule resolution, exception
  priority, atomic weekly save, conflict rejection, blocked-day snapshot,
  public feed inclusion, API roundtrip, owner-token enforcement, seed
  preservation on existing data) and 3 new web tests (page render, weekly
  save POST wiring, failure message). Suites: booking-api 37/37, web 25/25.
- Live end-to-end re-verification on the local stack: weekly save returns
  200 and persists 7 rows; an in-window day with its exception removed
  offers template slots (24 slots, 10:00-22:00) and the exception wins again
  once restored; the Friday-off template row removes that day's slots.
- Visual verification: owner hours page with the weekly grid at 1560px and
  390px, element-rect overflow audit clean on both, RTL layout intact.
- Bug found and fixed during this verification: the weekly save response
  returned HTTP 500 after persisting (`WeeklyHours` import missing in the
  API view). Fixed; a new API roundtrip test locks the behavior in.
