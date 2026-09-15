# Feature Flags API — Design

## Requirements

### Functional (MVP)

- Create and persist feature flags (`key`, `description`, `enabled` default).
- Enable/disable a flag globally.
- Enable/disable a flag for a specific user (override).
- Evaluate whether a flag is enabled for a user (override → else global default).
- Cache evaluations/flag data; invalidate on writes.
- Sensible HTTP status codes (`200`, `201`, `204`, `400`, `404`, `409`, `422`, `500`, `503`).

### Deferred

Percentage cohorts beyond integer percent, multi-tenant RBAC/OIDC, audit log, SDKs, webhooks, workers/queues, sticky assignment when percent decreases.

### Assumptions

- Missing flag on evaluate → `404`.
- Dev defaults: SQLite + in-process TTL cache; API key optional.
- Production: Postgres + Redis + required `API_KEY`; multi-instance safe.
- DigitalOcean App Platform (or docker compose) for deploy.
- `rollout_percent` default **100** so `enabled=true` still means everyone unless ramped down.
## Non-functional

| Quality | Prototype target |
|---------|------------------|
| Correctness | Deterministic precedence; write-through cache invalidation; tests |
| Durability | SQLite/Postgres via SQLAlchemy + Alembic |
| Latency | Warm-cache evaluate without DB round-trip |
| Consistency | Unique constraints; last-write-wins on concurrent updates |
| Deployability | Docker + App Platform + `/live` `/ready` + GitHub Actions |

## Core entities

### FeatureFlag

- Fields: `id`, `key`, `description`, `enabled`, `rollout_percent` (0–100, default 100), `created_at`, `updated_at`
- Constraints: `UNIQUE(key)`, `key` pattern `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`, check on `rollout_percent`
- Relations: 1 → N `UserOverride`

### UserOverride

- Fields: `id`, `flag_id`, `user_id`, `enabled`, `created_at`, `updated_at`
- Constraints: `UNIQUE(flag_id, user_id)`, FK cascade delete
- Precedence: override wins over global `enabled` + `rollout_percent`

## API contract

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/flags` | Create; optional `rollout_percent` (default 100); `409` on duplicate |
| `GET` | `/flags` | List |
| `GET` | `/flags/{key}` | Get; `404` if missing |
| `PATCH` | `/flags/{key}` | Update `enabled`, `description`, and/or `rollout_percent` |
| `PUT` | `/flags/{key}/users/{user_id}` | Upsert override |
| `DELETE` | `/flags/{key}/users/{user_id}` | Remove override; `404` if missing |
| `GET` | `/evaluate/{key}?user_id=` | Evaluate; returns `source`, `bucket`, `cached` |
| `GET` | `/live` | Liveness (no deps) |
| `GET` | `/ready` | DB + cache readiness |
| `GET` | `/health` | DB check (compat) |

## Data flow

1. **Create/update:** validate → DB transaction → commit → invalidate cache → respond.
2. **Evaluate (miss):** validate → load flag → load override → compute (override / kill switch / SHA-256 bucket vs `rollout_percent`) → cache → respond (`cached: false`).
3. **Evaluate (hit):** cache → respond (`cached: true`).
4. **Duplicate create:** unique violation → `409`.
5. **Startup:** load env → init DB → init cache → bind `0.0.0.0:$PORT`.

**Evaluate precedence:** override → `enabled=false` (source `default`) → else `rollout` via `SHA-256(flag_key:user_id) % 100 < rollout_percent`.
## Architecture

### Development (default)

```mermaid
flowchart LR
  Client --> API[FastAPI / Uvicorn]
  API --> Val[Pydantic validation]
  Val --> Svc[Flag service]
  Svc --> Cache[In-process TTL cache]
  Svc --> DB[(SQLite)]
  API --> Ready["/live /ready /health"]
```

### Production (`ENVIRONMENT=production` + docker compose / App Platform)

```mermaid
flowchart LR
  Client -->|HTTPS + X-API-Key| LB[LB / App Platform]
  LB --> API[FastAPI replicas]
  API --> Val[Pydantic validation]
  Val --> Svc[Flag service]
  Svc --> Redis[(Redis shared TTL cache)]
  Svc --> PG[(Postgres)]
  API --> Ready["/live /ready"]
  API --> Log[Stdout logs + X-Request-ID]
```

Production boot **fails fast** unless Postgres, Redis, and `API_KEY` are configured.

## Technology stack

Python 3.12 · FastAPI · Pydantic · SQLAlchemy · Alembic · Postgres (prod) / SQLite (dev) · Redis (prod) / cachetools memory (dev) · pytest · Uvicorn · Docker Compose · DigitalOcean App Platform · GitHub Actions

## Tradeoffs

| Decision | Choice | Why |
|----------|--------|-----|
| Cache | Redis in prod, memory in dev | Shared coherency across replicas |
| DB | Postgres in prod, SQLite in dev | Concurrent writes + HA |
| Shape | Modular monolith | Enough until async side effects appear |
| Auth | API key when configured | Simple shared-secret for service-to-service |
| Migrations | Alembic | Repeatable schema changes |

## Known limitations

- API key is shared-secret (not OIDC / per-tenant RBAC).
- Last-write-wins under concurrent updates (no optimistic versioning).
- Redis `SCAN` invalidation is good enough at interview/prod-early scale; key versioning is a later optimization.
- No rate limiting / WAF yet — put at the gateway if needed.
- No audit log, percentage rollouts, or webhooks.

## Testing strategy

- Create / duplicate / validation / 404 paths
- Global vs override vs percentage-rollout evaluation
- Cache invalidation after write (including `rollout_percent`)
- `/live`, `/ready`, `/health`
- API-key auth when configured
- Integration tests via FastAPI `TestClient` + temp SQLite + memory cache
- Unit tests for `rollout_bucket` stability

## Scaling plan

Already supports multi-instance via Postgres + Redis. Next increments: gateway rate limits, managed Redis failover, read replicas, OIDC, optional queue for webhooks/audit.
