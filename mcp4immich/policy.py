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

import logging
from typing import Any

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
        self._operation_by_tool = operation_by_tool or {}
        self._sibling_get = sibling_get

    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        if getattr(ctx, "method", None) != "tools/call":
            return await call_next(ctx)

        params = getattr(ctx, "params", None) or {}
        name = params.get("name") if isinstance(params, dict) else None
        risk = self._risk_by_tool.get(name)
        if risk not in GATED:
            return await call_next(ctx)

        arguments = (params.get("arguments") if isinstance(params, dict) else None) or {}
        if arguments.get("confirm") is True:
            return await call_next(ctx)

        logger.info(f"Refused unconfirmed destructive call to {name}")
        return {
            "ok": False,
            "error": CONFIRMATION_REQUIRED,
            "risk": str(risk),
            "tool": name,
            "would_call": self._describe_call(name),
            "preview": self._preview(name, arguments),
            "hint": "This call can destroy data. Re-send with confirm=true to proceed.",
        }

    def _describe_call(self, name: str) -> str | None:
        operation = self._operation_by_tool.get(name)
        return f"{operation[0]} {operation[1]}" if operation else None

    def _preview(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """Best effort: for a by-id delete with a sibling GET, show what would go.

        Never mutating, never fatal: any failure yields None so the refusal
        itself is never blocked by a failed preview.
        """
        operation = self._operation_by_tool.get(name)
        if not operation or not self._sibling_get:
            return None
        method, path = operation
        if method != "DELETE" or "{" not in path:
            return None
        try:
            return self._sibling_get(path, arguments)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Preview for {name} failed: {exc}")
            return None
