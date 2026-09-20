from unittest.mock import patch

from mcp4immich.tooling import download_asset


def test_download_asset_default_base64() -> None:
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="inline_base64",
    ), patch(
        "mcp4immich.tooling._request_bytes",
        return_value=(
            b"abc",
            {
                "content-type": "image/jpeg",
                "content-disposition": 'attachment; filename="image.jpg"',
            },
        ),
    ):
        result = download_asset("asset-1")

    assert result["asset_id"] == "asset-1"
    assert result["output"] == "base64"
    assert result["content_type"] == "image/jpeg"
    assert result["size_bytes"] == 3
    assert result["filename"] == "image.jpg"
    assert result["data"] == "YWJj"

def test_download_asset_rejects_invalid_output() -> None:
    result = download_asset("asset-3", output="json")
    assert "error" in result
    assert "base64" in result["error"]


def test_download_asset_immich_link_delivery_mode() -> None:
    """immich_link falls back to base_url when no external domain is configured."""
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="immich_link",
    ), patch(
        "mcp4immich.tooling._request",
        side_effect=Exception("shared-link api unavailable"),
    ), patch(
        "mcp4immich.tooling.get_external_domain",
        return_value=None,
    ), patch(
        "mcp4immich.tooling._get_config",
        return_value={
            "base_url": "https://immich.example.com",
            "api_key": "test",
            "api_token": "",
        },
    ):
        result = download_asset("asset-link")

    assert result["asset_id"] == "asset-link"
    assert result["delivery_mode"] == "immich_link"
    assert result["requires_auth"] is True
    assert result["download_url"] == "https://immich.example.com/api/assets/asset-link/original"


def test_download_asset_immich_link_prefers_external_domain() -> None:
    """immich_link uses the external domain when it is configured."""
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="immich_link",
    ), patch(
        "mcp4immich.tooling._request",
        side_effect=Exception("shared-link api unavailable"),
    ), patch(
        "mcp4immich.tooling.get_external_domain",
        return_value="https://photos.mydomain.com",
    ), patch(
        "mcp4immich.tooling._get_config",
        return_value={
            "base_url": "http://immich:2283",
            "api_key": "test",
            "api_token": "",
        },
    ):
        result = download_asset("asset-ext")

    assert result["asset_id"] == "asset-ext"
    assert result["delivery_mode"] == "immich_link"
    assert result["download_url"] == "https://photos.mydomain.com/api/assets/asset-ext/original"


def test_download_asset_shared_link_mode_success() -> None:
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="shared_link",
    ), patch(
        "mcp4immich.tooling.get_external_domain",
        return_value="https://photos.mydomain.com",
    ), patch(
        "mcp4immich.tooling._request",
        return_value={
            "token": "abc-token",
            "expiresAt": "2026-02-19T13:00:00Z",
        },
    ):
        result = download_asset("asset-shared")

    assert result["asset_id"] == "asset-shared"
    assert result["delivery_mode"] == "shared_link"
    assert result["download_url"] == "https://photos.mydomain.com/share/abc-token"
    assert result["expires_in_minutes"] == 30
    assert result["tokenized"] is True
    assert result["requires_auth"] is False
    assert "data" not in result


def test_download_asset_shared_link_mode_failure() -> None:
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="shared_link",
    ), patch(
        "mcp4immich.tooling._request",
        side_effect=Exception("forbidden"),
    ):
        result = download_asset("asset-shared-fail")

    assert result["asset_id"] == "asset-shared-fail"
    assert result["delivery_mode"] == "shared_link"
    assert "error" in result


def test_download_asset_immich_link_prefers_shared_link_when_available() -> None:
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="immich_link",
    ), patch(
        "mcp4immich.tooling.get_external_domain",
        return_value="https://photos.mydomain.com",
    ), patch(
        "mcp4immich.tooling._request",
        return_value={
            "url": "https://photos.mydomain.com/share/custom-link",
            "expiresAt": "2026-02-19T13:00:00Z",
        },
    ):
        result = download_asset("asset-immich-shared")

    assert result["asset_id"] == "asset-immich-shared"
    assert result["delivery_mode"] == "shared_link"
    assert result["download_url"] == "https://photos.mydomain.com/share/custom-link"


def test_download_asset_default_delivery_mode_is_shared_link() -> None:
    with patch(
        "mcp4immich.tooling.get_download_asset_delivery_mode",
        return_value="shared_link",
    ), patch(
        "mcp4immich.tooling.get_external_domain",
        return_value="https://photos.mydomain.com",
    ), patch(
        "mcp4immich.tooling._request",
        return_value={
            "token": "default-token",
            "expiresAt": "2026-02-19T13:00:00Z",
        },
    ):
        result = download_asset("asset-default")

    assert result["delivery_mode"] == "shared_link"
    assert result["download_url"] == "https://photos.mydomain.com/share/default-token"


# --- I4: downloadAsset claims read-only but writes by default -------------
#
# IMMICH_DOWNLOAD_ASSET_DELIVERY defaults to shared_link, which POSTs
# /api/shared-links and returns a 30-minute unauthenticated public URL. That
# is a write, so IMMICH_PROFILE=read_only must refuse it before any HTTP
# call is attempted, and the tool's risk classification / annotations must
# say WRITE, not READ, for every mode except inline_base64.


def test_download_asset_shared_link_refused_when_profile_disallows_write() -> None:
    with (
        patch(
            "mcp4immich.tooling.get_download_asset_delivery_mode",
            return_value="shared_link",
        ),
        patch("mcp4immich.tooling.get_profile", return_value="read_only"),
        patch("mcp4immich.tooling._request") as mock_request,
    ):
        result = download_asset("asset-ro")

    assert "error" in result
    mock_request.assert_not_called(), "must refuse before attempting the write"


