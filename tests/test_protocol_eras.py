import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp4immich.mcp_app import create_mcp


@pytest.mark.anyio
async def test_server_reports_project_version_not_sdk_version():
    from importlib.metadata import version

    mcp = create_mcp()

    assert mcp.version == version("mcp4immich")
    assert not mcp.version.startswith("2."), "that would be the SDK's version"


def _register_with_mocked_openapi(mcp) -> None:
    """Register the real tool set against the vendored spec, network mocked out.

    These tests exercise protocol negotiation, not the OpenAPI resolution
    path, so the spec fetch and capability probes are patched the same way as
    test_policy.py's test_every_registered_tool_carries_annotations — without
    this, `_register_tools` reaches out to a live Immich (`_fetch_openapi_spec`
    calls `_require_server_health()` first), which is not available in CI.
    """
    from mcp4immich.tooling import _register_tools

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    with (
        patch("mcp4immich.tooling._fetch_openapi_spec", return_value=spec),
        patch(
            "mcp4immich.tooling._discover_write_capability",
            return_value={"allowed": True},
        ),
        patch(
            "mcp4immich.tooling._discover_user_profile",
            return_value={"isAdmin": True},
        ),
        patch(
            "mcp4immich.tooling._discover_capabilities",
            return_value={"get_current_user": {"allowed": True}},
        ),
        patch(
            "mcp4immich.tooling._get_config",
            return_value={"api_key": "test", "api_token": "", "base_url": "http://x"},
        ),
        patch("mcp4immich.tooling.get_external_domain", return_value=None),
    ):
        _register_tools(mcp)


@pytest.mark.anyio
async def test_serves_both_protocol_eras():
    """2.x serves the current revision and pre-2026 handshake clients from one server.

    The brief's original draft imported `mcp.client.Client` and called it with
    `protocol_version=...`. Confirmed against the installed SDK (mcp==2.2.0,
    per Step 2 of this task): `Client` takes `mode=`, not `protocol_version=`.
    `mode` accepts `'auto'`, `'legacy'`, or a string from
    `mcp_types.version.MODERN_PROTOCOL_VERSIONS` — which in this SDK is only
    `('2026-07-28',)`. A handshake-era version string such as `'2025-06-18'`
    (one of `HANDSHAKE_PROTOCOL_VERSIONS`) is *not* accepted directly there;
    `Client.__post_init__` raises `ValueError` naming exactly this case and
    pointing at `mode='legacy'` instead. `'legacy'` forces the pre-2026
    JSON-RPC initialize handshake outright (byte-identical pre-2026 behavior),
    which negotiates `LATEST_HANDSHAKE_VERSION` — `'2025-11-25'` in this SDK —
    the same handshake path every 2025-era client speaks. So the two modes
    below are the real two eras this server must serve: modern discovery-based
    negotiation, and the legacy initialize handshake.
    """
    from mcp.client import Client

    mcp = create_mcp()
    _register_with_mocked_openapi(mcp)

    for mode in ("2026-07-28", "legacy"):
        async with Client(mcp, mode=mode) as client:
            result = await client.list_tools()
            assert result.tools, f"no tools served for mode={mode}"


@pytest.mark.anyio
async def test_tools_list_is_deterministically_ordered():
    """The current spec asks for stable ordering so clients can cache prompts."""
    mcp = create_mcp()
    _register_with_mocked_openapi(mcp)

    first = [t.name for t in await mcp.list_tools()]
    second = [t.name for t in await mcp.list_tools()]

    assert first == second
