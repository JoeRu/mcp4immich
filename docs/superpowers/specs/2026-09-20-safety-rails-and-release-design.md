# mcp4immich: destructive-tool safety rails, version resilience, release discipline, rename

Date: 2026-09-20 · Branch: `feat/safety-rails-and-release` (from `a39ae71`) · Repo: `github.com/JoeRu/mcp4immich` (renamed from `claw2immich` 2026-09-20)

## Problem

mcp4immich generates its tool set from Immich's OpenAPI spec: **282 tools** (276 operations + 6 hand-written) against Immich 3.2.1. Coverage is therefore complete and self-maintaining — and that is exactly what makes the gaps below matter.

| # | Problem | Evidence |
|---|---|---|
| 1 | **Nothing guards destructive tools.** Once the write probe passes, `DELETE /assets`, `DELETE /admin/users/{id}`, `DELETE /admin/database-backups`, `POST /duplicates/resolve`, empty-trash are ordinary tools: no confirm, no preview, no MCP annotations for clients to prompt on. | 43 DELETE operations in the 3.2.1 spec; `tooling.py` filters by auth / admin / write-probe / profile only |
| 2 | **`/api/server-config` is hardcoded** but Immich 3.x serves `/api/server/config`. External-domain discovery silently fails, so `web_url` links point at `IMMICH_BASE_URL` (an internal address when deployed that way). | `config.py:66`, `constants.py:18`; observed 404 in a live startup 2026-09-20 |
| 3 | **Startup depends on the public internet.** The spec is fetched from `raw.githubusercontent.com` with only an in-process `lru_cache`; an offline restart yields a server with almost no tools. | `openapi.py:42`, `:62` |
| 4 | **Three version numbers disagree** and none is authoritative: `pyproject.toml` `0.1.0`, newest commit message `0.6.0`, MCP `serverInfo` `1.26.0` (the SDK's own version, because `FastMCP.__init__` takes no `version`). No git tags, no GitHub releases. | verified against the running image |
| 5 | **The repo was renamed to mcp4immich**; package, folder, image name, GHCR path, README and badges still say `claw2immich`. | `pyproject.toml`, `docker-compose.yaml`, README badges |
| 6 | **Compose publishes `0.0.0.0:8000`** while the code defaults `MCP_HOST` to `127.0.0.1`. On a host where Docker DNAT bypasses UFW, that exposes a server holding a full Immich API key. | `docker-compose.yaml:27`, `config.py:9` |

Backlog item **#20** (the only open one of 61) belongs here too: some parameters expose `query_type: unknown` with no enum, so agents guess. It is fixed in the same per-operation pass that classifies risk.

## Goals

1. A stranger who runs the published image cannot destroy their library by accident.
2. The server starts correctly offline and on both Immich 2.x and 3.x.
3. One version number, tagged and released, matching the GHCR image.
4. The project is called mcp4immich everywhere.
5. It runs here as a monitored service, VPN-bound, replacing the retired C# ImmichMCP.

Non-goals: progressive disclosure / curated tool groups to shrink the 282-tool surface (a separate spec, after this ships); PyPI publishing; supporting Immich versions older than 2.x.

## Decisions taken (user)

- Destructive tools need `confirm=true`; the worst class is **hidden unless explicitly enabled**.
- Immich version detected at runtime, with a **vendored spec as fallback**.
- **Rename everything now**, in the release that bumps the version.
- **Build → release → deploy here**, with a stop for approval before the production step.

## 1. Risk classification — one source of truth

New module `mcp4immich/risk.py`:

```python
class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    DESTRUCTIVE_ADMIN = "destructive_admin"

def classify(method: str, path: str, operation: dict) -> Risk: ...
```

Rules, applied in order (first match wins), on the spec path (no base prefix):

| Rule | Class |
|---|---|
| method DELETE **and** path starts `/admin/` (`/admin/users/{id}`, `/admin/database-backups`, `/admin/integrity/report/{id}`) | `DESTRUCTIVE_ADMIN` |
| method + path in the explicit high-risk set: `DELETE /assets`, `DELETE /people`, `POST /trash/empty`, `POST /duplicates/resolve` | `DESTRUCTIVE_ADMIN` |
| any other DELETE | `DESTRUCTIVE` |
| method in POST/PUT/PATCH | `WRITE` |
| otherwise | `READ` |

The split is "can destroy many originals at once, or affects other users" versus "loses one named thing". The high-risk set is an **explicit list, not a shape heuristic**: an earlier draft keyed on "DELETE without a trailing `{id}`", which wrongly swept in `DELETE /albums/{id}/assets`, `/memories/{id}/assets`, `/tags/{id}/assets` and `/shared-links/{id}/assets` — those only remove *membership*, leaving every asset in place, so they belong in `DESTRUCTIVE` (confirm, but visible). `POST /trash/restore` and `/trash/restore/assets` are restorative and stay `WRITE`.

A new Immich release could add a high-risk endpoint the explicit list does not know. That is why the fallback is `DESTRUCTIVE` for *every* remaining DELETE (never `WRITE`), and why the spec-wide test below is the real guarantee: unknown deletes fail closed into a confirm-gated tool, and only the hidden-by-default class is curated by hand.

The classifier is pure and data-driven, and a test asserts that **every** DELETE operation in the vendored spec lands in one of the two destructive classes — so a future Immich release cannot quietly add an unguarded delete.

The same pass fixes backlog **#20**: where a parameter's schema has no `enum` and no usable `type`, the generated description gains `allowed:` values from the spec (or `type: string (free text)` when genuinely unconstrained), and a test asserts no parameter is left as bare `query_type: unknown`.

## 2. Annotations on every generated tool

`FastMCP.add_tool` accepts `annotations=ToolAnnotations(...)` (verified in SDK 1.26.0; fields `title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).

| Risk | readOnlyHint | destructiveHint | idempotentHint |
|---|---|---|---|
| READ | true | false | true |
| WRITE | false | false | PUT → true, POST/PATCH → false |
| DESTRUCTIVE / DESTRUCTIVE_ADMIN | false | true | true for DELETE by id, false for collection deletes |

`openWorldHint` is false everywhere: the server talks to one Immich instance.

## 3. The confirm gate

Applies to `DESTRUCTIVE` and `DESTRUCTIVE_ADMIN` tools that are registered.

- Their input schema gains `confirm: bool = False`, documented as "must be true to actually perform this destructive call".
- Without `confirm=true` the tool makes **no** call to Immich and returns a refusal object: `{"ok": false, "error": "CONFIRMATION_REQUIRED", "risk": "<class>", "would_call": "DELETE /assets", "preview": {...}, "hint": "re-send with confirm=true"}`.
- `preview` is best-effort and cheap: when the operation is a by-id delete and the spec has a sibling `GET` on the same path, the gate fetches it and reports identifying fields (`originalFileName`/`name`/`title`, `id`, dates). If no sibling GET exists, `preview` is `null` and the refusal says so. A failed preview never blocks the refusal, and never turns into a call.
- With `confirm=true` the call proceeds unchanged.

**Interaction with existing gates:** the risk gate runs *after* the current auth/admin/write-probe/profile filtering. A tool blocked by those is still blocked; the risk gate only ever removes capability, never grants it.

## 4. Enabling the worst class

New env var `IMMICH_ENABLE_DESTRUCTIVE` (default `false`).

- `false`: `DESTRUCTIVE_ADMIN` tools are **not registered at all**, and each appears in `tool_access_report`'s `blocked_tools` with reason `"Destructive-admin endpoint disabled (set IMMICH_ENABLE_DESTRUCTIVE=true)"`. An agent thus learns *why*, instead of concluding the capability doesn't exist.
- `true`: they are registered, and still require `confirm=true`.
- `IMMICH_PROFILE=read_only` continues to block all writes regardless.

`tool_access_report` gains a `risk` field per tool and a `destructive_enabled` flag, so one call tells an agent the whole policy.

## 5. Version-aware endpoints

New module `mcp4immich/compat.py` holding endpoints that moved:

```python
SERVER_CONFIG = {2: "/api/server-config", 3: "/api/server/config"}
def endpoint(name: str, major: int) -> str: ...
```

The server major version already comes from `GET /api/server/version` at startup (used to pick the spec). `config.py` and `constants.py` stop hardcoding the path and ask `compat.endpoint("server_config", major)`. Unknown/newer majors use the highest known mapping and log once.

Tests cover both majors and the fallback. This is the pattern for any future move; only endpoints that actually moved live here.

## 6. Spec resolution: disk cache → network → vendored

Order at startup, with the chosen source logged at INFO:

1. **Disk cache** `${MCP4IMMICH_SPEC_CACHE:-/app/.cache/openapi}/immich-<version>.json`, if present and parseable.
2. **Network** `raw.githubusercontent.com/immich-app/immich/v<version>/open-api/immich-openapi-specs.json` (current behaviour), written to the cache on success.
3. **Vendored** `mcp4immich/data/immich-openapi-<major>.json` shipped in the image (3.x at time of writing), used when the network fails. The server logs a warning naming the vendored version and the detected server version when they differ.

If all three fail the server starts with only the six hand-written tools and says so loudly — it must never look like "this Immich has no endpoints".

## 7. One version number

- `pyproject.toml` `version` is the source of truth; `mcp4immich/__init__.py` exposes `__version__` via `importlib.metadata`.
- `FastMCP.__init__` has no `version` parameter, but the low-level server does. After constructing `FastMCP`, set the version on the underlying server (`mcp._mcp_server.version = __version__`) and assert in a test that `initialize` reports it in `serverInfo.version` — the current `1.26.0` is the SDK's.
- Release flow: bump `pyproject.toml` → tag `v<version>` → GitHub release → CI builds and pushes GHCR `ghcr.io/joeru/mcp4immich:<version>` and `:latest`.
- Starting version for this work: **`1.0.0`** — the first release where the published artifact, the tag and `serverInfo` agree. The earlier "0.6.0" commit message is noted in the changelog as historical.

## 8. Rename to mcp4immich

Package `claw2immich/` → `mcp4immich/`; `pyproject` name; `docker-compose.yaml` image `mcp4immich:local`; README title, badges and GHCR paths; `docs/usage-guide.md`; `CLAUDE.md`; the local checkout directory. Old GHCR tags stay, new ones use the new path; the README says so. The MCP server name reported to clients becomes `mcp4immich` — **breaking for any client pinning the old name**, which the changelog states.

## 9. Local deployment (last, after the release)

`docker-compose.yaml` for this host:

- `ports: "192.168.176.224:8000:8000"` — WireGuard only, never `0.0.0.0`.
- `IMMICH_BASE_URL=http://immich_server:2283`, external network `immich_default`, `IMMICH_ALLOW_HTTP=true`.
- `MCP_TRANSPORT=streamable-http` (endpoint `/mcp`).
- `IMMICH_ENABLE_DESTRUCTIVE` unset (i.e. off).
- A `/healthz` route via `FastMCP.custom_route` (verified present in SDK 1.26.0) returning 200 with `{"status":"ok","immich_reachable":<bool>,"spec_source":"cache|network|vendored"}`; used by both the container healthcheck and a Prometheus blackbox probe with an alert (`Mcp4ImmichDown`, warning, 10m), mirroring what the retired server had.
- README gains a **Security** section: `0.0.0.0` plus Docker DNAT bypasses host firewalls; bind to a VPN address; the process holds a full Immich API key.

## 10. Testing

- **Unit:** classifier (every spec DELETE is destructive; collection vs by-id split; admin paths); annotations map per class; confirm gate (refuses with zero HTTP calls — asserted with a transport that raises on use; proceeds with `confirm=true`; preview absent when no sibling GET); `IMMICH_ENABLE_DESTRUCTIVE` on/off registration and the report's reason text; compat endpoint for majors 2, 3 and unknown; spec resolution order including network-blocked → vendored; `serverInfo.version`; no parameter left `query_type: unknown`.
- **Integration (live, existing style):** unchanged read-only checks, plus `tool_access_report` exposing `risk` and `destructive_enabled`. No test ever calls a destructive tool with `confirm=true` against real data.
- **CI:** run the unit suite on PRs; run the build; publish the image on tagged releases.

## Breaking changes (changelog must list)

1. Server name and package rename to `mcp4immich`.
2. Destructive tools now require `confirm=true`.
3. `DESTRUCTIVE_ADMIN` tools are absent unless `IMMICH_ENABLE_DESTRUCTIVE=true`.
4. `serverInfo.version` now reports the project version, not the SDK's.

## Risks

- The classifier is the single point of failure for safety: if it mislabels an operation as `READ`, the gate never sees it. Mitigated by the "every DELETE is destructive" test over the vendored spec and by annotations being derived from the same source.
- A preview costs one extra GET per refused call; harmless, but it means a refusal is not strictly zero-traffic (it is zero *mutating* traffic — stated in the tool description).
- Renaming breaks anyone importing the package or pinning the server name. Accepted, and the reason for a 1.0.0 release.
