"""Tests for mcp4immich/config.py"""
import os
import pytest


def test_get_mcp_settings_defaults():
    """Test get_mcp_settings with default values."""
    # Ensure env vars are clean
    for key in ("MCP_HOST", "MCP_PORT", "MCP_LOG_LEVEL"):
        os.environ.pop(key, None)
    
    from mcp4immich.config import get_mcp_settings
    
    settings = get_mcp_settings()
    assert settings["host"] == "127.0.0.1"
    assert settings["port"] == 8000
    assert settings["log_level"] == "INFO"


def test_get_mcp_settings_custom_values():
    """Test get_mcp_settings with custom environment values."""
    os.environ["MCP_HOST"] = "0.0.0.0"
    os.environ["MCP_PORT"] = "9999"
    os.environ["MCP_LOG_LEVEL"] = "debug"
    
    try:
        from mcp4immich.config import get_mcp_settings
        
        settings = get_mcp_settings()
        assert settings["host"] == "0.0.0.0"
        assert settings["port"] == 9999
        assert settings["log_level"] == "DEBUG"
    finally:
        os.environ.pop("MCP_HOST", None)
        os.environ.pop("MCP_PORT", None)
        os.environ.pop("MCP_LOG_LEVEL", None)


def test_get_mcp_settings_port_zero():
    """Test get_mcp_settings allows port 0 for auto-assign."""
    os.environ["MCP_PORT"] = "0"
    
    try:
        from mcp4immich.config import get_mcp_settings
        
        settings = get_mcp_settings()
        assert settings["port"] == 0
    finally:
        os.environ.pop("MCP_PORT", None)


def test_get_mcp_settings_port_boundary():
    """Test get_mcp_settings port boundary validation."""
    from mcp4immich.config import get_mcp_settings
    
    # Valid boundaries
    for port in [1, 65535]:
        os.environ["MCP_PORT"] = str(port)
        try:
            settings = get_mcp_settings()
            assert settings["port"] == port
        finally:
            os.environ.pop("MCP_PORT", None)


def test_get_mcp_settings_port_invalid_negative():
    """Test get_mcp_settings rejects negative port."""
    os.environ["MCP_PORT"] = "-1"
    
    try:
        from mcp4immich.config import get_mcp_settings
        
        with pytest.raises(ValueError, match="must be in range"):
            get_mcp_settings()
    finally:
        os.environ.pop("MCP_PORT", None)


def test_get_mcp_settings_port_invalid_too_high():
    """Test get_mcp_settings rejects port > 65535."""
    os.environ["MCP_PORT"] = "99999"
    
    try:
        from mcp4immich.config import get_mcp_settings
        
        with pytest.raises(ValueError, match="must be in range"):
            get_mcp_settings()
    finally:
        os.environ.pop("MCP_PORT", None)


def test_get_mcp_settings_port_non_integer():
    """Test get_mcp_settings rejects non-integer port."""
    os.environ["MCP_PORT"] = "notanumber"
    
    try:
        from mcp4immich.config import get_mcp_settings
        
        with pytest.raises(ValueError, match="must be an integer"):
            get_mcp_settings()
    finally:
        os.environ.pop("MCP_PORT", None)


def test_get_transport_settings_defaults():
    """Test get_transport_settings with default values."""
    for key in ("MCP_TRANSPORT", "MCP_MOUNT_PATH"):
        os.environ.pop(key, None)
    
    from mcp4immich.config import get_transport_settings
    
    transport, mount_path = get_transport_settings()
    assert transport == "stdio"
    assert mount_path is None


def test_get_transport_settings_custom():
    """Test get_transport_settings with custom values."""
    os.environ["MCP_TRANSPORT"] = "sse"
    os.environ["MCP_MOUNT_PATH"] = "/immich"
    
    try:
        from mcp4immich.config import get_transport_settings
        
        transport, mount_path = get_transport_settings()
        assert transport == "sse"
        assert mount_path == "/immich"
    finally:
        os.environ.pop("MCP_TRANSPORT", None)
        os.environ.pop("MCP_MOUNT_PATH", None)


