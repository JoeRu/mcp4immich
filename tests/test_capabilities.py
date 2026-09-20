import os
import unittest
from unittest.mock import patch

from mcp4immich import capabilities


class CapabilityErrorReasonTests(unittest.TestCase):
    def tearDown(self) -> None:
        capabilities._discover_capabilities.cache_clear()
        capabilities._discover_write_capability.cache_clear()

    def test_get_current_user_reason_http_500(self) -> None:
        probe = {"ok": False, "status_code": 500, "detail": "boom"}
        with patch.dict(
            os.environ,
            {"IMMICH_API_KEY": "test", "IMMICH_BASE_URL": "http://example.com"},
            clear=False,
        ):
            with patch("mcp4immich.capabilities._probe", return_value=probe):
                report = capabilities._discover_capabilities()
        reason = report["get_current_user"]["reason"]
        self.assertIn("HTTP 500", reason)
        self.assertIn("/api/users/me", reason)

    def test_get_current_user_reason_network_error(self) -> None:
        probe = {
            "ok": False,
            "error": "Network error",
            "detail": "timed out",
        }
        with patch.dict(
            os.environ,
            {"IMMICH_API_KEY": "test", "IMMICH_BASE_URL": "http://example.com"},
            clear=False,
        ):
            with patch("mcp4immich.capabilities._probe", return_value=probe):
                report = capabilities._discover_capabilities()
        reason = report["get_current_user"]["reason"]
        self.assertIn("Network error", reason)
        self.assertIn("timed out", reason)

    def test_write_capability_reason_http_403(self) -> None:
        probe = {"ok": False, "status_code": 403, "detail": "forbidden"}
        with patch.dict(
            os.environ,
            {"IMMICH_API_KEY": "test", "IMMICH_BASE_URL": "http://example.com"},
            clear=False,
        ):
            with patch("mcp4immich.capabilities._probe", return_value=probe):
                report = capabilities._discover_write_capability()
        reason = str(report.get("reason"))
        self.assertIn("lacks permission", reason)

    def test_write_capability_reason_http_500(self) -> None:
        probe = {"ok": False, "status_code": 500, "detail": "boom"}
        with patch.dict(
            os.environ,
            {"IMMICH_API_KEY": "test", "IMMICH_BASE_URL": "http://example.com"},
            clear=False,
        ):
            with patch("mcp4immich.capabilities._probe", return_value=probe):
                report = capabilities._discover_write_capability()
        reason = str(report.get("reason"))
        self.assertIn("HTTP 500", reason)

    def test_write_capability_reason_network_error(self) -> None:
        probe = {
            "ok": False,
            "error": "Network error",
            "detail": "timeout",
        }
        with patch.dict(
            os.environ,
            {"IMMICH_API_KEY": "test", "IMMICH_BASE_URL": "http://example.com"},
            clear=False,
        ):
            with patch("mcp4immich.capabilities._probe", return_value=probe):
                report = capabilities._discover_write_capability()
        reason = str(report.get("reason"))
        self.assertIn("Network error", reason)
        self.assertIn("timeout", reason)
