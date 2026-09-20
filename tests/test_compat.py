import pytest

from mcp4immich.compat import endpoint


def test_server_config_path_per_major():
    assert endpoint("server_config", 2) == "/api/server-config"
    assert endpoint("server_config", 3) == "/api/server/config"


def test_unknown_future_major_uses_newest_known():
    assert endpoint("server_config", 9) == "/api/server/config"


def test_unknown_name_is_an_error():
    with pytest.raises(KeyError):
        endpoint("nope", 3)
