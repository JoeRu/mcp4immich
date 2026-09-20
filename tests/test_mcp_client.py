import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

import main
import mcp
import mcp_types
from mcp.client import sse as mcp_sse


def _parse_env_file(path: str) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"").strip("'")
            if key:
                env_vars[key] = value
    return env_vars


def _build_server_env(env_path: str) -> dict[str, str]:
    if not os.path.exists(env_path):
        raise unittest.SkipTest(f"Missing env file: {env_path}")
    env_vars = os.environ.copy()
    env_vars.update(_parse_env_file(env_path))
    return env_vars


def _extract_tool_payload(result: mcp_types.CallToolResult) -> object:
    if result.structured_content is not None:
        return result.structured_content
    if not result.content:
        return None
    first = result.content[0]
    text = getattr(first, "text", None)
    if text is None and isinstance(first, dict):
        text = first.get("text")
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_tool_input_schema(tool: object) -> dict[str, Any] | None:
    if isinstance(tool, dict):
        schema = tool.get("inputSchema") or tool.get("input_schema")
        return schema if isinstance(schema, dict) else None
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    return schema if isinstance(schema, dict) else None


def _extract_tool_description(tool: object) -> str | None:
    if isinstance(tool, dict):
        description = tool.get("description")
        return description if isinstance(description, str) else None
    description = getattr(tool, "description", None)
    return description if isinstance(description, str) else None


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


