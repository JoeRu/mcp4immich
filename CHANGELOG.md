# Changelog

## 1.0.1 — 2026-09-20

### Security
- Refreshed every locked dependency, closing **30 Dependabot alerts** (1 critical,
  9 high, 11 medium, 7 low). All were transitive — the direct dependencies are only
  `httpx`, `mcp[cli]` and `anyio`. Notable moves: `anyio` 4.12.1 → 4.15.1
  (CVE-2026-63374, critical), `cryptography` 46.0.5 → 50.0.1, `starlette` 0.52.1 → 1.6.0,
  `pyjwt` 2.11 → 2.14, `python-multipart` 0.0.22 → 0.0.32, `uvicorn` 0.40 → 0.53.
- The MCP SDK itself is unchanged at 2.2.0, so no protocol behaviour moved. Verified
  after the upgrade: 288 unit tests, a live `streamable-http` session on protocol
  2026-07-28 (273 tools, a destructive call still refused), and an `sse` session —
  the last because Starlette crossed a major version.

### Added
- `.github/dependabot.yml`: weekly update checks for the `uv` ecosystem and for
  GitHub Actions, so a gap like this surfaces as a PR instead of accumulating.
- CI fails on known-vulnerable dependencies (`uv-secure` audit of the lockfile).

## 1.0.0 — 2026-09-20

First release where the git tag, the published image and the version the
server reports to clients all agree.

### Breaking
- Package, server name and image renamed `claw2immich` → `mcp4immich`.
- Destructive tools require `confirm=true` (or an accepted elicitation).
- Tools that can destroy many items at once are not registered unless
  `IMMICH_ENABLE_DESTRUCTIVE=true`: `DELETE /assets`, `DELETE /people`,
  `POST /trash/empty`, `POST /duplicates/resolve`, `POST /people/merge`,
  `POST /admin/database-backups/start-restore`, and every `DELETE /admin/*`.
  Every other mutating (`POST`/`PUT`/`PATCH`) call under `/admin/*` — e.g.
  `PUT /admin/config`, `POST /admin/maintenance`,
  `POST /admin/auth/unlink-all` — is gated as `DESTRUCTIVE` (requires
  `confirm=true`, but is registered without `IMMICH_ENABLE_DESTRUCTIVE`).
- Runs on MCP Python SDK 2.x and speaks protocol revision 2026-07-28; older
  clients are still served by the same server.
- `serverInfo.version` now reports the project version, not the SDK's.

### Added
- Risk classification for every generated tool, with MCP annotations.
- Elicitation-based confirmation where the client supports it.
- OpenAPI spec resolution from disk cache, network, then a vendored copy, so
  startup works offline.
- `GET /healthz` for container and monitoring probes.

### Fixed
- External-domain discovery used the Immich 2.x `/api/server-config` path and
  404'd on 3.x, so `web_url` links pointed at the internal base URL.
- Parameters with no schema type no longer render as `query_type: unknown`
  (backlog #20).
- The `mcp` dependency is bounded (`>=2.2,<3`); the previous unbounded pin
  meant a fresh install resolved to an incompatible major.
- `anyio` is imported by production code (`mcp4immich/policy.py`) but was
  listed only in the dev dependency group; moved to `[project].dependencies`.
