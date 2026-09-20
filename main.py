import logging

from mcp4immich.capabilities import (
    _discover_capabilities,
    _discover_write_capability,
    _write_probe_settings,
)
from mcp4immich.config import get_mcp_settings
from mcp4immich.http_client import _probe
from mcp4immich.mcp_app import run
from mcp4immich.openapi import (
    _fetch_openapi_spec,
    _list_openapi_operations,
    _merge_parameters,
    _operation_admin_only,
    _operation_param_specs,
    _operation_request_body_spec,
    _tool_name_for_operation,
)
from mcp4immich.tooling import tool_access_report

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure root logger based on MCP_LOG_LEVEL."""
    settings = get_mcp_settings()
    log_level = settings["log_level"]
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    _configure_logging()
    logger.info("Starting mcp4immich MCP server")
    run()


if __name__ == "__main__":
    main()