async def _wait_for_port(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            await asyncio.sleep(0.1)
    raise TimeoutError(f"Server did not open port {port} within {timeout:.1f}s")


class WriteProbeDefaultsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        original_env = os.environ.copy()
        try:
            os.environ.pop("IMMICH_WRITE_PROBE_METHOD", None)
            os.environ.pop("IMMICH_WRITE_PROBE_PATH", None)

            method, path = main._write_probe_settings()

            self.assertEqual(method, "POST")
            self.assertEqual(path, "/api/assets")
        finally:
            os.environ.clear()
            os.environ.update(original_env)


class BaseMCPClientTests(unittest.IsolatedAsyncioTestCase):
    TEST_TIMEOUT_SECONDS = float(os.getenv("MCP_TEST_TIMEOUT", "20"))
    ENV_PATH_VAR = "IMMICH_ENV_TEST"
    DEFAULT_ENV_FILE = ".env_test"

    async def asyncSetUp(self) -> None:
        self.env_path = os.getenv(self.ENV_PATH_VAR, self.DEFAULT_ENV_FILE)
        self.repo_root = Path(__file__).resolve().parents[1]
        self.mcp_host = os.getenv("MCP_TEST_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port_env = os.getenv("MCP_TEST_PORT", "0").strip()
        self.mcp_port = int(port_env) if port_env.isdigit() else 0
        if self.mcp_port == 0:
            self.mcp_port = _find_free_port(self.mcp_host)

        self.server_env = _build_server_env(self.env_path)
        self.server_env["MCP_TRANSPORT"] = "sse"
        self.server_env["MCP_HOST"] = self.mcp_host
        self.server_env["MCP_PORT"] = str(self.mcp_port)
        self.server_env["MCP_LOG_LEVEL"] = os.getenv("MCP_LOG_LEVEL", "DEBUG")

        self.server_log_file = tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", delete=False
        )
        self.server_process = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=str(self.repo_root),
            env=self.server_env,
            stdout=self.server_log_file,
            stderr=self.server_log_file,
        )
        try:
            await _wait_for_port(
                self.mcp_host, self.mcp_port, self.TEST_TIMEOUT_SECONDS
            )
        except TimeoutError as exc:
            self.server_process.terminate()
            raise AssertionError(str(exc)) from exc

    async def asyncTearDown(self) -> None:
        if self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
        self.server_log_file.flush()
        self.server_log_file.close()

    def _read_server_log_tail(self, max_lines: int = 40) -> str:
        try:
            with open(self.server_log_file.name, "r", encoding="utf-8") as log:
                lines = log.read().splitlines()
            tail = lines[-max_lines:]
            return "\n".join(tail)
        except OSError:
            return "(server log unavailable)"

    async def _with_session(self, callback):
        async def run_session():
            url = f"http://{self.mcp_host}:{self.mcp_port}/sse"
            async with mcp_sse.sse_client(
                url, timeout=5, sse_read_timeout=self.TEST_TIMEOUT_SECONDS
            ) as (read_stream, write_stream):
                async with mcp.ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await callback(session)

        try:
            return await asyncio.wait_for(
                run_session(), timeout=self.TEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            log_tail = self._read_server_log_tail()
            self.fail(
                "Timed out waiting for MCP response after "
                f"{self.TEST_TIMEOUT_SECONDS:.1f}s.\n"
                f"Server log: {self.server_log_file.name}\n{log_tail}"
            )

    def _get_write_capability(self) -> dict[str, str | bool]:
        env_vars = _parse_env_file(self.env_path)
        original_env = os.environ.copy()
        try:
            os.environ.update(env_vars)
            main._discover_write_capability.cache_clear()
            return main._discover_write_capability()
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def _find_write_operation(self) -> dict[str, Any] | None:
        spec = main._fetch_openapi_spec()
        operations = main._list_openapi_operations(spec)
        for entry in operations:
            method = entry["method"]
            operation = entry["operation"]
            if method not in {"POST", "PUT", "PATCH", "DELETE"}:
                continue
            if main._operation_admin_only(operation):
                continue
            return entry
        for entry in operations:
            method = entry["method"]
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                return entry
        return None

    def _scan_openapi_parameter_presence(self) -> dict[str, bool]:
        spec = main._fetch_openapi_spec()
        operations = main._list_openapi_operations(spec)
        presence = {"path": False, "query": False, "body": False}
        for entry in operations:
            operation = entry.get("operation", {})
            if main._operation_admin_only(operation):
                continue
            params = main._merge_parameters(
                entry.get("path_parameters"),
                operation.get("parameters"),
            )
            for param in params:
                location = param.get("in")
                if location in presence:
                    presence[location] = True
            if operation.get("requestBody"):
                presence["body"] = True
            if all(presence.values()):
                break
        return presence

    def _find_openapi_tool_with_required_params(
        self, tool_names: set[str]
    ) -> str | None:
        spec = main._fetch_openapi_spec()
        operations = main._list_openapi_operations(spec)
        for entry in operations:
            operation = entry.get("operation", {})
            if main._operation_admin_only(operation):
                continue
            tool_name = main._tool_name_for_operation(
                entry["method"], entry["path"], operation
            )
            if tool_name not in tool_names:
                continue
            param_specs = main._operation_param_specs(entry)
            body_spec = main._operation_request_body_spec(operation)
            has_required = any(spec.get("required") for spec in param_specs)
            if body_spec and body_spec.get("required"):
                has_required = True
            if has_required:
                return tool_name
        return None

    async def test_list_tools_includes_core_tools(self) -> None:
        async def run(session: mcp.ClientSession) -> list[str]:
            tools_result = await session.list_tools()
            if isinstance(tools_result, list):
                tools = tools_result
            else:
                tools = getattr(tools_result, "tools", [])
            names: list[str] = []
            for tool in tools:
                if isinstance(tool, dict):
                    name = tool.get("name")
                else:
                    name = getattr(tool, "name", None)
                if name:
                    names.append(name)
            return names

        tool_names = await self._with_session(run)
        expected = {
            "ping_server",
            "get_server_version",
            "tool_access_report",
            "write_capability_report",
        }
        self.assertTrue(expected.issubset(set(tool_names)))

    async def test_write_tools_filtered_by_capability(self) -> None:
        entry = self._find_write_operation()
        if entry is None:
            self.skipTest("No write operations found in OpenAPI spec")
        tool_name = main._tool_name_for_operation(
            entry["method"], entry["path"], entry["operation"]
        )

        capability = self._get_write_capability()
        if not capability.get("configured"):
            self.skipTest("Write capability probe not configured")

        async def run(session: mcp.ClientSession) -> list[str]:
            tools_result = await session.list_tools()
            if isinstance(tools_result, list):
                tools = tools_result
            else:
                tools = getattr(tools_result, "tools", [])
            names: list[str] = []
            for tool in tools:
                name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
                if name:
                    names.append(name)
            return names

        tool_names = await self._with_session(run)
        if capability.get("allowed"):
            self.assertIn(tool_name, tool_names)
        else:
            self.assertNotIn(tool_name, tool_names)

    async def test_tool_access_report_shape(self) -> None:
        async def run(session: mcp.ClientSession) -> object:
            return _extract_tool_payload(await session.call_tool("tool_access_report"))

        payload = await self._with_session(run)
        if not isinstance(payload, dict):
            self.fail("Expected tool_access_report to return a dict payload")
        self.assertIn("allowed_tools", payload)
        self.assertIn("blocked_tools", payload)

    async def test_openapi_tool_parameter_schema(self) -> None:
        async def run(session: mcp.ClientSession) -> list[object]:
            tools_result = await session.list_tools()
            if isinstance(tools_result, list):
                return tools_result
            return list(getattr(tools_result, "tools", []))

        tools = await self._with_session(run)
        tool_map: dict[str, object] = {}
        for tool in tools:
            name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if name:
                tool_map[name] = tool

        openapi_tools = {
            name: tool for name, tool in tool_map.items() if name.startswith("immich_")
        }
        if not openapi_tools:
            self.skipTest("No OpenAPI tools available to validate parameter schemas")

        presence = self._scan_openapi_parameter_presence()
        write_capability = self._get_write_capability()
        if not (write_capability.get("configured") and write_capability.get("allowed")):
            presence["body"] = False
        checks = {
            "path": "path_",
            "query": "query_",
            "body": "body_",  # Changed to body_ to match resolved body field parameters
        }
        for key, prefix in checks.items():
            if not presence.get(key):
                continue
            found = False
            for tool in openapi_tools.values():
                schema = _extract_tool_input_schema(tool)
                if not schema:
                    continue
                properties = schema.get("properties", {})
                if not isinstance(properties, dict):
                    continue
                if key == "body":
                    # Check for body_* parameters (resolved from $ref schemas)
                    # or legacy "body" parameter
                    if "body" in properties or any(
                        name.startswith(prefix) for name in properties.keys()
                    ):
                        found = True
                        break
                else:
                    if any(name.startswith(prefix) for name in properties.keys()):
                        found = True
                        break
            self.assertTrue(
                found,
                f"Expected at least one OpenAPI tool with {key} parameter schema",
            )

    async def test_openapi_tool_descriptions_enriched(self) -> None:
        async def run(session: mcp.ClientSession) -> list[object]:
            tools_result = await session.list_tools()
            if isinstance(tools_result, list):
                return tools_result
            return list(getattr(tools_result, "tools", []))

        tools = await self._with_session(run)
        tool_map: dict[str, object] = {}
        for tool in tools:
            name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if name:
                tool_map[name] = tool

        openapi_tools = {
            name: tool for name, tool in tool_map.items() if name.startswith("immich_")
        }
        if not openapi_tools:
            self.skipTest("No OpenAPI tools available to validate descriptions")

        descriptions = [
            _extract_tool_description(tool) for tool in openapi_tools.values()
        ]
        self.assertTrue(any(desc and "returns:" in desc for desc in descriptions))

        tool_with_required = self._find_openapi_tool_with_required_params(
            set(openapi_tools.keys())
        )
        if tool_with_required is None:
            self.skipTest("No OpenAPI tools with required parameters available")
        description = _extract_tool_description(openapi_tools[tool_with_required])
        if not description:
            self.fail("Expected OpenAPI tool description to be populated")
        self.assertIn("params:", description)
        self.assertIn("example:", description)

    async def test_ping_server(self) -> None:
        async def run(session: mcp.ClientSession) -> object:
            return _extract_tool_payload(await session.call_tool("ping_server"))

        payload = await self._with_session(run)
        if isinstance(payload, dict) and payload.get("error"):
            self.skipTest(f"Immich server not reachable: {payload.get('detail')}")


class MCPClientFullAccessTests(BaseMCPClientTests):
    ENV_PATH_VAR = "IMMICH_ENV_FULL"
    DEFAULT_ENV_FILE = ".env"
