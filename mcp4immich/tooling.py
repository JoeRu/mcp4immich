import logging
import inspect
import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

from .capabilities import (
    _discover_capabilities,
    _discover_user_profile,
    _discover_write_capability,
)
from .config import (
    _get_config,
    get_profile,
    get_external_domain,
    get_download_asset_delivery_mode,
    profile_allows_admin,
    profile_allows_write,
)
from .constants import MAX_DESCRIPTION_LEN, MAX_SUMMARY_LEN, WRITE_METHODS
from .http_client import _request, _request_bytes
from .openapi import (
    _apply_path_params,
    _fetch_openapi_spec,
    _format_example,
    _format_param_summary,
    _format_response_hint,
    _list_openapi_operations,
    _openapi_base_path,
    _operation_admin_only,
    _operation_param_specs,
    _operation_permission,
    _operation_request_body_spec,
    _operation_request_body_field_specs,
    _operation_requires_auth,
    _permission_is_read,
    _response_schema_info,
    _tool_name_for_operation,
    _truncate_description,
)


def _should_decorate_response(method: str, path: str) -> tuple[bool, str | None]:
    """
    Determine if a tool response should be decorated with web URLs.
    
    Args:
        method: HTTP method
        path: OpenAPI path template
    
    Returns:
        Tuple of (should_decorate, url_type) where url_type is 'asset', 'album', 'person', 'place', or None.
        For array endpoints (search, browse), returns 'array' to indicate special handling needed.
    """
    method_upper = (method or "").upper()

    if method_upper not in ("GET", "POST"):
        return False, None
    if method_upper == "POST" and not path.startswith("/search/"):
        return False, None
    
    # Single-entity endpoints with direct ID in path
    if path.startswith("/assets/") and "{" in path:
        return True, "asset"
    if path.startswith("/albums/") and "{" in path:
        return True, "album"
    if path.startswith("/people/") and "{" in path:
        return True, "person"
    if path.startswith("/places/") and "{" in path:
        return True, "place"
    
    # Array endpoints that may contain type fields (IMAGE, VIDEO, etc.)
    # Search endpoints
    if path.startswith("/search/"):
        return True, "array"
    
    # Collection/bulk endpoints for assets, albums, people, places
    if path in ("/assets", "/albums", "/people", "/places"):
        return True, "array"
    
    # Browse/explore/discovery endpoints
    if any(
        path.startswith(prefix)
        for prefix in (
            "/cine",
            "/explore",
            "/memories",
            "/map",
            "/duplicates",
        )
    ):
        return True, "array"
    
    # Stats/timeline endpoints that often return arrays
    if path.startswith("/statistics") or path.startswith("/timelines"):
        return True, "array"
    
    return False, None


def _extract_single_id(data: Any) -> str | None:
    """
    Extract a single ID field from response data for URL building.
    
    Args:
        data: Response data (dict or other)
    
    Returns:
        The ID string if found, None otherwise
    """
    if not isinstance(data, dict):
        return None
    
    # Try common ID field names
    for id_field in ("id", "albumId", "personId", "placeId"):
        if id_field in data and data[id_field]:
            return str(data[id_field])
    
    return None


def _extract_entity_id(data: Any, url_type: str) -> str | None:
    """Extract an entity ID using URL-type-aware precedence."""
    if not isinstance(data, dict):
        return None

    id_priority: tuple[str, ...]
    if url_type == "asset":
        # Prefer asset-specific identifiers and avoid personId leakage.
        id_priority = ("assetId", "id")
    elif url_type == "album":
        id_priority = ("albumId", "id")
    elif url_type == "person":
        id_priority = ("personId", "id")
    elif url_type == "place":
        id_priority = ("placeId", "id")
    else:
        id_priority = ("id", "albumId", "personId", "placeId")

    for id_field in id_priority:
        if id_field in data and data[id_field]:
            return str(data[id_field])
    return None


