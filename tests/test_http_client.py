import os
import unittest
from unittest.mock import MagicMock, patch

import httpx

from mcp4immich.http_client import (
    ImmichAPIError,
    ImmichConfigError,
    ImmichNetworkError,
    _build_headers,
    _request,
    _request_bytes,
)


class TestBuildHeaders(unittest.TestCase):
    def test_build_headers_with_api_key(self):
        config = {"api_key": "test-key", "api_token": None}
        headers = _build_headers(config, require_auth=False, extra_headers=None)
        self.assertEqual(headers["x-api-key"], "test-key")
        self.assertNotIn("authorization", headers)

    def test_build_headers_with_api_token(self):
        config = {"api_key": None, "api_token": "test-token"}
        headers = _build_headers(config, require_auth=False, extra_headers=None)
        self.assertEqual(headers["authorization"], "Bearer test-token")
        self.assertNotIn("x-api-key", headers)

    def test_build_headers_require_auth_missing_credentials(self):
        config = {"api_key": None, "api_token": None}
        with self.assertRaises(ValueError) as ctx:
            _build_headers(config, require_auth=True, extra_headers=None)
        self.assertIn("IMMICH_API_KEY or IMMICH_API_TOKEN", str(ctx.exception))

    def test_build_headers_extra_headers(self):
        config = {"api_key": "test-key", "api_token": None}
        extra = {"X-Custom": "value"}
        headers = _build_headers(config, require_auth=False, extra_headers=extra)
        self.assertEqual(headers["X-Custom"], "value")


class TestRequest(unittest.TestCase):
    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    def test_request_success_json(self, mock_client_class, mock_get_config):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "success"}
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = _request("GET", "/api/test")
        self.assertEqual(result, {"result": "success"})

    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    def test_request_success_text(self, mock_client_class, mock_get_config):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "plain text response"
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = _request("GET", "/api/test")
        self.assertEqual(result, "plain text response")

    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    def test_request_success_binary_wrapped_base64(
        self,
        mock_client_class,
        mock_get_config,
    ):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"\x00\x01\x02"
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = _request("GET", "/api/test")
        self.assertEqual(result["encoding"], "base64")
        self.assertEqual(result["content_type"], "image/jpeg")
        self.assertEqual(result["size_bytes"], 3)
        self.assertEqual(result["data"], "AAEC")

    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    def test_request_http_status_error(self, mock_client_class, mock_get_config):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with self.assertRaises(ImmichAPIError) as ctx:
            _request("GET", "/api/test")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "Forbidden")

    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    def test_request_network_error(self, mock_client_class, mock_get_config):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_client = MagicMock()
        mock_client.request.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with self.assertRaises(ImmichNetworkError) as ctx:
            _request("GET", "/api/test")
        self.assertIn("Connection refused", str(ctx.exception))

    @patch("mcp4immich.http_client._get_config")
    def test_request_config_error(self, mock_get_config):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": None,
            "api_token": None,
        }

        with self.assertRaises(ImmichConfigError) as ctx:
            _request("GET", "/api/test", require_auth=True)
        self.assertIn("IMMICH_API_KEY or IMMICH_API_TOKEN", str(ctx.exception))

    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    def test_request_bytes_success(self, mock_client_class, mock_get_config):
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xd8\xff"
        mock_response.headers = {
            "content-type": "image/jpeg",
            "content-disposition": 'attachment; filename="photo.jpg"',
        }
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        payload, headers = _request_bytes("GET", "/api/assets/test/original")
        self.assertEqual(payload, b"\xff\xd8\xff")
        self.assertEqual(headers["content-type"], "image/jpeg")
        self.assertIn("filename=\"photo.jpg\"", headers["content-disposition"])


class TestHTTPWarning(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=False)
    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    @patch("mcp4immich.http_client.logger")
    def test_warn_credentials_over_http(
        self,
        mock_logger,
        mock_client_class,
        mock_get_config,
    ):
        """Test that a warning is logged when credentials are sent over plain HTTP."""
        os.environ.pop("IMMICH_ALLOW_HTTP", None)
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "success"}
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        _request("GET", "/api/test")

        # Check that warning was logged about HTTP with credentials
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if "plain HTTP" in str(call)
        ]
        self.assertTrue(
            len(warning_calls) > 0,
            "Expected warning about credentials over HTTP",
        )

    @patch.dict(os.environ, {"IMMICH_ALLOW_HTTP": "true"}, clear=False)
    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    @patch("mcp4immich.http_client.logger")
    def test_suppress_http_warning_with_flag(
        self,
        mock_logger,
        mock_client_class,
        mock_get_config,
    ):
        """Test that HTTP warning is suppressed when IMMICH_ALLOW_HTTP=true."""
        mock_get_config.return_value = {
            "base_url": "http://localhost",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "success"}
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        _request("GET", "/api/test")

        # Check that warning was NOT logged
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if "plain HTTP" in str(call)
        ]
        self.assertEqual(
            len(warning_calls),
            0,
            "Expected no warning when IMMICH_ALLOW_HTTP=true",
        )

    @patch("mcp4immich.http_client._get_config")
    @patch("mcp4immich.http_client.httpx.Client")
    @patch("mcp4immich.http_client.logger")
    def test_no_warning_for_https(
        self,
        mock_logger,
        mock_client_class,
        mock_get_config,
    ):
        """Test that no warning is logged when using HTTPS."""
        mock_get_config.return_value = {
            "base_url": "https://immich.example.com",
            "api_key": "test-key",
            "api_token": None,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "success"}
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        _request("GET", "/api/test")

        # Check that no warning about HTTP was logged
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if "plain HTTP" in str(call)
        ]
        self.assertEqual(len(warning_calls), 0)


if __name__ == "__main__":
    unittest.main()
