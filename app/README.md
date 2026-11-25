# Barbershop Booking - Microservices

A small Arabic-language booking system for a single barber shop, split into
independently buildable services. Guests book, change or cancel an appointment
with just a phone number (no account). The shop owner signs in to set working
hours per day, close days or time ranges, manage services and prices, and
track bookings.

The project is designed as a DevOps training ground: every service has its own
Dockerfile and can be built, tested and run on its own, while
`docker compose up --build` starts the whole connected system locally.

## Services

| Service       | Responsibility | Owns |
| ------------- | -------------- | ---- |
| `web`         | Arabic UI (server-rendered Django templates). Talks to the two APIs over HTTP; owns no business data. | Its own private session store (SQLite file inside its container) |
| `booking-api` | Services, prices, daily hours, bookings, blocked periods, availability, and every booking rule. | The `booking` PostgreSQL database |
| `identity-api`| Owner login, password change, login lockout (10 failures lock for 15 minutes), owner tokens. | The `identity` PostgreSQL database |
| `gateway`     | nginx entry point. The only port published to the host. | Nothing (infrastructure, not a business service) |
| `db`          | PostgreSQL 16. One server process, two separate databases with separate least-privilege roles. | Persistent volume `postgres_data` |

## Architecture and communication

All calls are synchronous HTTP/JSON (REST). Arrows show who calls whom.

```
                 browser
                   |  HTTP, localhost:8000 (only published port)
                   v
   +---------------------------------- edge network
   |             gateway (nginx :8000)
   |             |            \
   |  /          | /api/booking/*   \ /api/identity/*
   |  v          v                   v
   |  web (:8000) --------+   booking-api (:8001)
   |        |             |          |
   +--------|-------------|----------|------------ app network
            |             |          |
            | HTTP        | HTTP     | HTTP token verification
            v             v          v
          identity-api (:8002) <-----+
            |                |
            +----------------|----------- data network
                         (SQL)
                    db (PostgreSQL :5432)
                    databases: booking, identity
```

Communication pairs and where they live:

| Caller | Callee | Protocol | Port | Shared network |
| ------ | ------ | -------- | ---- | -------------- |
| browser | gateway | HTTP | 8000 | host -> published port |
| gateway | web | HTTP | 8000 | edge |
| gateway | booking-api / identity-api | HTTP | 8001 / 8002 | app |
| web | booking-api | HTTP/JSON | 8001 | app |
| web | identity-api | HTTP/JSON | 8002 | app |
| booking-api | identity-api | HTTP/JSON token verification | 8002 | app |
| booking-api / identity-api | db | PostgreSQL | 5432 | data |

Data and network rules:

- Only `gateway` is reachable from the host (`127.0.0.1:8000`).
- `db` sits on the `data` network only; neither `gateway` nor `web` can reach it.
- Each API connects with its own role, which owns only its own database and
  cannot connect to the other one (`db/init/01-init.sh`).
- The only volume is `postgres_data`. The APIs are stateless; `web` keeps its
  sessions in a private SQLite file inside its own container. That session
  store is container-local and is NOT in `postgres_data`: recreating the
  `web` container ends all sessions, so `web` is not fully stateless. Run
  it as a single replica (the default). To keep sessions across recreation,
  mount a volume at `/app/data` in the `web` container and set
  `WEB_DB_PATH=/app/data/web.sqlite3`; the signing key file is kept next to
  it. Scaling `web` to multiple replicas would additionally need a shared
  session backend, which this single-shop setup does not include.
- One PostgreSQL process holds both databases, so database isolation is at
  the role/privilege level, not separate servers. Network membership is
  defense in depth; it never replaces API authentication or database
  credentials.

## Authentication and authorization

- Guests need no account. A booking is managed with its booking code plus the
  phone number used at booking time. Lookups are rate-limited per web session
  (10 failures lock for 15 minutes).
- Owner login goes to `identity-api`, which returns an opaque bearer token
  (only its SHA-256 hash is stored; tokens expire after 12 hours). The token
  lives only in the `web` service's server-side session, never in a readable
  cookie.