def _detect_response_type(item: Any) -> str | None:
    """
    Detect the URL type based on response item content and type field.
    
    Args:
        item: Response item (typically dict with 'type' and/or 'id' fields)
    
    Returns:
        URL type ('asset', 'album', 'person', 'place') or None if unable to determine
    """
    if not isinstance(item, dict):
        return None
    
    # Check for explicit type field (IMAGE, VIDEO for assets)
    item_type = item.get("type")
    if item_type:
        if item_type in ("IMAGE", "VIDEO", "MEMORY"):
            return "asset"
        elif item_type == "ALBUM":
            return "album"
        elif item_type == "PERSON":
            return "person"
        elif item_type == "PLACE":
            return "place"
    
    # Try to infer from ID field names
    if "personId" in item:
        return "person"
    if "albumId" in item:
        return "album"
    if "placeId" in item:
        return "place"

    # Check for album-specific fields (for album objects that may only have "id")
    if any(
        key in item
        for key in (
            "albumName",
            "albumThumbnailAssetId",
            "sharedLinkId",
            "isActivityEnabled",
        )
    ):
        return "album"
    
    # Check for person-specific fields (for person objects that may only have "id")
    # birthDate, thumbnailPath, isHidden, and faces are exclusive to Immich person objects
    # and never appear on asset/album/place records.
    if any(k in item for k in ("birthDate", "thumbnailPath", "isHidden", "faces")):
        return "person"
    
    # Default: if has "id" field, likely an asset
    if "id" in item:
        return "asset"
    
    return None


# Wrapper field names for single-array extraction.
_ARRAY_FIELD_NAMES = (
    "results",
    "data",
    "items",
    "assets",
    "albums",
    "people",
    "places",
    "photos",
    "memories",
    "timelines",
    "statistics",
)

# Section keys whose inner "items" lists should be decorated in
# multi-section responses (e.g. Immich search results).
_SEARCH_SECTION_KEYS = ("assets", "albums", "people", "places")


def _extract_decoratable_array(response: Any) -> tuple[list[Any] | None, str]:
    """
    Extract a decoratable array from a response, handling nested structures.
    
    Supports various response formats:
    - Direct array: [...]
    - Wrapped array: {"results": [...], ...}, {"data": [...], ...}, {"assets": [...], ...}
    - Nested section: {"assets": {"items": [...]}, "albums": {"items": [...]}}
    - Other wrapped formats with nested arrays
    
    Args:
        response: Response data (dict, list, or other)
    
    Returns:
        Tuple of (array, wrapper_type) where:
        - array: the extracted array or None if not found
        - wrapper_type: 'direct' for direct array, 'wrapped' for dict with array
          field, 'sections' for multi-section search responses, or 'none' if not found
    """
    if isinstance(response, list):
        return response, "direct"
    
    if not isinstance(response, dict):
        return None, "none"
    
    # 1) Direct list fields (e.g. {"results": [...], "total": 5})
    for field_name in _ARRAY_FIELD_NAMES:
        if field_name in response and isinstance(response[field_name], list):
            return response[field_name], "wrapped"
    
    # 2) Multi-section search responses where each section is a dict
    #    containing an inner "items" list
    #    e.g. {"assets": {"items": [...]}, "albums": {"items": [...]}}
    for section_key in _SEARCH_SECTION_KEYS:
        section = response.get(section_key)
        if (
            isinstance(section, dict)
            and isinstance(section.get("items"), list)
        ):
            return None, "sections"
    
    return None, "none"


def _decorate_response(
    response: Any, external_domain: str | None, url_type: str
) -> Any:
    """
    Add web_url field(s) to a response for direct browsing.
    
    Handles various response structures:
    - Single entity: adds web_url field directly
    - Direct array: processes each item and adds web_url to decoratable items
    - Wrapped array: extracts array from common wrapper fields (results, data, assets, etc.)
    - Multi-section search: {"assets": {"items": [...]}, "albums": {"items": [...]}}
    - Mixed structures: applies decoration to decoratable items and preserves structure
    
    Args:
        response: Response data (dict, list, or other)
        external_domain: Base domain for URLs (e.g., https://immich.example.com)
        url_type: Type of URL to build ('asset', 'album', 'person', 'place', or 'array' for auto-detection)
    
    Returns:
        Modified response with web_url field(s) added, preserving original structure
    """
    if not external_domain:
        return response

    # Single-entity endpoints should decorate the top-level object directly.
    # This prevents relation arrays like `people` inside asset detail responses
    # from being misinterpreted as top-level wrapped result arrays.
    if url_type != "array" and isinstance(response, dict):
        return _decorate_single_item(response, external_domain, url_type)
    
    # Try to extract a decoratable array (handles both direct and wrapped)
    decoratable_array, wrapper_type = _extract_decoratable_array(response)
    
    if decoratable_array and wrapper_type == "direct":
        # Direct array: decorate each item
        return [_decorate_single_item(item, external_domain, url_type) for item in decoratable_array]
    
    if decoratable_array and wrapper_type == "wrapped":
        # Wrapped array: decorate items and return modified response with updated array
        decorated_array = [_decorate_single_item(item, external_domain, url_type) for item in decoratable_array]
        # Update the response with decorated array
        result = dict(response)  # Shallow copy
        # Find which field contains the array and update it
        for field_name in _ARRAY_FIELD_NAMES:
            if field_name in result and isinstance(result[field_name], list):
                result[field_name] = decorated_array
                break
        return result
    
    if wrapper_type == "sections":
        # Multi-section search response, e.g.
        # {"assets": {"items": [...]}, "albums": {"items": [...]}}
        result = dict(response)  # Shallow copy
        for section_key in _SEARCH_SECTION_KEYS:
            section = result.get(section_key)
            if not isinstance(section, dict):
                continue
            items = section.get("items")
            if not isinstance(items, list):
                continue
            decorated_items = [
                _decorate_single_item(item, external_domain, url_type)
                for item in items
            ]
            result[section_key] = {**section, "items": decorated_items}
        return result
    
    # Not an array - try to decorate as single item if it's a dict
    if isinstance(response, dict):
        return _decorate_single_item(response, external_domain, url_type)
    
    return response


