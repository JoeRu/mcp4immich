import asyncio
import os
import sys

import mcp
from mcp.client import sse as mcp_sse


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except ValueError:
        return default


async def _main() -> int:
    host = os.getenv("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.getenv("MCP_PORT", "8000").strip() or "8000"
    mount_path = os.getenv("MCP_MOUNT_PATH", "").strip()
    timeout = _parse_float(os.getenv("MCP_CLIENT_TIMEOUT", "20"), 20.0)

    base = f"http://{host}:{port}"
    if mount_path:
        base = f"{base}/{mount_path.strip('/')}"
    url = f"{base}/sse"

    async with mcp_sse.sse_client(
        url, timeout=5, sse_read_timeout=timeout
    ) as (read_stream, write_stream):
        async with mcp.ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("tool_access_report")

    payload = result.structured_content
    if payload is None and result.content:
        first = result.content[0]
        text = getattr(first, "text", None)
        if text is None and isinstance(first, dict):
            text = first.get("text")
        payload = text

    if payload is None:
        print("No payload returned.")
        return 1

    if isinstance(payload, (dict, list)):
        import json

        print(json.dumps(payload, indent=2))
        return 0

    print(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except KeyboardInterrupt:
        sys.exit(130)
