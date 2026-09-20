import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from mcp_types import CallToolResult

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


from mcp4immich.policy import CONFIRMATION_REQUIRED, RiskPolicyMiddleware


class _Ctx:
    def __init__(self, method, params):
        self.method = method
        self.params = params


@pytest.mark.anyio
async def test_destructive_call_without_confirm_is_refused_and_never_dispatched():
    dispatched = []

    async def call_next(ctx):
        dispatched.append(ctx)
        return {"unexpected": True}

    mw = RiskPolicyMiddleware({"immich_deleteassets": Risk.DESTRUCTIVE_ADMIN})
    result = await mw(_Ctx("tools/call", {"name": "immich_deleteassets", "arguments": {}}), call_next)

    # The refusal is a short-circuit result the SDK passes through verbatim,
    # so it must itself validate as a `CallToolResult` (content is required) —
    # a raw dict without `content` raises `ValidationError` and the agent sees
    # a protocol error instead of the refusal's hint.
    validated = CallToolResult.model_validate(result)
    assert validated.is_error is True
    payload = result["structuredContent"]
    assert payload["error"] == CONFIRMATION_REQUIRED
    assert payload["risk"] == "destructive_admin"
    assert dispatched == [], "the handler must not run"


@pytest.mark.anyio
async def test_destructive_call_with_confirm_is_dispatched():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_deletealbum": Risk.DESTRUCTIVE})
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {"confirm": True}}),
        call_next,
    )

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_refusal_includes_what_would_be_called_and_a_preview():
    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    mw = RiskPolicyMiddleware(
        {"immich_deletealbum": Risk.DESTRUCTIVE},
        operation_by_tool={"immich_deletealbum": ("DELETE", "/albums/{id}")},
        sibling_get=lambda path, args: {"id": args["path_id"], "name": "Holiday 2024"},
    )
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {"path_id": "a-1"}}),
        call_next,
    )

    CallToolResult.model_validate(result)
    payload = result["structuredContent"]
    assert payload["would_call"] == "DELETE /albums/{id}"
    assert payload["preview"]["name"] == "Holiday 2024"


@pytest.mark.anyio
async def test_failing_preview_still_refuses():
    def boom(path, args):
        raise RuntimeError("immich unreachable")

    mw = RiskPolicyMiddleware(
        {"immich_deletealbum": Risk.DESTRUCTIVE},
        operation_by_tool={"immich_deletealbum": ("DELETE", "/albums/{id}")},
        sibling_get=boom,
    )
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {}}), lambda ctx: None
    )

    CallToolResult.model_validate(result)
    payload = result["structuredContent"]
    assert payload["error"] == CONFIRMATION_REQUIRED
    assert payload["preview"] is None


@pytest.mark.anyio
async def test_read_tools_pass_straight_through():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_getallalbums": Risk.READ})
    result = await mw(
        _Ctx("tools/call", {"name": "immich_getallalbums", "arguments": {}}), call_next
    )

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_unknown_tool_is_not_gated():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({})
    result = await mw(_Ctx("tools/call", {"name": "something_else", "arguments": {}}), call_next)

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_non_tool_calls_pass_through():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_deleteassets": Risk.DESTRUCTIVE_ADMIN})
    result = await mw(_Ctx("resources/list", {}), call_next)

    assert result == {"ok": True}


def test_admin_class_is_hidden_unless_enabled(monkeypatch):
    monkeypatch.delenv("IMMICH_ENABLE_DESTRUCTIVE", raising=False)
    from mcp4immich.config import destructive_enabled

    assert destructive_enabled() is False

    monkeypatch.setenv("IMMICH_ENABLE_DESTRUCTIVE", "true")
    assert destructive_enabled() is True


# --- Fix round 1: production-path coverage --------------------------------
#
# The tests above exercise RiskPolicyMiddleware in isolation, with hand-built
# risk/operation maps. None of them registered the real tool set and then
# drove the middleware against the module-level TOOL_RISK/TOOL_OPERATION
# dicts the way create_mcp() + _register_tools() actually do in production —
# which is exactly the gap that let the severed-dict bug (`operation_by_tool
# or {}`) and the invalid-envelope bug ship. These reconstruct that real
# sequencing.

