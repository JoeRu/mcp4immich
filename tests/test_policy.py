import pytest

from mcp4immich.risk import Risk
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
