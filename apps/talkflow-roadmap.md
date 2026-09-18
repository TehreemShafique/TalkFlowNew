# TalkFlow Backend — Build Manual

**Build order, exact steps, and how to test each piece.**
70% standalone → then VICIdial/Asterisk integration.

---

## Phase Map

```
PHASE 1  STEPS 1-9     Foundation                    
PHASE 2  STEPS 10-13   Auth / RBAC / Users / Audit   
PHASE 3  STEPS 4-9   Calls / Transcripts / Ingest  
PHASE 4  STEPS 20-25   Scripts / Rules / Compliance  
PHASE 5  STEPS 26-3   Leads / Suppression / Campaigns 
PHASE 6  STEPS 32-37   Outbox / WebSocket / Transfer / Verifier 
PHASE 7  STEPS 38-40   Recordings / Basic analytics  
PHASE 8  STEPS 41-48   VICIdial + Asterisk           
PHASE 9  STEPS 49-55   QA / Full analytics / Exports / Ops 
PHASE 10 STEPS 56-60   Hardening                     
```

---

# PHASE 1 — FOUNDATION

## STEP 1 — Clean the repo

```bash
cd talkflow
git rm --cached final_logs.txt temp_logs.txt timeline.txt models.txt \
  test_73.py test_74.py investigate_audio.py timeline_parser.py
git rm -r --cached services/ai-gateway/scratch
git rm --cached services/ai-gateway/fix_tests.py
rm -rf services/ai-gateway/services   # the duplicated nested path
cat >> .gitignore <<'EOF'
*.log
*_logs.txt
scratch/
.env
EOF
```

Rotate the Postgres password. In `docker-compose.yml` replace `POSTGRES_PASSWORD: admin` with `${POSTGRES_PASSWORD}` and put the real value in `.env` (gitignored). The repo is public — assume the old one is burned.

Remove the runtime pip install. In the `ai-gateway` service, delete `pip install aiokafka==0.10.0 &&` from `command:` and add `aiokafka==0.10.0` to `services/ai-gateway/requirements.txt`.

**Test:**
```bash
docker compose build ai-gateway && docker compose up -d
docker compose logs ai-gateway | grep -i aiokafka   # no install line
curl -s localhost:8000/health                       # still 200
git log --all -p | grep -c "POSTGRES_PASSWORD: admin"   # you'll see history; rotate anyway
```

## STEP 2 — Workspace scaffold

```bash
mkdir -p packages/{contracts,db,core,storage,telephony}
mkdir -p services/{app-api,realtime-api,workers}
pipx install uv   # or: pip install uv
```

Root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = ["packages/*", "services/app-api", "services/realtime-api", "services/workers"]

