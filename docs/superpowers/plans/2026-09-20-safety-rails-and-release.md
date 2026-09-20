# mcp4immich Safety Rails & Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship mcp4immich 1.0.0 — destructive Immich operations guarded by a confirm gate (with elicitation where clients support it), offline-safe startup, correct Immich 2.x/3.x endpoints, one honest version number, the rename completed, on the maintained MCP SDK 2.x line — then deploy it here VPN-bound and monitored.

**Architecture:** A pure risk classifier maps every OpenAPI operation to `read`/`write`/`destructive`/`destructive_admin`. Everything else derives from it: MCP annotations at registration time, and a single `ServerMiddleware` that enforces the confirm gate on `tools/call` and hides the admin class from `tools/list`. Generated-tool plumbing, permission probes and response decoration stay as they are.

**Tech Stack:** Python 3.12, `mcp[cli]>=2.2,<3` (MCPServer, `mcp_types`), httpx, pytest, uv, Docker.

**Spec:** `docs/superpowers/specs/2026-09-20-safety-rails-and-release-design.md`

## Global Constraints

- Repo `/container/compose/immich-app/claw2immich`, branch `feat/safety-rails-and-release` (base `a39ae71`; spec commits `e0f574c`, `2fb7b95`). The directory keeps its old name until Task 11.
- **Test command (host has `uv` + Python 3.12):** `uv run pytest tests/ -q -m "not integration"`. Integration tests need a live Immich and are run only where a task says so.
- Package rename lands in Task 2: `claw2immich` → `mcp4immich`. Tasks after 2 use the new name; Tasks 1 uses the old one.
- SDK 2.x facts, verified against an installed `mcp==2.2.0` on 2026-09-20: `from mcp.server.mcpserver import MCPServer, Context, Elicit, Resolve`; `from mcp.server.context import ServerMiddleware, ServerRequestContext, HandlerResult`; `from mcp_types import ToolAnnotations` with **snake_case** fields `read_only_hint`, `destructive_hint`, `idempotent_hint`, `open_world_hint`; `MCPServer(name, version=..., instructions=..., host=..., port=..., log_level=..., middleware=[...])`; decorators `@mcp.tool`, `@mcp.resource`, `@mcp.prompt`, `mcp.add_tool(fn, name=, description=, annotations=)`, `mcp.custom_route(path, methods)`, `mcp.run(transport=, mount_path=)`.
- `ServerMiddleware` is a Protocol: `async def __call__(self, ctx, call_next)`, where `ctx.method` is the JSON-RPC method and `ctx.params` the raw inbound params. It wraps every request.
- Risk classes and their rules are defined in the spec §1 and must be copied exactly.
- **No destructive call may ever reach Immich without `confirm=true` (or an accepted elicitation).** A refusal performs no mutating HTTP call.
- Version for this release: **1.0.0**, sourced from `pyproject.toml`.
- Every commit ends with:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_017iZ3QwZDAnhG6nuobSajC1
  ```
  (written as `<trailer>` in the commit steps below).
- Never print or commit `IMMICH_API_KEY`. Never run the integration suite against real data with a destructive tool confirmed.

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml`, `uv.lock` (modify) | pin `mcp[cli]>=2.2,<3`; project name/version |
| `mcp4immich/mcp_app.py` (modify) | build `MCPServer`, attach middleware, register `/healthz`, run |
| `mcp4immich/risk.py` (create) | `Risk` enum + `classify()` — the single source of truth |
| `mcp4immich/policy.py` (create) | `RiskPolicyMiddleware`: confirm gate, preview, admin hiding |
| `mcp4immich/confirm.py` (create) | elicitation helper used by the middleware |
| `mcp4immich/compat.py` (create) | endpoints that moved between Immich majors |
| `mcp4immich/specsource.py` (create) | disk cache → network → vendored resolution |
| `mcp4immich/data/immich-openapi-3.json` (create) | vendored spec fallback |
| `mcp4immich/tooling.py` (modify) | annotations at registration; parameter enum disclosure; risk in `tool_access_report` |
| `mcp4immich/openapi.py`, `config.py`, `constants.py`, `http_client.py`, `prompts.py` (modify) | imports, rename strings, compat endpoint, spec source |
| `tests/test_risk.py`, `test_policy.py`, `test_confirm.py`, `test_compat.py`, `test_specsource.py`, `test_protocol_eras.py` (create) | one per new unit |
| `docker-compose.yaml`, `Dockerfile`, `.github/workflows/*.yml`, `README.md`, `CHANGELOG.md` (modify/create) | packaging, CI, release, docs |

---

### Task 1: Migrate to MCP SDK 2.x and bound the pin

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `claw2immich/mcp_app.py`, `claw2immich/tooling.py`
- Test: `tests/test_mcp_app.py`

**Interfaces:**
- Produces: `create_mcp() -> MCPServer` (same name as today, new return type), and the project running on `mcp[cli]>=2.2,<3`. Every later task builds on 2.x APIs.

- [ ] **Step 1: Reproduce the break that motivates this task**

Run: `uv run --with "mcp[cli]==2.2.0" --no-project python -c "from mcp.server.fastmcp import FastMCP"`
Expected: `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` mentioning the rename to `MCPServer`. This is what a fresh install of the project does today.

- [ ] **Step 2: Write the failing test** — replace the contents of `tests/test_mcp_app.py`'s server-construction test (keep other tests) with:

```python
def test_create_mcp_returns_mcpserver_with_project_version():
    from mcp.server.mcpserver import MCPServer
    from claw2immich.mcp_app import create_mcp
    from importlib.metadata import version

    mcp = create_mcp()

    assert isinstance(mcp, MCPServer)
    assert mcp.version == version("claw2immich")
```

- [ ] **Step 3: Run it and watch it fail**

Run: `uv run pytest tests/test_mcp_app.py -q -m "not integration"`
Expected: FAIL — import error for `mcp.server.mcpserver` (still on 1.26.0).

- [ ] **Step 4: Bump the dependency**

In `pyproject.toml` change `"mcp[cli]>=1.26.0"` to `"mcp[cli]>=2.2,<3"`. Then:

Run: `uv lock && uv sync`
Expected: lock updated to an `mcp` 2.x release.

- [ ] **Step 5: Migrate `mcp_app.py`**

```python
import logging
from importlib.metadata import version

from mcp.server.mcpserver import MCPServer

from .config import get_mcp_settings, get_transport_settings, get_external_domain
from .constants import build_server_instructions
from .prompts import register_prompts_and_resources
from .tooling import _register_tools

logger = logging.getLogger(__name__)

__version__ = version("claw2immich")


def _resolve_external_domain() -> str | None:
    return get_external_domain()


def create_mcp() -> MCPServer:
    logger.info("Creating MCP server")
    settings = get_mcp_settings()
    instructions = build_server_instructions(_resolve_external_domain())
    return MCPServer(
        "claw2immich",
        version=__version__,
        host=settings["host"],
        port=settings["port"],
        log_level=settings["log_level"],
        instructions=instructions,
    )
```

`run()` stays as it is: `mcp.run(transport=transport, mount_path=mount_path)`.

- [ ] **Step 6: Fix any other 1.x imports**

Run: `grep -rn "mcp.server.fastmcp\|from mcp import types\|mcp\.types" claw2immich/ tests/`
Change each hit: `mcp.types` → `mcp_types`; `mcp.server.fastmcp` → `mcp.server.mcpserver`. If a test constructs protocol models with camelCase fields (`inputSchema`, `readOnlyHint`), switch them to snake_case — 2.x renamed them.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass. If a failure is about `Tool.input_schema` vs `inputSchema`, it is the casing change — fix the test, not the SDK.