def _decorate_single_item(item: Any, external_domain: str, url_type: str) -> Any:
    """
    Decorate a single item with web_url if applicable.
    
    Args:
        item: Single response item (dict or other)
        external_domain: Base domain for URLs
        url_type: URL type, or 'array' to auto-detect from item
    
    Returns:
        Modified item with web_url field added if applicable
    """
    if not isinstance(item, dict):
        return item
    
    # For array endpoints, detect the type from the item itself
    if url_type == "array":
        detected_type = _detect_response_type(item)
        if not detected_type:
            return item
        effective_url_type = detected_type
    else:
        effective_url_type = url_type
    
    # Extract ID from item using URL-type-aware precedence
    entity_id = _extract_entity_id(item, effective_url_type)
    if not entity_id:
        return item
    
    # Build the appropriate web URL
    if effective_url_type == "asset":
        web_url = f"{external_domain}/photos/{entity_id}"
    elif effective_url_type == "album":
        web_url = f"{external_domain}/albums/{entity_id}"
    elif effective_url_type == "person":
        web_url = f"{external_domain}/people/{entity_id}"
    elif effective_url_type == "place":
        web_url = f"{external_domain}/explore?places={entity_id}"
    else:
        return item
    
    # Add web_url to item (don't overwrite if already present)
    if "web_url" not in item:
        item["web_url"] = web_url
    
    return item


def _deduplicate_name(base_name: str, seen: set[str]) -> str:
    """
    Generate a unique tool name by appending suffix if the base name already exists.
    
    Args:
        base_name: The base tool name
        seen: Set of already-used tool names
        
    Returns:
        A unique name (either the base_name or base_name_N where N >= 2)
    """
    if base_name not in seen:
        return base_name
    suffix = 2
    while f"{base_name}_{suffix}" in seen:
        suffix += 1
    return f"{base_name}_{suffix}"


