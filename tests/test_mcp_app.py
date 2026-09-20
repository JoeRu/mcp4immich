"""Tests for claw2immich/mcp_app.py"""
from unittest.mock import patch


def test_resolve_external_domain_success():
    """Test _resolve_external_domain with successful API response."""
    from claw2immich.mcp_app import _resolve_external_domain
    
    mock_response = {"externalDomain": "immich.example.com"}
    
    # Patch _request at the source where it's imported from
    with patch("claw2immich.http_client._request", return_value=mock_response):
        domain = _resolve_external_domain()
        assert domain == "immich.example.com"


def test_resolve_external_domain_alternative_field():
    """Test _resolve_external_domain with alternative field name."""
    from claw2immich.mcp_app import _resolve_external_domain
    
    mock_response = {"external_domain": "immich.example.com"}
    
    # Patch _request at the source where it's imported from
    with patch("claw2immich.http_client._request", return_value=mock_response):
        domain = _resolve_external_domain()
        assert domain == "immich.example.com"


def test_resolve_external_domain_empty():
    """Test _resolve_external_domain with empty externalDomain falls back to base URL."""
    from claw2immich.mcp_app import _resolve_external_domain
    
    mock_response = {"externalDomain": ""}
    
    # When API returns empty domain, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("claw2immich.http_client._request", return_value=mock_response):
        with patch("claw2immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None


def test_resolve_external_domain_missing():
    """Test _resolve_external_domain when field is missing falls back to base URL."""
    from claw2immich.mcp_app import _resolve_external_domain
    
    mock_response = {"someOtherField": "value"}
    
    # When API response doesn't have externalDomain, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("claw2immich.http_client._request", return_value=mock_response):
        with patch("claw2immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None


def test_resolve_external_domain_request_error():
    """Test _resolve_external_domain when _request raises exception falls back to base URL."""
    from claw2immich.mcp_app import _resolve_external_domain
    from claw2immich.http_client import ImmichAPIError
    
    # When _request fails, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("claw2immich.http_client._request", side_effect=ImmichAPIError("401", "Unauthorized")):
        with patch("claw2immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None

def test_resolve_external_domain_non_dict_response():
    """Test _resolve_external_domain when response is not a dict falls back to base URL."""
    from claw2immich.mcp_app import _resolve_external_domain
    
    # When _request returns non-dict, should fall back to IMMICH_BASE_URL
    # Patch both _request and _get_config to control both fallbacks
    with patch("claw2immich.http_client._request", return_value="not a dict"):
        with patch("claw2immich.config._get_config", return_value={"base_url": ""}):
            domain = _resolve_external_domain()
            assert domain is None


def test_create_mcp_returns_mcpserver_with_project_version():
    from mcp.server.mcpserver import MCPServer
    from claw2immich.mcp_app import create_mcp
    from importlib.metadata import version

    mcp = create_mcp()

    assert isinstance(mcp, MCPServer)
    assert mcp.version == version("claw2immich")


def test_run_validates_transport():
    """Test run() validates MCP_TRANSPORT."""
    from claw2immich.mcp_app import run
    import os
    
    os.environ["MCP_TRANSPORT"] = "invalid_transport"
    
    try:
        # Mock create_mcp and all its dependencies
        with patch("claw2immich.mcp_app.create_mcp") as mock_create:
            with patch("claw2immich.mcp_app.register_prompts_and_resources"):
                with patch("claw2immich.mcp_app._register_tools"):
                    mock_mcp = mock_create.return_value
                    with patch.object(mock_mcp, "run"):
                        try:
                            run()
                            assert False, "Should have raised ValueError"
                        except ValueError as e:
                            assert "MCP_TRANSPORT" in str(e)
    finally:
        os.environ.pop("MCP_TRANSPORT", None)
