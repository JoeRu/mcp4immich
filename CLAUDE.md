# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mcp4immich is a Python MCP (Model Context Protocol) server that exposes the Immich REST API. It uses the MCP Python SDK 2.x (`mcp.server.mcpserver.MCPServer`) for server scaffolding and httpx for HTTP requests to the Immich API — not FastMCP; the SDK 2.x migration replaced it. The OpenAPI spec from Immich is the source of truth for API shape.



## Development Setup

- **Python**: >= 3.12
- **Package manager**: uv
- **Dependencies**: `uv sync` to install
- **Run**: `python main.py` (stdio transport for Claude Desktop)
- **Test**: `pytest tests/` (integration tests exist in [tests/](tests/))

## Architecture
- Always check on https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md
for implementation details of MCP.
- Entry point remains [main.py](main.py) but logic is split into the `mcp4immich/` package; server setup lives in `mcp_app.py`
- MCP tools are defined as plain functions registered via `_register_tools()` based on runtime capability discovery
- Config helpers in `config.py` read `IMMICH_BASE_URL`, `IMMICH_API_KEY`, and `IMMICH_API_TOKEN`
- HTTP handling lives in `http_client.py` (`_request()`, `_probe()`)
- Capability probes live in `capabilities.py` (`_discover_capabilities()`, `_discover_write_capability()`)
- OpenAPI spec is fetched and cached via `_fetch_openapi_spec()` in `openapi.py`
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

!Read [CLAUDE-implementation-plan-chapter.md](CLAUDE-implementation-plan-chapter.md) for details.

This project uses an XML-based planning system under [ai-docs/](ai-docs/):
- `overview.xml` — project architecture baseline
- `overview-features-bugs.xml` — feature/bug tracking
- `implementation-plan-template-v3.1.xml` — XML schema reference

Workflow prompts live in [.github/prompts/](.github/prompts/). Key ones:
- `init_overview.prompt.md` — baseline codebase scan
- `implement.prompt.md` — plan item execution (max 5 items per invocation)
- `feature.prompt.md`, `bug.prompt.md`, `refactor.prompt.md` — create new items

Item lifecycle: BACKLOG → PENDING → APPROVED → IN_PROGRESS → DONE

## Security

- Security audit process is documented in [security.prompt.md](.github/prompts/security.prompt.md)
- Auth is handled via `_build_headers()` — supports both API key (`x-api-key`) and bearer token
- `require_auth=True` on a request will raise if neither credential is set