- Every owner request to `booking-api` is verified by calling
  `identity-api`'s introspection endpoint (`POST /api/identity/verify/`).
  Logout, password change and lockout therefore take effect immediately, and
  calling `booking-api` directly without a valid token is refused.

## Booking rules (enforced by booking-api)

- Booking window: today plus two days ahead.
- Working hours come from a recurring weekly template (the owner saves
  it once, e.g. Sat-Thu 10:00-22:00, Friday off). A per-date exception
  (special hours or a day off) always wins over the template for that
  date. New days become bookable automatically as the window rolls
  forward - no daily data entry.
- One barber: overlapping bookings are impossible. Every occupied minute is a
  unique row (`Occupancy`), written in the same PostgreSQL transaction as the
  booking, so even two simultaneous requests for the same slot produce exactly
  one booking.
- Guests may change or cancel up to 2 hours before the appointment.
- Changing a day's hours, closing a day, or shortening the weekly template
  is rejected when it conflicts with existing bookings in the affected
  window; bookings are never auto-cancelled.
- Booking, schedule and occupancy stay in one service on purpose: the
  no-double-booking guarantee depends on row locks and the unique occupancy
  rows inside a single transaction.

## Run it (Docker Compose)

Requirements: Docker Desktop (or any Docker with Compose v2).

```sh
cp .env.example .env    # then fill in the three passwords (any characters work)
docker compose up --build
```

The first start creates the databases and roles, runs migrations and loads
fictional demo data (three services, three days of hours, and a weekly
template of 10:00-22:00 every day). Migrations and the seed are idempotent,
so restarts never duplicate or reset data. On an existing installation the
seed never creates or changes schedule data: the owner saves the weekly
template once from the hours page and it then applies automatically to
every day that has no per-date exception.

- Site: http://127.0.0.1:8000/
- Owner login: http://127.0.0.1:8000/owner/login/ (opened directly; customer
  pages deliberately carry no link to it, and the owner menu appears only
  after sign-in)

Create the owner account once, from a second terminal:

```sh
docker compose exec identity-api python manage.py createsuperuser
```

This is the one deliberate manual step: no default account or password exists.
To disable demo data, set `SEED_DEMO=false` in `.env`.

### Each service independently

Every service is a normal project in its own folder:

```sh
docker build ./booking-api            # or: cd booking-api && pip install -r requirements.txt
cd booking-api && python manage.py test
```

## Tests

```sh
cd booking-api  && python manage.py test   # 27 tests, incl. a PostgreSQL-only concurrency test
cd identity-api && python manage.py test   # 7 tests (tokens, lockout, password change)
cd web          && python manage.py test   # 17 tests (views, sessions, escaping; API layer mocked)
```

The booking concurrency test (`test_two_parallel_requests_only_one_wins`)
runs only against PostgreSQL; it skips on SQLite.

## Verification status (honest)

- All 51 automated tests pass; the booking suite ran against real PostgreSQL 16.
- The full system (all three services plus PostgreSQL with the shipped init
  script and least-privilege roles) was executed and exercised end to end over
  real HTTP: guest booking flow, conflict rejection, lookup limits, owner
  login/lockout, hours/blocks rules, cancellation, and restart idempotency.
- The container definitions (Dockerfiles, `compose.yaml`, nginx config) were
  statically reviewed but **have not been executed with Docker** in the
  authoring environment (no Docker available there). First
  `docker compose up --build` on a real Docker host is the remaining check.

## Limitations

- Single shop, single barber, fictional Egyptian market rules (Arabic UI,
  Egyptian phone numbers, Africa/Cairo timezone).
- No online payment, no notifications (no WhatsApp/email sending).
- Development-oriented local setup: HTTP on localhost, demo seed, one-command
  startup. Production hardening (TLS, real domains, secrets management,
  multiple replicas) is intentionally out of scope.

## Project layout

```
compose.yaml           one-command local startup, networks and volumes
db/init/               database + least-privilege role creation (runs once)
gateway/               nginx entry point
web/                   Django UI service (templates, static, sessions)
booking-api/           Django REST booking service + PostgreSQL
identity-api/          Django REST identity service + PostgreSQL
```
