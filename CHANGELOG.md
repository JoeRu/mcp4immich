# Changelog

## 1.0.0 — 2026-09-20

First release where the git tag, the published image and the version the
server reports to clients all agree.

### Breaking
- Package, server name and image renamed `claw2immich` → `mcp4immich`.
- Destructive tools require `confirm=true` (or an accepted elicitation).
- Tools that can destroy many items at once are not registered unless
  `IMMICH_ENABLE_DESTRUCTIVE=true`: `DELETE /assets`, `DELETE /people`,
  `POST /trash/empty`, `POST /duplicates/resolve`, and every `DELETE /admin/*`.
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