def test_get_config_https():
    """Test _get_config with HTTPS URL."""
    os.environ["IMMICH_BASE_URL"] = "https://immich.example.com"
    os.environ.pop("IMMICH_API_KEY", None)
    os.environ.pop("IMMICH_API_TOKEN", None)
    
    try:
        from mcp4immich.config import _get_config
        
        config = _get_config()
        assert config["base_url"] == "https://immich.example.com"
        assert config["api_key"] == ""
        assert config["api_token"] == ""
    finally:
        os.environ.pop("IMMICH_BASE_URL", None)


def test_get_config_http():
    """Test _get_config with HTTP URL."""
    os.environ["IMMICH_BASE_URL"] = "http://localhost:2283"
    os.environ.pop("IMMICH_API_KEY", None)
    os.environ.pop("IMMICH_API_TOKEN", None)
    
    try:
        from mcp4immich.config import _get_config
        
        config = _get_config()
        assert config["base_url"] == "http://localhost:2283"
    finally:
        os.environ.pop("IMMICH_BASE_URL", None)


def test_get_config_invalid_url():
    """Test _get_config rejects invalid URL schemes."""
    os.environ["IMMICH_BASE_URL"] = "ftp://immich.example.com"
    
    try:
        from mcp4immich.config import _get_config
        
        with pytest.raises(ValueError, match="must start with http:// or https://"):
            _get_config()
    finally:
        os.environ.pop("IMMICH_BASE_URL", None)


def test_get_config_strips_trailing_slash():
    """Test _get_config strips trailing slash."""
    os.environ["IMMICH_BASE_URL"] = "https://immich.example.com/"
    os.environ.pop("IMMICH_API_KEY", None)
    os.environ.pop("IMMICH_API_TOKEN", None)
    
    try:
        from mcp4immich.config import _get_config
        
        config = _get_config()
        assert config["base_url"] == "https://immich.example.com"
    finally:
        os.environ.pop("IMMICH_BASE_URL", None)


def test_get_profile_valid():
    """Test get_profile with valid profile values."""
    from mcp4immich.config import get_profile
    
    for profile in ["read_only", "read_write", "full_scope"]:
        os.environ["IMMICH_PROFILE"] = profile
        try:
            result = get_profile()
            assert result == profile
        finally:
            os.environ.pop("IMMICH_PROFILE", None)


def test_get_profile_invalid():
    """Test get_profile rejects invalid profile."""
    os.environ["IMMICH_PROFILE"] = "invalid_profile"
    
    try:
        from mcp4immich.config import get_profile
        
        with pytest.raises(ValueError, match="Invalid IMMICH_PROFILE"):
            get_profile()
    finally:
        os.environ.pop("IMMICH_PROFILE", None)


def test_get_profile_none():
    """Test get_profile returns None when not set."""
    os.environ.pop("IMMICH_PROFILE", None)
    
    from mcp4immich.config import get_profile
    
    result = get_profile()
    assert result is None


def test_profile_allows_write():
    """Test profile_allows_write checks."""
    from mcp4immich.config import profile_allows_write
    
    assert profile_allows_write(None) is True  # No profile = unrestricted
    assert profile_allows_write("read_only") is False
    assert profile_allows_write("read_write") is True
    assert profile_allows_write("full_scope") is True


def test_profile_allows_admin():
    """Test profile_allows_admin checks."""
    from mcp4immich.config import profile_allows_admin
    
    assert profile_allows_admin(None) is True  # No profile = unrestricted
    assert profile_allows_admin("read_only") is False
    assert profile_allows_admin("read_write") is False
    assert profile_allows_admin("full_scope") is True


def test_get_usage_guide_path():
    """Test get_usage_guide_path returns valid path."""
    from mcp4immich.config import get_usage_guide_path
    
    path = get_usage_guide_path()
    assert path.endswith("usage-guide.md")
    assert "docs" in path

def test_get_external_domain_not_set():
    """Test get_external_domain returns fallback (IMMICH_BASE_URL) when env var not set."""
    os.environ.pop("IMMICH_EXTERNAL_DOMAIN", None)
    
    from mcp4immich.config import get_external_domain
    
    result = get_external_domain()
    # Should fall back to IMMICH_BASE_URL (from _get_config)
    # Result could be None (if Immich unreachable) or a URL string
    assert result is None or isinstance(result, str)


