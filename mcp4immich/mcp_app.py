import logging
from importlib.metadata import version

from mcp.server.mcpserver import MCPServer

from .config import get_mcp_settings, get_transport_settings, get_external_domain
from .constants import build_server_instructions
from .policy import RiskPolicyMiddleware
from .prompts import register_prompts_and_resources
from .tooling import TOOL_OPERATION, TOOL_RISK, _register_tools, _sibling_get

logger = logging.getLogger(__name__)

__version__ = version("mcp4immich")


def _resolve_external_domain() -> str | None:
    """Get external domain from config (which handles all fallback logic)."""
    return get_external_domain()


def create_mcp() -> MCPServer:
    logger.info("Creating MCP server")
    settings = get_mcp_settings()
    instructions = build_server_instructions(_resolve_external_domain())
    # The SDK only accepts middleware at construction time (`MCPServer.middleware`
    # is a read-only property; assigning to it after the fact raises
    # AttributeError). Tools are not registered yet at this point, so
    # RiskPolicyMiddleware is handed the *same* TOOL_RISK/TOOL_OPERATION dict
    # objects that `_register_openapi_tools` populates afterwards — being
    # mutable and shared by reference, the middleware sees every entry added
    # later without needing to be rebuilt, and without a second network probe
    # of the OpenAPI spec just to pre-compute the risk map.
    middleware = [RiskPolicyMiddleware(TOOL_RISK, TOOL_OPERATION, sibling_get=_sibling_get)]
    server = MCPServer(
        "mcp4immich",
        version=__version__,
        log_level=settings["log_level"],
        instructions=instructions,
        middleware=middleware,
    )

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):  # noqa: ANN001 - starlette request
        import anyio
        from starlette.responses import JSONResponse

        from .http_client import _probe
        from .openapi import _get_last_spec_source

        # I5: `_probe` is synchronous httpx with a 10s timeout. Awaited
        # inline (the old code), it was the only blocking call left on the
        # loop -- an unreachable Immich stalled MCP request handling on
        # every probe. Offload to a worker thread, same pattern as
        # `policy.py`'s preview GET (`anyio.to_thread.run_sync`).
        #
        # `_probe` already catches `httpx.RequestError`/`ValueError`, but
        # this route's whole job is to answer honestly, not to propagate --
        # any other exception (a bug elsewhere, e.g. in config resolution)
        # must still produce `immich_reachable: false`, not a 500.
        try:
            probe_result = await anyio.to_thread.run_sync(_probe, "GET", "/api/server/ping")
            reachable = bool(probe_result.get("ok"))
        except Exception:
            reachable = False
        return JSONResponse(
            {
                "status": "ok",
                "immich_reachable": reachable,
                "spec_source": _get_last_spec_source(),
                "version": __version__,
            }
        )

    return server


def run() -> None:
    logger.info("Starting MCP server run loop")
    mcp = create_mcp()
    register_prompts_and_resources(mcp)
    _register_tools(mcp)

    transport, mount_path = get_transport_settings()
    logger.info(f"Using transport: {transport}")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("MCP_TRANSPORT must be stdio, sse, or streamable-http")

    if transport == "stdio":
        # stdio has no network binding; host/port/mount_path do not apply.
        mcp.run(transport=transport)
        return

    settings = get_mcp_settings()
    run_kwargs: dict[str, object] = {"host": settings["host"], "port": settings["port"]}
    if mount_path:
        path_kwarg = "sse_path" if transport == "sse" else "streamable_http_path"
        run_kwargs[path_kwarg] = mount_path
    mcp.run(transport=transport, **run_kwargs)