def _register_real_tools(monkeypatch, mcp, *, destructive_enabled: bool, reset: bool = True):
    """Register the real OpenAPI tool set against `mcp`, with only the network
    boundary mocked (copied from `test_every_registered_tool_carries_annotations`).

    By default also resets the module-global TOOL_RISK/TOOL_OPERATION/
    HIDDEN_ADMIN_TOOLS state to fresh, empty objects first, so this test
    doesn't see leftovers from another test in the same session. Pass
    `reset=False` when the caller already reset them itself and is holding a
    reference (e.g. a RiskPolicyMiddleware built against the pre-registration,
    still-empty dicts) that a fresh reset here would sever.
    """
    import mcp4immich.tooling as tooling_mod

    if reset:
        monkeypatch.setattr(tooling_mod, "TOOL_RISK", {})
        monkeypatch.setattr(tooling_mod, "TOOL_OPERATION", {})
        monkeypatch.setattr(tooling_mod, "HIDDEN_ADMIN_TOOLS", [])
    if destructive_enabled:
        monkeypatch.setenv("IMMICH_ENABLE_DESTRUCTIVE", "true")
    else:
        monkeypatch.delenv("IMMICH_ENABLE_DESTRUCTIVE", raising=False)

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    with (
        patch("mcp4immich.tooling._fetch_openapi_spec", return_value=spec),
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

    return tooling_mod


@pytest.mark.anyio
async def test_registration_populates_the_middleware_shared_maps_with_a_working_preview(
    monkeypatch,
):
    """This is the test that would have caught the severed-dict bug.

    `RiskPolicyMiddleware` is constructed the way `create_mcp()` constructs
    it: against TOOL_RISK/TOOL_OPERATION *before* registration has run, i.e.
    while both are still empty (falsy) dicts -- exactly the state in which
    `operation_by_tool or {}` used to silently bind a brand-new dict instead
    of keeping the shared reference. Registration then runs, and the
    middleware must see the entries without being rebuilt.
    """
    from mcp.server.mcpserver import MCPServer

    import mcp4immich.tooling as tooling_mod
    from mcp4immich.policy import RiskPolicyMiddleware

    monkeypatch.setattr(tooling_mod, "TOOL_RISK", {})
    monkeypatch.setattr(tooling_mod, "TOOL_OPERATION", {})
    monkeypatch.setattr(tooling_mod, "HIDDEN_ADMIN_TOOLS", [])
    monkeypatch.delenv("IMMICH_ENABLE_DESTRUCTIVE", raising=False)

    # Built BEFORE registration, against the still-empty shared dicts.
    mw = RiskPolicyMiddleware(tooling_mod.TOOL_RISK, tooling_mod.TOOL_OPERATION)
    assert mw._risk_by_tool is tooling_mod.TOOL_RISK
    assert mw._operation_by_tool is tooling_mod.TOOL_OPERATION, (
        "constructor severed the shared operation map (the `or {}` bug)"
    )

    mcp = MCPServer("test", version="0.0.0")
    _register_real_tools(monkeypatch, mcp, destructive_enabled=False, reset=False)

    destructive_tools = [
        name for name, risk in mw._risk_by_tool.items() if risk is Risk.DESTRUCTIVE
    ]
    assert destructive_tools, "expected at least one DESTRUCTIVE tool to be registered"
    tool_name = destructive_tools[0]
    assert tool_name in mw._operation_by_tool, (
        "operation map is still empty after registration -- the severed-dict bug"
    )

    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    result = await mw(_Ctx("tools/call", {"name": tool_name, "arguments": {}}), call_next)

    CallToolResult.model_validate(result)
    payload = result["structuredContent"]
    assert payload["error"] == CONFIRMATION_REQUIRED
    assert payload["would_call"] is not None, "would_call is null -- the severed-dict bug"


def test_admin_tool_absent_from_registration_by_default_present_when_enabled(monkeypatch):
    """DESTRUCTIVE_ADMIN tools must not merely be gated at call time -- they
    must not be registered (visible via tools/list) at all unless
    IMMICH_ENABLE_DESTRUCTIVE is set.
    """
    from mcp.server.mcpserver import MCPServer

    mcp_disabled = MCPServer("test-disabled", version="0.0.0")
    tooling_mod = _register_real_tools(monkeypatch, mcp_disabled, destructive_enabled=False)
    disabled_names = {tool.name for tool in mcp_disabled._tool_manager.list_tools()}

    assert tooling_mod.HIDDEN_ADMIN_TOOLS, "expected at least one admin tool hidden by default"
    admin_tool_name = tooling_mod.HIDDEN_ADMIN_TOOLS[0]
    assert admin_tool_name not in disabled_names

    mcp_enabled = MCPServer("test-enabled", version="0.0.0")
    _register_real_tools(monkeypatch, mcp_enabled, destructive_enabled=True)
    enabled_names = {tool.name for tool in mcp_enabled._tool_manager.list_tools()}

    assert admin_tool_name in enabled_names


def test_report_does_not_list_hidden_admin_tools_as_allowed(monkeypatch):
    """`tool_access_report`'s allowed_tools must not contain a name that
    hidden_destructive_admin also lists -- otherwise an agent reading only
    allowed_tools would try to call a tool that was never registered.
    """
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("test", version="0.0.0")
    tooling_mod = _register_real_tools(monkeypatch, mcp, destructive_enabled=False)

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    with (
        patch("mcp4immich.tooling._fetch_openapi_spec", return_value=spec),
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
        report = tooling_mod.tool_access_report()

    assert tooling_mod.HIDDEN_ADMIN_TOOLS
    for name in tooling_mod.HIDDEN_ADMIN_TOOLS:
        assert name not in report["allowed_tools"], f"{name} is hidden but still listed as allowed"
    assert {item["tool"] for item in report["hidden_destructive_admin"]} == set(
        tooling_mod.HIDDEN_ADMIN_TOOLS
    )


def test_hand_written_tools_are_recorded_as_read_risk(monkeypatch):
    """The six hand-written tools must appear in TOOL_RISK too, so
    tool_access_report's `risk` map doesn't silently omit them."""
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("test", version="0.0.0")
    tooling_mod = _register_real_tools(monkeypatch, mcp, destructive_enabled=False)

    for name in (
        "ping_server",
        "get_server_version",
        "tool_access_report",
        "write_capability_report",
        "downloadAsset",
        "get_current_user",
    ):
        assert tooling_mod.TOOL_RISK.get(name) is Risk.READ, name


class _ReadOnlyMapping(Mapping):
    """A Mapping that is deliberately not a dict, to prove the middleware's
    isinstance checks aren't dict-only (ctx.params is typed
    Mapping[str, Any] | None, not dict)."""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


@pytest.mark.anyio
async def test_non_dict_mapping_params_still_gate():
    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    mw = RiskPolicyMiddleware({"immich_deleteassets": Risk.DESTRUCTIVE_ADMIN})
    params = _ReadOnlyMapping(
        {"name": "immich_deleteassets", "arguments": _ReadOnlyMapping({})}
    )
    result = await mw(_Ctx("tools/call", params), call_next)

    CallToolResult.model_validate(result)
    assert result["structuredContent"]["error"] == CONFIRMATION_REQUIRED


@pytest.mark.anyio
async def test_preview_runs_off_the_event_loop_thread():
    """A synchronous, blocking sibling_get must not stall the server's read
    loop. Proved by execution: a concurrent coroutine keeps making progress
    (ticking) while a slow, blocking preview call is in flight.
    """
    import time

    import anyio

    def slow_sibling_get(path, args):
        time.sleep(0.2)
        return {"id": "x"}

    mw = RiskPolicyMiddleware(
        {"immich_deletealbum": Risk.DESTRUCTIVE},
        operation_by_tool={"immich_deletealbum": ("DELETE", "/albums/{id}")},
        sibling_get=slow_sibling_get,
    )

    ticks: list[int] = []

    async def ticker():
        for _ in range(4):
            await anyio.sleep(0.05)
            ticks.append(1)

    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    result_box: dict[str, Any] = {}

    async def do_preview():
        result_box["result"] = await mw(
            _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {}}),
            call_next,
        )

    async with anyio.create_task_group() as tg:
        tg.start_soon(ticker)
        tg.start_soon(do_preview)

    payload = result_box["result"]["structuredContent"]
    assert payload["preview"] == {"id": "x"}
    assert len(ticks) >= 3, "the event loop was blocked while the preview ran"