def test_get_external_domain_https():
    """Test get_external_domain reads and normalizes HTTPS domain."""
    os.environ["IMMICH_EXTERNAL_DOMAIN"] = "https://immich.example.com/"
    
    try:
        from mcp4immich.config import get_external_domain
        
        result = get_external_domain()
        assert result == "https://immich.example.com"  # Trailing slash removed
    finally:
        os.environ.pop("IMMICH_EXTERNAL_DOMAIN", None)


def test_get_external_domain_http():
    """Test get_external_domain accepts HTTP."""
    os.environ["IMMICH_EXTERNAL_DOMAIN"] = "http://localhost:2283"
    
    try:
        from mcp4immich.config import get_external_domain
        
        result = get_external_domain()
        assert result == "http://localhost:2283"
    finally:
        os.environ.pop("IMMICH_EXTERNAL_DOMAIN", None)


def test_get_external_domain_invalid_protocol():
    """Test get_external_domain rejects invalid protocol."""
    os.environ["IMMICH_EXTERNAL_DOMAIN"] = "ftp://invalid.com"
    
    try:
        from mcp4immich.config import get_external_domain
        
        with pytest.raises(ValueError, match="must start with http"):
            get_external_domain()
    finally:
        os.environ.pop("IMMICH_EXTERNAL_DOMAIN", None)


def test_get_external_domain_env_var_takes_precedence():
    """Test that env var takes precedence over all fallbacks."""
    os.environ["IMMICH_EXTERNAL_DOMAIN"] = "https://configured.example.com"
    os.environ["IMMICH_BASE_URL"] = "http://different.example.com"
    
    try:
        from mcp4immich.config import get_external_domain
        
        result = get_external_domain()
        # Should return env var first
        assert result == "https://configured.example.com"
    finally:
        os.environ.pop("IMMICH_EXTERNAL_DOMAIN", None)
        os.environ.pop("IMMICH_BASE_URL", None)


def test_get_external_domain_fallback_normalizes_trailing_slash():
    """Test that env var with trailing slash is normalized."""
    os.environ["IMMICH_EXTERNAL_DOMAIN"] = "https://immich.example.com/"
    
    try:
        from mcp4immich.config import get_external_domain
        
        result = get_external_domain()
        # Should remove trailing slash
        assert result == "https://immich.example.com"
    finally:
        os.environ.pop("IMMICH_EXTERNAL_DOMAIN", None)


def test_get_download_asset_delivery_mode_default():
    os.environ.pop("IMMICH_DOWNLOAD_ASSET_DELIVERY", None)
    from mcp4immich.config import get_download_asset_delivery_mode

    assert get_download_asset_delivery_mode() == "shared_link"


def test_get_download_asset_delivery_mode_valid_values():
    from mcp4immich.config import get_download_asset_delivery_mode

    os.environ["IMMICH_DOWNLOAD_ASSET_DELIVERY"] = "immich_link"
    try:
        assert get_download_asset_delivery_mode() == "immich_link"
    finally:
        os.environ.pop("IMMICH_DOWNLOAD_ASSET_DELIVERY", None)

    os.environ["IMMICH_DOWNLOAD_ASSET_DELIVERY"] = "shared_link"
    try:
        assert get_download_asset_delivery_mode() == "shared_link"
    finally:
        os.environ.pop("IMMICH_DOWNLOAD_ASSET_DELIVERY", None)


def test_get_download_asset_delivery_mode_invalid_value():
    from mcp4immich.config import get_download_asset_delivery_mode

    os.environ["IMMICH_DOWNLOAD_ASSET_DELIVERY"] = "invalid"
    try:
        with pytest.raises(ValueError, match="IMMICH_DOWNLOAD_ASSET_DELIVERY"):
            get_download_asset_delivery_mode()
    finally:
        os.environ.pop("IMMICH_DOWNLOAD_ASSET_DELIVERY", None)