- [ ] **Step 8: Smoke-test a real startup**

Run:
```bash
IMMICH_BASE_URL=http://127.0.0.1:2283 IMMICH_API_KEY="$(sed -n 's/^IMMICH_API_KEY=//p' /container/compose/immich-app/immichmcp.tar.gz.env 2>/dev/null || true)" \
MCP_TRANSPORT=stdio timeout 20 uv run python main.py </dev/null
```
Expected: it starts, logs "Registering MCP tools", and exits on EOF without a traceback. (No key is needed for this check; unauthenticated startup is a valid path.)

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock claw2immich tests
git commit -m "feat!: migrate to MCP Python SDK 2.x and bound the dependency

pip install mcp now resolves to 2.x, where FastMCP was renamed MCPServer;
the unbounded >=1.26.0 pin meant a fresh source install was broken.

<trailer>"
```

---

### Task 2: Rename the package to mcp4immich

**Files:**
- Rename: `claw2immich/` → `mcp4immich/`
- Modify: `pyproject.toml`, `Dockerfile`, `docker-compose.yaml`, `main.py`, `README.md`, `CLAUDE.md`, `docs/usage-guide.md`, `.github/workflows/ci.yml`, `.github/workflows/build-docker.yml`, `helper/*.py`, all of `tests/`, `claw2immich/constants.py` (server instruction string)

**Interfaces:**
- Produces: every later task imports from `mcp4immich.*`; the MCP server name reported to clients becomes `mcp4immich`.

- [ ] **Step 1: Move the package with git so history follows**

```bash
git mv claw2immich mcp4immich
```

- [ ] **Step 2: Rewrite references**

```bash
grep -rl 'claw2immich' --exclude-dir=.git --exclude-dir=ai-docs --exclude-dir=docs/superpowers . \
  | xargs sed -i 's/claw2immich/mcp4immich/g'
```

Then check what that touched and fix anything wrong by hand:

Run: `git status --short && grep -rn 'mcp4immich' pyproject.toml Dockerfile docker-compose.yaml .github/workflows/*.yml | head -20`
Expected: `pyproject.toml` `name = "mcp4immich"` and the packages-find include; `Dockerfile` `COPY mcp4immich ./mcp4immich`; compose `image: mcp4immich:local`; CI `--cov=mcp4immich`. Historical references inside `ai-docs/` and the spec/plan under `docs/superpowers/` are left alone deliberately — they are records of the past.

- [ ] **Step 3: Keep the GHCR note honest** — in `README.md`, under the pre-built images section, replace the image paths with `ghcr.io/joeru/mcp4immich` and add this line:

```markdown
> Images published before 2026-09-20 live at `ghcr.io/joeru/claw2immich` and keep working; new tags are published under `mcp4immich`.
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass. A `ModuleNotFoundError: claw2immich` means a reference was missed — `grep -rn claw2immich tests/ mcp4immich/`.

- [ ] **Step 5: Verify the built image still starts**

Run: `docker compose build && docker run --rm --entrypoint sh mcp4immich:local -c 'uv run python -c "import mcp4immich, main; print(\"import ok\")"'`
Expected: `import ok`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor!: rename package claw2immich to mcp4immich

<trailer>"
```

---

### Task 3: Offline-safe spec resolution (disk cache → network → vendored)

**Files:**
- Create: `mcp4immich/specsource.py`, `mcp4immich/data/immich-openapi-3.json`, `tests/test_specsource.py`
- Modify: `mcp4immich/openapi.py` (replace the fetch body in `_fetch_openapi_spec`), `Dockerfile` (ship `mcp4immich/data`), `pyproject.toml` (package data)

**Interfaces:**
- Produces: `resolve_spec(version_tag: str, fetch: Callable[[str], dict], cache_dir: Path | None = None) -> tuple[dict, str]` returning `(spec, source)` where `source` is `"cache" | "network" | "vendored"`.
- Consumed by Task 4's classifier test, which reads the vendored file.

- [ ] **Step 1: Vendor the spec**

```bash
mkdir -p mcp4immich/data
curl -sfL -o mcp4immich/data/immich-openapi-3.json \
  https://raw.githubusercontent.com/immich-app/immich/v3.2.1/open-api/immich-openapi-specs.json
python3 -c "import json;d=json.load(open('mcp4immich/data/immich-openapi-3.json'));print(d['info']['version'], len(d['paths']))"
```
Expected: `3.2.1` and a path count around 150.

- [ ] **Step 2: Write the failing tests** — `tests/test_specsource.py`:

```python
import json
from pathlib import Path

import pytest

from mcp4immich.specsource import resolve_spec


def _fake_spec(marker: str) -> dict:
    return {"openapi": "3.1.0", "info": {"version": marker}, "paths": {}}


def test_uses_disk_cache_without_calling_network(tmp_path: Path):
    cached = tmp_path / "immich-v3.2.1.json"
    cached.write_text(json.dumps(_fake_spec("from-cache")))

    def fetch(url: str) -> dict:
        raise AssertionError("network must not be used when the cache is warm")

    spec, source = resolve_spec("v3.2.1", fetch, cache_dir=tmp_path)

    assert source == "cache"
    assert spec["info"]["version"] == "from-cache"


def test_network_result_is_written_to_cache(tmp_path: Path):
    spec, source = resolve_spec("v3.2.1", lambda url: _fake_spec("from-net"), cache_dir=tmp_path)

    assert source == "network"
    assert json.loads((tmp_path / "immich-v3.2.1.json").read_text())["info"]["version"] == "from-net"


def test_falls_back_to_vendored_when_network_fails(tmp_path: Path):
    def fetch(url: str) -> dict:
        raise OSError("no route to host")

    spec, source = resolve_spec("v3.2.1", fetch, cache_dir=tmp_path)

    assert source == "vendored"
    assert spec["paths"], "vendored spec must contain paths"


def test_corrupt_cache_is_ignored(tmp_path: Path):
    (tmp_path / "immich-v3.2.1.json").write_text("{not json")

    spec, source = resolve_spec("v3.2.1", lambda url: _fake_spec("from-net"), cache_dir=tmp_path)

    assert source == "network"
```

- [ ] **Step 3: Run them and watch them fail**

Run: `uv run pytest tests/test_specsource.py -q`
Expected: FAIL — `ModuleNotFoundError: mcp4immich.specsource`.

- [ ] **Step 4: Implement** — `mcp4immich/specsource.py`:

```python
"""Resolve the Immich OpenAPI spec: disk cache, then network, then vendored.

Startup must not depend on reaching raw.githubusercontent.com: an offline
restart used to leave the server with almost no tools, which looks exactly
like an Immich with no endpoints.
"""

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VENDORED_DIR = Path(__file__).parent / "data"
DEFAULT_CACHE_DIR = Path(os.getenv("MCP4IMMICH_SPEC_CACHE", "/app/.cache/openapi"))


def _cache_file(cache_dir: Path, version_tag: str) -> Path:
    return cache_dir / f"immich-{version_tag}.json"


def _vendored_file(version_tag: str) -> Path:
    major = version_tag.lstrip("v").split(".")[0] or "3"
    return VENDORED_DIR / f"immich-openapi-{major}.json"


def resolve_spec(
    version_tag: str,
    fetch: Callable[[str], dict[str, Any]],
    cache_dir: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (spec, source) with source in {"cache", "network", "vendored"}."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cached = _cache_file(cache_dir, version_tag)

    if cached.is_file():
        try:
            return json.loads(cached.read_text()), "cache"
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Ignoring unreadable spec cache {cached}: {exc}")

    url = (
        "https://raw.githubusercontent.com/immich-app/immich/"
        f"{version_tag}/open-api/immich-openapi-specs.json"
    )
    try:
        spec = fetch(url)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(spec))
        except OSError as exc:
            logger.warning(f"Could not write spec cache {cached}: {exc}")
        return spec, "network"
    except Exception as exc:
        logger.warning(f"Could not fetch spec for {version_tag} ({exc}); using vendored copy")

    vendored = _vendored_file(version_tag)
    spec = json.loads(vendored.read_text())
    vendored_version = spec.get("info", {}).get("version", "unknown")
    if not version_tag.lstrip("v").startswith(str(vendored_version)):
        logger.warning(
            f"Vendored spec is {vendored_version} but the server reports "
            f"{version_tag}; some endpoints may be missing or stale"
        )
    return spec, "vendored"
```

- [ ] **Step 5: Wire it into `openapi.py`** — inside `_fetch_openapi_spec`, replace the `httpx.Client` block that fetches `spec_url` with:

```python
    def _fetch(url: str) -> dict[str, Any]:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url)
        response.raise_for_status()
        return response.json()

    spec, source = resolve_spec(version_tag, _fetch)
    logger.info(f"OpenAPI spec source: {source} ({len(spec.get('paths', {}))} paths)")
```

Add `from .specsource import resolve_spec` at the top, and keep everything after (validation, return) as it is.

- [ ] **Step 6: Ship the data file** — in `pyproject.toml` add under `[tool.setuptools]`:

```toml
package-data = { "mcp4immich" = ["data/*.json"] }
```

and in `Dockerfile`, after `COPY mcp4immich ./mcp4immich`, add:

```dockerfile
ENV MCP4IMMICH_SPEC_CACHE=/app/.cache/openapi
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_specsource.py tests/ -q -m "not integration"`
Expected: all pass.

- [ ] **Step 8: Prove the offline path end to end**

Run: `docker compose build && docker run --rm --network none -e IMMICH_BASE_URL=http://127.0.0.1:2283 --entrypoint sh mcp4immich:local -c 'uv run python -c "
from mcp4immich.specsource import resolve_spec
def boom(url): raise OSError(\"offline\")
spec, source = resolve_spec(\"v3.2.1\", boom)
print(source, len(spec[\"paths\"]))"'`
Expected: `vendored` and a non-zero path count.

- [ ] **Step 9: Commit**

```bash
git add mcp4immich tests pyproject.toml Dockerfile
git commit -m "feat(spec): resolve OpenAPI spec from cache, network, then vendored copy

<trailer>"
```

---

### Task 4: Risk classifier

**Files:**
- Create: `mcp4immich/risk.py`, `tests/test_risk.py`

**Interfaces:**
- Consumes: `mcp4immich/data/immich-openapi-3.json` (Task 3) for the spec-wide test.
- Produces: `class Risk(StrEnum)` with members `READ`, `WRITE`, `DESTRUCTIVE`, `DESTRUCTIVE_ADMIN`; `classify(method: str, path: str) -> Risk`; `HIGH_RISK: frozenset[tuple[str, str]]`. Tasks 6, 7 and 8 import these.

- [ ] **Step 1: Write the failing tests** — `tests/test_risk.py`:

```python
import json
from pathlib import Path

import pytest

from mcp4immich.risk import Risk, classify

SPEC = json.loads((Path("mcp4immich/data/immich-openapi-3.json")).read_text())


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("GET", "/assets", Risk.READ),
        ("GET", "/search/suggestions", Risk.READ),
        ("POST", "/search/metadata", Risk.WRITE),
        ("PUT", "/assets/{id}", Risk.WRITE),
        ("POST", "/trash/restore", Risk.WRITE),
        ("DELETE", "/albums/{id}", Risk.DESTRUCTIVE),
        ("DELETE", "/albums/{id}/assets", Risk.DESTRUCTIVE),
        ("DELETE", "/memories/{id}/assets", Risk.DESTRUCTIVE),
        ("DELETE", "/tags/{id}/assets", Risk.DESTRUCTIVE),
        ("DELETE", "/stacks", Risk.DESTRUCTIVE),
        ("DELETE", "/assets", Risk.DESTRUCTIVE_ADMIN),
        ("DELETE", "/people", Risk.DESTRUCTIVE_ADMIN),
        ("POST", "/trash/empty", Risk.DESTRUCTIVE_ADMIN),
        ("POST", "/duplicates/resolve", Risk.DESTRUCTIVE_ADMIN),
        ("DELETE", "/admin/users/{id}", Risk.DESTRUCTIVE_ADMIN),
        ("DELETE", "/admin/database-backups", Risk.DESTRUCTIVE_ADMIN),
    ],
)
def test_classifies_known_operations(method, path, expected):
    assert classify(method, path) is expected


def test_method_case_does_not_matter():
    assert classify("delete", "/albums/{id}") is Risk.DESTRUCTIVE


def test_every_delete_in_the_spec_is_destructive():
    """A future Immich release must not be able to add an unguarded delete."""
    unguarded = [
        path
        for path, ops in SPEC["paths"].items()
        if "delete" in ops
        and classify("DELETE", path) not in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN)
    ]
    assert unguarded == []


def test_membership_removals_are_not_admin_class():
    """Removing assets from an album/tag/memory leaves the assets in place."""
    for path in (
        "/albums/{id}/assets",
        "/memories/{id}/assets",
        "/tags/{id}/assets",
        "/shared-links/{id}/assets",
    ):
        assert classify("DELETE", path) is Risk.DESTRUCTIVE
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/test_risk.py -q`
Expected: FAIL — `ModuleNotFoundError: mcp4immich.risk`.

- [ ] **Step 3: Implement** — `mcp4immich/risk.py`:

```python
"""Risk classification for Immich operations — the single source of truth.

Everything downstream (tool annotations, the confirm gate, tool hiding)
derives from `classify()`. The fallback for an unrecognised DELETE is
DESTRUCTIVE, never WRITE: an endpoint we have never seen must fail closed.
"""

from enum import StrEnum

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})

#: Operations that can destroy many originals at once, or affect other users.
#: An explicit list, not a shape heuristic: "DELETE without a trailing {id}"
#: would wrongly include membership removals such as DELETE /albums/{id}/assets.
HIGH_RISK: frozenset[tuple[str, str]] = frozenset(
    {
        ("DELETE", "/assets"),
        ("DELETE", "/people"),
        ("POST", "/trash/empty"),
        ("POST", "/duplicates/resolve"),
    }
)


class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    DESTRUCTIVE_ADMIN = "destructive_admin"


def classify(method: str, path: str) -> Risk:
    """Classify one OpenAPI operation by method and spec path (no base prefix)."""
    method = method.upper()
    path = "/" + path.lstrip("/")

    if method == "DELETE" and path.startswith("/admin/"):
        return Risk.DESTRUCTIVE_ADMIN

    if (method, path) in HIGH_RISK:
        return Risk.DESTRUCTIVE_ADMIN

    if method == "DELETE":
        return Risk.DESTRUCTIVE

    if method in WRITE_METHODS:
        return Risk.WRITE

    return Risk.READ
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_risk.py -q`
Expected: PASS, including the spec-wide delete test.

- [ ] **Step 5: Commit**

```bash
git add mcp4immich/risk.py tests/test_risk.py
git commit -m "feat(risk): classify every Immich operation by destructiveness

<trailer>"
```

---

### Task 5: Parameter value disclosure (backlog item #20)

**Files:**
- Modify: `mcp4immich/tooling.py` (the parameter-spec builder used for tool descriptions)
- Test: `tests/test_dedup_and_schema.py` (append)

**Interfaces:**
- Produces: generated tool descriptions state allowed values or an explicit free-text type for every parameter; no parameter is left as `query_type: unknown`.

- [ ] **Step 1: See the current behaviour**

Run: `grep -n "query_type\|unknown" mcp4immich/tooling.py mcp4immich/openapi.py | head -10`
Expected: the place where a parameter's type is rendered `unknown` when the schema has neither `type` nor `enum`. Note the function name — the next step edits it.

- [ ] **Step 2: Write the failing test** — append to `tests/test_dedup_and_schema.py`:

```python
def test_parameter_without_type_or_enum_is_described_as_free_text():
    from mcp4immich.tooling import _describe_parameter

    described = _describe_parameter({"name": "q", "in": "query", "schema": {}})

    assert "unknown" not in described
    assert "string" in described


def test_parameter_with_enum_lists_allowed_values():
    from mcp4immich.tooling import _describe_parameter

    described = _describe_parameter(
        {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["country", "city"]}}
    )

    assert "allowed: country, city" in described
```

- [ ] **Step 3: Run and watch it fail**

Run: `uv run pytest tests/test_dedup_and_schema.py -q`
Expected: FAIL — `_describe_parameter` does not exist yet.

- [ ] **Step 4: Implement** — add to `mcp4immich/tooling.py`:

```python
def _describe_parameter(param: dict[str, Any]) -> str:
    """One human/agent-readable line for a parameter.

    Backlog #20: parameters whose schema has neither `type` nor `enum` used to
    render as `query_type: unknown`, which forced agents to guess. They are now
    described as free text, and enums list their values.
    """
    schema = param.get("schema") or {}
    location = param.get("in", "query")
    name = param.get("name", "")
    enum_values = schema.get("enum")
    if enum_values:
        rendered = ", ".join(str(v) for v in enum_values)
        return f"{location}_{name} (allowed: {rendered})"
    declared = schema.get("type") or "string (free text)"
    return f"{location}_{name} ({declared})"
```

Then route the existing rendering through it. Find the call sites with:

```bash
grep -n "query_type\|param.get(\"name\")\|_param_line\|params:" mcp4immich/tooling.py | head
```

and replace each per-parameter string built inline with `_describe_parameter(param)`, so description text has exactly one implementation.

- [ ] **Step 5: Add the regression test over the real spec** — append to `tests/test_dedup_and_schema.py`:

```python
def test_no_spec_parameter_renders_as_unknown():
    import json
    from pathlib import Path

    from mcp4immich.tooling import _describe_parameter

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    rendered = [
        _describe_parameter(p)
        for ops in spec["paths"].values()
        for op in ops.values()
        if isinstance(op, dict)
        for p in op.get("parameters", [])
        if isinstance(p, dict)
    ]

    assert rendered, "spec should expose parameters"
    assert [r for r in rendered if "unknown" in r] == []
```

- [ ] **Step 6: Run the suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add mcp4immich/tooling.py tests/test_dedup_and_schema.py
git commit -m "fix(tools): describe parameter values instead of query_type unknown

Closes backlog item #20.

<trailer>"
```

---

### Task 6: Annotations on every generated tool

**Files:**
- Modify: `mcp4immich/tooling.py` (`_register_openapi_tools`, and the hand-written tool registrations in `_register_tools`)
- Test: `tests/test_policy.py` (create — annotation tests live here with the policy they describe)

**Interfaces:**
- Consumes: `Risk`, `classify` (Task 4).
- Produces: `annotations_for(risk: Risk, method: str) -> ToolAnnotations`, used at registration.

- [ ] **Step 1: Write the failing tests** — `tests/test_policy.py`:

```python
import pytest

from mcp4immich.risk import Risk
from mcp4immich.tooling import annotations_for


def test_read_tools_are_marked_read_only():
    ann = annotations_for(Risk.READ, "GET")
    assert ann.read_only_hint is True
    assert ann.destructive_hint is False


def test_destructive_tools_are_marked_destructive():
    for risk in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN):
        ann = annotations_for(risk, "DELETE")
        assert ann.read_only_hint is False
        assert ann.destructive_hint is True


def test_put_is_idempotent_and_post_is_not():
    assert annotations_for(Risk.WRITE, "PUT").idempotent_hint is True
    assert annotations_for(Risk.WRITE, "POST").idempotent_hint is False


def test_open_world_hint_is_false_everywhere():
    assert annotations_for(Risk.READ, "GET").open_world_hint is False
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/test_policy.py -q`
Expected: FAIL — `cannot import name 'annotations_for'`.

- [ ] **Step 3: Implement** — add to `mcp4immich/tooling.py`:

```python
from mcp_types import ToolAnnotations

from .risk import Risk, classify


def annotations_for(risk: Risk, method: str) -> ToolAnnotations:
    """MCP hints for a tool. Advisory only — clients may ignore or strip them,
    which is why the confirm gate, not these hints, is the enforcement point."""
    method = method.upper()
    destructive = risk in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN)
    if risk is Risk.READ:
        idempotent = True
    elif destructive:
        idempotent = method == "DELETE" and not _is_collection_delete(method, risk)
    else:
        idempotent = method == "PUT"
    return ToolAnnotations(
        read_only_hint=risk is Risk.READ,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=False,
    )


def _is_collection_delete(method: str, risk: Risk) -> bool:
    return method == "DELETE" and risk is Risk.DESTRUCTIVE_ADMIN
```

- [ ] **Step 4: Attach them at registration** — in `_register_openapi_tools`, replace the final registration line

```python
        mcp.tool(name=tool_name, description=description)(tool_func)
```

with

```python
        risk = classify(method, path)
        mcp.add_tool(
            tool_func,
            name=tool_name,
            description=description,
            annotations=annotations_for(risk, method),
        )
```

and in `_register_tools`, register the hand-written read-only tools with `annotations=annotations_for(Risk.READ, "GET")` (`ping_server`, `get_server_version`, `tool_access_report`, `write_capability_report`, `get_current_user`, `downloadAsset`).

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add mcp4immich/tooling.py tests/test_policy.py
git commit -m "feat(tools): annotate every tool with MCP risk hints

<trailer>"
```

---

### Task 7: Risk policy middleware — confirm gate and hidden admin class

**Files:**
- Create: `mcp4immich/policy.py`
- Modify: `mcp4immich/mcp_app.py` (attach middleware), `mcp4immich/tooling.py` (`tool_access_report`, registration of the admin class), `mcp4immich/config.py` (new env var)
- Test: `tests/test_policy.py` (append)

**Interfaces:**
- Consumes: `Risk`, `classify` (Task 4); `annotations_for` (Task 6).
- Produces: `destructive_enabled() -> bool` in `config.py`; `RiskPolicyMiddleware(risk_by_tool: dict[str, Risk])` in `policy.py`; `TOOL_RISK: dict[str, Risk]` populated during registration and read by `tool_access_report`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_policy.py`:

```python
import pytest

from mcp4immich.policy import CONFIRMATION_REQUIRED, RiskPolicyMiddleware
from mcp4immich.risk import Risk


class _Ctx:
    def __init__(self, method, params):
        self.method = method
        self.params = params


@pytest.mark.anyio
async def test_destructive_call_without_confirm_is_refused_and_never_dispatched():
    dispatched = []

    async def call_next(ctx):
        dispatched.append(ctx)
        return {"unexpected": True}

    mw = RiskPolicyMiddleware({"immich_deleteassets": Risk.DESTRUCTIVE_ADMIN})
    result = await mw(_Ctx("tools/call", {"name": "immich_deleteassets", "arguments": {}}), call_next)

    assert result["error"] == CONFIRMATION_REQUIRED
    assert result["risk"] == "destructive_admin"
    assert dispatched == [], "the handler must not run"


@pytest.mark.anyio
async def test_destructive_call_with_confirm_is_dispatched():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_deletealbum": Risk.DESTRUCTIVE})
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {"confirm": True}}),
        call_next,
    )

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_refusal_includes_what_would_be_called_and_a_preview():
    async def call_next(ctx):
        raise AssertionError("must not dispatch")

    mw = RiskPolicyMiddleware(
        {"immich_deletealbum": Risk.DESTRUCTIVE},
        operation_by_tool={"immich_deletealbum": ("DELETE", "/albums/{id}")},
        sibling_get=lambda path, args: {"id": args["path_id"], "name": "Holiday 2024"},
    )
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {"path_id": "a-1"}}),
        call_next,
    )

    assert result["would_call"] == "DELETE /albums/{id}"
    assert result["preview"]["name"] == "Holiday 2024"


@pytest.mark.anyio
async def test_failing_preview_still_refuses():
    def boom(path, args):
        raise RuntimeError("immich unreachable")

    mw = RiskPolicyMiddleware(
        {"immich_deletealbum": Risk.DESTRUCTIVE},
        operation_by_tool={"immich_deletealbum": ("DELETE", "/albums/{id}")},
        sibling_get=boom,
    )
    result = await mw(
        _Ctx("tools/call", {"name": "immich_deletealbum", "arguments": {}}), lambda ctx: None
    )

    assert result["error"] == CONFIRMATION_REQUIRED
    assert result["preview"] is None


@pytest.mark.anyio
async def test_read_tools_pass_straight_through():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_getallalbums": Risk.READ})
    result = await mw(
        _Ctx("tools/call", {"name": "immich_getallalbums", "arguments": {}}), call_next
    )

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_unknown_tool_is_not_gated():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({})
    result = await mw(_Ctx("tools/call", {"name": "something_else", "arguments": {}}), call_next)

    assert result == {"ok": True}


@pytest.mark.anyio
async def test_non_tool_calls_pass_through():
    async def call_next(ctx):
        return {"ok": True}

    mw = RiskPolicyMiddleware({"immich_deleteassets": Risk.DESTRUCTIVE_ADMIN})
    result = await mw(_Ctx("resources/list", {}), call_next)

    assert result == {"ok": True}
```

Add to `pyproject.toml` dev group if not present: `"anyio>=4"`, and a `tests/conftest.py` fixture:

```python
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/test_policy.py -q`
Expected: FAIL — `ModuleNotFoundError: mcp4immich.policy`.

- [ ] **Step 3: Implement** — `mcp4immich/policy.py`:

```python
"""Server middleware enforcing the destructive-operation policy.

MCP tool annotations are advisory: the specification tells clients to treat
them as untrusted, and proxies strip them. This middleware is the enforcement
point — it sees every `tools/call` before the handler runs.
"""

import logging
from typing import Any

from .risk import Risk

logger = logging.getLogger(__name__)

CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"

GATED = (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN)


class RiskPolicyMiddleware:
    """Refuse destructive tool calls that are not explicitly confirmed."""

    def __init__(self, risk_by_tool: dict[str, Risk]):
        self._risk_by_tool = risk_by_tool

    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        if getattr(ctx, "method", None) != "tools/call":
            return await call_next(ctx)

        params = getattr(ctx, "params", None) or {}
        name = params.get("name") if isinstance(params, dict) else None
        risk = self._risk_by_tool.get(name)
        if risk not in GATED:
            return await call_next(ctx)

        arguments = (params.get("arguments") if isinstance(params, dict) else None) or {}
        if arguments.get("confirm") is True:
            return await call_next(ctx)

        logger.info(f"Refused unconfirmed destructive call to {name}")
        return {
            "ok": False,
            "error": CONFIRMATION_REQUIRED,
            "risk": str(risk),
            "tool": name,
            "would_call": self._describe_call(name),
            "preview": self._preview(name, arguments),
            "hint": "This call can destroy data. Re-send with confirm=true to proceed.",
        }

    def _describe_call(self, name: str) -> str | None:
        operation = self._operation_by_tool.get(name)
        return f"{operation[0]} {operation[1]}" if operation else None

    def _preview(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """Best effort: for a by-id delete with a sibling GET, show what would go.

        Never mutating, never fatal: any failure yields None so the refusal
        itself is never blocked by a failed preview.
        """
        operation = self._operation_by_tool.get(name)
        if not operation or not self._sibling_get:
            return None
        method, path = operation
        if method != "DELETE" or "{" not in path:
            return None
        try:
            return self._sibling_get(path, arguments)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Preview for {name} failed: {exc}")
            return None
```

The constructor takes the two extra maps:

```python
    def __init__(
        self,
        risk_by_tool: dict[str, Risk],
        operation_by_tool: dict[str, tuple[str, str]] | None = None,
        sibling_get: Any = None,
    ):
        self._risk_by_tool = risk_by_tool
        self._operation_by_tool = operation_by_tool or {}
        self._sibling_get = sibling_get
```

`sibling_get(path, arguments)` is supplied by `tooling.py` as a small function that substitutes the `{id}` path parameters from `arguments` and issues the GET through the existing `_request`, returning the identifying fields (`id`, and whichever of `originalFileName`/`name`/`title` exists). Registration records `TOOL_OPERATION[tool_name] = (method, path)` next to `TOOL_RISK`.

- [ ] **Step 4: Run the policy tests**

Run: `uv run pytest tests/test_policy.py -q`
Expected: PASS.

- [ ] **Step 5: Record risk per tool and hide the admin class** — in `mcp4immich/config.py` add:

```python
def destructive_enabled() -> bool:
    """Whether DESTRUCTIVE_ADMIN tools are registered at all."""
    return os.getenv("IMMICH_ENABLE_DESTRUCTIVE", "").strip().lower() in ("1", "true", "yes")
```

In `mcp4immich/tooling.py`, add a module-level `TOOL_RISK: dict[str, Risk] = {}`, and in `_register_openapi_tools` replace the block from Task 6 with:

```python
        risk = classify(method, path)
        if risk is Risk.DESTRUCTIVE_ADMIN and not destructive_enabled():
            blocked_admin.append(tool_name)
            continue
        TOOL_RISK[tool_name] = risk
        mcp.add_tool(
            tool_func,
            name=tool_name,
            description=_with_confirm_note(description, risk),
            annotations=annotations_for(risk, method),
        )
```

with

```python
def _with_confirm_note(description: str, risk: Risk) -> str:
    if risk in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN):
        return description + " DESTRUCTIVE: pass confirm=true to actually perform this call."
    return description
```

and `blocked_admin: list[str] = []` initialised beside `used_names`. After the loop, log `f"{len(blocked_admin)} destructive-admin tools hidden (set IMMICH_ENABLE_DESTRUCTIVE=true to expose them)"` when the list is non-empty, and store it in a module-level `HIDDEN_ADMIN_TOOLS` list.

- [ ] **Step 6: Report the policy to agents** — in `tool_access_report`, add to the returned dict:

```python
        "destructive_enabled": destructive_enabled(),
        "risk": {name: str(risk) for name, risk in TOOL_RISK.items()},
        "hidden_destructive_admin": [
            {
                "tool": name,
                "reason": "Destructive-admin endpoint disabled (set IMMICH_ENABLE_DESTRUCTIVE=true)",
            }
            for name in HIDDEN_ADMIN_TOOLS
        ],
```

- [ ] **Step 7: Attach the middleware** — in `mcp4immich/mcp_app.py`:

```python
from .policy import RiskPolicyMiddleware
from .tooling import TOOL_RISK
```

and in `run()`, build the server *after* tools are registered so the risk map is populated:

```python
def run() -> None:
    logger.info("Starting MCP server run loop")
    mcp = create_mcp()
    register_prompts_and_resources(mcp)
    _register_tools(mcp)
    mcp.middleware = [RiskPolicyMiddleware(TOOL_RISK)]

    transport, mount_path = get_transport_settings()
    logger.info(f"Using transport: {transport}")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("MCP_TRANSPORT must be stdio, sse, or streamable-http")
    mcp.run(transport=transport, mount_path=mount_path)
```

If assigning `mcp.middleware` after construction is rejected by the SDK, construct the server with `middleware=[RiskPolicyMiddleware(TOOL_RISK)]` instead and populate `TOOL_RISK` before `create_mcp()` by calling `_openapi_tool_access()` first — the risk map only needs the operation list, not the registered tools. Note in the commit which form was used.

- [ ] **Step 8: Add a registration test** — append to `tests/test_policy.py`:

```python
def test_admin_class_is_hidden_unless_enabled(monkeypatch):
    monkeypatch.delenv("IMMICH_ENABLE_DESTRUCTIVE", raising=False)
    from mcp4immich.config import destructive_enabled

    assert destructive_enabled() is False

    monkeypatch.setenv("IMMICH_ENABLE_DESTRUCTIVE", "true")
    assert destructive_enabled() is True
```

- [ ] **Step 9: Run the suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add mcp4immich tests
git commit -m "feat(policy): require confirm for destructive tools, hide the admin class

<trailer>"
```

---

### Task 8: Elicitation for clients that support it

**Files:**
- Create: `mcp4immich/confirm.py`, `tests/test_confirm.py`
- Modify: `mcp4immich/policy.py`

**Interfaces:**
- Consumes: `CONFIRMATION_REQUIRED`, `RiskPolicyMiddleware` (Task 7).
- Produces: `async def ask_confirmation(ctx, tool_name: str, risk: Risk) -> bool` — True only on an explicit accept.

- [ ] **Step 1: Write the failing tests** — `tests/test_confirm.py`:

```python
import pytest

from mcp4immich.confirm import ask_confirmation
from mcp4immich.risk import Risk


class _Elicitor:
    def __init__(self, action, supported=True):
        self._action = action
        self._supported = supported
        self.asked = None

    def client_capabilities(self):
        return {"elicitation": {}} if self._supported else {}

    async def elicit(self, message, schema):
        self.asked = message

        class _Result:
            action = self._action
            data = None

        return _Result()


@pytest.mark.anyio
async def test_accept_confirms():
    ctx = _Elicitor("accept")
    assert await ask_confirmation(ctx, "immich_deleteassets", Risk.DESTRUCTIVE_ADMIN) is True
    assert "immich_deleteassets" in ctx.asked


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["decline", "cancel"])
async def test_decline_and_cancel_refuse(action):
    ctx = _Elicitor(action)
    assert await ask_confirmation(ctx, "immich_deletealbum", Risk.DESTRUCTIVE) is False


@pytest.mark.anyio
async def test_client_without_capability_refuses_without_asking():
    ctx = _Elicitor("accept", supported=False)
    assert await ask_confirmation(ctx, "immich_deletealbum", Risk.DESTRUCTIVE) is False
    assert ctx.asked is None


@pytest.mark.anyio
async def test_elicitation_failure_refuses():
    class _Broken(_Elicitor):
        async def elicit(self, message, schema):
            raise RuntimeError("transport gone")

    assert await ask_confirmation(_Broken("accept"), "immich_deletealbum", Risk.DESTRUCTIVE) is False
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/test_confirm.py -q`
Expected: FAIL — `ModuleNotFoundError: mcp4immich.confirm`.

- [ ] **Step 3: Implement** — `mcp4immich/confirm.py`:

```python
"""Ask the human to confirm a destructive call, where the client supports it.

This never widens what is permitted: a model can set confirm=true by itself,
but it cannot answer an elicitation on the user's behalf. A client that does
not support elicitation simply falls back to the confirm parameter.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from .risk import Risk

logger = logging.getLogger(__name__)


class ConfirmDestructive(BaseModel):
    confirm: bool = Field(
        default=False,
        description="Yes, perform this destructive operation.",
    )


def _supports_elicitation(ctx: Any) -> bool:
    try:
        capabilities = ctx.client_capabilities()
    except Exception:
        return False
    if capabilities is None:
        return False
    if isinstance(capabilities, dict):
        return bool(capabilities.get("elicitation"))
    return getattr(capabilities, "elicitation", None) is not None


async def ask_confirmation(ctx: Any, tool_name: str, risk: Risk) -> bool:
    """True only when the human explicitly accepted."""
    if not _supports_elicitation(ctx):
        return False

    severity = (
        "This can delete many items at once and cannot be undone by this server."
        if risk is Risk.DESTRUCTIVE_ADMIN
        else "This deletes data in Immich."
    )
    try:
        result = await ctx.elicit(
            f"Run the destructive tool {tool_name}? {severity}",
            ConfirmDestructive,
        )
    except Exception as exc:
        logger.warning(f"Elicitation failed for {tool_name}: {exc}")
        return False

    action = getattr(result, "action", None)
    if action != "accept":
        logger.info(f"Destructive call to {tool_name} was {action or 'not accepted'}")
        return False

    data = getattr(result, "data", None)
    if data is None:
        return True
    return bool(getattr(data, "confirm", True))
```

- [ ] **Step 4: Use it in the middleware** — in `policy.py`, change the refusal branch to try elicitation first:

```python
        arguments = (params.get("arguments") if isinstance(params, dict) else None) or {}
        if arguments.get("confirm") is True:
            return await call_next(ctx)

        if await ask_confirmation(ctx, name, risk):
            return await call_next(ctx)

        logger.info(f"Refused unconfirmed destructive call to {name}")
```

with `from .confirm import ask_confirmation` at the top. The existing middleware tests pass `_Ctx` objects that have no `client_capabilities`, so `_supports_elicitation` returns False and they keep asserting refusal — which is the fallback behaviour we want.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add mcp4immich tests
git commit -m "feat(policy): ask the human via elicitation before destructive calls

<trailer>"
```

---

### Task 9: Immich version compatibility for moved endpoints

**Files:**
- Create: `mcp4immich/compat.py`, `tests/test_compat.py`
- Modify: `mcp4immich/config.py` (`get_external_domain`), `mcp4immich/constants.py` (instruction text)

**Interfaces:**
- Produces: `endpoint(name: str, major: int) -> str` and `server_major(probe: Callable[[], dict] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests** — `tests/test_compat.py`:

```python
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
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/test_compat.py -q`
Expected: FAIL — `ModuleNotFoundError: mcp4immich.compat`.

- [ ] **Step 3: Implement** — `mcp4immich/compat.py`:

```python
"""Immich endpoints that moved between major versions.

Only endpoints that actually moved belong here. `/api/server-config` became
`/api/server/config` in Immich 3.x; calling the old path on a 3.x server
returns 404, which silently disabled external-domain discovery and made every
web_url point at the internal base URL.
"""

import logging

logger = logging.getLogger(__name__)

_ENDPOINTS: dict[str, dict[int, str]] = {
    "server_config": {2: "/api/server-config", 3: "/api/server/config"},
}


def endpoint(name: str, major: int) -> str:
    by_major = _ENDPOINTS[name]
    if major in by_major:
        return by_major[major]
    newest = max(by_major)
    if major > newest:
        logger.info(f"Immich major {major} is newer than known; using the {newest} path for {name}")
        return by_major[newest]
    oldest = min(by_major)
    return by_major[oldest]
```

- [ ] **Step 4: Use it** — in `mcp4immich/config.py`'s `get_external_domain`, replace the hardcoded call

```python
        payload = _request("GET", "/api/server-config")
```

with

```python
        from .compat import endpoint
        from .openapi import _server_major

        payload = _request("GET", endpoint("server_config", _server_major()))
```

and add to `mcp4immich/openapi.py`:

```python
def _server_major() -> int:
    """Immich major version, defaulting to the newest supported when unknown."""
    try:
        payload = _request("GET", "/api/server/version")
        return int(payload["major"])
    except Exception as exc:
        logger.warning(f"Could not read Immich major version ({exc}); assuming 3")
        return 3
```

In `constants.py`, change the instruction fallback text `"or call GET /api/server-config and read externalDomain. "` to `"or call the server config endpoint and read externalDomain. "` so the string cannot go stale again.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q -m "not integration"`
Expected: all pass.

- [ ] **Step 6: Verify against the live server**

Run:
```bash
IMMICH_BASE_URL=http://127.0.0.1:2283 \
IMMICH_API_KEY="$(sed -n 's/^IMMICH_API_KEY=//p' /container/compose/immich-app/ImmichMCP/.env 2>/dev/null)" \
uv run python -c "
from mcp4immich.config import get_external_domain
print('external domain:', get_external_domain())"
```
Expected: it prints a domain and the log shows no 404 for the config endpoint. If the key file is gone, extract it from the archive instead: `tar -xzOf /container/compose/immich-app/immichmcp.tar.gz ImmichMCP/.env | sed -n 's/^IMMICH_API_KEY=//p'`. Never echo the key itself.

- [ ] **Step 7: Commit**

```bash
git add mcp4immich tests
git commit -m "fix(compat): use the Immich 3.x server config endpoint

<trailer>"
```

---

### Task 10: Health route, version, docs, CI and release

**Files:**
- Modify: `mcp4immich/mcp_app.py` (`/healthz`), `pyproject.toml` (version 1.0.0), `README.md`, `.github/workflows/ci.yml`, `.github/workflows/build-docker.yml`
- Create: `CHANGELOG.md`, `tests/test_protocol_eras.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `GET /healthz` returning `{"status","immich_reachable","spec_source","version"}`; a tagged 1.0.0 release.

- [ ] **Step 1: Write the failing protocol-era test** — `tests/test_protocol_eras.py`:

```python
import pytest

from mcp4immich.mcp_app import create_mcp


@pytest.mark.anyio
async def test_server_reports_project_version_not_sdk_version():
    from importlib.metadata import version

    mcp = create_mcp()

    assert mcp.version == version("mcp4immich")
    assert not mcp.version.startswith("2."), "that would be the SDK's version"


@pytest.mark.anyio
async def test_serves_both_protocol_eras():
    """2.x serves the current revision and 2025-era clients from one server."""
    from mcp.client import Client  # if this import path differs, adjust it here only
    from mcp4immich.tooling import _register_tools

    mcp = create_mcp()
    _register_tools(mcp)

    for protocol_version in ("2026-07-28", "2025-06-18"):
        async with Client(mcp, protocol_version=protocol_version) as client:
            tools = await client.list_tools()
            assert tools, f"no tools served for {protocol_version}"


@pytest.mark.anyio
async def test_tools_list_is_deterministically_ordered():
    """The current spec asks for stable ordering so clients can cache prompts."""
    mcp = create_mcp()
    from mcp4immich.tooling import _register_tools

    _register_tools(mcp)
    first = [t.name for t in await mcp.list_tools()]
    second = [t.name for t in await mcp.list_tools()]

    assert first == second
```

- [ ] **Step 2: Confirm the in-memory client API before running**

Run: `uv run python -c "
import mcp.client as c, inspect
print([n for n in dir(c) if 'Client' in n])
import mcp.client as m; print(inspect.signature(m.Client.__init__) if hasattr(m,'Client') else 'no Client')"`
Expected: a `Client` class and its signature. If the import path or the keyword for the protocol version differs from the test above, fix those two lines in the test — the assertions stay the same.

- [ ] **Step 3: Run and watch it fail**

Run: `uv sync && uv run pytest tests/test_protocol_eras.py -q`
Expected: FAIL on the version assertion until `pyproject.toml` says 1.0.0.

- [ ] **Step 4: Set the version and changelog**

`pyproject.toml`: `version = "1.0.0"`. Create `CHANGELOG.md`:

```markdown
# Changelog

## 1.0.0 — 2026-09-20

First release where the git tag, the published image and the version the
server reports to clients all agree.

### Breaking
- Package, server name and image renamed `claw2immich` → `mcp4immich`.
- Destructive tools require `confirm=true` (or an accepted elicitation).
- Tools that can destroy many items at once are not registered unless
  `IMMICH_ENABLE_DESTRUCTIVE=true`: `DELETE /assets`, `DELETE /people`,
  `POST /trash/empty`, `POST /duplicates/resolve`, and every `DELETE /admin/*`.
- Runs on MCP Python SDK 2.x and speaks protocol revision 2026-07-28; older
  clients are still served by the same server.
- `serverInfo.version` now reports the project version, not the SDK's.

### Added
- Risk classification for every generated tool, with MCP annotations.
- Elicitation-based confirmation where the client supports it.
- OpenAPI spec resolution from disk cache, network, then a vendored copy, so
  startup works offline.
- `GET /healthz` for container and monitoring probes.

### Fixed
- External-domain discovery used the Immich 2.x `/api/server-config` path and
  404'd on 3.x, so `web_url` links pointed at the internal base URL.
- Parameters with no schema type no longer render as `query_type: unknown`
  (backlog #20).
- The `mcp` dependency is bounded (`>=2.2,<3`); the previous unbounded pin
  meant a fresh install resolved to an incompatible major.
```

- [ ] **Step 5: Add the health route** — in `mcp4immich/mcp_app.py`, inside `create_mcp()` before the return:

```python
    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):  # noqa: ANN001 - starlette request
        from starlette.responses import JSONResponse

        from .http_client import _probe

        reachable = bool(_probe("GET", "/api/server/ping").get("ok"))
        return JSONResponse(
            {
                "status": "ok",
                "immich_reachable": reachable,
                "version": __version__,
            }
        )
```

(assign the constructed `MCPServer` to `server`, register the route, then `return server`).

- [ ] **Step 6: Update CI**

In `.github/workflows/ci.yml` the coverage flag is already `--cov=mcp4immich` after Task 2; add a job step after the tests:

```yaml
      - name: Assert the dependency pin is bounded
        run: |
          grep -q 'mcp\[cli\]>=2.2,<3' pyproject.toml || {
            echo "mcp dependency must keep an upper bound (see CHANGELOG 1.0.0)"; exit 1; }
```

In `.github/workflows/build-docker.yml`, ensure the image is tagged from the git tag as well as `latest`, and that it pushes to `ghcr.io/joeru/mcp4immich`.

- [ ] **Step 7: Update the README**

- Replace the tool-list section's claim that the tool set is "a small, permission-aware tool set for common read-only checks" with the truth: ~282 generated tools, permission-filtered, risk-classified.
- Add a **Safety** section documenting `confirm`, `IMMICH_ENABLE_DESTRUCTIVE`, and the hidden class.
- Add a **Security** section: binding to `0.0.0.0` lets Docker's DNAT bypass host firewalls; bind to a VPN address; the process holds a full Immich API key.
- Add `IMMICH_ENABLE_DESTRUCTIVE` and `MCP4IMMICH_SPEC_CACHE` to the environment-variable table.

- [ ] **Step 8: Run everything**

Run: `uv run pytest tests/ -q -m "not integration"` then `docker compose build`
Expected: tests pass; image builds.

- [ ] **Step 9: Run the live integration suite once**

Run:
```bash
IMMICH_BASE_URL=http://127.0.0.1:2283 \
IMMICH_API_KEY="$(tar -xzOf /container/compose/immich-app/immichmcp.tar.gz ImmichMCP/.env | sed -n 's/^IMMICH_API_KEY=//p')" \
uv run pytest tests/ -q -m integration
```
Expected: pass. These are read-only/permission tests; no destructive tool is confirmed. If a test calls a destructive tool, stop and report — that is a bug in the test, not a thing to confirm.

- [ ] **Step 10: Commit and tag**

```bash
git add -A
git commit -m "release: mcp4immich 1.0.0

<trailer>"
git tag -a v1.0.0 -m "mcp4immich 1.0.0"
```

Do **not** push yet — pushing and publishing the GitHub release is part of Task 11, which stops for the user first.

---

### Task 11: Deploy here, monitored (STOPS FOR APPROVAL FIRST)

**Files:**
- Modify: `docker-compose.yaml`, `/container/compose/prometheus/prometheus.yml`, `/container/compose/prometheus/rules/alert.rules`, `/root/my.jru.me/CLAUDE.md`
- Rename: the local checkout directory `/container/compose/immich-app/claw2immich` → `mcp4immich`

**This task changes production and publishes a release. Present the state to the user and get an explicit go-ahead before step 1.**

- [ ] **Step 1: Push the branch and publish the release**

```bash
git push -u origin feat/safety-rails-and-release
git push origin v1.0.0
gh release create v1.0.0 --title "mcp4immich 1.0.0" --notes-file CHANGELOG.md
```

- [ ] **Step 2: Local compose for this host**

```yaml
services:
  mcp:
    build:
      context: .
      dockerfile: Dockerfile
    image: mcp4immich:local
    container_name: mcp4immich
    restart: unless-stopped
    ports:
      - "192.168.176.224:8000:8000"
    environment:
      IMMICH_BASE_URL: ${IMMICH_BASE_URL:-http://immich_server:2283}
      IMMICH_API_KEY: ${IMMICH_API_KEY:?Set IMMICH_API_KEY in .env}
      IMMICH_ALLOW_HTTP: "true"
      MCP_TRANSPORT: ${MCP_TRANSPORT:-streamable-http}
      MCP_HOST: 0.0.0.0
      MCP_PORT: 8000
      MCP_LOG_LEVEL: ${MCP_LOG_LEVEL:-INFO}
    networks:
      - immich
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz').read()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

networks:
  immich:
    external: true
    name: immich_default
```

Create `.env` beside it with `IMMICH_API_KEY=` taken from the archive (never echoed):
```bash
tar -xzOf /container/compose/immich-app/immichmcp.tar.gz ImmichMCP/.env | sed -n 's/^IMMICH_API_KEY=/IMMICH_API_KEY=/p' > .env
chmod 600 .env
```

- [ ] **Step 3: Start and verify**

```bash
docker compose up -d --build
sleep 20
docker compose ps
curl -s http://192.168.176.224:8000/healthz
```
Expected: healthy; `{"status":"ok","immich_reachable":true,...}`.

Then exercise the policy over MCP:
```bash
U=http://192.168.176.224:8000/mcp
H='-H Content-Type:application/json -H Accept:application/json,text/event-stream'
SID=$(curl -s -D - -o /dev/null $H $U -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}' | sed -n 's/^[Mm]cp-[Ss]ession-[Ii]d: *//p' | tr -d '\r')
curl -s $H -H "mcp-session-id: $SID" $U -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
curl -s $H -H "mcp-session-id: $SID" $U -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | sed -n 's/^data: //p' | python3 -c "
import json,sys
t=json.loads(sys.stdin.read())['result']['tools']
names=[x['name'] for x in t]
print('tools:',len(names))
print('admin class hidden:', not any('deleteassets' in n.lower() for n in names))"
```
Expected: a tool count, and the admin class hidden.

- [ ] **Step 4: Monitoring**

Back up first (`cp prometheus.yml prometheus.yml.bak-2026-09-20`, same for `rules/alert.rules`), then add a blackbox job `mcp4immich` probing `http://192.168.176.224:8000/healthz` with module `http_2xx` (same relabel shape as the retired `immichmcp` job, which the git history of `prometheus.yml` still shows), and an alert:

