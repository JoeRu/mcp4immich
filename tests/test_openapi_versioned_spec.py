import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from mcp4immich import openapi


class OpenApiVersionedSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        # resolve_spec's default cache dir must never be a shared location:
        # a previous run's cached spec would make the mocked-network
        # assertions below meaningless (they'd hit the cache instead of the
        # mock). Point it at a fresh per-test temp dir every time.
        self._tmp_cache_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_cache_dir.cleanup)
        self._env_patcher = patch.dict(
            os.environ, {"MCP4IMMICH_SPEC_CACHE": self._tmp_cache_dir.name}
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

    def test_version_tag_from_payload(self) -> None:
        payload = {"major": 2, "minor": 5, "patch": 6}
        self.assertEqual(openapi._version_tag_from_payload(payload), "v2.5.6")

    def test_version_tag_from_payload_missing(self) -> None:
        with self.assertRaises(ValueError):
            openapi._version_tag_from_payload({"major": 2, "minor": 5})

    def test_fetch_openapi_spec_health_failure(self) -> None:
        with patch(
            "mcp4immich.openapi._probe",
            return_value={"ok": False, "status_code": 500, "detail": "down"},
        ):
            with self.assertRaises(ValueError) as exc:
                openapi._fetch_openapi_spec.cache_clear()
                openapi._fetch_openapi_spec()
        self.assertIn("health check failed", str(exc.exception))

    def test_fetch_openapi_spec_uses_versioned_url(self) -> None:
        with patch("mcp4immich.openapi._probe", return_value={"ok": True}):
            with patch(
                "mcp4immich.openapi._request",
                return_value={"major": 2, "minor": 5, "patch": 6},
            ):
                response = MagicMock()
                response.json.return_value = {"openapi": "3.0.0"}
                response.raise_for_status.return_value = None
                client = MagicMock()
                client.get.return_value = response
                client.__enter__.return_value = client
                client.__exit__.return_value = None
                with patch("mcp4immich.openapi.httpx.Client", return_value=client):
                    openapi._fetch_openapi_spec.cache_clear()
                    result = openapi._fetch_openapi_spec()

        self.assertEqual(result.get("openapi"), "3.0.0")
        client.get.assert_called_once()
        url = client.get.call_args[0][0]
        self.assertIn("/v2.5.6/", url)
