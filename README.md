# mcp4immich

[![Docker](https://github.com/JoeRu/mcp4immich/actions/workflows/build-docker.yml/badge.svg)](https://github.com/JoeRu/mcp4immich/actions/workflows/build-docker.yml)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/JoeRu/mcp4immich/ci.yml?branch=main)

mcp4immich is a Python MCP (Model Context Protocol) server that exposes the Immich REST API as MCP tools. It generates one tool per OpenAPI operation — currently ~282 tools with a fully-permissioned key and `IMMICH_ENABLE_DESTRUCTIVE=true` — filtered down by the caller's actual Immich API permissions, and every one is risk-classified (read / write / destructive / destructive_admin) with MCP annotations attached. See **Safety** below for what that classification gates.

## Status
- Core MCP server and capability filtering are implemented.
- Tool exposure is gated by Immich API permissions and by risk class (see Safety).
- Integration tests cover tool listing and permission probes.

## Available tools
- `ping_server`
- `get_server_version`
- `tool_access_report`
- `write_capability_report`
- `get_current_user` (only when permitted by API key/token)
- `downloadAsset` (only when API key/token is configured; returns transport-safe `base64` payloads and supports optional `immich_link` delivery mode)

All OpenAPI endpoints are exposed as tools named `immich_<operation>` or `immich_<method>_<path>`.
Tools are filtered based on auth presence, admin-only markers, and write capability probes (default `POST /api/assets`).

OpenAPI tool descriptions include:
- `params:` summary of required path/query/body fields
- `example:` short call sketch for required inputs
- `returns:` response schema title and key fields when available

OpenAPI tool responses for assets, albums, people, and places include a `web_url` field with a direct link to the item in the Immich web UI (when `IMMICH_EXTERNAL_DOMAIN` is configured or discovered from server settings).

OpenAPI tool parameters use explicit, prefixed fields so MCP clients can discover what to set:
- `path_<name>` for path parameters
- `query_<name>` for query parameters
- `header_<name>` for header parameters
- `cookie_<name>` for cookie parameters
- `body` for JSON request bodies

Legacy fields `path_params`, `query_params`, `headers`, and `json_body` are still accepted for compatibility.

`downloadAsset` is intended for clients that cannot access the Immich API key directly. Default delivery mode is `shared_link`: the server returns a short-lived tokenized link (30 minutes) without inline payload data when supported by Immich shared-links API. For MCP JSON safety, inline payload delivery (`inline_base64`) remains base64-encoded. Optional compatibility mode `immich_link` returns a direct authenticated Immich URL.

**`shared_link` and `immich_link` both create a shared link first** — a write, even though the tool otherwise looks like a plain download. Only `inline_base64` is a pure `GET` with no side effect. `downloadAsset` is therefore risk-classified `write` (not `read`) unless `IMMICH_DOWNLOAD_ASSET_DELIVERY=inline_base64`, and under `IMMICH_PROFILE=read_only` the link-creating modes are refused outright, before any HTTP call — see Safety below.

## Safety

Every generated tool is classified into one of four risk levels before it is
registered, and the classification drives both its MCP annotations
(`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and what
the server will actually let a client do. The one hand-written exception is
`downloadAsset`: it is classified `write` (not `read`) unless
`IMMICH_DOWNLOAD_ASSET_DELIVERY=inline_base64`, because its default and
`immich_link` modes both create a shared link — a write — before returning
anything; `IMMICH_PROFILE=read_only` refuses those modes outright.

| Risk | Examples | What happens |
|---|---|---|
| `read` | `GET` endpoints | Registered and callable normally. |
| `write` | non-destructive `POST`/`PUT`/`PATCH` | Registered and callable normally. |
| `destructive` | `DELETE /albums/{id}`, `DELETE /assets/{id}`, and — fail-closed — every other mutating (`POST`/`PUT`/`PATCH`) call under `/admin/*` not listed below, e.g. `PUT /admin/config`, `POST /admin/maintenance`, `POST /admin/auth/unlink-all` | Registered, but **refused unless the call carries `confirm=true`**, or the client accepts an elicitation prompt asking to confirm. |
| `destructive_admin` | bulk/irreversible operations: `DELETE /assets`, `DELETE /people`, `POST /trash/empty`, `POST /duplicates/resolve`, `POST /people/merge`, `POST /admin/database-backups/start-restore`, every `DELETE /admin/*` | **Not registered at all** unless `IMMICH_ENABLE_DESTRUCTIVE=true` — these tools do not exist for a client to even see or call by default. |

**Confirmation (`confirm`)**: a `RiskPolicyMiddleware` inspects every
`tools/call` before it reaches the tool's handler. For a `destructive` or
`destructive_admin` tool, it requires `confirm=true` in the call's arguments —
if the client's MCP session supports elicitation, it instead (or additionally)
prompts the human directly and treats an accepted elicitation as confirmation.
**No destructive call ever reaches Immich without one of these** — a refusal
never dispatches the underlying HTTP request. The refusal response includes
`would_call` (the HTTP method and path that were about to run) and, for a
by-id `DELETE`, a best-effort read-only `preview` of what would be removed.

**`IMMICH_ENABLE_DESTRUCTIVE`**: gates whether `destructive_admin`-class tools
are registered at all. Unset (or falsy), the server never advertises them —
they cannot be discovered via `tools/list`, and calling one by name fails as
an unknown tool, not as a refused one. Set it to `true`/`1`/`yes` only when
that machine's operator actually wants an MCP client to be able to run
account-wide or irreversible operations, subject still to the `confirm=true`
gate above.

Call `tool_access_report` to see, for the current API key/token and
`IMMICH_ENABLE_DESTRUCTIVE` setting, each tool's `risk`, whether destructive
tools are enabled, and how many `destructive_admin` tools are currently
hidden.

## Security

- **Do not bind the server to `0.0.0.0` on a host with other Docker
  containers.** Docker writes its own `iptables`/`DOCKER` DNAT rules for
  published ports, which bypass host-level firewalls (UFW, etc.) that only see
  the `INPUT` chain — a container publishing `0.0.0.0:8000` is reachable from
  the network regardless of what the host firewall says. Bind to a specific
  interface instead (a VPN address such as a Tailscale or WireGuard IP,
  `MCP_HOST=100.x.x.x`), or publish the container port to that same specific
  host IP in your compose/run configuration.
- **The process holds a full Immich API key.** Whatever that key can do in
  Immich, this server can be asked to do — `IMMICH_PROFILE` and the risk/
  confirmation gates above reduce what an MCP *client* can trigger, but they
  are enforced here, not by Immich. Treat the key, and network access to this
  server, with the same care as the Immich admin credentials it was minted
  from.

## MCP documentation surfaces
- Server instructions are sent during initialize. Use them as the short on-ramp and point to the usage guide resource.
- Initialize instructions now call out externalDomain discovery, workflow groups, do/don't guidance, and an example instruction string.
- Resource: `docs://usage-guide` contains a detailed workflow guide with examples.
- Prompts: workflow templates are available under titles like "Immich: Get image", "Immich: Find person", and "Immich: Share album".

## Configuration
Environment variables:
- `IMMICH_BASE_URL` (default `http://localhost:2283`)
- `IMMICH_API_KEY`
- `IMMICH_API_TOKEN`
- `IMMICH_EXTERNAL_DOMAIN` (optional: domain for web UI links like `https://immich.example.com`; if not set, discovered from the server-config endpoint — `/api/server-config` on Immich 2.x, `/api/server/config` on 3.x)
- `IMMICH_ENABLE_DESTRUCTIVE` (optional: `true`/`1`/`yes` to register `destructive_admin`-class tools — bulk/irreversible operations, see Safety below; unset or false hides them entirely)
- `MCP4IMMICH_SPEC_CACHE` (optional: directory for the cached OpenAPI spec; defaults to `$XDG_CACHE_HOME/mcp4immich` outside a container, `/app/.cache/openapi` inside the Docker image — see Docker section)
- `IMMICH_PROFILE` (optional: `read_only`, `read_write`, or `full_scope`)
- `IMMICH_WRITE_PROBE_PATH` (default `/api/assets`)
- `IMMICH_WRITE_PROBE_METHOD` (default `POST`)
- `IMMICH_DOWNLOAD_ASSET_DELIVERY` (optional: `shared_link` (default), `inline_base64`, or `immich_link`)

MCP server environment variables:
- `MCP_TRANSPORT` (`stdio`, `sse`, or `streamable-http`; default `stdio`)
- `MCP_HOST` (default `127.0.0.1`)
- `MCP_PORT` (default `8000`)
- `MCP_MOUNT_PATH` (optional mount path for SSE transport)
- `MCP_LOG_LEVEL` (default `INFO`)

OpenAPI spec source:
Version-matched spec (after `/api/health` and `/api/server/version`):
https://raw.githubusercontent.com/immich-app/immich/v{VERSION}/open-api/immich-openapi-specs.json

## Access Profiles

Access profiles provide predefined permission levels to simplify API key management and reduce misconfiguration risk. Set `IMMICH_PROFILE` to one of the following values:

### `read_only`
**Use case:** Safe browsing, search, and reporting without modification risk.

**Permissions required:**
- `asset.read` - View photos and videos
- `album.read` - View albums
- `library.read` - Browse libraries
- `timeline.read` - Access timeline and memories

**Typical tools exposed:**
- `immich_getAllAssets`, `immich_getAssetById`, `immich_searchAssets`
- `immich_getAllAlbums`, `immich_getAlbumInfo`
- `immich_getMyUserInfo`, `immich_getServerVersion`
- All GET endpoints for reading data

**Blocked tools:**
- Asset upload, update, delete
- Album creation, modification
- User management
- Server configuration
- `downloadAsset` in its `shared_link` (default) or `immich_link` mode — both create a shared link, a write; use `IMMICH_DOWNLOAD_ASSET_DELIVERY=inline_base64` for a read-only download under this profile

**Example Claude Desktop config (`mcporter.json` snippet):**
```json
{
  "mcpServers": {
    "mcp4immich-readonly": {
      "command": "python",
      "args": ["c:\\path\\to\\mcp4immich\\main.py"],
      "env": {
        "IMMICH_BASE_URL": "https://immich.example.com",
        "IMMICH_API_KEY": "your-read-only-key",
        "IMMICH_PROFILE": "read_only"
      }
    }
  }
}
```

### `read_write`
**Use case:** Full asset and album management without admin privileges.

**Permissions required:**
- All `read_only` permissions plus:
- `asset.create` - Upload photos/videos
- `asset.update` - Edit metadata, favorites
- `asset.delete` - Remove assets
- `album.create` - Create albums
- `album.update` - Modify albums
- `album.delete` - Remove albums

**Typical tools exposed:**
- All read-only tools plus:
- `immich_uploadAsset`, `immich_updateAsset`, `immich_deleteAssets`
- `immich_createAlbum`, `immich_addAssetsToAlbum`, `immich_removeAssetFromAlbum`
- `immich_updateUser` (own user only)
- All POST, PUT, PATCH, DELETE endpoints except admin-only

**Blocked tools:**
- User administration (`getAllUsers`, `createUser`, `deleteUser`)
- Server configuration (`setServerConfig`, `updateServerConfig`)
- System maintenance (`runJobs`, `validateStorage`)
- API key management

**Example Claude Desktop config:**
```json
{
  "mcpServers": {
    "mcp4immich-readwrite": {
      "command": "python",
      "args": ["c:\\path\\to\\mcp4immich\\main.py"],
      "env": {
        "IMMICH_BASE_URL": "https://immich.example.com",
        "IMMICH_API_KEY": "your-readwrite-key",
        "IMMICH_PROFILE": "read_write"
      }
    }
  }
}
```

### `full_scope`
**Use case:** Administrative tasks, user management, server configuration.

**Permissions required:**
- All `read_write` permissions plus:
- `admin.user` - User administration
- `admin.config` - Server configuration
- `admin.jobs` - Job management
- `admin.apiKey` - API key management

**Typical tools exposed:**
- All read_write tools plus:
- `immich_getAllUsers`, `immich_createUser`, `immich_updateUser`, `immich_deleteUser`
- `immich_getServerConfig`, `immich_updateServerConfig`
- `immich_getAllJobs`, `immich_runJob`
- `immich_createApiKey`, `immich_updateApiKey`, `immich_deleteApiKey`

**Example Claude Desktop config:**
```json
{
  "mcpServers": {
    "mcp4immich-admin": {
      "command": "python",
      "args": ["c:\\path\\to\\mcp4immich\\main.py"],
      "env": {
        "IMMICH_BASE_URL": "https://immich.example.com",
        "IMMICH_API_KEY": "your-admin-key",
        "IMMICH_PROFILE": "full_scope"
      }
    }
  }
}
```

### No profile (default)
When `IMMICH_PROFILE` is not set, tool filtering relies solely on capability probes and the API key's actual permissions. This is backward-compatible with existing configurations.

**Profile selection guidelines:**
- Use `read_only` for AI assistants performing search and analysis without modification needs
- Use `read_write` for general asset and album management workflows
- Use `full_scope` only when administrative access is required
- Always create a dedicated Immich API key with minimal permissions for each profile

## Run
```
python main.py
```

## Helper script: Smart Search CLI

For quick local debugging without MCP client setup, use the helper script:

```sh
python helper/smart_search_cli.py --list-envs
python helper/smart_search_cli.py --env .env --query "golden retriever on beach" --size 25 --order desc
```

Behavior:
- Lists available `.env` files in the current directory (`.env`, `.env_*`).
- Loads `IMMICH_BASE_URL` and `IMMICH_API_KEY` or `IMMICH_API_TOKEN` from the selected env file.
- Calls `POST /api/search/smart` and prints the JSON response directly to stdout.

## Tests
Integration tests use the standard library `unittest` runner (pytest can also discover them).

Blocked tool reasons now include HTTP status or network error details to help troubleshoot capability checks.

Integration test setup:
1. Ensure an Immich server is running and reachable.
2. Create `.env_test` with read-only credentials.
3. Create `.env` with full-access credentials, or set `IMMICH_ENV_FULL` to another file.

MCP client tests start a background server using SSE. You can override defaults:
- `MCP_TEST_HOST` (default `127.0.0.1`)
- `MCP_TEST_PORT` (default `0` for auto-assign)
- `MCP_TEST_TIMEOUT` (default `20` seconds)
- `MCP_LOG_LEVEL` (default `DEBUG` for test server logs)

Run:
```
python -m unittest discover -s tests -v
```

Optional with pytest:
```
pytest tests/
```

You can override env file locations:
- `IMMICH_ENV_TEST` for the restricted credentials file (default `.env_test`)
- `IMMICH_ENV_FULL` for the full-access credentials file (default `.env`)

### URL access integration tests (`test_integration_url_access.py`)

Verifies that `web_url` fields generated by the URL decoration layer are accessible
against a live Immich instance (requires session login credentials in addition to an
API key).

Create `.env_web` in the project root (excluded by `.gitignore`):

```
IMMICH_BASE_URL=https://your-immich.example.com
IMMICH_API_KEY=<api-key-with-read-access>
IMMICH_EMAIL=<user@example.com>
IMMICH_PASSWORD=<your-password>
```

| Variable | Purpose |
|---|---|
| `IMMICH_BASE_URL` | Base URL of your Immich instance |
| `IMMICH_API_KEY` | API key for authenticated API calls |
| `IMMICH_EMAIL` | Account email for `POST /api/auth/login` |
| `IMMICH_PASSWORD` | Account password for session login |

`IMMICH_EXTERNAL_DOMAIN` may also be included to override the URL decoration base;
if omitted it falls back to the `/api/server-config` discovery chain.

Run:
```sh
pytest tests/test_integration_url_access.py -v
```

Tests skip automatically when `.env_web` is absent, the server is unreachable, or
the instance has no data of that type. Override the file path with `IMMICH_ENV_WEB`:
```sh
IMMICH_ENV_WEB=/path/to/other.env pytest tests/test_integration_url_access.py -v
```

| Test | Endpoint | Expected URL pattern | Regression for |
|---|---|---|---|
| `test_asset_web_url_accessible` | `GET /api/assets` (fallback: `POST /api/search/assets`) | `.../photos/{id}` | — |
| `test_album_web_url_accessible` | `GET /api/albums` | `.../albums/{id}` | — |
| `test_person_web_url_accessible` | `GET /api/people` | `.../people/{id}` (not `/photos/{id}`) | item 49 |
| `test_place_web_url_accessible` | `GET /api/places` | `.../explore...` | — |
| `test_newest_image_search_web_url_accessible` | `POST /api/search/assets` | `.../photos/{id}` | — |
| `test_random_person_web_url_accessible` | `GET /api/people` (random pick) | `.../people/{id}` | — |
| `test_random_album_web_url_accessible` | `GET /api/albums` (random pick) | `.../albums/{id}` | — |
| `test_random_video_web_url_accessible` | `POST /api/search/assets` type=VIDEO (random pick) | `.../photos/{id}` | — |

## Docker

### Build and run locally

Build and run with Docker Compose:
```
docker compose build
docker compose up
```

Note: the container runs `main.py`, which imports the `mcp4immich` package.
If you change the package layout, rebuild the image so the updated package is
copied into the container.

Environment variables are passed through from your shell or `.env` file:
- `IMMICH_BASE_URL` (default `http://host.docker.internal:2283`)
- `IMMICH_API_KEY`
- `IMMICH_API_TOKEN`
- `IMMICH_WRITE_PROBE_PATH` (default `/api/assets`)
- `IMMICH_WRITE_PROBE_METHOD` (default `POST`)

MCP server settings for Docker Compose:
- `MCP_TRANSPORT` (default `sse` in compose; use `streamable-http` for HTTP)
- `MCP_HOST` (default `0.0.0.0` in compose — this is the address the process binds *inside* the container's own network namespace, not the host mapping; see `MCP_BIND_IP` for the host side)
- `MCP_PORT` (default `8000`; published as the host port)
- `MCP_BIND_IP` (default `127.0.0.1` — the **host** interface the published port is bound to, e.g. `docker-compose.yaml`'s `ports:` maps `${MCP_BIND_IP:-127.0.0.1}:${MCP_PORT}:${MCP_PORT}`. Set it to a specific interface, such as a Tailscale or WireGuard address, to expose the server deliberately; see **Security** above before ever setting it to `0.0.0.0`.)

`GET /healthz` reports `{"status", "immich_reachable", "spec_source", "version"}` for container/monitoring probes. It always returns `200` — even when Immich is unreachable, which just sets `immich_reachable: false` — so a probe should check that field, not just the HTTP status.

### Use pre-built images from GitHub Container Registry

Pre-built Docker images are automatically published to GitHub Container Registry (GHCR) for every push to `main` and `develop` branches, as well as for releases.

> Images published before 2026-09-20 live at `ghcr.io/joeru/claw2immich` and keep working; new tags are published under `mcp4immich`.

**Pull the image:**
```bash
# Latest build from main branch
docker pull ghcr.io/joeru/mcp4immich:latest

# Latest build from develop branch
docker pull ghcr.io/joeru/mcp4immich:develop

# Specific version (e.g., 1.0.0)
docker pull ghcr.io/joeru/mcp4immich:1.0.0
```

**Run the image:**

The examples below publish to `127.0.0.1` only. The process holds a full
Immich API key, and Docker writes its own `iptables` DNAT rules for a
published port — these bypass host firewalls (UFW, etc.) that only see the
`INPUT` chain, so `-p 8000:8000` (i.e. `0.0.0.0:8000`) is reachable from the
network regardless of what the host firewall says. To expose it
deliberately, publish to a specific interface instead, e.g.
`-p 100.x.x.x:8000:8000` for a Tailscale address, or `-p 0.0.0.0:8000:8000`
only when you have verified the host firewall genuinely blocks that port.

```bash
docker run -e IMMICH_BASE_URL=https://immich.example.com \
           -e IMMICH_API_KEY=your-api-key \
           -p 127.0.0.1:8000:8000 \
           ghcr.io/joeru/mcp4immich:latest
```

**Run with SSE transport (HTTP):**
```bash
docker run -e IMMICH_BASE_URL=https://immich.example.com \
           -e IMMICH_API_KEY=your-api-key \
           -e MCP_TRANSPORT=sse \
           -e MCP_HOST=0.0.0.0 \
           -p 127.0.0.1:8000:8000 \
           ghcr.io/joeru/mcp4immich:latest
```

**Run with read-only profile:**
```bash
docker run -e IMMICH_BASE_URL=https://immich.example.com \
           -e IMMICH_API_KEY=your-readonly-api-key \
           -e IMMICH_PROFILE=read_only \
           -p 127.0.0.1:8000:8000 \
           ghcr.io/joeru/mcp4immich:latest
```

Images support multiple architectures (amd64, arm64) and are automatically selected based on your platform.