def _openapi_tool_access() -> dict[str, Any]:
    logger.debug("Computing OpenAPI tool access")
    spec = _fetch_openapi_spec()
    operations = _list_openapi_operations(spec)
    logger.debug(f"OpenAPI spec has {len(operations)} operations")
    base_path = _openapi_base_path(spec)
    config = _get_config()
    has_auth = bool(config["api_key"] or config["api_token"])
    write_capability = _discover_write_capability()
    profile = _discover_user_profile() if has_auth else {}
    is_admin = bool(profile.get("isAdmin"))
    access_profile = get_profile()

    allowed_tools: list[str] = []
    blocked_tools: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for entry in operations:
        method = entry["method"]
        path = entry["path"]
        operation = entry["operation"]
        tool_name = _tool_name_for_operation(method, path, operation)
        tool_name = _deduplicate_name(tool_name, seen_names)
        seen_names.add(tool_name)

        requires_auth = _operation_requires_auth(operation, spec)
        if requires_auth and not has_auth:
            blocked_tools.append(
                {
                    "tool": tool_name,
                    "reason": "Missing IMMICH_API_KEY or IMMICH_API_TOKEN",
                }
            )
            continue

        if _operation_admin_only(operation) and not is_admin:
            blocked_tools.append(
                {
                    "tool": tool_name,
                    "reason": "Admin-only endpoint",
                }
            )
            continue

        if _operation_admin_only(operation) and not profile_allows_admin(
            access_profile
        ):
            blocked_tools.append(
                {
                    "tool": tool_name,
                    "reason": f"Admin endpoint blocked by profile: {access_profile}",
                }
            )
            continue

        permission = _operation_permission(operation)
        # Only block write operations when we have explicit permission metadata
        # indicating write access. When permission is None (no metadata), treat
        # as unknown and do not block based on write probe alone.
        is_write = (
            method in WRITE_METHODS
            and permission is not None
            and not _permission_is_read(permission)
        )
        if is_write and not bool(write_capability.get("allowed")):
            reason = str(
                write_capability.get("reason") or "Write capability not allowed"
            )
            blocked_tools.append({"tool": tool_name, "reason": reason})
            continue

        if is_write and not profile_allows_write(access_profile):
            blocked_tools.append(
                {
                    "tool": tool_name,
                    "reason": f"Write endpoint blocked by profile: {access_profile}",
                }
            )
            continue

        allowed_tools.append(tool_name)

    return {
        "allowed_tools": allowed_tools,
        "blocked_tools": blocked_tools,
        "base_path": base_path,
        "operations": operations,
    }


# def openapi_summary() -> dict[str, Any]:
#     """Return OpenAPI title, version, and path count."""
#     spec = _fetch_openapi_spec()
#     info = spec.get("info", {})
#     paths = spec.get("paths", {})
#     return {
#         "title": info.get("title"),
#         "version": info.get("version"),
#         "path_count": len(paths),
#     }


# def list_openapi_paths(limit: int = 20) -> list[str]:
#     """List OpenAPI method/path entries (limited)."""
#     spec = _fetch_openapi_spec()
#     paths = spec.get("paths", {})
#     entries: list[str] = []
#     for path, methods in paths.items():
#         for method in methods.keys():
#             entries.append(f"{method.upper()} {path}")
#             if len(entries) >= limit:
#                 return entries
#     return entries


def ping_server() -> Any:
    """Check whether the Immich server is reachable."""
    try:
        return _request("GET", "/api/server/ping")
    except Exception as exc:
        return {"error": str(exc)}


def get_server_version() -> Any:
    """Fetch Immich server version information."""
    try:
        return _request("GET", "/api/server/version")
    except Exception as exc:
        return {"error": str(exc)}


def get_current_user() -> Any:
    """Fetch the current user (requires API key or token)."""
    try:
        return _request("GET", "/api/users/me", require_auth=True)
    except Exception as exc:
        return {"error": str(exc)}


def tool_access_report() -> dict[str, Any]:
    """Describe which tools are available based on API key permissions."""
    logger.debug("Generating tool access report")
    capabilities = _discover_capabilities()
    config = _get_config()
    has_auth = bool(config["api_key"] or config["api_token"])
    allowed_tools = [
        # "openapi_summary",
        # "list_openapi_paths",
        "ping_server",
        "get_server_version",
        "tool_access_report",
        "write_capability_report",
    ]
    blocked_tools: list[dict[str, str]] = []
    if has_auth:
        allowed_tools.append("downloadAsset")
    else:
        blocked_tools.append(
            {
                "tool": "downloadAsset",
                "reason": "Missing IMMICH_API_KEY or IMMICH_API_TOKEN",
            }
        )
    for tool_name, info in capabilities.items():
        if info.get("allowed"):
            allowed_tools.append(tool_name)
        else:
            blocked_tools.append(
                {"tool": tool_name, "reason": str(info.get("reason"))}
            )
    openapi_access = _openapi_tool_access()
    allowed_tools.extend(openapi_access["allowed_tools"])
    blocked_tools.extend(openapi_access["blocked_tools"])
    logger.info(
        f"Tool access report: {len(allowed_tools)} allowed, {len(blocked_tools)} blocked"
    )
    return {"allowed_tools": allowed_tools, "blocked_tools": blocked_tools}


def write_capability_report() -> dict[str, str | bool]:
    """Report optional write capability probe results."""
    return _discover_write_capability()


