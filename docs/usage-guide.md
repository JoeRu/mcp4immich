---
description: 'Usage Guide only for AI Agents as mcp clients.'
agent: 'agent'
---

# mcp4immich MCP Usage Guide

This guide explains how to use the MCP server to discover tools and perform common Immich workflows. It is designed for MCP clients and AI agents.

## Build Web URLs (Assets, Albums, People, Places)
The tool responses for asset, album, person, and place endpoints automatically include a `web_url` field with a direct link to the item in the Immich web UI. This field is populated when `IMMICH_EXTERNAL_DOMAIN` is configured (or discovered from `/api/server-config`).

For tools that fetch individual items (e.g., GET /api/assets/{id}), the response will include:
```json
{
  "id": "asset-id",
  "name": "Photo.jpg",
  "web_url": "https://immich.example.com/photos/asset-id",
  ...
}
```

If you need to construct URLs manually or for tools that don't include web_url, call the tool whose description starts with `GET /api/server-config` and read `externalDomain`.

Use `externalDomain` as the base URL (no trailing slash). Build web UI links like:
- Asset (image): `<externalDomain>/photos/<asset-id>`
- Album: `<externalDomain>/albums/<album-id>`
- Person: `<externalDomain>/people/<person-id>`
- Place: `<externalDomain>/places/<place-id>`

If `externalDomain` is empty, fall back to the base URL you connected to (for example `IMMICH_BASE_URL`). If a URL does not resolve, prefer share-link endpoints or verify the web UI path for your Immich version.

## Tool Documentation
Tools include:
- `name` and `description` (always includes the HTTP method and path)
- `inputSchema` (JSON Schema for arguments)
- parameter prefixes: `path_`, `query_`, `header_`, `cookie_`, and `body`

Descriptions are enriched with:
- `params:` summary of required path/query/body fields
- Enum constraints shown as `param_name[value1|value2|value3]` for parameters with limited valid values
- `example:` short call sketch when required inputs exist
- `returns:` response schema title and key fields when available

When possible, call known tool names directly (for example `immich_getassetinfo`, `immich_searchassets`, `immich_searchsmart`) and use `inputSchema` only to confirm required fields.

### Parameter Naming
OpenAPI tool parameters are exposed as explicit fields:
- `path_<name>` for path parameters
- `query_<name>` for query parameters
- `header_<name>` for header parameters
- `cookie_<name>` for cookie parameters
- `body` for JSON request bodies

Legacy parameters (`path_params`, `query_params`, `headers`, `json_body`) still work but are not recommended for new clients.

## Resources and Prompts
- Resources provide readable docs. Use `resources/list` then `resources/read` for `docs://usage-guide`.
- Prompts provide workflow templates for common tasks and can be fetched via `prompts/list` and `prompts/get`.

## Client Handling
Clients automatically receive server info, instructions, capabilities, and tool lists on connect. Use this to inform tool selection and reduce guesswork.

## Access Profiles
The server supports optional access profiles via the `IMMICH_PROFILE` environment variable to restrict tool exposure based on permission level. Profiles work as an additional filter layer on top of capability probes.

### Available Profiles
- **`read_only`**: Only exposes GET endpoints for browsing and searching. Blocks all write operations (upload, update, delete) and admin tools.
- **`read_write`**: Exposes read tools plus write operations for assets and albums. Blocks admin-only endpoints (user management, server config, system jobs).
- **`full_scope`**: Exposes all available tools including admin endpoints. No profile restrictions; tool exposure depends only on API key permissions and capability probes.
- **No profile (default)**: When `IMMICH_PROFILE` is unset, no profile restrictions apply. Tool filtering relies solely on capability probes and API key permissions (backward compatible).

### How Profiles Affect Tool Availability
- **read_only**: Only tools with `GET` methods appear (searching, browsing, reporting). Write tools (`POST`, `PUT`, `PATCH`, `DELETE`) are blocked with reason: "Write endpoint blocked by profile: read_only".
- **read_write**: All non-admin tools appear. Admin-only endpoints are blocked with reason: "Admin endpoint blocked by profile: read_write".
- **full_scope**: All tools that pass capability probes appear. No profile-based blocking.

### Checking Active Profile
Profiles are transparent to MCP clients. To understand which tools are blocked:
1. Call `tool_access_report` to see allowed and blocked tools.
2. Review `blocked_tools` array for items with profile-related reasons.
3. If a required tool is blocked by profile, ask the user to adjust `IMMICH_PROFILE` or use a less restrictive profile.