# --- Elicitation wiring (Task 8) -------------------------------------------
#
# `ask_confirmation` itself is unit-tested in isolation against a duck-typed
# `_Elicitor` in tests/test_confirm.py. These prove the *wiring*: that the
# middleware's real `ctx` (a `ServerRequestContext`-shaped object here, with
# a `.session`) actually reaches an elicitation-capable client through
# `_SessionElicitor`, using the SDK's own `mcp_types.ClientCapabilities` and
# `mcp.server.elicitation.elicit_with_validation` -- not a mock of this
# module's own adapter code.

from mcp_types import ClientCapabilities, ElicitationCapability

from mcp4immich.confirm import ConfirmDestructive


class _FakeSession:
    """Stands in for `ServerSession`: only what `_SessionElicitor` touches."""

    def __init__(self, *, elicitation_supported: bool, action: str, confirm: bool = True):
        self.client_capabilities = ClientCapabilities(
            elicitation=ElicitationCapability() if elicitation_supported else None
        )
        self._action = action
        self._confirm = confirm

    async def elicit_form(self, message, requested_schema, related_request_id=None):
        from mcp_types import ElicitResult

        content = {"confirm": self._confirm} if self._action == "accept" else None
        return ElicitResult(action=self._action, content=content)


class _SessionCtx:
    def __init__(self, method, params, session):
        self.method = method
        self.params = params
        self.session = session
        self.request_id = "req-1"