def download_asset(asset_id: str, output: str = "base64") -> dict[str, Any]:
    """Download an asset or return a link-based delivery payload."""
    try:
        mode = (output or "base64").strip().lower()
        if mode not in ("base64"):
            raise ValueError("output must be 'base64'")

        delivery_mode = get_download_asset_delivery_mode()

        def _resolve_shared_link_url(
            payload: dict[str, Any],
            external_domain: str,
        ) -> str | None:
            direct_url = payload.get("url") or payload.get("sharedUrl") or payload.get("sharedLink")
            if isinstance(direct_url, str) and direct_url.strip():
                url = direct_url.strip()
                if url.startswith("http://") or url.startswith("https://"):
                    return url
                return f"{external_domain}/{url.lstrip('/')}"

            token = payload.get("token") or payload.get("key") or payload.get("slug")
            if isinstance(token, str) and token.strip():
                return f"{external_domain}/share/{token.strip()}"

            link_id = payload.get("id")
            if isinstance(link_id, str) and link_id.strip():
                return f"{external_domain}/share/{link_id.strip()}"

            return None

        def _create_shared_link(ttl_minutes: int = 30) -> dict[str, Any]:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
            expires_at_iso = expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            external_domain = get_external_domain() or _get_config()["base_url"]

            candidate_requests: list[tuple[str, dict[str, Any]]] = [
                (
                    "/api/shared-links/createSharedLink",
                    {
                        "type": "INDIVIDUAL",
                        "assetIds": [asset_id],
                        "expiresAt": expires_at_iso,
                    },
                ),
                (
                    "/api/shared-links",
                    {
                        "type": "INDIVIDUAL",
                        "assetIds": [asset_id],
                        "expiresAt": expires_at_iso,
                    },
                ),
                (
                    "/api/shared-links/createSharedLink",
                    {
                        "assetIds": [asset_id],
                        "expiresAt": expires_at_iso,
                    },
                ),
                (
                    "/api/shared-links",
                    {
                        "assetIds": [asset_id],
                        "expiresAt": expires_at_iso,
                    },
                ),
            ]

            errors: list[str] = []
            for api_path, payload in candidate_requests:
                try:
                    response = _request(
                        "POST",
                        api_path,
                        json_body=payload,
                        require_auth=True,
                    )
                except Exception as exc:
                    errors.append(f"{api_path}: {exc}")
                    continue

                if not isinstance(response, dict):
                    errors.append(f"{api_path}: non-dict response")
                    continue

                shared_url = _resolve_shared_link_url(response, external_domain)
                if not shared_url:
                    errors.append(f"{api_path}: shared URL/token missing")
                    continue

                return {
                    "ok": True,
                    "delivery_mode": "shared_link",
                    "asset_id": asset_id,
                    "download_url": shared_url,
                    "expires_in_minutes": ttl_minutes,
                    "expires_at": response.get("expiresAt") or expires_at_iso,
                    "tokenized": True,
                    "requires_auth": False,
                    "source": api_path,
                }

            return {"ok": False, "error": "; ".join(errors) if errors else "shared link creation failed"}

        if delivery_mode in ("immich_link", "shared_link"):
            shared_link_result = _create_shared_link(ttl_minutes=30)
            if shared_link_result.get("ok"):
                return {
                    "asset_id": asset_id,
                    "delivery_mode": "shared_link",
                    "download_url": shared_link_result["download_url"],
                    "expires_in_minutes": shared_link_result["expires_in_minutes"],
                    "expires_at": shared_link_result["expires_at"],
                    "tokenized": True,
                    "requires_auth": False,
                    "note": (
                        "Short-lived shared link generated via Immich shared-links API. "
                        "No inline file payload is returned in this mode."
                    ),
                }

        if delivery_mode == "shared_link":
            return {
                "asset_id": asset_id,
                "delivery_mode": "shared_link",
                "error": "Shared-link delivery is configured but shared-link creation is unavailable.",
                "fallback": "Switch IMMICH_DOWNLOAD_ASSET_DELIVERY to immich_link or inline_base64.",
            }

        if delivery_mode == "immich_link":
            config = _get_config()
            domain = get_external_domain() or config["base_url"]
            return {
                "asset_id": asset_id,
                "delivery_mode": "immich_link",
                "download_url": f"{domain}/api/assets/{asset_id}/original",
                "requires_auth": True,
                "note": (
                    "Shared-link creation unavailable; falling back to direct Immich authenticated link. "
                    "Client must authenticate directly against Immich when using immich_link mode."
                ),
            }

        content, response_headers = _request_bytes(
            "GET",
            f"/api/assets/{asset_id}/original",
            require_auth=True,
        )
        content_type = response_headers.get("content-type", "application/octet-stream")
        content_disposition = response_headers.get("content-disposition", "")
        filename_match = re.search(
            r'filename="?([^";]+)"?', content_disposition, re.IGNORECASE
        )
        filename = filename_match.group(1) if filename_match else None

        payload = base64.b64encode(content).decode("ascii")

        result: dict[str, Any] = {
            "asset_id": asset_id,
            "delivery_mode": "inline_base64",
            "output": "base64",
            "requested_output": mode,
            "encoding": "base64",
            "content_type": content_type,
            "size_bytes": len(content),
            "data": payload,
        }
        if filename:
            result["filename"] = filename
        return result
    except Exception as exc:
        return {"error": str(exc)}