### Profile Selection Guidance
- Use `read_only` for AI assistants performing search, analysis, and reporting without modification needs.
- Use `read_write` for workflows that manage assets and albums but do not require admin access.
- Use `full_scope` only when user management, server configuration, or system maintenance is required.
- When unsure, check `tool_access_report` blocked reasons to diagnose profile restrictions.

## Initialize Instructions
Initialize instructions include externalDomain guidance for link building. Use the tool whose description starts with `GET /api/server-config` and read `externalDomain` before constructing links.

Workflow groups called out in instructions:
- discovery: tool access reports and server config
- assets: assets and search endpoints
- people: people and face endpoints
- albums: album and share endpoints
- utilities: server info/version

Do:
- Read `tool_access_report` when permissions are uncertain.
- Follow `inputSchema` prefixes (`path_`, `query_`, `body`) for arguments.

Don't:
- Guess domains or tool names.

Example instructions string:
"1) Read tool_access_report and server config. 2) Pick tools by description. 3) Use inputSchema prefixes and required params."

## Workflow Examples
These examples use tool descriptions and parameter prefixes rather than hard-coded tool names.

### Get an Image (Asset by ID)
1. Call `immich_getassetinfo`.
2. Set `path_id` to the asset id.

Example call:
- Tool: `immich_getassetinfo`
- Args: `{ "path_id": "<asset-id>" }`

### Download Original Asset File (Link/Base64)
Use `downloadAsset` when the MCP client needs download access but does not have direct access to an Immich API key.

1. Call `downloadAsset` with `asset_id`.
2. Choose delivery strategy via `IMMICH_DOWNLOAD_ASSET_DELIVERY` on server side:
  - `shared_link` (default): server creates a short-lived tokenized shared link (30 minutes) and returns link metadata without payload bytes. The link requires no authentication and can be shared directly.
  - `inline_base64`: server fetches bytes and returns base64 payload through MCP. Note: large files may be truncated by MCP transport limits (~64 KB).
  - `immich_link`: server first attempts shared-link creation; if unavailable, returns a direct Immich download URL (`/api/assets/{id}/original`) that requires authentication.
3. Read link metadata (`download_url`, `expires_in_minutes`, `expires_at`) for shared-link mode or payload metadata (`content_type`, `size_bytes`, optional `filename`) for inline mode.

Example call:
- Tool: `downloadAsset`
- Args: `{ "asset_id": "<asset-id>" }`

### Find a Person
1. Use `immich_searchperson` when available for direct name matching.
2. Otherwise use `immich_getallpeople` and filter by name client-side.

Example call:
- Tool: `immich_searchperson`
- Args: `{ "query_name": "Ada" }`

### Find a Location
1. Use `immich_getmapmarkers` for map/location discovery.
2. Use `immich_searchassets` for location-related asset retrieval.

Example call:
- Tool: `immich_searchassets`
- Args: `{ "body_query": "Seattle" }`

### Get the Newest Photo
1. Use `immich_searchassets`.
2. Set ordering and page size explicitly.

Example call:
- Tool: `immich_searchassets`
- Args: `{ "body_order": "desc", "body_size": 1 }`

### Search Assets (searchAssets)
1. Use tool `immich_searchassets`.
2. Pass query/body fields directly.
3. Use `inputSchema` only for field validation.

Example call:
- Tool: `immich_searchassets`
- Args: `{ "body_query": "mountain", "body_page": 1 }`

### Smart Search (searchSmart)
1. Use tool `immich_searchsmart`.
2. Pass the natural-language query in `body_query`.
3. Add filters only when present in `inputSchema`.

Example call:
- Tool: `immich_searchsmart`
- Args: `{ "body_query": "golden retriever" }`

### Upload a Photo
1. Use `immich_uploadasset` when available.
2. Fill required upload fields from `inputSchema`.
3. Send explicit `body_*` fields.

Example call:
- Tool: `immich_uploadasset`
- Args: `{ "body_deviceAssetId": "...", "body_deviceId": "camera-1", "body_fileCreatedAt": "2026-01-01T10:00:00.000Z" }`

### Share an Album
1. Use `immich_createsharedlink` to create a shared link for an album.
2. Pass the album ID and sharing options in body fields.

Example call:
- Tool: `immich_createsharedlink`
- Args: `{ "body_type": "ALBUM", "body_albumId": "<album-id>", "body_allowDownload": true }`

## Tips
- Always call `tool_access_report` first when permissions are uncertain.
- Write tools only appear when your credentials allow `POST /api/assets` (use `write_capability_report` to see the reason).
- Prefer explicit tool names and argument templates; use descriptions only as fallback when names differ by Immich version.
- Blocked tools now include specific HTTP status or network error reasons to help troubleshoot access issues.
- Some search endpoints use `POST` but still require only read permissions; they should appear when the permission is read-only.