@pytest.mark.anyio
async def test_destructive_call_confirmed_via_accepted_elicitation_is_dispatched():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_deletealbum": Risk.DESTRUCTIVE})
    ctx = _SessionCtx(
        "tools/call",
        {"name": "immich_deletealbum", "arguments": {}},
        _FakeSession(elicitation_supported=True, action="accept"),
    )

    result = await mw(ctx, call_next)

    assert result == {"ok": True}


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["decline", "cancel"])
async def test_destructive_call_declined_or_cancelled_via_elicitation_is_refused(action):
    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    mw = RiskPolicyMiddleware({"immich_deletealbum": Risk.DESTRUCTIVE})
    ctx = _SessionCtx(
        "tools/call",
        {"name": "immich_deletealbum", "arguments": {}},
        _FakeSession(elicitation_supported=True, action=action),
    )

    result = await mw(ctx, call_next)

    CallToolResult.model_validate(result)
    assert result["structuredContent"]["error"] == CONFIRMATION_REQUIRED


@pytest.mark.anyio
async def test_destructive_call_with_no_capability_is_refused_without_asking():
    asked = []

    class _WatchedSession(_FakeSession):
        async def elicit_form(self, *args, **kwargs):
            asked.append(True)
            return await super().elicit_form(*args, **kwargs)

    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    mw = RiskPolicyMiddleware({"immich_deletealbum": Risk.DESTRUCTIVE})
    ctx = _SessionCtx(
        "tools/call",
        {"name": "immich_deletealbum", "arguments": {}},
        _WatchedSession(elicitation_supported=False, action="accept"),
    )

    result = await mw(ctx, call_next)

    CallToolResult.model_validate(result)
    assert result["structuredContent"]["error"] == CONFIRMATION_REQUIRED
    assert asked == [], "a client without the capability must not be asked at all"


@pytest.mark.anyio
async def test_no_session_context_refuses_exactly_like_before_this_task():
    """`_Ctx` (used throughout this file) has no `.session` at all -- the
    shape every pre-Task-8 middleware test passes. Confirms the elicitation
    path degrades to exactly the old refusal, not an exception.
    """

    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    mw = RiskPolicyMiddleware({"immich_deletealbum": Risk.DESTRUCTIVE})
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {}}), call_next
    )

    CallToolResult.model_validate(result)
    assert result["structuredContent"]["error"] == CONFIRMATION_REQUIRED
