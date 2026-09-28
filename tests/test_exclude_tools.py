"""MCP_EXCLUDE_TOOLS hides named OpenAPI tools, and says so."""
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.server.mcpserver import MCPServer

import mcp4immich.tooling as tooling_mod
from mcp4immich.config import get_excluded_tools

SPEC = json.loads(
    (Path(__file__).resolve().parents[1] / "mcp4immich" / "data" / "immich-openapi-3.json").read_text()
)


@pytest.fixture(autouse=True)
def _fresh_globals(monkeypatch):
    monkeypatch.setattr(tooling_mod, "TOOL_RISK", {})
    monkeypatch.setattr(tooling_mod, "TOOL_OPERATION", {})
    monkeypatch.setattr(tooling_mod, "HIDDEN_ADMIN_TOOLS", [])
    monkeypatch.setattr(tooling_mod, "EXCLUDED_TOOLS", [])


def _register(monkeypatch, excluded: str | None) -> MCPServer:
    if excluded is None:
        monkeypatch.delenv("MCP_EXCLUDE_TOOLS", raising=False)
    else:
        monkeypatch.setenv("MCP_EXCLUDE_TOOLS", excluded)
    mcp = MCPServer("test", version="0.0.0")
    with (
        patch("mcp4immich.tooling._fetch_openapi_spec", return_value=SPEC),
        patch("mcp4immich.tooling._discover_write_capability", return_value={"allowed": True}),
        patch("mcp4immich.tooling._discover_user_profile", return_value={"isAdmin": True}),
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
        tooling_mod._register_tools(mcp)
    return mcp


def _names(mcp) -> set[str]:
    return {t.name for t in mcp._tool_manager.list_tools()}


def test_get_excluded_tools_parses_and_trims(monkeypatch):
    monkeypatch.setenv("MCP_EXCLUDE_TOOLS", " a, b ,,c ")
    assert get_excluded_tools() == frozenset({"a", "b", "c"})


def test_get_excluded_tools_empty_by_default(monkeypatch):
    monkeypatch.delenv("MCP_EXCLUDE_TOOLS", raising=False)
    assert get_excluded_tools() == frozenset()


def test_no_exclusion_registers_shared_link_tools(monkeypatch):
    names = _names(_register(monkeypatch, None))
    assert "immich_createsharedlink" in names
    assert "immich_updatesharedlink" in names


def test_excluded_tools_are_not_registered(monkeypatch):
    names = _names(
        _register(monkeypatch, "immich_createsharedlink,immich_updatesharedlink")
    )
    assert "immich_createsharedlink" not in names
    assert "immich_updatesharedlink" not in names
    assert "downloadAsset" in names  # hand-written tools are out of scope
    assert "immich_getallsharedlinks" in names
    assert "immich_createsharedlink" not in tooling_mod.TOOL_RISK
    assert sorted(tooling_mod.EXCLUDED_TOOLS) == [
        "immich_createsharedlink",
        "immich_updatesharedlink",
    ]


def test_exclude_tools_warns_on_unknown_name(monkeypatch, caplog):
    # Review Focus 3: a typo must be visible, not silently expose the real tool.
    with caplog.at_level(logging.WARNING, logger="mcp4immich.tooling"):
        _register(monkeypatch, "immich_createsharedlnk")
    assert "immich_createsharedlnk" in caplog.text
    assert "unknown" in caplog.text.lower()


def test_exclude_tools_warns_on_hand_written_tool_name(monkeypatch, caplog):
    # Review Focus (c): downloadAsset is hand-written, not an OpenAPI tool,
    # so it can never be excluded. The warning must say so rather than
    # calling a real (if non-excludable) tool name "unknown".
    with caplog.at_level(logging.WARNING, logger="mcp4immich.tooling"):
        mcp = _register(monkeypatch, "downloadAsset")
    assert "downloadAsset" in caplog.text
    assert "unknown" in caplog.text.lower()
    assert "non-excludable" in caplog.text.lower()
    assert "downloadAsset" in _names(mcp)


def test_tool_access_report_lists_and_omits_excluded(monkeypatch):
    _register(monkeypatch, "immich_createsharedlink")
    with (
        patch("mcp4immich.tooling._discover_capabilities", return_value={}),
        patch(
            "mcp4immich.tooling._get_config",
            return_value={"api_key": "test", "api_token": "", "base_url": "http://x"},
        ),
        patch(
            "mcp4immich.tooling._openapi_tool_access",
            return_value={"allowed_tools": ["immich_createsharedlink", "immich_getallsharedlinks"], "blocked_tools": []},
        ),
    ):
        report = tooling_mod.tool_access_report()
    assert report["excluded_tools"] == ["immich_createsharedlink"]
    assert "immich_createsharedlink" not in report["allowed_tools"]
    assert "immich_getallsharedlinks" in report["allowed_tools"]
