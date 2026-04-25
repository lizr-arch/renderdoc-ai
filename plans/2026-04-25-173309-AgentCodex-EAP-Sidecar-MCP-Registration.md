# EAP Sidecar MCP Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the Phase 3 `.rmeta.json` loader behind a new read-only MCP surface without
touching legacy RDC open/analyze tools.

**Architecture:** Keep `tools/mcp/providers/sidecar_loader.py` as the path-to-dict primitive. Add a
small pure adapter that converts loader success/failure into `mcp-query.v1` envelopes, then register
that adapter in a new read-only MCP server under `tools/mcp/mcp_server/`. The new server must require
an allowlist from configuration for path loading and must return sidecar summaries plus Data
Availability, not raw full sidecar payloads.

**Tech Stack:** Python 3.11 via `py -3`, pytest, existing `mcp.server.fastmcp.FastMCP` pattern,
existing `tools/mcp/providers` registry and `tools/mcp/snapshot_consumer.py` envelope helpers.

---

## Scope / Assumptions

Mainline ownership: intelligent collaboration line, MCP sub-area.

Contract dependencies:

| Contract | Usage |
| --- | --- |
| `docs/product/development_charter.md` | MCP is realtime/query/fill, not a report generator. |
| `docs/product/mcp_query_contract_v1.md` | Tool responses use `mcp-query.v1` envelope semantics. |
| `docs/EAP/EAP_MCP_PROVIDER_REFACTOR_PLAN.md` | Phase 4 is separate from loader-only Phase 3. |
| `docs/EAP/EAP_MCP_DATA_MODEL.md` | Loaded sidecar data must feed ProviderRegistry Data Availability. |

Out of scope:

- No changes to RenderDoc core, qrenderdoc, replay, or `.rdc` parsing.
- Do not register in `scripts/rdc_mcp/rdc_mcp.py`; that legacy server opens `.rdc` files and can
  generate reports.
- Do not return the full sidecar JSON from MCP by default.
- Do not allow arbitrary path reads. MCP registration must require configured allowlist roots.
- Do not add dependency installation steps.

## File Map

| File | Role |
| --- | --- |
| `tools/mcp/mcp_server/provider_tools.py` | New pure adapter: sidecar load envelope, error mapping, allowlist parsing, sidecar summary. |
| `tools/mcp/mcp_server/provider_readonly_server.py` | New FastMCP registration surface for read-only provider tools. |
| `tools/mcp/tests/test_provider_mcp_tools.py` | New adapter tests for success, allowlist failure, loader error mapping, and data availability. |
| `tools/mcp/tests/test_provider_readonly_server.py` | New server registration tests using an injected fake FastMCP class. |
| `docs/EAP/EAP_MCP_PROVIDER_REFACTOR_PLAN.md` | Update Phase 4 section with concrete registered tool names and safety boundary. |
| `docs/EAP/EAP_MCP_DATA_MODEL.md` | Document MCP tool output shape and confirm full sidecar payload is not returned. |

## Build / Test / Lint Quick Guide

Record these in `/plan`; run them during `/do`.

```powershell
py -3 -m pytest tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py -q
py -3 -m pytest tools\mcp\tests\test_snapshot_consumer.py tools\mcp\tests\test_provider_registry.py tools\mcp\tests\test_provider_routing.py tools\mcp\tests\test_sidecar_loader.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py -q
py -3 -m py_compile tools\mcp\mcp_server\provider_tools.py tools\mcp\mcp_server\provider_readonly_server.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py
git diff --check -- tools\mcp docs\EAP\EAP_MCP_PROVIDER_REFACTOR_PLAN.md docs\EAP\EAP_MCP_DATA_MODEL.md
```

Expected:

- Focused tests pass.
- Existing provider and snapshot consumer tests remain green.
- `py_compile` exits with code 0.
- `git diff --check` has no whitespace errors.

## Task Checklist

### Task 1: Write Failing Adapter Tests

**Files:**
- Create: `tools/mcp/tests/test_provider_mcp_tools.py`

- [x] **Step 1: Add test imports and helpers**

```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.provider_tools import (  # type: ignore
    load_eap_sidecar_envelope,
    parse_allowlist_env,
    sidecar_load_error_to_envelope,
)
from providers import SidecarLoadError  # type: ignore


def _sidecar(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": {"name": "EngineAnnotationProtocol", "version": 1},
        "capture": {"id": "cap:eap"},
        "render_graph": {"nodes": [{"id": "pass:main"}]},
        "commands": [{"id": "cmd:1"}],
        "resources": [{"id": "res:1"}],
    }
    payload.update(extra)
    return payload


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
```

