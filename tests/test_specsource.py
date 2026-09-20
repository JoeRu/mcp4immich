import json
from pathlib import Path

import pytest

from mcp4immich.specsource import resolve_spec


def _fake_spec(marker: str) -> dict:
    return {"openapi": "3.1.0", "info": {"version": marker}, "paths": {}}


def test_uses_disk_cache_without_calling_network(tmp_path: Path):
    cached = tmp_path / "immich-v3.2.1.json"
    cached.write_text(json.dumps(_fake_spec("from-cache")))

    def fetch(url: str) -> dict:
        raise AssertionError("network must not be used when the cache is warm")

    spec, source = resolve_spec("v3.2.1", fetch, cache_dir=tmp_path)

    assert source == "cache"
    assert spec["info"]["version"] == "from-cache"


def test_network_result_is_written_to_cache(tmp_path: Path):
    spec, source = resolve_spec("v3.2.1", lambda url: _fake_spec("from-net"), cache_dir=tmp_path)

    assert source == "network"
    assert json.loads((tmp_path / "immich-v3.2.1.json").read_text())["info"]["version"] == "from-net"


def test_falls_back_to_vendored_when_network_fails(tmp_path: Path):
    def fetch(url: str) -> dict:
        raise OSError("no route to host")

    spec, source = resolve_spec("v3.2.1", fetch, cache_dir=tmp_path)

    assert source == "vendored"
    assert spec["paths"], "vendored spec must contain paths"


def test_corrupt_cache_is_ignored(tmp_path: Path):
    (tmp_path / "immich-v3.2.1.json").write_text("{not json")

    spec, source = resolve_spec("v3.2.1", lambda url: _fake_spec("from-net"), cache_dir=tmp_path)

    assert source == "network"
