import pytest

from mcp4immich.confirm import ask_confirmation
from mcp4immich.risk import Risk


class _Elicitor:
    def __init__(self, action, supported=True):
        self._action = action
        self._supported = supported
        self.asked = None

    def client_capabilities(self):
        return {"elicitation": {}} if self._supported else {}

    async def elicit(self, message, schema):
        self.asked = message

        class _Result:
            action = self._action
            data = None

        return _Result()


@pytest.mark.anyio
async def test_accept_confirms():
    ctx = _Elicitor("accept")
    assert await ask_confirmation(ctx, "immich_deleteassets", Risk.DESTRUCTIVE_ADMIN) is True
    assert "immich_deleteassets" in ctx.asked


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["decline", "cancel"])
async def test_decline_and_cancel_refuse(action):
    ctx = _Elicitor(action)
    assert await ask_confirmation(ctx, "immich_deletealbum", Risk.DESTRUCTIVE) is False


@pytest.mark.anyio
async def test_client_without_capability_refuses_without_asking():
    ctx = _Elicitor("accept", supported=False)
    assert await ask_confirmation(ctx, "immich_deletealbum", Risk.DESTRUCTIVE) is False
    assert ctx.asked is None


@pytest.mark.anyio
async def test_elicitation_failure_refuses():
    class _Broken(_Elicitor):
        async def elicit(self, message, schema):
            raise RuntimeError("transport gone")

    assert await ask_confirmation(_Broken("accept"), "immich_deletealbum", Risk.DESTRUCTIVE) is False
