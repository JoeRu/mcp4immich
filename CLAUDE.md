# CLAUDE.md

## Project Overview

mcp4immich is a Python MCP (Model Context Protocol) server that exposes the Immich REST API. It uses the MCP Python SDK 2.x (`mcp.server.mcpserver.MCPServer`) for server scaffolding and httpx for HTTP requests to the Immich API — not FastMCP; the SDK 2.x migration replaced it. The OpenAPI spec from Immich is the source of truth for API shape.



## Architecture
- Always check on https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md
for implementation details of MCP.
- Risk classification (`READ`/`WRITE`/`DESTRUCTIVE`/`DESTRUCTIVE_ADMIN`) lives in `risk.py` (`classify()`) — the single source of truth every other safety mechanism derives from
- Destructive-call enforcement lives in `policy.py` (`RiskPolicyMiddleware`) — refuses an unconfirmed `tools/call` for a gated tool before the handler ever runs
- Elicitation-based confirmation (asking the human directly when the client supports it) lives in `confirm.py` (`ask_confirmation()`)
- Immich endpoints that moved between major versions (e.g. `/api/server-config` → `/api/server/config` in 3.x) are shimmed in `compat.py`
- OpenAPI spec resolution (disk cache → network → vendored fallback, so startup doesn't depend on reaching GitHub) lives in `specsource.py`

## Key Conventions

- No formatter or linter configured; keep style minimal and consistent with existing code
- Coding guideline: https://peps.python.org/pep-0008/
- Immich API key/token handling is security-sensitive — never log secrets
- OpenAPI spec source: https://github.com/immich-app/immich/blob/main/open-api/immich-openapi-specs.json

## Docs

- [`docs/usage-guide.md`](docs/usage-guide.md) is an **MCP client-facing resource** served at runtime via `resources/read`. It documents tool usage, URL patterns, and workflow examples for AI agents consuming the server. Do **not** put developer or contributor information (test setup, env files, architecture) there.
- Developer and contributor documentation belongs in this file (`CLAUDE.md`) or `README.md`.

## AI-Assisted Development Workflow

Before running any plan-item command (`/implement`, `/feature`, `/bug`, `/refactor`, `/approve`, `/archive`), read [CLAUDE-implementation-plan-chapter.md](CLAUDE-implementation-plan-chapter.md) first.

This project uses an XML-based planning system under [ai-docs/](ai-docs/).

Workflow prompts live in [.github/prompts/](.github/prompts/).

Item lifecycle: BACKLOG → PENDING → APPROVED → IN_PROGRESS → DONE

## Security

- Security audit process is documented in [security.prompt.md](.github/prompts/security.prompt.md)
- Auth is handled via `_build_headers()` — supports both API key (`x-api-key`) and bearer token
- `require_auth=True` on a request will raise if neither credential is set