[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E","F","I","UP","B","ASYNC","S","T20"]
ignore = ["S101"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["services", "packages"]

[tool.mypy]
python_version = "3.11"
strict = true
```

Each package gets a minimal `pyproject.toml` with `name`, `version`, `dependencies`.

**Test:**
```bash
uv sync
uv run ruff check .
uv run python -c "import contracts, db, core"   # after step 3-4 create __init__
```

## STEP 3 — Makefile

```makefile
.PHONY: setup up down migrate seed test check contract fmt

setup:
	uv sync && uv run pre-commit install && $(MAKE) contract

up:
	docker compose up -d postgres redis kafka
	uv run uvicorn app.main:app --reload --port 8080 --app-dir services/app-api

down:
	docker compose down

migrate:
	cd services/app-api && uv run alembic upgrade head

seed:
	uv run python -m app.seed --app-dir services/app-api

test:
	uv run pytest -q

test-fast:
	uv run pytest -q -m "not integration"

check:
	uv run ruff check . && uv run ruff format --check . \
	&& uv run mypy packages services \
	&& uv run lint-imports \
	&& cd services/app-api && uv run alembic heads | wc -l | grep -q '^1$$'

contract:
	uv run python -m app.export_openapi > docs/openapi.json
	npx openapi-typescript docs/openapi.json -o apps/dashboard/src/types/api.d.ts

fmt:
	uv run ruff format . && uv run ruff check --fix .
```

**Test:** `make check` fails loudly on an empty repo. That's correct — it proves the gates run.

## STEP 4 — `packages/core`

Files:
```
core/ids.py        uuid7() generator
core/time.py       utcnow()
core/logging.py    structlog config + PII redaction processor
core/errors.py     AppError base
core/phone.py      to_e164(), mask()
core/redaction.py  redact(dict) -> dict
```

`core/ids.py` — UUID v7 (Postgres 16 has no native `uuidv7()`, generate app-side):

```python
import os, time, uuid

def uuid7() -> uuid.UUID:
    ms = int(time.time() * 1000)
    rand = os.urandom(10)
    b = bytearray(ms.to_bytes(6, "big") + rand)
    b[6] = (b[6] & 0x0F) | 0x70          # version 7
    b[8] = (b[8] & 0x3F) | 0x80          # variant
    return uuid.UUID(bytes=bytes(b))
```

**Test:**
```python
# packages/core/tests/test_ids.py
def test_uuid7_is_monotonic_and_versioned():
    ids = [uuid7() for _ in range(1000)]
    assert all(i.version == 7 for i in ids)
    assert [str(i) for i in ids] == sorted(str(i) for i in ids)  # time-ordered

def test_phone_masking():
    assert mask("+13125551234") == "+1312***1234"
```
```bash
uv run pytest packages/core -q
```

## STEP 5 — `packages/contracts`

```
contracts/enums.py       every StrEnum
contracts/errors.py      ErrorCode registry + HTTP status map
contracts/envelope.py    DataResponse[T], PagedResponse[T], Meta, ErrorResponse
contracts/dto/*.py       per-domain pydantic models
contracts/events/*.py    Kafka + WS payloads
contracts/version.py     CONTRACT_VERSION = "1.0.0"
```

Base model — set the camelCase rule once:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class Schema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True,
        from_attributes=True, use_enum_values=False,
    )
```

Envelope:

```python
T = TypeVar("T")

class DataResponse(Schema, Generic[T]):
    data: T

class Meta(Schema):
    page: int; page_size: int; total: int; total_pages: int

class PagedResponse(Schema, Generic[T]):
    data: list[T]
    meta: Meta

class ErrorBody(Schema):
    code: str; message: str; status: int
    details: dict | None = None
    trace_id: str

class ErrorResponse(Schema):
    error: ErrorBody
```

Error registry — one enum, no free strings:

```python
class ErrorCode(StrEnum):
    AUTH_INVALID         = "auth.invalid"
    AUTH_EXPIRED         = "auth.expired"
    AUTH_FORBIDDEN       = "auth.forbidden"
    SCRIPT_NOT_APPROVED  = "script.not_approved"
    SCRIPT_ALREADY_ACTIVE= "script.already_active"
    SCRIPT_SELF_APPROVAL = "script.self_approval_forbidden"
    LEAD_DUPLICATE       = "lead.duplicate"
    LEAD_SUPPRESSED      = "lead.suppressed"
    CAMPAIGN_NO_SCRIPT   = "campaign.no_active_script"
    # ...

STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.AUTH_INVALID: 401, ErrorCode.AUTH_FORBIDDEN: 403,
    ErrorCode.SCRIPT_NOT_APPROVED: 409, ErrorCode.LEAD_DUPLICATE: 409,
}
```

**Test:**
```python
def test_every_error_code_has_a_status():
    for c in ErrorCode:
        assert c in STATUS_MAP, f"{c} missing from STATUS_MAP"

def test_wire_is_camel_case():
    class X(Schema):
        script_version_id: str
    assert "scriptVersionId" in X(script_version_id="a").model_dump(by_alias=True)
```

## STEP 6 — Reconcile the gateway enums (G10)

The gateway already defines `ConversationState`, `QualificationStatus`, `FieldName` in `services/ai-gateway/app/realtime/qualification/types.py`. Move them into `contracts/enums.py`, then in the gateway:

```python
from contracts.enums import ConversationState, QualificationStatus, FieldName
```

**Test:** the gateway's existing suite is the regression check.
```bash
cd services/ai-gateway && uv run pytest -q
```
Green means the move was clean. This is the cheapest possible verification and it uses tests that already exist.

## STEP 7 — `packages/db`

```
db/base.py          DeclarativeBase, TimestampMixin, VersionMixin
db/session.py       async engine, sessionmaker, get_session dependency
db/models/*.py      one file per aggregate
db/repositories/*.py
db/scope.py         AccessScope
db/triggers/*.sql   raw SQL for immutability
db/seed/*.py
```

`db/base.py`:

```python
class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}   # SQLAlchemy does the 409 for you
```

`__mapper_args__ = {"version_id_col": version}` gives you optimistic locking free — SQLAlchemy raises `StaleDataError` on a concurrent write, which you map to a 409.

`db/scope.py` — no default value, so it cannot be forgotten:

```python
@dataclass(frozen=True)
class AccessScope:
    user_id: UUID
    role: str
    campaign_ids: frozenset[UUID] | None   # None = all
    verifier_only: bool = False

    def apply(self, stmt, model):
        if self.campaign_ids is not None and hasattr(model, "campaign_id"):
            stmt = stmt.where(model.campaign_id.in_(self.campaign_ids))
        if self.verifier_only and hasattr(model, "verifier_id"):
            stmt = stmt.where(model.verifier_id == self.user_id)
        return stmt
```

## STEP 8 — Alembic, one history

```bash
cd services/app-api
uv run alembic init -t async alembic
```

In `alembic/env.py`: import `from db.base import Base`, set `target_metadata = Base.metadata`, read `DATABASE_URL` from env.

**Chain off the existing head — do not start a new history:**

```bash
uv run alembic revision --autogenerate \
  -m "control plane core" --head 41960d8b814f
```

Then retire the recording-worker's alembic directory:
```bash
git rm -r services/recording-worker/alembic services/recording-worker/alembic.ini
```

Append the triggers manually inside the migration's `upgrade()`:

```python
op.execute("""
CREATE OR REPLACE FUNCTION raise_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'row is immutable'; END;
$$ LANGUAGE plpgsql;
""")
op.execute("""
CREATE TRIGGER audit_log_immutable BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION raise_immutable();
""")
op.execute("""
CREATE TRIGGER script_version_immutable BEFORE UPDATE ON script_versions
  FOR EACH ROW WHEN (OLD.status <> 'draft') EXECUTE FUNCTION raise_immutable();
""")
op.execute("""
CREATE UNIQUE INDEX one_active_script_per_campaign
  ON script_activations (campaign_id) WHERE deactivated_at IS NULL;
""")
op.execute("""
CREATE UNIQUE INDEX suppression_active_unique
  ON suppression_entries (phone_normalized) WHERE removed_at IS NULL;
""")
```

Partitioning for `calls`, `call_events`, `transcript_turns` — declare the parent partitioned, then a function that creates monthly children:

```python
op.execute("""
CREATE TABLE calls (...) PARTITION BY RANGE (started_at);
""")
op.execute("""
CREATE OR REPLACE FUNCTION ensure_month_partition(tbl text, d date) RETURNS void AS $$
DECLARE s date := date_trunc('month', d); e date := s + interval '1 month';
        name text := tbl || '_' || to_char(s,'YYYYMM');
BEGIN
  EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                  FOR VALUES FROM (%L) TO (%L)', name, tbl, s, e);
END; $$ LANGUAGE plpgsql;
""")
for t in ("calls","call_events","transcript_turns"):
    for off in (0,1,2):
        op.execute(f"SELECT ensure_month_partition('{t}', "
                   f"(CURRENT_DATE + interval '{off} month')::date)")
```

**Test:**
```bash
docker compose up -d postgres
DATABASE_URL=postgresql+asyncpg://... uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head   # round trip
uv run alembic heads      # MUST print exactly one head
psql $DB -c "\d+ calls"   # confirm 'Partition key: RANGE (started_at)'
```

## STEP 9 — Test harness (do this before any feature)

This is the step that makes every later step cheap. `conftest.py` at repo root:

```python
import pytest, asyncio
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from httpx import AsyncClient, ASGITransport

@pytest.fixture(scope="session")
def pg():
    with PostgresContainer("postgres:16-alpine") as c:
        yield c.get_connection_url().replace("psycopg2", "asyncpg")

@pytest.fixture(scope="session")
def redis_url():
    with RedisContainer("redis:7-alpine") as c:
        yield f"redis://{c.get_container_host_ip()}:{c.get_exposed_port(6379)}/0"

@pytest.fixture(scope="session", autouse=True)
def _migrate(pg):
    os.environ["DATABASE_URL"] = pg
    subprocess.run(["alembic","upgrade","head"], cwd="services/app-api", check=True)

@pytest.fixture
async def db(pg):
    """Each test runs in a transaction that is rolled back. No cleanup needed."""
    engine = create_async_engine(pg)
    async with engine.connect() as conn:
        trans = await conn.begin()
        Session = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with Session() as s:
            yield s
        await trans.rollback()

@pytest.fixture
async def client(db):
    from app.main import app
    app.dependency_overrides[get_session] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
async def as_admin(client, db):
    user = await make_user(db, role="MASTER_ADMIN")
    token = issue_access_token(user)
    client.headers["Authorization"] = f"Bearer {token}"
    return user
```

The transaction-rollback fixture is the trick that matters: tests never clean up, never collide, and run in any order.

Factories in `tests/factories.py` — plain async functions, not a framework:

```python
async def make_user(db, *, role="CAMPAIGN_MANAGER", email=None):
    u = User(id=uuid7(), email=email or f"{uuid7()}@t.com",
             role=role, password_hash=hash_pw("x"), status="active")
    db.add(u); await db.flush(); return u

async def make_campaign(db, **kw): ...
async def make_script_version(db, *, status="draft", **kw): ...
async def make_call(db, **kw): ...
```

Mark integration tests so the fast loop stays fast:
```python
# pyproject
markers = ["integration: needs containers"]
```

**Test the harness itself:**
```bash
uv run pytest -q          # should collect 0 tests, 0 errors, containers start/stop
uv run pytest --collect-only | tail -1
```

---

# PHASE 2 — AUTH / RBAC / USERS / AUDIT

## STEP 10 — `app-api` skeleton + cross-cutting

```
services/app-api/app/
  main.py
  core/
    config.py      pydantic-settings
    deps.py        get_session, get_actor, require_permission, Page, IdempotencyKey
    errors.py      exception handlers
    middleware.py  trace_id, request logging
  modules/
  internal/
  export_openapi.py
  seed.py
```

Exception handler — one place, every module inherits it:

```python
class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str | None = None,
                 details: dict | None = None):
        self.code, self.message, self.details = code, message or code.value, details

@app.exception_handler(AppError)
async def handle(request: Request, exc: AppError):
    return JSONResponse(
        status_code=STATUS_MAP.get(exc.code, 400),
        content=ErrorResponse(error=ErrorBody(
            code=exc.code, message=exc.message,
            status=STATUS_MAP.get(exc.code, 400),
            details=exc.details,
            trace_id=request.state.trace_id)).model_dump(by_alias=True))

@app.exception_handler(StaleDataError)
async def handle_stale(request, exc):
    raise AppError(ErrorCode.CONFLICT_STALE)   # optimistic lock -> 409
```

**Test:**
```python
async def test_error_envelope_shape(client):
    r = await client.get("/api/v1/leads/00000000-0000-0000-0000-000000000000")
    assert r.status_code in (401, 404)
    body = r.json()
    assert set(body["error"]) == {"code","message","status","details","traceId"}
```

## STEP 11 — Auth

Endpoints: `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`

Rules to implement:
- Access JWT 15 min, returned in body.
- Refresh: 256-bit random, store SHA-256 hash, set as `httpOnly; Secure; SameSite=Strict`, 7 days.
- Every refresh rotates: new token issued, old marked `revoked_at` + `replaced_by`, same `family_id`.
- If a token with `revoked_at IS NOT NULL` is presented → revoke the whole `family_id` and raise a security alert.
- Argon2id: `argon2-cffi`, `PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)`.
- `/auth/me` returns the user **with resolved `permissions: [str]`**.

**Test — easiest first:**

```bash
# 1. curl smoke against a seeded admin
curl -s -c j.txt -X POST localhost:8080/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@talkflow.local","password":"admin"}' | jq .data.accessToken

curl -s -b j.txt -X POST localhost:8080/api/v1/auth/refresh | jq .data.accessToken
```

```python
# 2. the one test that actually matters
async def test_refresh_reuse_revokes_family(client, db):
    r1 = await login(client)
    old_cookie = client.cookies["refresh_token"]
    await client.post("/api/v1/auth/refresh")            # rotates
    client.cookies.set("refresh_token", old_cookie)      # replay the old one
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401
    rows = (await db.execute(select(RefreshToken))).scalars().all()
    assert all(t.revoked_at is not None for t in rows)   # whole family dead
```

## STEP 12 — RBAC

`core/deps.py`:

```python
def require_permission(perm: str):
    async def dep(actor: Actor = Depends(get_actor)) -> Actor:
        if perm not in actor.permissions:
            raise AppError(ErrorCode.AUTH_FORBIDDEN, details={"required": perm})
        return actor
    return dep
```

Seed roles and permission keys in `db/seed/roles.py`. Six roles: `MASTER_ADMIN`, `CAMPAIGN_MANAGER`, `VERIFIER`, `QA_MANAGER`, `REPORTING_USER`, `IT_OPS`.

**The test that enforces R4 across the whole app — write it once, it guards forever:**

```python
PUBLIC = {"/api/v1/auth/login", "/api/v1/auth/refresh", "/health", "/ready",
          "/docs", "/openapi.json", "/redoc"}

def test_every_route_is_permission_guarded():
    from app.main import app
    naked = []
    for route in app.routes:
        if getattr(route, "path", None) in PUBLIC: continue
        if not hasattr(route, "dependant"): continue
        names = {d.call.__qualname__ for d in route.dependant.dependencies if d.call}
        if not any("require_permission" in n or "public" in n for n in names):
            naked.append(f"{route.methods} {route.path}")
    assert not naked, f"routes with no permission dependency: {naked}"
```

Add a new endpoint without a guard and CI fails. That single test replaces a code-review rule.

## STEP 13 — Audit

Decorator writes in the caller's transaction:

```python
def audited(action: str, resource_type: str):
    def deco(fn):
        @wraps(fn)
        async def inner(self, *a, actor: Actor, **kw):
            result = await fn(self, *a, actor=actor, **kw)
            self.db.add(AuditLog(
                id=uuid7(), ts=utcnow(), actor_id=actor.id, actor_role=actor.role,
                action=action, resource_type=resource_type,
                resource_id=getattr(result, "id", None), result="success",
                metadata=redact(kw), trace_id=trace_id_var.get()))
            return result
        return inner
    return deco
```

**Test — both halves:**

```python
async def test_audit_rolls_back_with_business_write(db, svc):
    with pytest.raises(AppError):
        await svc.do_thing_that_fails(actor=admin)
    assert (await db.scalar(select(func.count()).select_from(AuditLog))) == 0

async def test_audit_is_immutable(db):
    row = await make_audit(db)
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(text("UPDATE audit_log SET action='x' WHERE id=:i"),
                         {"i": row.id})
```

The second test is the pattern for **every** invariant from now on: attempt the violation in raw SQL, assert the database refuses.

---

# PHASE 3 — CALLS / TRANSCRIPTS / INGEST

**This is the milestone that turns the bot into a product. Build it before scripts.**

## STEP 14 — Call tables + read API

Endpoints:
```
GET   /api/v1/calls                     list + filters + scope
GET   /api/v1/calls/live                Redis snapshot, not Postgres
GET   /api/v1/calls/{id}
PATCH /api/v1/calls/{id}/disposition    writes call_disposition_history
GET   /api/v1/calls/{id}/transcript
GET   /api/v1/calls/{id}/timeline
GET   /api/v1/calls/{id}/performance
GET   /api/v1/calls/{id}/script-path
```

Stamp at open, never update: `script_version_id`, `rule_set_version_id`, `campaign_config_version`, `compliance_profile_version`, `channel_id`, `did_used`, `caller_id_used`, `agent_alias_used`.

`status` (telephony) and `disposition` (business) are **separate columns with separate state machines**. Do not merge them — contact rate becomes uncomputable if you do.

## STEP 15 — Ingest consumer

`services/workers/app/consumers/call_ingest.py` consuming:
```
talkflow.call.opened.v1  .event.v1  .transcript.v1  .field.v1  .closed.v1
```

Three rules in the handler:
1. **Dedupe** on `(call_id, external_event_id)` — unique index does the work, catch `IntegrityError` and ack.
2. **Open is idempotent** on `channel_id` — unique constraint; on conflict, return the existing call.
3. **Out-of-order**: reconcile by `event_ts`, never arrival order. A `closed` that arrives before an `event` still accepts the event into `call_events` but does not reopen the call.

## STEP 16 — The fake gateway (build this, it unblocks everything)

`tools/fake_gateway.py` — publishes a realistic call to Kafka so you can build and demo the whole product with no bot, no Asterisk, no phone.

```python
import asyncio, json, uuid, time
from aiokafka import AIOKafkaProducer

SCRIPT = [
    ("bot",  "Hi, how are you doing today? This is Adriana.",        "n_greeting"),
    ("bot",  "I'm calling because your health and groceries benefit "
             "have not been claimed yet, and they're about to close out.", "n_pitch"),
    ("bot",  "So do you currently have Medicare Part A and B?",      "n_part_ab"),
    ("user", "yes I do",                                            "n_part_ab"),
    ("bot",  "And are you between the age of 60 to 87?",             "n_age_range"),
    ("user", "yeah I'm 71",                                         "n_age_range"),
    ("bot",  "Alright, great.",                                     "n_confirm"),
    ("bot",  "Now let me bring the senior on the line. Please stay on the line.",
                                                                    "n_transfer"),
]

async def run(campaign_id, lead_id, outcome="qualified", speed=1.0):
    p = AIOKafkaProducer(bootstrap_servers="localhost:9092",
                         value_serializer=lambda v: json.dumps(v).encode())
    await p.start()
    call_id, chan = str(uuid.uuid4()), f"{int(time.time())}.{uuid.uuid4().hex[:6]}"
    seq = 0
    def ev(**kw):
        nonlocal seq; seq += 1
        return {"callId": call_id, "externalEventId": f"{call_id}-{seq}",
                "eventTs": time.time(), **kw}

    await p.send_and_wait("talkflow.call.opened.v1", ev(
        channelId=chan, campaignId=campaign_id, leadId=lead_id,
        direction="outbound", scriptVersionId=None, agentAlias="Adriana"))

    t = 0
    for speaker, text, node in SCRIPT:
        await asyncio.sleep(0.3 * speed)
        await p.send_and_wait("talkflow.call.event.v1",
                              ev(type="node_entered", nodeId=node))
        await p.send_and_wait("talkflow.call.transcript.v1", ev(
            speaker=speaker, text=text, startMs=t, endMs=t+2000,
            nodeId=node, confidence=0.93, isFinal=True))
        t += 2500
        if speaker == "user" and node == "n_part_ab":
            await p.send_and_wait("talkflow.call.field.v1", ev(
                field="medicare_part_ab", value=True, valueType="boolean",
                confidence=0.95, nodeId=node))
        if speaker == "user" and node == "n_age_range":
            await p.send_and_wait("talkflow.call.field.v1", ev(
                field="age_in_range", value=True, valueType="boolean",
                confidence=0.91, nodeId=node))

    await p.send_and_wait("talkflow.call.closed.v1", ev(
        status="completed", proposedDisposition=outcome, durationSeconds=int(t/1000),
        performance={"vadMs": 18, "sttMs": 240, "decideMs": 9,
                     "ttsTtfaMs": 410, "totalTurnMs": 690}))
    await p.stop()
    print("call:", call_id, "channel:", chan)

if __name__ == "__main__":
    import sys
    asyncio.run(run(sys.argv[1], sys.argv[2],
                    sys.argv[3] if len(sys.argv) > 3 else "qualified"))
```

**Test — this is now your whole dev loop:**

```bash
python tools/fake_gateway.py <campaign_id> <lead_id> qualified
curl -s localhost:8080/api/v1/calls | jq '.data[0]'
curl -s localhost:8080/api/v1/calls/<id>/transcript | jq '.data | length'   # 8
curl -s localhost:8080/api/v1/calls/<id>/script-path | jq
```

Loop it for volume:
```bash
for i in $(seq 1 200); do
  python tools/fake_gateway.py $CAMP $LEAD \
    $(shuf -n1 -e qualified disqualified_no_part_ab no_answer opted_out) &
done; wait
```
200 calls in seconds. Now the dashboard, analytics, QA and filters all have real data to build against.

## STEP 17 — Idempotency test for ingest

```python
async def test_replayed_events_create_nothing_new(db, ingest):
    events = load_fixture("call_qualified.json")
    for e in events: await ingest.handle(e)
    for e in events: await ingest.handle(e)          # full replay
    assert await db.scalar(select(func.count()).select_from(Call)) == 1
    assert await db.scalar(select(func.count()).select_from(TranscriptTurn)) == 8

async def test_out_of_order_events(db, ingest):
    events = load_fixture("call_qualified.json")
    await ingest.handle(events[0])
    await ingest.handle(events[-1])                   # closed arrives early
    for e in events[1:-1]: await ingest.handle(e)     # the middle catches up
    call = await get_call(db)
    assert call.status == "completed"
    assert call.ended_at == events[-1]["eventTs"]     # not overwritten
```

## STEP 18 — Transcripts

Only `isFinal` turns persist. Partials are realtime-only. `node_id` is mandatory — it is what makes the script-path tab and node-level QA possible.

Search column:
```sql
ALTER TABLE transcript_turns ADD COLUMN tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX transcript_tsv_idx ON transcript_turns USING GIN (tsv);
```

**Test:**
```python
async def test_transcript_search(db):
    await make_turns(db, ["I have medicare part a and b", "no thanks"])
    rows = await repo.search(scope=ADMIN, q="medicare")
    assert len(rows) == 1
```

## STEP 19 — Gateway changes G1/G2/G3/G5/G8/G9

In `services/ai-gateway`:

**G1** — an `EventPublisher` that mirrors the existing `RecordingRequestPublisher` shape, publishing the five topics.

**G2** — buffer and replay. The current publisher logs and drops. Replace with a bounded `asyncio.Queue` plus a disk spill:

```python
class BufferedPublisher:
    async def publish(self, topic, payload):
        try:
            await self._producer.send_and_wait(topic, payload)
        except Exception:
            await self._spill(topic, payload)      # append JSONL to /var/lib/tf/spill
    async def replay_loop(self):
        while True:
            await self._drain_spill()
            await asyncio.sleep(5)
```

**G3** — identity at session open. Dialplan side (you have the box, go read `/etc/asterisk/extensions.conf` first):
```
exten => _X.,n,Set(TF_UUID=${UNIQUEID})
exten => _X.,n,AudioSocket(${TF_UUID},<gateway>:9019)
```
Gateway side: on connect, take the UUID from the AudioSocket handshake, call `GET /internal/session/{uniqueid}`; if that 404s, refuse the call and alert. **No guessing.**

**G5** track `recording_offset_ms` at each compliance node. **G8** attach `node_id` to every emitted turn. **G9** emit the frozen latency field names.

**Test G2 specifically — this is the one that silently fails in production:**
```bash
docker compose stop kafka
python services/ai-gateway/run_test_client.py      # run a full call
ls -la /var/lib/tf/spill/                          # events on disk
docker compose start kafka
sleep 15
curl -s localhost:8080/api/v1/calls | jq '.data[0].id'   # call appears, nothing lost
```

---

# PHASE 4 — SCRIPTS / RULES / COMPLIANCE

## STEP 20 — Scripts + versions

```
GET/POST   /api/v1/scripts
GET/PATCH  /api/v1/scripts/{id}
POST       /api/v1/scripts/{id}/duplicate
GET/POST   /api/v1/scripts/{id}/versions
GET/PATCH  /api/v1/scripts/{id}/versions/{v}
POST       .../submit  .../approve  .../reject  .../activate
GET        .../diff?against=N
POST       .../simulate
GET        /api/v1/scripts/approvals
```

State machine in `policies.py`, pure:

```python
ALLOWED = {
    ("draft","pending_approval"), ("pending_approval","approved"),
    ("pending_approval","draft"), ("approved","active"),
    ("active","archived"), ("approved","archived"),
}
def can_transition(frm: str, to: str) -> bool: return (frm,to) in ALLOWED
```

## STEP 21 — Graph validation

Pure function, no DB. Rules:

```python
def validate_graph(nodes, entry_id, profile) -> list[GraphError]:
    errs = []
    ids = {n["id"] for n in nodes}
    if entry_id not in ids: errs.append(...MISSING_ENTRY)
    for n in nodes:
        for t in n.get("transitions", []):
            if t["nextNodeId"] not in ids:
                errs.append(GraphError(n["id"], "DANGLING_TRANSITION", t["nextNodeId"]))
    reachable = bfs(nodes, entry_id)
    for n in nodes:
        if n["id"] not in reachable:
            errs.append(GraphError(n["id"], "UNREACHABLE"))
        if n.get("terminal") is not True and not n.get("transitions"):
            errs.append(GraphError(n["id"], "DEAD_END"))
    # compliance: no benefit node reachable before the disclaimer node
    if profile.rule("tpmo_disclaimer_precedes_benefits") == "enforce":
        for path in all_paths(nodes, entry_id):
            seen_disc = False
            for nid in path:
                node = by_id[nid]
                if node.get("complianceRole") == "tpmo_disclaimer": seen_disc = True
                if node.get("discussesBenefits") and not seen_disc:
                    errs.append(GraphError(nid, "BENEFITS_BEFORE_DISCLAIMER"))
                    break
    return errs
```

**Test — table-driven, fast, no I/O:**
```python
@pytest.mark.parametrize("fixture,expected", [
    ("valid_medicare.json",       []),
    ("dangling_transition.json",  ["DANGLING_TRANSITION"]),
    ("unreachable_node.json",     ["UNREACHABLE"]),
    ("dead_end.json",             ["DEAD_END"]),
    ("benefits_first.json",       ["BENEFITS_BEFORE_DISCLAIMER"]),
])
def test_graph_validation(fixture, expected):
    codes = [e.code for e in validate_graph(*load(fixture), profile=STRICT)]
    assert sorted(codes) == sorted(expected)
```
Add a fixture file per rule. Runs in milliseconds, catches everything.

## STEP 22 — Immutability + single-active

**The two invariant tests that justify the whole module:**

```python
async def test_approved_version_cannot_be_mutated(db):
    v = await make_script_version(db, status="approved")
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(text("UPDATE script_versions SET nodes='{}' WHERE id=:i"),
                         {"i": v.id})

async def test_concurrent_activation_yields_exactly_one(pg):
    """Two sessions, two versions, same campaign, same instant."""
    v1, v2 = await make_two_approved_versions()
    async def act(v):
        async with new_session(pg) as s:
            try:
                await ScriptService(s).activate(v.script_id, v.version, actor=ADMIN)
                return "ok"
            except (IntegrityError, AppError):
                return "rejected"
    results = await asyncio.gather(act(v1), act(v2))
    assert sorted(results) == ["ok", "rejected"]
```

The second one needs **two real sessions**, not one — a single session will not exercise the partial unique index.

## STEP 23 — Simulation

Takes per-node **events**, not a flat answer map. Otherwise you cannot test `no_response` or `invalid` paths.

```json
POST /api/v1/scripts/{id}/versions/{v}/simulate
{ "events": [
    {"nodeId":"n_greeting","event":"always"},
    {"nodeId":"n_part_ab","event":"yes","value":true},
    {"nodeId":"n_age_range","event":"no_response"},
    {"nodeId":"n_age_range","event":"yes","value":true}
]}
```

Returns the node path, captured fields, the qualification result and any compliance rules unsatisfied.

**Test — reproduce a real persisted call:**
```python
async def test_simulation_matches_a_real_call(db, client):
    call = await seeded_call(db)                   # from fake_gateway
    events = derive_events_from(call.node_path, call.fields)
    r = await client.post(f"/api/v1/scripts/{sid}/versions/1/simulate",
                          json={"events": events})
    assert r.json()["data"]["nodePath"] == [n.node_id for n in call.node_path]
    assert r.json()["data"]["qualificationStatus"] == call.qualification_status
```
If the simulator and the engine can diverge, the preview lies. This test is what stops that.

## STEP 24 — Rule sets

Constrained expression language only — field refs, comparisons, boolean composition, set membership. **No eval, no Python, no LLM.**

```python
OPS = {"==": eq, "!=": ne, "<": lt, "<=": le, ">": gt, ">=": ge, "in": isin}

def evaluate(rule_set: dict, fields: dict) -> Evaluation:
    for cond in rule_set["all"]:
        v = fields.get(cond["field"])
        if v is None:
            return Evaluation("incomplete", f"missing:{cond['field']}")
        if not OPS[cond["operator"]](v, cond["value"]):
            return Evaluation("disqualified",
                              rule_set["disqualificationReasons"][cond["field"]])
    return Evaluation("qualified", None)
```

**Test — the whole truth table for the live rule set:**
```python
@pytest.mark.parametrize("part_ab,age,expected,reason", [
    (True,  True,  "qualified",    None),
    (False, True,  "disqualified", "disqualified_no_part_ab"),
    (True,  False, "disqualified", "disqualified_age_range"),
    (False, False, "disqualified", "disqualified_no_part_ab"),  # first failure wins
    (None,  True,  "incomplete",   "missing:medicare_part_ab"),
])
def test_medicare_rule_set(part_ab, age, expected, reason):
    r = evaluate(MEDICARE_RS, {"medicare_part_ab": part_ab, "age_in_range": age})
    assert (r.status, r.reason) == (expected, reason)
```

## STEP 25 — Compliance profiles + bundle compile

`compliance_profiles` / `compliance_rules` with modes `enforce | warn | off`. Setting anything to `warn` or `off` requires `MASTER_ADMIN`, a typed confirmation and a mandatory rationale, and writes an audit row.

On activation, compile the version into a bundle and write it to Redis:
```
cp:script:bundle:{scriptVersionId}   → the full JSON
cp:campaign:{id}:active_script       → the version id
```

**Test:**
```python
async def test_activation_publishes_bundle(redis, svc):
    v = await make_approved_version()
    await svc.activate(v.script_id, v.version, actor=ADMIN)
    ptr = await redis.get(f"cp:campaign:{v.campaign_id}:active_script")
    assert ptr.decode() == str(v.id)
    assert json.loads(await redis.get(f"cp:script:bundle:{v.id}"))["entryNodeId"]

async def test_inflight_calls_keep_their_bundle(redis, svc):
    v1 = await activate_version(1)
    bundle_before = await redis.get(f"cp:script:bundle:{v1.id}")
    await activate_version(2)
    assert await redis.get(f"cp:script:bundle:{v1.id}") == bundle_before  # not evicted
```

## STEP 26 — G4: gateway executes the bundle

Replace the hardcoded `ConversationState` walk with a graph walk. **Reuse unchanged:** extractors, validators, clarification counting, LLM fallback, response planner, speech normalization, TTS, barge-in. Only sequencing and prompt source become data.

**Test — parity first, features second:**
```bash
# 1. author a bundle that reproduces today's hardcoded flow exactly
# 2. run the existing gateway suite against it
cd services/ai-gateway && uv run pytest tests/ -q
# 3. drive it through the existing text harness
curl -s -X POST localhost:8000/internal/qualification/test \
  -d '{"utterances":["yes","yeah I am 71"]}' | jq
```
Green existing tests = the rewrite is safe. Do not author a new script until parity passes.

---

# PHASE 5 — LEADS / SUPPRESSION / CAMPAIGNS

## STEP 27 — Leads

```
GET/POST   /api/v1/leads
GET/PATCH  /api/v1/leads/{id}
POST       /api/v1/leads/bulk-assign
```

Non-negotiables:
- `phone_normalized` E.164 on write.
- `external_key` — **≤20 chars**, base32 of a 12-byte prefix, unique. This is what becomes `vendor_lead_code` in Phase 8. Add it now; retrofitting a key into a live lead table is miserable.
- `attempts`, `last_attempt_at`, `next_attempt_at` are system-written only. Reject them in the PATCH schema entirely — not "ignore", reject with 422.
- Status transitions validated against a state machine.

**Test:**
```python
def test_system_fields_are_rejected_not_ignored():
    with pytest.raises(ValidationError):
        LeadPatch(attempts=0)

async def test_external_key_fits_vendor_lead_code():
    lead = await make_lead(db)
    assert len(lead.external_key) <= 20
```

## STEP 28 — Import pipeline

Five stages, five endpoints:
```
POST /api/v1/leads/import                  multipart → jobId, status=mapping
POST /api/v1/leads/import/{job}/mapping
GET  /api/v1/leads/import/{job}            poll status + counts
GET  /api/v1/leads/import/{job}/errors     CSV download
POST /api/v1/leads/import/{job}/commit     Idempotency-Key required
```

Stream the file, never load it. Validate into `lead_import_rows` with a verdict per row. **Nothing touches `leads` until commit.** Commit in batches of 1000, each its own transaction.

**Test:**
```bash
# generate 100k rows and time it
python - <<'EOF'
import csv, random
with open('/tmp/leads.csv','w',newline='') as f:
    w = csv.writer(f); w.writerow(['phone','first_name','state','zip'])
    for i in range(100_000):
        w.writerow([f"1312{random.randint(1000000,9999999)}", "Test", "IL", "60601"])
EOF

time curl -s -F file=@/tmp/leads.csv localhost:8080/api/v1/leads/import
# → jobId
curl -s -X POST .../mapping -d '{"phone":"phone","firstName":"first_name"}'
curl -s .../<job>            # watch counts climb
curl -s -X POST .../commit -H 'Idempotency-Key: abc123'
curl -s -X POST .../commit -H 'Idempotency-Key: abc123'   # replay
```
```python
async def test_double_commit_creates_no_duplicates(client, db):
    job = await staged_job(db, rows=1000)
    h = {"Idempotency-Key": "k1"}
    r1 = await client.post(f"/api/v1/leads/import/{job}/commit", headers=h)
    r2 = await client.post(f"/api/v1/leads/import/{job}/commit", headers=h)
    assert r1.json() == r2.json()
    assert await db.scalar(select(func.count()).select_from(Lead)) == 1000
```
Target: ≥5,000 rows/min. If it's slower, you're not streaming.

## STEP 29 — Suppression

```
GET    /api/v1/suppression
POST   /api/v1/suppression
POST   /api/v1/suppression/import
DELETE /api/v1/suppression/{id}         MASTER_ADMIN + reason + typed confirm
GET    /api/v1/suppression/check?phone= Redis-first, Postgres fallback
```

Rules:
- Global to the caller, **not campaign-scoped**.
- Multi-channel intake: `in_call_keyword`, `in_call_keypress`, `inbound_call`, `web_form`, `manual`, `free_text_review`.
- SLA clock: `honored_at - received_at`, alert before 10 business days.
- Removal is **soft** — set `removed_at`, keep the row.
- Column `vicidial_synced_at` exists now, stays NULL until Phase 8.

**Test:**
```python
async def test_suppressed_lead_is_never_dialable(db):
    lead = await make_lead(db, phone="13125551234")
    await suppression_svc.add("13125551234", reason="caller_request", actor=ADMIN)
    dialable = await lead_repo.find_dialable(scope=ADMIN, campaign_id=c.id)
    assert lead.id not in {l.id for l in dialable}

async def test_removal_is_soft():
    await suppression_svc.remove(e.id, reason="wrong number", actor=ADMIN)
    row = await db.get(SuppressionEntry, e.id)
    assert row is not None and row.removed_at is not None
```

## STEP 30 — Campaigns

```
GET/POST   /api/v1/campaigns
GET/PATCH  /api/v1/campaigns/{id}
POST       /api/v1/campaigns/{id}/start|pause|stop
GET        /api/v1/campaigns/{id}/stats
```

Start guard returns **all** problems:

```python
def can_start(c: CampaignSnapshot) -> list[ErrorCode]:
    p = []
    if not c.active_script_version_id: p.append(E.CAMPAIGN_NO_ACTIVE_SCRIPT)
    if not c.rule_set_version_id:      p.append(E.CAMPAIGN_NO_RULE_SET)
    if not c.compliance_profile_id:    p.append(E.CAMPAIGN_NO_COMPLIANCE_PROFILE)
    if not c.verifier_group_id:        p.append(E.CAMPAIGN_NO_VERIFIER_GROUP)
    if not c.caller_ids:               p.append(E.CAMPAIGN_NO_CALLER_ID)
    return p
```

Add `vicidial_campaign_id` and `campaign_vicidial_lists` now, nullable, unused.

**Test:**
```python
async def test_start_reports_every_gap_at_once(client):
    c = await make_campaign(client, bare=True)
    r = await client.post(f"/api/v1/campaigns/{c}/start")
    assert r.status_code == 409
    assert len(r.json()["error"]["details"]["problems"]) == 5
```

## STEP 31 — Telephony seam (the thing that makes Phase 8 one file)

`packages/telephony/protocol.py`:

```python
class TelephonyAdapter(Protocol):
    async def push_lead(self, lead: Lead, campaign: Campaign) -> ExternalLeadRef: ...
    async def suppress(self, phone: str, scope: str) -> None: ...
    async def unsuppress(self, phone: str, scope: str) -> None: ...
    async def write_disposition(self, call: Call, status: str) -> None: ...
    async def verifier_availability(self, group: str) -> AvailabilityCounts: ...
    async def find_recording(self, call: Call) -> RecordingRef | None: ...
```

`packages/telephony/manual.py` — ships now:

```python
class ManualDialAdapter:
    """No dialer. Logs intent, returns synthetic refs. Calls placed by hand."""
    async def push_lead(self, lead, campaign):
        log.info("manual.push_lead", lead=str(lead.id), phone=lead.phone_normalized)
        return ExternalLeadRef(system="manual", external_id=lead.external_key)
    async def suppress(self, phone, scope):
        log.info("manual.suppress", phone=mask(phone), scope=scope)
    async def write_disposition(self, call, status):
        log.info("manual.disposition", call=str(call.id), status=status)
    async def verifier_availability(self, group):
        return AvailabilityCounts(available=len(await redis_available(group)))
    async def find_recording(self, call): return None
```

Wired by config: `TELEPHONY_ADAPTER=manual` now, `vicidial` in Phase 8.

**Test — write the contract suite once, run it against both adapters:**
```python
@pytest.fixture(params=["manual"])            # Phase 8: add "vicidial"
def adapter(request): return build_adapter(request.param)

async def test_push_lead_returns_a_ref(adapter, lead, campaign):
    ref = await adapter.push_lead(lead, campaign)
    assert ref.external_id

async def test_suppress_is_idempotent(adapter):
    await adapter.suppress("13125551234", "system")
    await adapter.suppress("13125551234", "system")   # no raise
```
In Phase 8 you add one string to `params` and the same suite validates the real adapter.

---

# PHASE 6 — OUTBOX / WEBSOCKET / TRANSFER / VERIFIER

## STEP 32 — Transactional outbox

```sql
CREATE TABLE outbox (
  id uuid PRIMARY KEY, aggregate_type text, aggregate_id uuid,
  channel text, event_type text, seq bigint, payload jsonb,
  created_at timestamptz DEFAULT now(), dispatched_at timestamptz, attempts int DEFAULT 0
);
CREATE INDEX outbox_pending ON outbox (created_at) WHERE dispatched_at IS NULL;
CREATE SEQUENCE outbox_seq_dashboard;   -- one per channel
```

`seq` comes from a **Postgres sequence assigned at insert**, not Redis `INCR`. Redis breaks ordering across replicas.

Dispatcher fans out to Kafka and Redis **in parallel**:
```python
await asyncio.gather(
    kafka.send(row.event_type, row.payload),
    redis.publish(f"cp:channel:{row.channel}", json.dumps(row.payload)),
)
```

**Test:**
```python
async def test_rollback_drops_the_event(db, svc):
    with pytest.raises(AppError):
        await svc.thing_that_fails()
    assert await db.scalar(select(func.count()).select_from(Outbox)) == 0

async def test_dispatcher_replays_after_outage(db, dispatcher, kafka_down):
    await svc.emit_something()
    await dispatcher.tick()                      # fails
    assert (await get_outbox_row()).dispatched_at is None
    kafka_down.restore()
    await dispatcher.tick()
    assert (await get_outbox_row()).dispatched_at is not None

async def test_seq_is_monotonic_under_concurrency(db):
    await asyncio.gather(*[svc.emit() for _ in range(50)])
    seqs = await db.scalars(select(Outbox.seq).order_by(Outbox.created_at))
    assert list(seqs) == sorted(seqs)
```

## STEP 33 — `realtime-api`

Protocol, in order:
1. Client connects.
2. First frame within 5s: `{"type":"auth","token":"<jwt>"}` — else close.
3. `{"type":"subscribe","channels":["dashboard","calls.live"]}` — **permission and scope checked at subscribe AND again at fanout**.
4. Server pings every 30s; two misses → close.
5. Each message carries `seq`; client drops anything ≤ last applied.
6. Per-socket outbound queue cap; on overflow emit `resync_required` rather than growing memory.

The heartbeat doubles as verifier presence — refresh `cp:verifier:{id}:availability` TTL on each pong.

**Test:**
```bash
# wscat is the fastest manual check
npm i -g wscat
wscat -c ws://localhost:8081/ws
> {"type":"auth","token":"<paste>"}
> {"type":"subscribe","channels":["calls.live"]}
# in another terminal:
python tools/fake_gateway.py $CAMP $LEAD
# events should stream into the wscat window
```
```python
async def test_verifier_cannot_subscribe_to_calls_live(ws_client):
    await ws_client.auth(as_role="VERIFIER")
    r = await ws_client.subscribe(["calls.live"])
    assert r["type"] == "error" and r["code"] == "auth.forbidden"

async def test_fanout_masks_pii_per_subscriber(ws_admin, ws_reporting):
    await emit_call_started(phone="+13125551234")
    assert (await ws_admin.recv())["caller"]["number"] == "+13125551234"
    assert (await ws_reporting.recv())["caller"].get("number") is None
```

## STEP 34 — Transfers

```
GET  /api/v1/transfers
GET  /api/v1/transfers/failed
POST /api/v1/transfers/{id}/retry
POST /api/v1/transfers/{id}/create-callback
```

Offer reservation — Redis `SET NX` with TTL = ring timeout, Postgres row as the durable truth:

```python
ok = await redis.set(f"cp:verifier:{vid}:offer", str(transfer_id),
                     nx=True, ex=ring_timeout_seconds)
if not ok: continue        # that verifier is already being offered a call
```

**Test — the race is the whole point:**
```python
async def test_two_verifiers_one_offer(redis, svc):
    t = await make_transfer()
    results = await asyncio.gather(
        svc.accept(t.id, verifier_a), svc.accept(t.id, verifier_b),
        return_exceptions=True)
    ok = [r for r in results if not isinstance(r, Exception)]
    assert len(ok) == 1

async def test_watchdog_recovers_stuck_transfer(db, clock):
    t = await make_transfer(status="ringing_verifier",
                            initiated_at=utcnow() - timedelta(minutes=5))
    await watchdog.tick()
    assert (await db.get(Transfer, t.id)).status == "failed_timeout"
    assert await alert_exists("transfer_failed")
```

## STEP 35 — Verifier workspace

```
GET  /api/v1/verifier/queue
GET  /api/v1/verifier/active
POST /api/v1/verifier/availability
POST /api/v1/verifier/calls/{id}/accept
POST /api/v1/verifier/calls/{id}/reject
POST /api/v1/verifier/calls/{id}/disposition
GET  /api/v1/verifier/history
```

**Accept returns everything in one payload** — captured fields, qualification result, compliance markers, recording ref, lead history. The verifier has a live human on the line; five round-trips is a failure.

**Test:**
```python
async def test_accept_returns_full_context_in_one_call(client, seeded_transfer):
    r = await client.post(f"/api/v1/verifier/calls/{call_id}/accept")
    d = r.json()["data"]
    assert d["qualificationFields"] and d["qualificationStatus"]
    assert d["leadHistory"] is not None and d["recordingRef"] is not None
    assert r.elapsed.total_seconds() < 0.3
```

## STEP 36 — Presence expiry

```python
async def test_closed_browser_becomes_unavailable(redis, ws):
    await ws.connect_as(verifier)
    assert await is_available(verifier.id)
    await ws.hard_close()                       # no clean disconnect
    await asyncio.sleep(HEARTBEAT_TTL + 1)
    assert not await is_available(verifier.id)
```
Without this, transfers route to a ghost and qualified callers are lost.

---

# PHASE 7 — RECORDINGS / BASIC ANALYTICS

## STEP 37 — Recording serving

```
GET  /api/v1/recordings
GET  /api/v1/calls/{id}/recording
GET  /api/v1/calls/{id}/recording/playback-url      5-min presigned, audited
POST /api/v1/calls/{id}/recording/download-token    single-use, audited
```

Align the worker's status strings to the frontend enum in the same migration:
`pending → waiting_for_source → fetching → validating → storing → ready | failed | purged`

`recording-reconciler` every 5 min: completed calls with no `ready`/`failed` row → requeue the fetch. Closes the orphan gap in `CURRENT_STATUS.md`.

**Test:**
```python
async def test_playback_url_expires(client, s3):
    url = (await client.get(f"/api/v1/calls/{cid}/recording/playback-url")).json()["data"]["url"]
    assert httpx.get(url).status_code == 200
    freeze(minutes=6)
    assert httpx.get(url).status_code == 403

async def test_download_token_is_single_use(client):
    tok = (await client.post(f".../download-token")).json()["data"]["token"]
    assert (await client.get(f"/api/v1/download/{tok}")).status_code == 200
    assert (await client.get(f"/api/v1/download/{tok}")).status_code == 410

async def test_access_is_audited(client, db):
    await client.get(f"/api/v1/calls/{cid}/recording/playback-url")
    assert await audit_exists(db, action="recording.played", resource_id=cid)
```

## STEP 38 — Retention

```sql
retention_policies(id, name, audio_days, transcript_days, metadata_days,
                   effective_from, created_by)
-- default: audio 180, transcript 2555, metadata NULL (indefinite)
```

Daily purger: delete the object, set `status='purged'` and `audio_purged_at`, **keep the metadata row**.

**Test:**
```python
async def test_purge_keeps_metadata(db, s3):
    r = await make_recording(db, retention_until=utcnow() - timedelta(days=1))
    await purger.run()
    row = await db.get(CallRecording, r.id)
    assert row is not None                      # metadata survives
    assert row.status == "purged" and row.audio_purged_at
    assert not await s3.exists(r.storage_key)   # audio gone
    assert await audit_exists(db, action="recording.purged")
```

## STEP 39 — Rollups

Six tables, one worker, 60s interval, incremental by watermark:

```sql
INSERT INTO agg_campaign_daily (date, campaign_id, total_calls, answered,
       contacted, qualified, transferred, verifier_accepted, disqualified, avg_duration)
SELECT date(started_at), campaign_id,
       count(*),
       count(*) FILTER (WHERE answered_at IS NOT NULL),
       count(*) FILTER (WHERE disposition_layer_conversation IS NOT NULL),
       count(*) FILTER (WHERE qualification_status='qualified'),
       count(*) FILTER (WHERE transfer_status='completed'),
       count(*) FILTER (WHERE verifier_disposition='verified_accepted'),
       count(*) FILTER (WHERE qualification_status='disqualified'),
       avg(duration_seconds)
FROM calls
WHERE started_at >= :watermark AND started_at < :now
GROUP BY 1,2
ON CONFLICT (date, campaign_id) DO UPDATE SET ...;
```

**The rule: no analytics endpoint touches `calls`.** Put it in CI:

```python
def test_no_analytics_query_hits_raw_calls():
    src = Path("app/modules/analytics").rglob("*.py")
    for f in src:
        t = f.read_text()
        assert "FROM calls" not in t and "select(Call)" not in t, f

async def test_backfill_is_idempotent(db):
    await rollup.run(date(2026,9,1))
    first = await snapshot(db, "agg_campaign_daily")
    await rollup.run(date(2026,9,1))             # re-run
    assert await snapshot(db, "agg_campaign_daily") == first
```

## STEP 40 — Wire the dashboard

Replace `DEFAULT_AGENTS`, `DEFAULT_SCRIPTS` and the inline arrays with `agg_*` reads. Trace each displayed number to a documented column in `docs/metrics.md`.

**Test:**
```bash
for i in $(seq 1 500); do python tools/fake_gateway.py $C $L \
  $(shuf -n1 -e qualified disqualified_no_part_ab no_answer opted_out) & done; wait
curl -s "localhost:8080/api/v1/analytics/summary?from=2026-09-01&to=2026-09-30" | jq
# open the dashboard — numbers should match the curl output exactly
```

---

## ✅ 70% LINE — STOP AND VERIFY

Everything below runs with **zero** VICIdial and **zero** Asterisk.

```bash
make check                        # lint, types, boundaries, single head, contract
make test                         # full suite green
python tools/fake_gateway.py ...  # x500, mixed outcomes
```

```
□ Login → dashboard renders real numbers from agg_* tables
□ A script authored in the UI validates, gets approved, activates
□ Simulation reproduces a persisted call's node path exactly
□ 100k lead import commits idempotently in under 20 minutes
□ A suppressed number is excluded from every dialable query
□ Fake calls appear in the live view over WebSocket within 250 ms
□ Two verifiers accepting one offer → exactly one wins
□ Recording playback URL expires at 5 minutes; download token single-use
□ Purge removes audio and keeps metadata
□ Approved script version cannot be mutated by raw SQL
□ Kafka killed mid-call → events replay from disk on restart, nothing lost
□ Every route has a permission dependency (CI-enforced)
□ openapi.json committed and drift-gated
```

If any box is unticked, fix it now. Integration doubles the surface area — do not carry known defects into Phase 8.

---

# PHASE 8 — VICIDIAL + ASTERISK

You have root, Termius and WSL. Use it. Steps 41–43 are reconnaissance and take an afternoon, not a sprint.

## STEP 41 — Read the box before writing code

```bash
ssh vicidial-server

# 1. Confirm versions and API build
mysql -u root -p asterisk -e "SELECT * FROM system_settings\G" | head -40
grep -m1 "Updated:" /srv/www/htdocs/vicidial/non_agent_api.php || \
  head -5 /var/www/html/vicidial/non_agent_api.php

# 2. THE dialplan question — what carries identity into AudioSocket?
grep -rn "AudioSocket" /etc/asterisk/
grep -rn "vicidial_lead_id\|campaign_id\|CAMPAIGN\|lead_id" /etc/asterisk/extensions*.conf | head -40

# 3. Real schema — do not trust any document, including this one
mysql -u root -p asterisk -e "
  DESCRIBE vicidial_list;
  DESCRIBE vicidial_log;
  DESCRIBE vicidial_closer_log;
  DESCRIBE recording_log;
  DESCRIBE vicidial_dnc;
  DESCRIBE vicidial_hopper;
  DESCRIBE vicidial_live_agents;"

# 4. YOUR actual statuses — the screenshot showed DNC/DNQ/CLBK/SALE/DAIR/RAXFER/NP
mysql -u root -p asterisk -e "
  SELECT status, status_name, selectable, human_answered, category
  FROM vicidial_statuses;
  SELECT campaign_id, status, status_name FROM vicidial_campaign_statuses;"

# 5. Campaign config as actually deployed
mysql -u root -p asterisk -e "
  SELECT campaign_id, dial_method, dial_level, dial_statuses, dial_timeout,
         local_call_time, amd_send_to_vmx, use_internal_dnc, use_campaign_dnc
  FROM vicidial_campaigns WHERE active='Y'\G"

# 6. Where recordings actually land
mysql -u root -p asterisk -e "SELECT * FROM recording_log ORDER BY start_time DESC LIMIT 3\G"
ls -la /var/spool/asterisk/monitorDONE/ | tail
```

Write every answer into `docs/adr/027-vicidial-environment.md`. Everything in Phase 8 is pinned to these findings, not to documentation.

## STEP 42 — Settle the hopper question empirically

Do not take my word or the docs' word. Watch it:

```bash
# insert a row manually
mysql -u root -p asterisk -e "
  INSERT INTO vicidial_hopper (lead_id, list_id, campaign_id, status, priority)
  VALUES (<known_lead>, <list>, '<CAMP>', 'READY', 50);"

# watch across the hopper daemon's cycle
watch -n 5 "mysql -u root -p asterisk -e \
  \"SELECT lead_id,status,priority FROM vicidial_hopper WHERE lead_id=<known_lead>\""

tail -f /var/log/astguiclient/AST_VDhopper.log
```

If the row survives and gets dialled → direct hopper writes are fine. If `AST_VDhopper.pl` wipes it → use `add_lead(add_to_hopper=Y)` or `hopper_bulk_insert`. **This single experiment decides your write strategy.** Record the result in the ADR.

## STEP 43 — Read path: direct MySQL

Read-only user on the VICIdial box:

```sql
CREATE USER 'talkflow_ro'@'<app-api-ip>' IDENTIFIED BY '<strong>';
GRANT SELECT ON asterisk.vicidial_log            TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_closer_log     TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_list           TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.recording_log           TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_live_agents    TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_auto_calls     TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_campaigns      TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_dnc            TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_statuses       TO 'talkflow_ro'@'<app-api-ip>';
GRANT SELECT ON asterisk.vicidial_campaign_statuses TO 'talkflow_ro'@'<app-api-ip>';
FLUSH PRIVILEGES;
```

`packages/telephony/vicidial/reader.py` — async MySQL via `aiomysql`, **read-only, no writes ever in this class.**

```python
class VicidialReader:
    async def call_by_uniqueid(self, uid: str) -> VdCall | None:
        return await self.q("""
            SELECT uniqueid, lead_id, campaign_id, status, length_in_sec,
                   call_date, phone_number, user, term_reason
            FROM vicidial_log WHERE uniqueid=%s
            UNION ALL
            SELECT uniqueid, lead_id, campaign_id, status, length_in_sec,
                   call_date, phone_number, user, term_reason
            FROM vicidial_closer_log WHERE uniqueid=%s
        """, (uid, uid))

    async def recording_for(self, uid: str) -> VdRecording | None:
        return await self.q("""
            SELECT recording_id, lead_id, location, filename, start_time, length_in_sec
            FROM recording_log WHERE vicidial_id=%s OR lead_id=%s
            ORDER BY start_time DESC LIMIT 1""", (uid, uid))

    async def available_in_group(self, group: str) -> int:
        return await self.scalar("""
            SELECT COUNT(*) FROM vicidial_live_agents
            WHERE status='READY' AND closer_campaigns LIKE %s""", (f"%{group}%",))
```

Set a **statement timeout and a small pool** (2–4 connections). You are sharing MySQL with a live dialer.

**Test:**
```python
@pytest.mark.integration
async def test_reader_against_staging(reader):
    uid = await seed_a_real_test_call()       # place one call by hand first
    call = await reader.call_by_uniqueid(uid)
    assert call.campaign_id and call.status

async def test_reader_has_no_write_methods():
    src = Path("packages/telephony/vicidial/reader.py").read_text()
    for kw in ("INSERT","UPDATE","DELETE","REPLACE"):
        assert kw not in src.upper()
```

## STEP 44 — Write path: API only where daemons own the invariant

Four operations, nothing more:

| Operation | Function | Why API and not SQL |
|---|---|---|
| Push a lead | `add_lead` | Derives `gmt_offset_now`, `entry_list_id`, `called_since_last_reset`; runs duplicate and DNC checks |
| Queue for dialing | `add_to_hopper=Y` / `hopper_bulk_insert` | Per STEP 42's finding |
| Suppress | `add_dnc_phone` | Writes both list forms consistently |
| Disposition writeback | `update_log_entry` | Targets `vicidial_log` or `vicidial_closer_log` correctly |

Three credential profiles, three accounts, minimum flags:

| Profile | Flags | Functions |
|---|---|---|
| `readonly` | level ≥8, view reports | (mostly unused — you read MySQL directly) |
| `leadwrite` | level ≥8, `modify_leads=1` | `add_lead`, `update_lead`, `hopper_bulk_insert` |
| `dncwrite` | level ≥8, `modify_lists`, Delete-From-DNC | `add_dnc_phone`, `delete_dnc_phone`, `update_log_entry` |

Response parsing — HTTP 200 always, prefix carries the outcome, **parse every line**:

```python
def parse(body: str) -> VdResponse:
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    out = VdResponse(raw=body, notices=[], error=None, data=None)
    for l in lines:
        if l.startswith("ERROR:"):    out.error = l[6:].strip()
        elif l.startswith("NOTICE:"): out.notices.append(l[7:].strip())
        elif l.startswith("SUCCESS:"):out.data = l[8:].strip().split("|")
    return out
```

The trap: `add_lead` returns `SUCCESS` **and** `NOTICE: ... NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME`. The lead exists but will never be dialled. If you only read the first line you will spend a day wondering why nothing dials.

## STEP 45 — Capture fixtures, then test offline forever

```bash
mkdir -p tests/fixtures/vicidial
V=https://<box>/vicidial/non_agent_api.php
A="user=$U&pass=$P&source=tf_fixture"

curl -s "$V?$A&function=version"                   > tests/fixtures/vicidial/version.txt
curl -s "$V?$A&function=campaigns_list&stage=json" > .../campaigns_list.json
curl -s "$V?$A&function=add_lead&phone_number=13125550000&list_id=<L>&dnc_check=Y&add_to_hopper=Y&hopper_local_call_time_check=Y" > .../add_lead_success.txt
# now provoke the failures — these are the ones that matter
curl -s "$V?$A&function=add_lead&phone_number=13125550000&list_id=<L>&duplicate_check=DUPSYS" > .../add_lead_dup.txt
curl -s "$V?$A&function=add_lead&phone_number=999&list_id=<L>"        > .../add_lead_badlen.txt
curl -s "$V?$A&function=add_dnc_phone&phone_number=13125550000&campaign_id=SYSTEM_INTERNAL" > .../dnc_add.txt
curl -s "$V?$A&function=add_dnc_phone&phone_number=13125550000&campaign_id=SYSTEM_INTERNAL" > .../dnc_dup.txt
```

```python
@pytest.mark.parametrize("fixture,expect", [
    ("add_lead_success.txt", ("ok", None)),
    ("add_lead_dup.txt",     ("duplicate", "existing_lead_id")),
    ("add_lead_badlen.txt",  ("error", "INVALID PHONE NUMBER LENGTH")),
    ("dnc_dup.txt",          ("ok", None)),          # already exists == success
])
def test_response_parsing(fixture, expect):
    r = parse(read_fixture(fixture))
    assert classify(r) == expect[0]
```
From here the adapter is tested offline, in CI, with no dialer.

## STEP 46 — Suppression dual-write

```
TalkFlow transaction:
  INSERT suppression_entries
  INSERT outbox(action=add_dnc)
  COMMIT
     ↓ worker
  add_dnc_phone(SYSTEM_INTERNAL)
  add_dnc_phone(<each active campaign>)
  update_lead(remove_from_hopper=Y)        ← belt and braces
  SET vicidial_synced_at
```

`dnc-reconciler`, hourly, both directions:
```sql
-- in TalkFlow, not in VICIdial
SELECT s.phone_normalized FROM suppression_entries s
WHERE s.removed_at IS NULL AND NOT EXISTS (
  SELECT 1 FROM vd_dnc_snapshot v WHERE v.phone_number = s.phone_normalized);
```

**Test:**
```python
@pytest.mark.integration
async def test_suppression_lands_in_both_systems(svc, reader):
    phone = f"1312555{random.randint(1000,9999)}"
    await svc.suppress(phone, reason="caller_request", actor=ADMIN)
    await worker.drain()
    assert await reader.is_dnc(phone)
    assert not await reader.in_hopper(phone)
```

## STEP 47 — Identity and disposition writeback

Lead push sets `vendor_lead_code = lead.external_key`; store the returned `lead_id` on `leads.vicidial_lead_id`.
Call join key is Asterisk `UNIQUEID` → `calls.channel_id` → `vicidial_log.uniqueid`.

Writeback maps your four-layer disposition to your **real** statuses from STEP 41 query 4 — seed the `dispositions.vicidial_status` column from that query result, not from my guesses.

**Test:**
```python
@pytest.mark.integration
async def test_disposition_writeback(adapter, reader, real_call):
    await adapter.write_disposition(real_call, "RAXFER")
    assert (await reader.call_by_uniqueid(real_call.channel_id)).status == "RAXFER"
```

## STEP 48 — Swap the adapter, run the same suite

```bash
# one line
TELEPHONY_ADAPTER=vicidial
```

```python
@pytest.fixture(params=["manual", "vicidial"])    # <- the only change
def adapter(request): return build_adapter(request.param)
```

The contract suite from STEP 31 now validates the real adapter. Add rate limiting (5 rps default), a circuit breaker, and `source=talkflow` on every call so the VICIdial admin can see your traffic in VICIdial's own API log.

**End-to-end test — the first real call:**
```bash
# 1. push one lead
curl -X POST localhost:8080/api/v1/leads -d '{"phone":"<your mobile>","state":"IL"}'
# 2. start the campaign
curl -X POST localhost:8080/api/v1/campaigns/<id>/start
# 3. answer your phone, talk to the bot, get transferred
# 4. verify every system agrees
curl -s localhost:8080/api/v1/calls | jq '.data[0]'
mysql -e "SELECT uniqueid,status FROM vicidial_log ORDER BY call_date DESC LIMIT 1"
ls -la /var/spool/asterisk/monitorDONE/ | tail -1
curl -s localhost:8080/api/v1/calls/<id>/transcript | jq
curl -s localhost:8080/api/v1/calls/<id>/recording/playback-url | jq
```

---

# PHASE 9 — QA / FULL ANALYTICS / EXPORTS / OPS

## STEP 49 — QA

Risk-weighted daily sampling — not random. Weight toward: compliance flags, failed transfers, missing recordings, low mean ASR confidence.

```sql
SELECT id FROM calls
WHERE date(started_at)=:d AND campaign_id=:c
ORDER BY (
  (qa_flags IS NOT NULL)::int * 100 +
  (transfer_status LIKE 'failed%')::int * 80 +
  (recording_status <> 'ready')::int * 60 +
  (1 - COALESCE(mean_confidence, 1)) * 40 +
  random() * 10
) DESC
LIMIT :sample_size;
```

Versioned scorecards; `auto_fail` criteria force the total to zero; a reviewer cannot review their own verified call.

**Test:**
```python
async def test_sampling_prefers_risky_calls(db):
    await make_calls(db, n=100, clean=True)
    risky = await make_call(db, transfer_status="failed_timeout")
    sample = await qa.sample(date.today(), campaign, size=10)
    assert risky.id in {c.id for c in sample}

def test_auto_fail_zeroes_the_score():
    assert score(criteria=[C(weight=50,value=10), C(auto_fail=True,value=0)]) == 0
```

## STEP 50 — Exports

Async only. Job → object storage → presigned URL. **Inherits the requester's scope; PII columns omitted without `pii.view_full`.** Every request and download audited. Expire at 7 days.

```python
async def test_export_omits_pii_for_reporting_user(client, as_reporting):
    j = await client.post("/api/v1/exports", json={"report":"calls"})
    csv = await download(j)
    assert "caller_number" not in csv.split("\n")[0]
```

## STEP 51 — Health, alerts, integrations, search, notifications

Health probes must include a **VICIdial API card** and a **VICIdial MySQL card**. Services not deployed are marked `disabled` in config and omitted — never rendered `unknown` forever.

Alert rules minimum: transfer failure rate, outbox pending, Kafka consumer lag, recording backlog, VICIdial circuit open, any reconciler divergence, dependency offline.

---

# PHASE 10 — HARDENING

## STEP 52 — Load test

```bash
pip install locust
# 10x pilot: 200 concurrent calls worth of ingest + 60 dashboard users
locust -f tools/load/dashboard.py --users 60 --spawn-rate 5
python tools/load/ingest_storm.py --calls 2000 --concurrency 200
```
Targets: read p95 <200ms, write p95 <400ms, analytics p95 <300ms, ingest lag <2s, WS fanout p95 <250ms.

## STEP 53 — Gateway capacity

```bash
grep -E "VAD_POOL_SIZE|ASR_WORKERS" services/ai-gateway/.env
# currently 4 and 1 — will not carry 20 concurrent calls
```
Raise, re-benchmark, and set `campaign.concurrencyLimit` to **measured** capacity, not the proposal's number.

## STEP 54 — Restore drill

```bash
pg_dump -Fc $PROD > /tmp/prod.dump
createdb restore_test && pg_restore -d restore_test /tmp/prod.dump
cd services/app-api && DATABASE_URL=...restore_test alembic upgrade head
uv run pytest -m integration -q
```
Run every migration against restored production data from the first day production has data.

## STEP 55 — Runbooks

`docs/runbooks/`: transfer-storm, gateway-down, vicidial-api-down, vicidial-mysql-slow, kafka-lag, disk-full, restore, credential-rotation. Each: symptom → check → action → escalation.

---

# QUICK REFERENCE

## Per-module build checklist

```
□ router.py       routes + @require_permission + response models
□ service.py      rules, transaction, @audited, outbox emit
□ repository.py   queries, scope=AccessScope (no default)
□ policies.py     pure functions, no I/O
□ errors.py       codes registered in contracts/errors.py
□ events.py       outbox payload builders
□ schemas.py      re-export from contracts
□ test_policies.py     100% branch
□ test_service.py      happy path + every documented failure
□ test_router.py       authorised / unauthorised / invalid
□ test_invariants.py   raw SQL violation attempts
□ seed extended
□ make contract regenerated
```

## The four tests that catch the most bugs

1. **Raw-SQL violation attempt** — proves the database, not the service, enforces it.
2. **Full event replay** — proves idempotency for real, not in theory.
3. **Two concurrent sessions** — proves the race, which a single session never exercises.
4. **Kill the dependency mid-flow** — proves the buffer, which is the thing that silently doesn't work in production.

## Daily loop

```bash
make test-fast                       # seconds, no containers
python tools/fake_gateway.py $C $L   # a call, end to end
make check                           # before every push
```

## Order of operations, one line

```
clean → scaffold → harness → auth → calls+fake_gateway → scripts → leads
      → outbox/ws → transfer → recordings → analytics → [70%] → recon the box
      → reader → writer → fixtures → swap adapter → QA/exports → harden
```