```yaml
  - name: mcp4immich
    rules:
      - alert: Mcp4ImmichDown
        expr: probe_success{job="mcp4immich"} == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "mcp4immich is not answering its health probe"
          description: "{{ $labels.instance }} has failed /healthz for 10 minutes. Check `docker logs mcp4immich` and immich_server."
```

Validate and reload:
```bash
docker run --rm -v /container/compose/prometheus/rules:/rules:ro --entrypoint promtool prom/prometheus:latest check rules /rules/alert.rules
docker compose -f /container/compose/prometheus/docker-compose.yml restart prom
```
Expected: `SUCCESS`, and after a minute `probe_success{job="mcp4immich"}` is 1.

- [ ] **Step 5: Rename the local directory**

```bash
cd /container/compose/immich-app
docker compose -f mcp4immich/docker-compose.yaml down 2>/dev/null || docker compose -f claw2immich/docker-compose.yaml down
mv claw2immich mcp4immich
cd mcp4immich && docker compose up -d --build
```

- [ ] **Step 6: Document on my.jru.me**

Update the Immich MCP section in `/root/my.jru.me/CLAUDE.md`: mcp4immich is deployed at `192.168.176.224:8000` (`/mcp`, `/healthz`), runs 1.0.0, destructive tools need `confirm=true`, the admin class needs `IMMICH_ENABLE_DESTRUCTIVE=true`, alert `Mcp4ImmichDown`. Commit it (this repo is the user's own checkout — a worktree branch plus a fast-forward command, as before).

- [ ] **Step 7: Rollback if needed**

```bash
cd /container/compose/immich-app/mcp4immich && docker compose down
git checkout main
cp /container/compose/prometheus/prometheus.yml.bak-2026-09-20 /container/compose/prometheus/prometheus.yml
cp /container/compose/prometheus/rules/alert.rules.bak-2026-09-20 /container/compose/prometheus/rules/alert.rules
docker compose -f /container/compose/prometheus/docker-compose.yml restart prom
```
