"""Tests for mcp4immich/mcp_app.py"""
import os
from unittest.mock import patch

import pytest


def test_resolve_external_domain_success():
    """Test _resolve_external_domain with successful API response."""
    from mcp4immich.mcp_app import _resolve_external_domain
    
    mock_response = {"externalDomain": "immich.example.com"}
    
    # Patch _request at the source where it's imported from
    with patch("mcp4immich.http_client._request", return_value=mock_response):
        domain = _resolve_external_domain()
        assert domain == "immich.example.com"


def test_resolve_external_domain_alternative_field():
    """Test _resolve_external_domain with alternative field name."""
    from mcp4immich.mcp_app import _resolve_external_domain
    
    mock_response = {"external_domain": "immich.example.com"}
    
    # Patch _request at the source where it's imported from
    with patch("mcp4immich.http_client._request", return_value=mock_response):
        domain = _resolve_external_domain()
        assert domain == "immich.example.com"


def test_resolve_external_domain_empty():
    """Test _resolve_external_domain with empty externalDomain falls back to base URL."""
    from mcp4immich.mcp_app import _resolve_external_domain
    
    mock_response = {"externalDomain": ""}
    
    # When API returns empty domain, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("mcp4immich.http_client._request", return_value=mock_response):
        with patch("mcp4immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None


def test_resolve_external_domain_missing():
    """Test _resolve_external_domain when field is missing falls back to base URL."""
    from mcp4immich.mcp_app import _resolve_external_domain
    
    mock_response = {"someOtherField": "value"}
    
    # When API response doesn't have externalDomain, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("mcp4immich.http_client._request", return_value=mock_response):
        with patch("mcp4immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None


def test_resolve_external_domain_request_error():
    """Test _resolve_external_domain when _request raises exception falls back to base URL."""
    from mcp4immich.mcp_app import _resolve_external_domain
    from mcp4immich.http_client import ImmichAPIError
    
    # When _request fails, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("mcp4immich.http_client._request", side_effect=ImmichAPIError("401", "Unauthorized")):
        with patch("mcp4immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None

def test_resolve_external_domain_non_dict_response():
    """Test _resolve_external_domain when response is not a dict falls back to base URL."""
    from mcp4immich.mcp_app import _resolve_external_domain
    
    # When _request returns non-dict, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("mcp4immich.http_client._request", return_value="not a dict"):
        with patch("mcp4immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None


def test_create_mcp_returns_mcpserver_with_project_version():
    from mcp.server.mcpserver import MCPServer
    from mcp4immich.mcp_app import create_mcp
    from importlib.metadata import version

    mcp = create_mcp()

    assert isinstance(mcp, MCPServer)
    assert mcp.version == version("mcp4immich")


def test_run_validates_transport():
    """Test run() validates MCP_TRANSPORT."""
    from mcp4immich.mcp_app import run
    import os
    
    os.environ["MCP_TRANSPORT"] = "invalid_transport"
    
    try:
        # Mock create_mcp and all its dependencies
        with patch("mcp4immich.mcp_app.create_mcp") as mock_create:
            with patch("mcp4immich.mcp_app.register_prompts_and_resources"):
                with patch("mcp4immich.mcp_app._register_tools"):
                    mock_mcp = mock_create.return_value
                    with patch.object(mock_mcp, "run"):
                        try:
                            run()
                            assert False, "Should have raised ValueError"
                        except ValueError as e:
                            assert "MCP_TRANSPORT" in str(e)
    finally:
        os.environ.pop("MCP_TRANSPORT", None)


_TRANSPORT_ENV_VARS = ("MCP_TRANSPORT", "MCP_HOST", "MCP_PORT", "MCP_MOUNT_PATH")


def _run_and_capture_mcp_run_call(env: dict[str, str]):
    """Call run() with the given env vars set, mocking out server construction,
    and return the mock MCPServer's `run(...)` call (a unittest.mock.call)."""
    from mcp4immich.mcp_app import run

    previous = {key: os.environ.get(key) for key in _TRANSPORT_ENV_VARS}
    for key in _TRANSPORT_ENV_VARS:
        os.environ.pop(key, None)
    os.environ.update(env)
    try:
        with patch("mcp4immich.mcp_app.create_mcp") as mock_create:
            with patch("mcp4immich.mcp_app.register_prompts_and_resources"):
                with patch("mcp4immich.mcp_app._register_tools"):
                    mock_mcp = mock_create.return_value
                    run()
                    return mock_mcp.run.call_args
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_run_stdio_dispatches_with_no_host_port_or_mount_path():
    """stdio has no network binding: host/port/mount_path must not be passed,
    even when the corresponding env vars are set."""
    call = _run_and_capture_mcp_run_call(
        {
            "MCP_TRANSPORT": "stdio",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": "9000",
            "MCP_MOUNT_PATH": "/custom",
        }
    )

    assert call.kwargs.get("transport") == "stdio"
    assert "host" not in call.kwargs
    assert "port" not in call.kwargs
    assert "sse_path" not in call.kwargs
    assert "streamable_http_path" not in call.kwargs


def test_run_sse_dispatches_with_host_port_and_sse_path():
    """sse must carry MCP_HOST/MCP_PORT as host/port, and MCP_MOUNT_PATH as
    sse_path (mcp 2.x's run() has no `mount_path` kwarg at all)."""
    call = _run_and_capture_mcp_run_call(
        {
            "MCP_TRANSPORT": "sse",
            "MCP_HOST": "10.0.0.5",
            "MCP_PORT": "9100",
            "MCP_MOUNT_PATH": "/mcp-sse",
        }
    )

    assert call.kwargs.get("transport") == "sse"
    assert call.kwargs["host"] == "10.0.0.5"
    assert call.kwargs["port"] == 9100
    assert call.kwargs["sse_path"] == "/mcp-sse"
    assert "streamable_http_path" not in call.kwargs
    assert "mount_path" not in call.kwargs


def test_run_sse_without_mount_path_omits_sse_path():
    """When MCP_MOUNT_PATH is unset, no path kwarg should be synthesized."""
    call = _run_and_capture_mcp_run_call(
        {
            "MCP_TRANSPORT": "sse",
            "MCP_HOST": "10.0.0.5",
            "MCP_PORT": "9100",
        }
    )

    assert call.kwargs.get("transport") == "sse"
    assert call.kwargs["host"] == "10.0.0.5"
    assert call.kwargs["port"] == 9100
    assert "sse_path" not in call.kwargs
    assert "streamable_http_path" not in call.kwargs


def test_run_streamable_http_dispatches_with_host_port_and_streamable_http_path():
    """streamable-http must carry MCP_HOST/MCP_PORT as host/port, and
    MCP_MOUNT_PATH as streamable_http_path."""
    call = _run_and_capture_mcp_run_call(
        {
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": "10.0.0.6",
            "MCP_PORT": "9200",
            "MCP_MOUNT_PATH": "/mcp-http",
        }
    )

    assert call.kwargs.get("transport") == "streamable-http"
    assert call.kwargs["host"] == "10.0.0.6"
    assert call.kwargs["port"] == 9200
    assert call.kwargs["streamable_http_path"] == "/mcp-http"
    assert "sse_path" not in call.kwargs
    assert "mount_path" not in call.kwargs


def test_run_invalid_transport_raises_before_any_dispatch():
    """An invalid MCP_TRANSPORT must raise ValueError, and must never reach
    mcp.run(...) at all (no destructive/side-effecting dispatch on bad input)."""
    from mcp4immich.mcp_app import run

    previous = {key: os.environ.get(key) for key in _TRANSPORT_ENV_VARS}
    for key in _TRANSPORT_ENV_VARS:
        os.environ.pop(key, None)
    os.environ["MCP_TRANSPORT"] = "invalid_transport"
    try:
        with patch("mcp4immich.mcp_app.create_mcp") as mock_create:
            with patch("mcp4immich.mcp_app.register_prompts_and_resources"):
                with patch("mcp4immich.mcp_app._register_tools"):
                    mock_mcp = mock_create.return_value
                    with pytest.raises(ValueError, match="MCP_TRANSPORT"):
                        run()
                    mock_mcp.run.assert_not_called()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# --- I5: /healthz must not block the event loop, and must never 500 -------
#
# `_probe` is synchronous httpx with a 10s timeout, awaited inline in the
# `/healthz` handler -- the only blocking call left on the loop. An
# unreachable Immich stalls MCP request handling on every probe, and
# `_probe` only catches httpx.RequestError/ValueError, so anything else
# (e.g. a bug in _get_config, or httpx raising something else entirely)
# turns the route into a 500 instead of a normal
# `{"immich_reachable": false}` response.


def _get_healthz_endpoint(mcp):
    for route in mcp._custom_starlette_routes:
        if route.path == "/healthz":
            return route.endpoint
    raise AssertionError("no /healthz route registered")


@pytest.mark.anyio
async def test_healthz_does_not_block_the_event_loop():
    """A slow, blocking `_probe` must not stall concurrent request handling.

    A weaker version of this test (just counting ticks by the end) passes
    even against the broken, blocking implementation, because the task
    group waits for every task to finish either way -- it doesn't prove
    the ticks landed *during* the probe. This instead records wall-clock
    timestamps and asserts at least one tick timestamp falls strictly
    inside the probe's [start, end) window, i.e. the ticker genuinely made
    progress while the blocking call was in flight.
    """
    import time

    import anyio

    from mcp4immich.mcp_app import create_mcp

    mcp = create_mcp()
    healthz = _get_healthz_endpoint(mcp)

    window: dict[str, float] = {}

    def slow_probe(*args, **kwargs):
        window["start"] = time.monotonic()
        time.sleep(0.2)
        window["end"] = time.monotonic()
        return {"ok": True}

    tick_times: list[float] = []

    async def ticker():
        for _ in range(4):
            await anyio.sleep(0.05)
            tick_times.append(time.monotonic())

    result_box: dict = {}

    async def call_healthz():
        with patch("mcp4immich.http_client._probe", side_effect=slow_probe):
            result_box["response"] = await healthz(None)

    async with anyio.create_task_group() as tg:
        tg.start_soon(ticker)
        tg.start_soon(call_healthz)

    overlapping = [t for t in tick_times if window["start"] < t < window["end"]]
    assert overlapping, (
        "no ticker tick landed while /healthz's probe was in flight -- "
        "the event loop was blocked"
    )

    import json as _json

    body = _json.loads(result_box["response"].body)
    assert body["immich_reachable"] is True


@pytest.mark.anyio
async def test_healthz_reports_unreachable_without_500_on_request_error():
    import httpx

    from mcp4immich.mcp_app import create_mcp

    mcp = create_mcp()
    healthz = _get_healthz_endpoint(mcp)

    with patch(
        "mcp4immich.http_client._probe",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        response = await healthz(None)

    assert response.status_code == 200
    import json as _json

    body = _json.loads(response.body)
    assert body["immich_reachable"] is False


@pytest.mark.anyio
async def test_healthz_reports_unreachable_without_500_on_unexpected_exception():
    """`_probe` itself already catches httpx.RequestError/ValueError, but the
    /healthz route must not 500 even if something else escapes it (a
    programming error in config resolution, e.g.) -- the route's whole job
    is to answer honestly, not to propagate."""
    from mcp4immich.mcp_app import create_mcp

    mcp = create_mcp()
    healthz = _get_healthz_endpoint(mcp)

    with patch(
        "mcp4immich.http_client._probe",
        side_effect=RuntimeError("unexpected"),
    ):
        response = await healthz(None)

    assert response.status_code == 200
    import json as _json

    body = _json.loads(response.body)
    assert body["immich_reachable"] is False


# --- I7: import-time version("mcp4immich") can raise -----------------------
#
# `PackageNotFoundError` is raised when the package is importable but not
# installed (no dist-info to read) -- exactly the README's Claude Desktop
# example, which runs `python .../main.py` against a checkout rather than an
# installed package.


def test_module_import_survives_missing_package_metadata():
    """Reloading mcp4immich.mcp_app with `version()` raising
    PackageNotFoundError must not raise -- it must fall back to a placeholder
    string instead of crashing the whole import (and therefore the server)
    at module load time."""
    import importlib

    from importlib.metadata import PackageNotFoundError

    import mcp4immich.mcp_app as mcp_app_module

    original_version = mcp_app_module.__version__
    try:
        with patch(
            "importlib.metadata.version",
            side_effect=PackageNotFoundError("mcp4immich"),
        ):
            importlib.reload(mcp_app_module)

        assert mcp_app_module.__version__
        assert isinstance(mcp_app_module.__version__, str)
    finally:
        # Restore the real version so later tests in this session (and
        # anything relying on the un-reloaded module state) see it again.
        importlib.reload(mcp_app_module)
        assert mcp_app_module.__version__ == original_version