def _register_tools(mcp) -> None:
    logger.info("Registering MCP tools")
    capabilities = _discover_capabilities()
    config = _get_config()
    has_auth = bool(config["api_key"] or config["api_token"])
    for tool_func in (
        # openapi_summary,
        # list_openapi_paths,
        ping_server,
        get_server_version,
        tool_access_report,
        write_capability_report,
    ):
        mcp.tool()(tool_func)

    if has_auth:
        mcp.tool(name="downloadAsset")(download_asset)

    if capabilities.get("get_current_user", {}).get("allowed"):
        mcp.tool()(get_current_user)

    _register_openapi_tools(mcp)


def _register_openapi_tools(mcp) -> None:
    logger.info("Registering OpenAPI tools")
    access = _openapi_tool_access()
    spec = _fetch_openapi_spec()
    base_path = access["base_path"]
    operations = access["operations"]
    allowed = set(access["allowed_tools"])
    used_names: set[str] = set()
    external_domain = get_external_domain()

    for entry in operations:
        method = entry["method"]
        path = entry["path"]
        operation = entry["operation"]
        tool_name = _tool_name_for_operation(method, path, operation)
        tool_name = _deduplicate_name(tool_name, used_names)
        used_names.add(tool_name)

        if tool_name not in allowed:
            continue

        summary = operation.get("summary") or operation.get("description") or ""
        permission = _operation_permission(operation)
        if permission:
            summary = f"{summary} (permission: {permission})".strip()
        if summary and len(summary) > MAX_SUMMARY_LEN:
            summary = summary[: MAX_SUMMARY_LEN - 3].rstrip() + "..."
        description = f"{method} {base_path}{path}"
        if summary:
            description = f"{description} - {summary}"

        requires_auth = _operation_requires_auth(operation, spec)
        param_specs = _operation_param_specs(entry)
        body_spec = _operation_request_body_spec(operation)
        
        # Try to extract individual field specs from resolved body schema
        body_field_specs = _operation_request_body_field_specs(operation, spec)
        if body_field_specs:
            # If we have resolved body fields, use them instead of generic 'body' parameter
            param_specs.extend(body_field_specs)
            body_spec = None  # Don't create a generic 'body' param
        
        params_summary = _format_param_summary(param_specs, body_spec, spec)
        example_summary = _format_example(param_specs, body_spec)
        response_info = _response_schema_info(operation, spec)
        response_hint = _format_response_hint(response_info, include_keys=True)

        details: list[str] = [params_summary]
        if example_summary:
            details.append(example_summary)
        details.append(response_hint)
        description = " | ".join([description, *details])

        if len(description) > MAX_DESCRIPTION_LEN and example_summary:
            description = " | ".join(
                [description.split(" | ")[0], params_summary, response_hint]
            )
        if len(description) > MAX_DESCRIPTION_LEN and "(keys:" in response_hint:
            response_hint = _format_response_hint(response_info, include_keys=False)
            description = " | ".join(
                [description.split(" | ")[0], params_summary, response_hint]
            )
        description = _truncate_description(description, MAX_DESCRIPTION_LEN)

        def _merge_cookie_header(
            headers: dict[str, Any], cookie_name: str, cookie_value: Any
        ) -> None:
            cookie_entry = f"{cookie_name}={cookie_value}"
            existing = headers.get("cookie")
            if existing:
                headers["cookie"] = f"{existing}; {cookie_entry}"
            else:
                headers["cookie"] = cookie_entry

        def _make_tool(
            method: str,
            path_template: str,
            require_auth: bool,
            specs: list[dict[str, Any]],
            request_body: dict[str, Any] | None,
            ext_domain: str | None = None,
        ):
            # Determine if this response should be decorated with web URLs
            should_decorate, url_type = _should_decorate_response(method, path_template)
            
            def tool(**kwargs: Any) -> Any:
                path_params = dict(kwargs.get("path_params") or {})
                query_params = dict(kwargs.get("query_params") or {})
                headers = dict(kwargs.get("headers") or {})
                json_body = kwargs.get("json_body")

                # Track which specs have body location for reconstruction
                body_fields: dict[str, Any] = {}

                for spec in specs:
                    arg_name = spec["arg_name"]
                    if arg_name not in kwargs:
                        continue
                    value = kwargs[arg_name]
                    if value is None:
                        continue
                    location = spec["location"]
                    if location == "path":
                        path_params[spec["name"]] = value
                    elif location == "query":
                        query_params[spec["name"]] = value
                    elif location == "header":
                        headers[spec["name"]] = value
                    elif location == "cookie":
                        _merge_cookie_header(headers, spec["name"], value)
                    elif location == "body":
                        # Accumulate body field values for later reconstruction
                        body_fields[spec["name"]] = value

                # Reconstruct JSON body from individual body_* parameters if any
                if body_fields:
                    json_body = body_fields

                # Legacy 'body' parameter takes precedence if provided
                if (
                    request_body
                    and "body" in kwargs
                    and kwargs["body"] is not None
                ):
                    json_body = kwargs["body"]

                missing: list[str] = []
                for spec in specs:
                    if not spec["required"]:
                        continue
                    arg_name = spec["arg_name"]
                    location = spec["location"]
                    provided = arg_name in kwargs and kwargs[arg_name] is not None
                    if not provided:
                        if location == "path":
                            provided = spec["name"] in path_params
                        elif location == "query":
                            provided = spec["name"] in query_params
                        elif location == "header":
                            provided = spec["name"] in headers
                        elif location == "cookie":
                            provided = "cookie" in headers
                        elif location == "body":
                            provided = spec["name"] in body_fields
                    if not provided:
                        missing.append(f"{location}:{spec['name']}")
                if (
                    request_body
                    and request_body.get("required")
                    and json_body is None
                ):
                    missing.append("body")
                if missing:
                    raise ValueError(
                        "Missing required parameters: " + ", ".join(missing)
                    )

                final_path = _apply_path_params(path_template, path_params)
                full_path = f"{base_path}{final_path}"
                try:
                    response = _request(
                        method,
                        full_path,
                        params=query_params,
                        json_body=json_body,
                        require_auth=require_auth,
                        extra_headers=headers,
                    )
                    # Decorate response with web URLs if applicable
                    if should_decorate and ext_domain:
                        response = _decorate_response(response, ext_domain, url_type)
                    return response
                except Exception as exc:
                    return {"error": str(exc)}

            signature_params: list[inspect.Parameter] = []
            annotations: dict[str, Any] = {"return": Any}

            for spec in specs:
                arg_name = spec["arg_name"]
                param_type = spec["py_type"]
                annotations[arg_name] = param_type
                default = inspect._empty if spec["required"] else None
                signature_params.append(
                    inspect.Parameter(
                        arg_name,
                        inspect.Parameter.KEYWORD_ONLY,
                        default=default,
                        annotation=param_type,
                    )
                )

            if request_body:
                body_type = request_body["py_type"]
                annotations["body"] = body_type
                default = (
                    inspect._empty if request_body.get("required") else None
                )
                signature_params.append(
                    inspect.Parameter(
                        "body",
                        inspect.Parameter.KEYWORD_ONLY,
                        default=default,
                        annotation=body_type,
                    )
                )

            legacy_type = dict[str, Any] | None
            for legacy_name in (
                "path_params",
                "query_params",
                "headers",
                "json_body",
            ):
                annotations[legacy_name] = legacy_type
                signature_params.append(
                    inspect.Parameter(
                        legacy_name,
                        inspect.Parameter.KEYWORD_ONLY,
                        default=None,
                        annotation=legacy_type,
                    )
                )

            tool.__signature__ = inspect.Signature(signature_params)
            tool.__annotations__ = annotations
            return tool

        tool_func = _make_tool(method, path, requires_auth, param_specs, body_spec, external_domain)
        mcp.tool(name=tool_name, description=description)(tool_func)