- [x] **Step 2: Add success envelope test**

```python
def test_load_eap_sidecar_envelope_returns_summary_and_data_availability(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    envelope = load_eap_sidecar_envelope(
        str(sidecar_path),
        allowlist_dirs=[str(tmp_path)],
    )

    assert envelope["ok"] is True
    assert envelope["contract_version"] == "mcp-query.v1"
    assert envelope["method"] == "load_eap_sidecar"
    assert envelope["source"] == "provider_readonly"
    assert envelope["data"]["sidecar"]["capture_id"] == "cap:eap"
    assert envelope["data"]["sidecar"]["schema_name"] == "EngineAnnotationProtocol"
    assert envelope["data"]["sidecar"]["path"] == str(sidecar_path.resolve())
    assert "payload" not in envelope["data"]["sidecar"]
    assert envelope["data"]["data_availability"]["providers"]["eap_sidecar"]["available"] is True
```

- [x] **Step 3: Add configured-allowlist requirement test**

```python
def test_load_eap_sidecar_envelope_requires_allowlist(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    envelope = load_eap_sidecar_envelope(str(sidecar_path), allowlist_dirs=[])

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "invalid_argument"
    assert envelope["error"]["details"]["sidecar_code"] == "not_allowed"
    assert "allowlist" in envelope["recovery_hint"].lower()
```

- [x] **Step 4: Add loader error mapping test**

```python
def test_sidecar_load_error_to_envelope_preserves_sidecar_error_code():
    exc = SidecarLoadError("invalid_extension", "Sidecar path must end with .rmeta.json", "bad.json")

    envelope = sidecar_load_error_to_envelope(
        exc,
        method="load_eap_sidecar",
        params={"path": "bad.json"},
    )

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "invalid_argument"
    assert envelope["error"]["details"]["sidecar_code"] == "invalid_extension"
    assert envelope["error"]["details"]["path"].endswith("bad.json")
```

- [x] **Step 5: Add env allowlist parsing test**

```python
def test_parse_allowlist_env_uses_os_path_separator(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    raw = f"{left}{__import__('os').pathsep}{right}"

    assert parse_allowlist_env({"RENDERDOC_EAP_SIDECAR_ALLOWLIST": raw}) == [str(left), str(right)]
```

- [x] **Step 6: Run tests to verify RED**

Run:

```powershell
py -3 -m pytest tools\mcp\tests\test_provider_mcp_tools.py -q
```

Expected:

```text
ImportError: No module named 'mcp_server.provider_tools'
```

### Task 2: Implement Pure Provider Tool Adapter

**Files:**
- Create: `tools/mcp/mcp_server/provider_tools.py`

- [x] **Step 1: Add imports and constants**

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from providers import (  # type: ignore
    ProviderContext,
    SidecarLoadError,
    build_default_registry,
    load_sidecar,
)
from providers.sidecar_loader import DEFAULT_MAX_BYTES  # type: ignore
from snapshot_consumer import build_mcp_envelope  # type: ignore


SOURCE = "provider_readonly"
LOAD_SIDECAR_METHOD = "load_eap_sidecar"
ALLOWLIST_ENV = "RENDERDOC_EAP_SIDECAR_ALLOWLIST"
```

- [x] **Step 2: Add env allowlist parser**

```python
def parse_allowlist_env(env: Optional[Mapping[str, str]] = None) -> list[str]:
    source = env if env is not None else os.environ
    raw = source.get(ALLOWLIST_ENV, "")
    return [item for item in (part.strip() for part in raw.split(os.pathsep)) if item]
