from functools import lru_cache

from .config import get_usage_guide_path


@lru_cache
def _load_usage_guide() -> str:
    try:
        with open(get_usage_guide_path(), "r", encoding="utf-8") as guide_file:
            return guide_file.read()
    except OSError as exc:
        return f"Usage guide not available: {exc}"


def register_prompts_and_resources(mcp) -> None:
    @mcp.resource("docs://usage-guide")
    def usage_guide() -> str:
        """Return the MCP usage guide markdown."""
        return _load_usage_guide()

    @mcp.prompt(title="Immich: Get image", description="Retrieve a single image or video asset by its ID.")
    def prompt_get_image(asset_id: str) -> str:
        return (
            "Use tool `immich_getassetinfo`. "
            "Call it with `path_id` set to the asset id. "
            "Example args: {\"path_id\": \"<asset-id>\"}. "
            f"Asset id: {asset_id}."
        )

    @mcp.prompt(title="Immich: Download asset", description="Download or get a link to an asset via MCP server credentials.")
    def prompt_download_asset(asset_id: str) -> str:
        return (
            "Use the tool named downloadAsset. "
            "Pass asset_id to get a download link or inline payload. "
            "By default, delivery mode is shared_link: the server creates a short-lived "
            "tokenized shared link (30 minutes) and returns link metadata without payload bytes. "
            "Set IMMICH_DOWNLOAD_ASSET_DELIVERY=inline_base64 on the server side to get inline base64 data instead. "
            "Example args: {\"asset_id\": \"<asset-id>\"}. "
            "This is useful when the MCP client does not have direct access to the Immich API key. "
            f"Asset id: {asset_id}."
        )

    @mcp.prompt(title="Immich: Find person", description="Search for a person by name using people or face endpoints.")
    def prompt_find_person(person_name: str) -> str:
        return (
            "Use `immich_getallpeople` to list people or `immich_searchperson` for direct search when available. "
            "Prefer explicit args over schema discovery. "
            "Example list args: {\"query_withHidden\": false}. "
            "Example search args: {\"query_name\": \"Ada\"}. "
            f"Target name: {person_name}."
        )

    @mcp.prompt(title="Immich: Find location", description="Search for assets or places by location name.")
    def prompt_find_location(location_name: str) -> str:
        return (
            "Use `immich_getmapmarkers` for map/location discovery and `immich_searchassets` for place-filtered assets. "
            "Example map args: {\"query_fileCreatedAfter\": \"2020-01-01T00:00:00.000Z\"}. "
            "Example asset search args: {\"body_query\": \"city skyline\"}. "
            f"Target location: {location_name}."
        )

    @mcp.prompt(title="Immich: Newest photo", description="Fetch the most recent photos sorted by date.")
    def prompt_newest_photo(limit: int = 1) -> str:
        return (
            "Use `immich_searchassets` for newest-first retrieval. "
            "Example args: {\"body_size\": 1, \"body_order\": \"desc\"}. "
            "Alternative: `immich_getallassets` with descending sort query fields when supported. "
            f"Limit: {limit}."
        )

    @mcp.prompt(title="Immich: Upload photo", description="Upload a photo or video file to the Immich library.")
    def prompt_upload_photo(filename: str) -> str:
        return (
            "Use `immich_uploadasset` when available; otherwise use the upload tool matching POST /api/assets. "
            "Send required metadata in body fields according to schema. "
            "Example args: {\"body_deviceAssetId\": \"<uuid>\", \"body_deviceId\": \"camera-1\", \"body_fileCreatedAt\": \"2026-01-01T10:00:00.000Z\"}. "
            f"Filename: {filename}."
        )

    @mcp.prompt(title="Immich: Share album", description="Share an existing album with other users or via link.")
    def prompt_share_album(album_id: str) -> str:
        return (
            "Use `immich_createsharedlink` to create a shared link for an album. "
            "Pass the album ID in body_assetIds or use the appropriate body fields. "
            "Example args: {\"body_type\": \"ALBUM\", \"body_albumId\": \"<album-id>\", \"body_allowDownload\": true}. "
            f"Album id: {album_id}."
        )

    @mcp.prompt(title="Immich: Search assets", description="Search assets using metadata filters and text queries.")
    def prompt_search_assets(query: str) -> str:
        return (
            "Use tool `immich_searchassets`. "
            "Pass query/body fields directly without extra tool discovery. "
            "Example args: {\"body_query\": \"mountain\", \"body_size\": 20, \"body_order\": \"desc\"}. "
            f"Search query: {query}."
        )

    @mcp.prompt(title="Immich: Smart search", description="Run a CLIP-based smart search using natural language queries.")
    def prompt_search_smart(query: str) -> str:
        return (
            "Use tool `immich_searchsmart`. "
            "Provide natural-language query using explicit body fields. "
            "Example args: {\"body_query\": \"golden retriever on beach\", \"body_size\": 25}. "
            f"Smart search query: {query}."
        )

    @mcp.prompt(title="Immich: Find images with multiple people", description="Search for images where two or more specific people appear together.")
    def prompt_search_multiple_people(person_ids: str) -> str:
        return (
            "Find images with multiple specific people using immich_searchassets. "
            "IMPORTANT: To find images with multiple people together (AND logic), "
            "pass body_personIds as an ARRAY: [\"person-id-1\", \"person-id-2\", ...]. "
            "This searches for images where ALL specified persons appear. "
            "For newest images first, set body_order to \"desc\". "
            "For OR logic (any person), you must make separate searches and merge results. "
            f"Person IDs (comma-separated): {person_ids}."
        )
