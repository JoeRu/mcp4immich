import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp4immich.risk import Risk, classify
from mcp4immich.tooling import annotations_for


def test_read_tools_are_marked_read_only():
    ann = annotations_for(Risk.READ, "GET")
    assert ann.read_only_hint is True
    assert ann.destructive_hint is False


def test_destructive_tools_are_marked_destructive():
    for risk in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN):
        ann = annotations_for(risk, "DELETE")
        assert ann.read_only_hint is False
        assert ann.destructive_hint is True


def test_put_is_idempotent_and_post_is_not():
    assert annotations_for(Risk.WRITE, "PUT").idempotent_hint is True
    assert annotations_for(Risk.WRITE, "POST").idempotent_hint is False


def test_open_world_hint_is_false_everywhere():
    assert annotations_for(Risk.READ, "GET").open_world_hint is False


def test_by_id_delete_is_idempotent():
    """A DELETE whose final path segment is a {param} removes one named
    resource — including admin-class ones like DELETE /admin/users/{id},
    which is by-id despite being DESTRUCTIVE_ADMIN."""
    for path in ("/albums/{id}", "/admin/users/{id}"):
        risk = classify("DELETE", path)
        assert annotations_for(risk, "DELETE", path).idempotent_hint is True


def test_collection_delete_is_not_idempotent():
    """A DELETE whose final path segment is not a {param} — a bare
    collection, or a membership list under a fixed segment name — removes an
    unbounded set and is not idempotent."""
    for path in ("/assets", "/albums/{id}/assets"):
        risk = classify("DELETE", path)
        assert annotations_for(risk, "DELETE", path).idempotent_hint is False


def test_delete_without_path_is_conservatively_not_idempotent():
    """With no path to inspect, by-id vs. collection cannot be told apart, so
    the documented conservative default is not idempotent."""
    assert annotations_for(Risk.DESTRUCTIVE, "DELETE").idempotent_hint is False


def test_every_registered_tool_carries_annotations():
    """Registers the real tool set against an in-process MCPServer, with only
    the network boundary mocked, and asserts every tool — generated and
    hand-written alike — carries a non-None ToolAnnotations. This is the
    permanent replacement for the one-off verification script used during
    development: it guards against annotations silently failing to reach a
    subset of tools, and the >200 floor keeps it from passing vacuously if
    registration were to silently no-op.
    """
    from mcp.server.mcpserver import MCPServer

    from mcp4immich.tooling import _register_tools

    spec = json.loads(
        Path("mcp4immich/data/immich-openapi-3.json").read_text()
    )

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
        mcp = MCPServer("test", version="0.0.0")
        _register_tools(mcp)
        tools = mcp._tool_manager.list_tools()

    assert len(tools) > 200
    missing = [tool.name for tool in tools if tool.annotations is None]
    assert missing == []