```

- [x] **Step 3: Add success adapter**

```python
def load_eap_sidecar_envelope(
    path: str,
    *,
    allowlist_dirs: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    params = {
        "path": str(path),
        "max_bytes": int(max_bytes),
    }
    roots = [str(root) for root in allowlist_dirs]
    if not roots:
        exc = SidecarLoadError(
            "not_allowed",
            f"{ALLOWLIST_ENV} is not configured for MCP sidecar loading",
            path,
        )
        return sidecar_load_error_to_envelope(exc, method=LOAD_SIDECAR_METHOD, params=params)

    try:
        payload = load_sidecar(path, allowlist_dirs=roots, max_bytes=max_bytes)
    except SidecarLoadError as exc:
        return sidecar_load_error_to_envelope(exc, method=LOAD_SIDECAR_METHOD, params=params)

    context = ProviderContext(eap_sidecar=payload)
    data_availability = build_default_registry().data_availability(context).as_dict()
    data = {
        "sidecar": summarize_eap_sidecar(payload, path=path),
        "data_availability": data_availability,
    }
    envelope = build_mcp_envelope(
        ok=True,
        data=data,
        method=LOAD_SIDECAR_METHOD,
        params=params,
        evidence=[{"kind": "file", "path": str(Path(path).expanduser().resolve(strict=False))}],
        source=SOURCE,
    )
    envelope["source"] = SOURCE
    return envelope
```

- [x] **Step 4: Add sidecar summary helper**

```python
def summarize_eap_sidecar(payload: Dict[str, Any], *, path: str) -> Dict[str, Any]:
    schema = payload.get("schema", {}) if isinstance(payload.get("schema"), dict) else {}
    capture = payload.get("capture", {}) if isinstance(payload.get("capture"), dict) else {}
    availability = build_default_registry().data_availability(
        ProviderContext(eap_sidecar=payload)
    ).as_dict()
    capabilities = availability["providers"]["eap_sidecar"]["capabilities"]
    return {
        "path": str(Path(path).expanduser().resolve(strict=False)),
        "schema_name": schema.get("name"),
        "schema_version": schema.get("version"),
        "capture_id": capture.get("id") or availability.get("capture_id"),
        "capabilities": capabilities,
    }
```

- [x] **Step 5: Add error mapping**

```python
def sidecar_load_error_to_envelope(
    exc: SidecarLoadError,
    *,
    method: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    mcp_code = _sidecar_code_to_mcp_code(exc.code)
    envelope = build_mcp_envelope(
        ok=False,
        data=None,
        method=method,
        params=params,
        availability={
            "status": "unavailable",
            "missing_fields": [],
            "notes": [f"sidecar_error={exc.code}"],
        },
        error={
            "code": mcp_code,
            "message": exc.message,
            "details": {
                "sidecar_code": exc.code,
                "path": exc.path,
            },
        },
        recovery_hint=_sidecar_recovery_hint(exc.code),
        source=SOURCE,
    )
    envelope["source"] = SOURCE
    return envelope


def _sidecar_code_to_mcp_code(code: str) -> str:
    if code == "not_found":
        return "not_found"
    if code in {"read_failed", "stat_failed"}:
        return "internal_error"
    return "invalid_argument"


def _sidecar_recovery_hint(code: str) -> str:
    if code == "not_allowed":
        return f"Configure {ALLOWLIST_ENV} with the directory that contains the .rmeta.json sidecar."
    if code == "invalid_extension":
        return "Use an explicit path ending in .rmeta.json."
    if code == "file_too_large":
        return "Use a smaller sidecar or raise max_bytes intentionally for this local run."
    if code == "invalid_sidecar":
        return "Provide an EngineAnnotationProtocol sidecar payload."
    if code == "not_found":
        return "Verify the sidecar path exists and retry."
    return "Fix the sidecar path or JSON payload and retry."
```

- [x] **Step 6: Run focused adapter tests to verify GREEN**

Run:

```powershell
py -3 -m pytest tools\mcp\tests\test_provider_mcp_tools.py -q
```

Expected:

```text
4 passed
```

### Task 3: Write Failing Read-Only Server Registration Tests

**Files:**
- Create: `tools/mcp/tests/test_provider_readonly_server.py`

- [x] **Step 1: Add fake FastMCP and imports**

```python
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.provider_readonly_server import create_mcp_server  # type: ignore


class FakeFastMCP:
    def __init__(self, name: str, instructions: str = ""):
        self.name = name
        self.instructions = instructions
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator
```

- [x] **Step 2: Add registration test**

```python
def test_create_mcp_server_registers_readonly_provider_tools():
    server = create_mcp_server(fastmcp_cls=FakeFastMCP, env={})

    assert server.name == "RenderDoc Provider Readonly"
    assert "read-only" in server.instructions.lower()
    assert set(server.tools) == {"get_data_availability", "load_eap_sidecar"}
```

- [x] **Step 3: Add no-allowlist behavior test through registered tool**

```python
def test_registered_load_eap_sidecar_requires_env_allowlist(tmp_path: Path):
    server = create_mcp_server(fastmcp_cls=FakeFastMCP, env={})
    sidecar_path = tmp_path / "capture.rmeta.json"
    sidecar_path.write_text("{}", encoding="utf-8")

    payload = server.tools["load_eap_sidecar"](str(sidecar_path))

    assert payload["ok"] is False
    assert payload["error"]["details"]["sidecar_code"] == "not_allowed"
```

- [x] **Step 4: Run tests to verify RED**

Run:

```powershell
py -3 -m pytest tools\mcp\tests\test_provider_readonly_server.py -q
```

Expected:

```text
ImportError: No module named 'mcp_server.provider_readonly_server'
```

### Task 4: Implement Read-Only FastMCP Registration

**Files:**
- Create: `tools/mcp/mcp_server/provider_readonly_server.py`

- [x] **Step 1: Add server module imports**

```python
from __future__ import annotations

from typing import Any, Mapping, Optional

from providers import ProviderContext, build_default_registry  # type: ignore

from .provider_tools import (
    DEFAULT_MAX_BYTES,
    LOAD_SIDECAR_METHOD,
    load_eap_sidecar_envelope,
    parse_allowlist_env,
)
```

- [x] **Step 2: Add FastMCP import helper**

```python
def _import_fastmcp() -> Any:
    from mcp.server.fastmcp import FastMCP

    return FastMCP
```

- [x] **Step 3: Add server factory with injectable FastMCP**

```python
def create_mcp_server(
    *,
    fastmcp_cls: Optional[Any] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Any:
    cls = fastmcp_cls or _import_fastmcp()
    mcp = cls(
        "RenderDoc Provider Readonly",
        instructions=(
            "Read-only RenderDoc provider availability tools. "
            "Does not open RDC files, generate reports, execute commands, or scan directories."
        ),
    )

    @mcp.tool()
    def get_data_availability() -> dict:
        return build_default_registry().data_availability(ProviderContext()).as_dict()

    @mcp.tool()
    def load_eap_sidecar(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
        return load_eap_sidecar_envelope(
            path,
            allowlist_dirs=parse_allowlist_env(env),
            max_bytes=max_bytes,
        )

    return mcp
```

- [x] **Step 4: Add main entrypoint**

```python
def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
```

- [x] **Step 5: Run server registration tests to verify GREEN**

Run:

```powershell
py -3 -m pytest tools\mcp\tests\test_provider_readonly_server.py -q
```

Expected:

```text
2 passed
```

### Task 5: Update EAP MCP Docs

**Files:**
- Modify: `docs/EAP/EAP_MCP_PROVIDER_REFACTOR_PLAN.md`
- Modify: `docs/EAP/EAP_MCP_DATA_MODEL.md`

- [x] **Step 1: Update Phase 4 section**

Add these bullets under Phase 4:

```markdown
Implemented Phase 4 tool names:

| Kind | Name | Registration | Notes |
| --- | --- | --- | --- |
| Tool | `get_data_availability` | `tools/mcp/mcp_server/provider_readonly_server.py` | Stateless default availability. Does not read files. |
| Tool | `load_eap_sidecar` | `tools/mcp/mcp_server/provider_readonly_server.py` | Requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; returns sidecar summary plus Data Availability. |

Boundary:

- This server is separate from `scripts/rdc_mcp/rdc_mcp.py`.
- `load_eap_sidecar` returns a summary and Data Availability, not raw full sidecar JSON.
- Loader errors are mapped to `mcp-query.v1` while preserving `error.details.sidecar_code`.
```

- [x] **Step 2: Update Data Model with tool output shape**

Add this example:

```json
{
  "ok": true,
  "contract_version": "mcp-query.v1",
  "data": {
    "sidecar": {
      "path": "D:/captures/capture.rmeta.json",
      "schema_name": "EngineAnnotationProtocol",
      "schema_version": 1,
      "capture_id": "cap:eap",
      "capabilities": []
    },
    "data_availability": {
      "schema_version": "mcp-data-availability.v1",
      "capture_id": "cap:eap",
      "providers": {},
      "limitations": []
    }
  },
  "availability": {"status": "full", "missing_fields": [], "notes": []},
  "evidence": [{"kind": "file", "path": "D:/captures/capture.rmeta.json"}],
  "warnings": [],
  "recovery_hint": null,
  "error": null,
  "method": "load_eap_sidecar",
  "params": {"path": "D:/captures/capture.rmeta.json", "max_bytes": 268435456},
  "source": "provider_readonly"
}
```

- [x] **Step 3: Run documentation whitespace check**

Run:

```powershell
git diff --check -- docs\EAP\EAP_MCP_PROVIDER_REFACTOR_PLAN.md docs\EAP\EAP_MCP_DATA_MODEL.md
```

Expected: exit code 0.

### Task 6: Final Verification And Commit

**Files:**
- All files from Tasks 1-5.

- [x] **Step 1: Run focused tests**

```powershell
py -3 -m pytest tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py -q
```

Expected:

```text
6 passed
```

- [x] **Step 2: Run provider regression tests**

```powershell
py -3 -m pytest tools\mcp\tests\test_snapshot_consumer.py tools\mcp\tests\test_provider_registry.py tools\mcp\tests\test_provider_routing.py tools\mcp\tests\test_sidecar_loader.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py -q
```

Expected:

```text
49 passed
```

- [x] **Step 3: Run compile check**

```powershell
py -3 -m py_compile tools\mcp\mcp_server\provider_tools.py tools\mcp\mcp_server\provider_readonly_server.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py
```

Expected: exit code 0.

- [x] **Step 4: Run diff check**

```powershell
git diff --check -- tools\mcp docs\EAP\EAP_MCP_PROVIDER_REFACTOR_PLAN.md docs\EAP\EAP_MCP_DATA_MODEL.md
```

Expected: exit code 0.

- [x] **Step 5: Commit after verification**

```powershell
git add tools\mcp\mcp_server\provider_tools.py tools\mcp\mcp_server\provider_readonly_server.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py docs\EAP\EAP_MCP_PROVIDER_REFACTOR_PLAN.md docs\EAP\EAP_MCP_DATA_MODEL.md plans\2026-04-25-173309-AgentCodex-EAP-Sidecar-MCP-Registration.md
git commit -m "feat(mcp): register readonly sidecar provider tools" -m "- Add read-only provider MCP server separate from legacy RDC tools" -m "- Map sidecar loader errors into mcp-query.v1 envelopes" -m "- Require configured allowlist for MCP sidecar path loading"
```

Expected: commit succeeds and includes only the implementation, EAP docs, and this plan file.

## Risks / Blockers

| Risk | Mitigation |
| --- | --- |
| Legacy MCP server mixes read-only sidecar path with `.rdc` open/analyze side effects | Do not modify `scripts/rdc_mcp/rdc_mcp.py`; create `provider_readonly_server.py`. |
| MCP path loading becomes arbitrary local file read | Require `RENDERDOC_EAP_SIDECAR_ALLOWLIST` in MCP adapter even though `load_sidecar()` supports explicit paths. |
| Tool returns large or sensitive sidecar JSON | Return summary plus Data Availability only; do not return `payload`. |
| FastMCP dependency is unavailable in test environment | Test registration through injected fake FastMCP class; only real runtime import happens in `main()` path. |
| Error codes drift from `mcp-query.v1` | Map to standard MCP codes while preserving loader-specific code at `error.details.sidecar_code`. |

## Decisions

- New MCP registration lives under `tools/mcp/mcp_server/`, not `scripts/rdc_mcp/`.
- Tool name is `load_eap_sidecar`, not generic `load_sidecar`, to keep the file type and protocol
  explicit.
- MCP tool requires configured allowlist roots. Empty allowlist returns an `invalid_argument`
  envelope with `sidecar_code=not_allowed`.
- The server is stateless in this phase. It does not store a sidecar context ID.

## Verification / Acceptance

Definition of Done:

- `load_eap_sidecar` returns `mcp-query.v1` success envelope for allowlisted `.rmeta.json`.
- Success envelope contains sidecar summary, Data Availability, and file evidence.
- Success envelope does not contain full sidecar payload.
- Missing allowlist and invalid loader inputs return `ok=false` envelopes with standard MCP error
  code and `error.details.sidecar_code`.
- `get_data_availability` remains read-only and does not read files.
- Legacy `scripts/rdc_mcp/rdc_mcp.py` remains untouched.
- Focused and regression pytest commands pass.
- Compile and diff checks pass.

## Next Steps

After this plan is approved, execute Tasks 1-6 in order using TDD. Pause and update this same plan if
server ownership changes, if the tool must support persistent context IDs, or if the allowlist source
must come from a config file instead of `RENDERDOC_EAP_SIDECAR_ALLOWLIST`.
