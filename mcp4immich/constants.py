OPENAPI_SPEC_URL = (
    "https://raw.githubusercontent.com/immich-app/immich/main/open-api/immich-openapi-specs.json"
)
DEFAULT_BASE_URL = "http://localhost:2283"
DEFAULT_TIMEOUT = 10.0
MAX_SUMMARY_LEN = 140
MAX_DESCRIPTION_LEN = 360
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def build_server_instructions(external_domain: str | None) -> str:
    if external_domain:
        domain_note = f"External domain for link building: {external_domain}. "
    else:
        domain_note = (
            "External domain for link building: set IMMICH_EXTERNAL_DOMAIN env var "
            "or call GET /api/server-config and read externalDomain. "
        )
    return (
        "mcp4immich MCP server for Immich. "
        "Use tool descriptions (method/path) to choose OpenAPI tools. "
        f"{domain_note}"
        "URL patterns: <externalDomain>/photos/<asset-id>, "
        "/albums/<album-id>, /people/<person-id>. "
        "Tool responses for assets, albums, and people include web_url field for direct browsing. "
        "Parameter naming: path_<name>, query_<name>, header_<name>, "
        "cookie_<name>, body. Legacy path_params/query_params/headers/json_body "
        "still accepted. "
        "Workflow groups: discovery (tool_access_report, write_capability_report, "
        "server config), assets (assets/search), people (people/faces), albums "
        "(albums/share), utilities (server version). "
        "Search: POST /api/search/assets for metadata filters, "
        "POST /api/search/smart for CLIP natural-language search. "
        "Do: call tool_access_report first when permissions are uncertain, "
        "follow inputSchema prefixes, use descriptions to pick tools. "
        "Don't: guess domains or tool names, hard-code tool names. "
        "Profiles: set IMMICH_PROFILE to read_only, read_write, or full_scope "
        "to restrict tool exposure. "
        "For detailed workflow examples read docs://usage-guide."
    )


SERVER_INSTRUCTIONS = build_server_instructions(None)
