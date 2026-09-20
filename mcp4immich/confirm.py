"""Ask the human to confirm a destructive call, where the client supports it.

This never widens what is permitted: a model can set confirm=true by itself,
but it cannot answer an elicitation on the user's behalf. A client that does
not support elicitation simply falls back to the confirm parameter.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from .risk import Risk

logger = logging.getLogger(__name__)


class ConfirmDestructive(BaseModel):
    confirm: bool = Field(
        default=False,
        description="Yes, perform this destructive operation.",
    )


def _supports_elicitation(ctx: Any) -> bool:
    try:
        capabilities = ctx.client_capabilities()
    except Exception:
        return False
    if capabilities is None:
        return False
    if isinstance(capabilities, dict):
        # `.get(...)` is not enough: an advertised-but-empty capability
        # object (`{"elicitation": {}}`, the normal wire shape) is a present
        # dict, but `bool({})` is False -- that would misread a supporting
        # client as unsupported. Presence of the key with a non-None value is
        # the actual signal, mirroring the object-shaped branch below.
        return capabilities.get("elicitation") is not None
    return getattr(capabilities, "elicitation", None) is not None


async def ask_confirmation(ctx: Any, tool_name: str, risk: Risk) -> bool:
    """True only when the human explicitly accepted."""
    if not _supports_elicitation(ctx):
        return False

    severity = (
        "This can delete many items at once and cannot be undone by this server."
        if risk is Risk.DESTRUCTIVE_ADMIN
        else "This deletes data in Immich."
    )
    try:
        result = await ctx.elicit(
            f"Run the destructive tool {tool_name}? {severity}",
            ConfirmDestructive,
        )
    except Exception as exc:
        logger.warning(f"Elicitation failed for {tool_name}: {exc}")
        return False

    action = getattr(result, "action", None)
    if action != "accept":
        logger.info(f"Destructive call to {tool_name} was {action or 'not accepted'}")
        return False

    data = getattr(result, "data", None)
    if data is None:
        return True
    return bool(getattr(data, "confirm", True))
