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
