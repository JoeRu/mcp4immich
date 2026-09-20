"""Server middleware enforcing the destructive-operation policy.

MCP tool annotations are advisory: the specification tells clients to treat
them as untrusted, and proxies strip them. This middleware is the enforcement
point — it sees every `tools/call` before the handler runs.

The binding rule: no destructive call may reach Immich without
``confirm=true`` in its arguments. A refusal never dispatches the handler, so
it can never perform a mutating HTTP call. The refusal's preview is
best-effort only: it may issue a single GET to show what would be deleted,
never a mutation, and a failed preview must never block the refusal itself.
"""

import json
import logging
from collections.abc import Mapping
from typing import Any

import anyio

from .risk import Risk

logger = logging.getLogger(__name__)

CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"

GATED = (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN)


class RiskPolicyMiddleware:
    """Refuse destructive tool calls that are not explicitly confirmed."""

    def __init__(
        self,
        risk_by_tool: dict[str, Risk],
        operation_by_tool: dict[str, tuple[str, str]] | None = None,
        sibling_get: Any = None,
    ):
        self._risk_by_tool = risk_by_tool
        # NOTE: `operation_by_tool or {}` would silently bind a *new* dict
        # whenever the caller's map is still empty (an empty dict is falsy) —
        # exactly the state TOOL_OPERATION is in when `create_mcp()`
        # constructs this middleware, before registration has run. That
        # severs the shared reference: every entry `_register_openapi_tools`
        # adds afterwards would be invisible here, and `would_call`/`preview`
        # would be permanently null. `is None` is the only correct check.
        self._operation_by_tool = {} if operation_by_tool is None else operation_by_tool
        self._sibling_get = sibling_get

    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        if getattr(ctx, "method", None) != "tools/call":
            return await call_next(ctx)

        params = getattr(ctx, "params", None)
        # `ctx.params` is typed `Mapping[str, Any] | None` — not `dict`. A
        # `dict`-only isinstance check would treat any other Mapping shape as
        # "no name", falling through to `call_next` UNGATED. Mapping keeps the
        # fail-closed behaviour for any conforming shape.
        name = params.get("name") if isinstance(params, Mapping) else None
        risk = self._risk_by_tool.get(name)
        if risk not in GATED:
            return await call_next(ctx)

        raw_arguments = params.get("arguments") if isinstance(params, Mapping) else None
        arguments = raw_arguments if isinstance(raw_arguments, Mapping) else {}
        if arguments.get("confirm") is True:
            return await call_next(ctx)

        logger.info(f"Refused unconfirmed destructive call to {name}")
        payload = {
            "ok": False,
            "error": CONFIRMATION_REQUIRED,
            "risk": str(risk),
            "tool": name,
            "would_call": self._describe_call(name),
            "preview": await self._preview(name, arguments),
            "hint": "This call can destroy data. Re-send with confirm=true to proceed.",
        }
        # A middleware short-circuit is passed through as the final result
        # verbatim — it must itself be a valid `tools/call` result
        # (`CallToolResult`), which requires `content`. Returning the bare
        # payload dict fails Pydantic validation (`content: Field required`),
        # so the caller sees a protocol error instead of the refusal.
        return {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "isError": True,
            "structuredContent": payload,
        }

    def _describe_call(self, name: str) -> str | None:
        operation = self._operation_by_tool.get(name)
        return f"{operation[0]} {operation[1]}" if operation else None

    async def _preview(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any] | None:
        """Best effort: for a by-id delete with a sibling GET, show what would go.

        Never mutating, never fatal: any failure yields None so the refusal
        itself is never blocked by a failed preview. Run off the event loop
        thread — `sibling_get` does a synchronous, blocking HTTP GET, and
        awaiting it inline would stall the server's read loop on every
        refusal.
        """
        operation = self._operation_by_tool.get(name)
        if not operation or not self._sibling_get:
            return None
        method, path = operation
        if method != "DELETE" or "{" not in path:
            return None
        try:
            return await anyio.to_thread.run_sync(self._sibling_get, path, arguments)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Preview for {name} failed: {exc}")
            return None