def test_download_asset_immich_link_refused_when_profile_disallows_write() -> None:
    with (
        patch(
            "mcp4immich.tooling.get_download_asset_delivery_mode",
            return_value="immich_link",
        ),
        patch("mcp4immich.tooling.get_profile", return_value="read_only"),
        patch("mcp4immich.tooling._request") as mock_request,
    ):
        result = download_asset("asset-ro-2")

    assert "error" in result
    mock_request.assert_not_called()


def test_download_asset_inline_base64_still_allowed_under_read_only_profile() -> None:
    """inline_base64 is a pure GET -- the profile write gate must not touch it."""
    with (
        patch(
            "mcp4immich.tooling.get_download_asset_delivery_mode",
            return_value="inline_base64",
        ),
        patch("mcp4immich.tooling.get_profile", return_value="read_only"),
        patch(
            "mcp4immich.tooling._request_bytes",
            return_value=(b"abc", {"content-type": "image/jpeg"}),
        ),
    ):
        result = download_asset("asset-ok")

    assert "error" not in result
    assert result["delivery_mode"] == "inline_base64"


def test_download_asset_shared_link_allowed_when_profile_allows_write() -> None:
    with (
        patch(
            "mcp4immich.tooling.get_download_asset_delivery_mode",
            return_value="shared_link",
        ),
        patch("mcp4immich.tooling.get_profile", return_value="read_write"),
        patch(
            "mcp4immich.tooling._request",
            return_value={"token": "tok", "expiresAt": "2026-02-19T13:00:00Z"},
        ),
        patch(
            "mcp4immich.tooling.get_external_domain",
            return_value="https://photos.mydomain.com",
        ),
    ):
        result = download_asset("asset-rw")

    assert "error" not in result
    assert result["delivery_mode"] == "shared_link"


def test_download_asset_no_profile_configured_still_allows_write_modes() -> None:
    """No IMMICH_PROFILE set (the documented default) relies on capability
    probes elsewhere, not this gate -- profile_allows_write(None) is True."""
    with (
        patch(
            "mcp4immich.tooling.get_download_asset_delivery_mode",
            return_value="shared_link",
        ),
        patch("mcp4immich.tooling.get_profile", return_value=None),
        patch(
            "mcp4immich.tooling._request",
            return_value={"token": "tok", "expiresAt": "2026-02-19T13:00:00Z"},
        ),
        patch(
            "mcp4immich.tooling.get_external_domain",
            return_value="https://photos.mydomain.com",
        ),
    ):
        result = download_asset("asset-none")

    assert "error" not in result


def test_downloadasset_registration_classifies_as_write_by_default(monkeypatch) -> None:
    """Default delivery mode (shared_link) creates a shared link -- a write --
    so the registered tool must not carry read_only_hint=True, and TOOL_RISK
    must not record it as READ."""
    import json
    from pathlib import Path
    from unittest.mock import patch as _patch

    from mcp.server.mcpserver import MCPServer

    import mcp4immich.tooling as tooling_mod
    from mcp4immich.risk import Risk

    monkeypatch.setattr(tooling_mod, "TOOL_RISK", {})
    monkeypatch.delenv("IMMICH_DOWNLOAD_ASSET_DELIVERY", raising=False)

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    mcp = MCPServer("test", version="0.0.0")
    with (
        _patch("mcp4immich.tooling._fetch_openapi_spec", return_value=spec),
        _patch("mcp4immich.tooling._discover_write_capability", return_value={"allowed": True}),
        _patch("mcp4immich.tooling._discover_user_profile", return_value={"isAdmin": True}),
        _patch(
            "mcp4immich.tooling._discover_capabilities",
            return_value={"get_current_user": {"allowed": True}},
        ),
        _patch(
            "mcp4immich.tooling._get_config",
            return_value={"api_key": "test", "api_token": "", "base_url": "http://x"},
        ),
        _patch("mcp4immich.tooling.get_external_domain", return_value=None),
    ):
        tooling_mod._register_tools(mcp)

    assert tooling_mod.TOOL_RISK["downloadAsset"] is Risk.WRITE
    tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "downloadAsset")
    assert tool.annotations.read_only_hint is False


def test_downloadasset_registration_classifies_as_read_for_inline_base64(monkeypatch) -> None:
    import json
    from pathlib import Path
    from unittest.mock import patch as _patch

    from mcp.server.mcpserver import MCPServer

    import mcp4immich.tooling as tooling_mod
    from mcp4immich.risk import Risk

    monkeypatch.setattr(tooling_mod, "TOOL_RISK", {})
    monkeypatch.setenv("IMMICH_DOWNLOAD_ASSET_DELIVERY", "inline_base64")

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    mcp = MCPServer("test", version="0.0.0")
    with (
        _patch("mcp4immich.tooling._fetch_openapi_spec", return_value=spec),
        _patch("mcp4immich.tooling._discover_write_capability", return_value={"allowed": True}),
        _patch("mcp4immich.tooling._discover_user_profile", return_value={"isAdmin": True}),
        _patch(
            "mcp4immich.tooling._discover_capabilities",
            return_value={"get_current_user": {"allowed": True}},
        ),
        _patch(
            "mcp4immich.tooling._get_config",
            return_value={"api_key": "test", "api_token": "", "base_url": "http://x"},
        ),
        _patch("mcp4immich.tooling.get_external_domain", return_value=None),
    ):
        tooling_mod._register_tools(mcp)

    assert tooling_mod.TOOL_RISK["downloadAsset"] is Risk.READ
    tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "downloadAsset")
    assert tool.annotations.read_only_hint is True
