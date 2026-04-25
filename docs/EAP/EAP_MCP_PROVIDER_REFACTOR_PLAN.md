# EAP MCP Provider Refactor Plan

Date: 2026-04-24

Goal: providerize the existing MCP/tooling layer so MCP can answer RenderDoc-native questions without
EAP, and report/use EAP sidecar data when `capture.rmeta.json` exists, without rewriting the existing
MCP or adding side-effect tools.

## Scope

In scope:

- Provider data model and availability disclosure.
- ProviderRegistry design.
- Minimal read-only Data Availability MVP.
- Controlled, explicit `.rmeta.json` sidecar loader that returns a validated dict for
  `ProviderContext(eap_sidecar=...)`.
- A staged migration path for existing `snapshot`, `renderdoc_native`, optional `live_renderdoc`,
  future `eap_sidecar`, `rules`, and optional `scout_report` providers.

Out of scope for this round:

- No RenderDoc core changes.
- No qrenderdoc changes.
- No capture/replay behavior changes.
- No real EAP runtime connection.
- No new upload/delete/create/run/exec/shell/capture/remote tools.
- No arbitrary file path reader.
- No MCP tool/resource registration for sidecar loading in Phase 3.
- No sidecar auto-discovery and no `.rdc` binary reads.
- No dependency additions.
- No deletion or renaming of existing MCP files.

## Mainline Ownership

This belongs to the intelligent collaboration line (`MCP`), with the following contract dependencies:

| Dependency | Reason |
| --- | --- |
| `docs/product/development_charter.md` | MCP is realtime query/fill, not full report generation. |
| `docs/product/mcp_query_contract_v1.md` | Existing query envelope and error model remain authoritative for per-query responses. |
| `docs/product/snapshot_schema_v1.md` | Snapshot provider must map to the shared fact schema. |
| `docs/EAP/02_EAP_PROTOCOL_SPEC.md` | EAP sidecar provider must understand `capture.rmeta.json` top-level fields. |
| `docs/EAP/10_TASK_MCP_READONLY_SERVER.md` | Future sidecar path loading must be read-only, allowlisted, and `.rmeta.json` only. |

## Current ProviderRegistry State

Implemented in this round:

| File | Change |
| --- | --- |
| `tools/mcp/providers/base.py` | Defines provider IDs, `ProviderCapability`, `DataAvailability`, `ProviderContext`, and pure payload helpers. |
| `tools/mcp/providers/registry.py` | Defines `ProviderRegistry`, `build_default_registry()`, provider-order aggregation, and query route selection. |
| `tools/mcp/providers/*_provider.py` | Implements `renderdoc_native`, `snapshot`, `eap_sidecar`, `rules`, `live_renderdoc`, and `scout_report` availability providers. |
| `tools/mcp/providers/sidecar_loader.py` | Loads one explicit `.rmeta.json` path into a validated EAP sidecar dict; it does not register MCP tools, scan directories, parse `.rdc`, or call RenderDoc. |
| `tools/mcp/snapshot_consumer.py` | Keeps `get_data_availability()` / `build_data_availability()` as compatibility wrappers over the default registry. |
| `tools/mcp/tests/test_provider_registry.py` | Covers provider order, missing limitations, snapshot/EAP/rules/live availability, and wrapper equivalence. |
| `tools/mcp/tests/test_provider_routing.py` | Covers route ownership, live/native fallback, snapshot-without-EAP routing, EAP-only unavailability, and preferred-provider errors. |
| `tools/mcp/tests/test_sidecar_loader.py` | Covers explicit sidecar path validation, size/JSON/payload errors, allowlist enforcement, and ProviderRegistry compatibility. |
| `tools/mcp/tests/test_snapshot_consumer.py` | Keeps existing snapshot-consumer tests and compatibility coverage. |
| `docs/EAP/EAP_MCP_EXISTING_AUDIT.md` | Existing MCP/data-source audit. |
| `docs/EAP/EAP_MCP_DATA_MODEL.md` | Data Availability JSON contract. |
| `docs/EAP/EAP_MCP_PROVIDER_REFACTOR_PLAN.md` | This plan. |

Implementation anchors:

- `tools/mcp/providers/base.py` data availability version, provider constants, provider context, and data structures.
- `tools/mcp/providers/registry.py` default registry, top-level `limitations[]` aggregation, method ownership map, and route envelope builder.
- `tools/mcp/providers/*_provider.py` provider-specific availability rules.
- `tools/mcp/providers/eap_sidecar_provider.py:looks_like_eap_sidecar()` shared shape predicate used by both the provider and the loader.
- `tools/mcp/providers/sidecar_loader.py:load_sidecar()` controlled path-to-dict loader.
- `tools/mcp/snapshot_consumer.py:get_data_availability()` and `build_data_availability()` compatibility wrappers.
- `tools/mcp/tests/test_provider_registry.py` focused ProviderRegistry tests.
- `tools/mcp/tests/test_sidecar_loader.py` focused loader tests.

Intentional non-change:

- No registration was added to `scripts/rdc_mcp/rdc_mcp.py` because that server currently exposes
  `rdc_open_capture(rdc_path)` and `rdc_analyze(...)`. Evidence: `scripts/rdc_mcp/rdc_mcp.py:104-193`.
- The ProviderRegistry still accepts preloaded dicts only. `load_sidecar()` is a separate helper that
  callers may use before constructing `ProviderContext(eap_sidecar=...)`.
- No provider query execution was added; routing only selects a provider or returns a structured error envelope.
- No MCP tool/resource exposes `load_sidecar()` yet.

## ProviderRegistry Design

### Interface

```python
class Provider:
    name: str

    def availability(self, context: ProviderContext) -> ProviderAvailability:
        ...

    def can_handle(self, method: str) -> bool:
        ...

    def call(self, method: str, params: dict) -> dict:
        ...
```

Provider methods must return structured JSON only. Provider `call()` must use `mcp-query.v1`
envelope for query results, not the Data Availability envelope.

### ProviderContext

```python
@dataclass(frozen=True)
class ProviderContext:
    capture_id: str | None = None
    snapshot: dict | None = None
    eap_sidecar: dict | None = None
    rules_payload: dict | None = None
    live_renderdoc_status: dict | None = None
    bridge_state: dict | None = None
    scout_report: dict | None = None
    renderdoc_native_available: bool = True
```

The context should initially contain already-loaded payloads. Path loading belongs to a later,
controlled `SidecarLoader`, not to the registry itself.

### Registry

```python
class ProviderRegistry:
    def __init__(self, providers: Sequence[Provider]):
        self._providers = {provider.name: provider for provider in providers}

    def data_availability(self, context: ProviderContext) -> dict:
        ...

    def route(
        self,
        method: str,
        preferred_provider: str | None = None,
        context: ProviderContext | None = None,
    ) -> dict:
        ...
```

Routing rules:

1. If caller specifies provider, use it only if available and can handle method.
2. For query-only native facts, prefer `live_renderdoc` when loaded, otherwise `renderdoc_native`.
3. For report facts, prefer `snapshot`.
4. For engine semantics, prefer `eap_sidecar` when present.
5. For deterministic rules, prefer `rules`.
6. Never silently downgrade EAP-only semantic questions to RenderDoc-native facts without reporting
   limitations.

The current route result is an `mcp-query.v1` envelope that names the selected provider. It does not
execute provider calls.

### Provider Names

Provider IDs are fixed:

```text
renderdoc_native
snapshot
eap_sidecar
rules
live_renderdoc
scout_report
```

These are already represented in the MVP output.

## Provider Responsibilities

| Provider | Reads from | Required methods later | Must not do |
| --- | --- | --- | --- |
| `renderdoc_native` | Existing RenderDoc Python worker or native bridge facts | `get_capture_status`, actions, textures, buffers, basic pipeline if available | Must not require EAP; must not write reports in the read-only provider path. |
| `snapshot` | Preloaded `snapshot.v1` dict | summary/actions/resources/shaders/findings lookups | Must not mutate snapshot or invent missing fields. |
| `eap_sidecar` | Preloaded `capture.rmeta.json` dict, later controlled sidecar loader | render graph, commands, resources, materials, shaders, pipelines, diagnostics | Must not read arbitrary paths; must not parse `.rdc` binary. |
| `rules` | `rules_payload`, sidecar `rules.results`, or snapshot `findings` | rule list/detail/evidence lookup | Must not run external commands in MVP. |
| `live_renderdoc` | GUI bridge file-IPC client | realtime per-capture detail queries | Must remain optional; unavailable bridge must not block other providers. |
| `scout_report` | EAP scout report dict | repo recon summary, implementation candidates | Must not be required for capture analysis. |

## Phased Plan

### Phase 0: Data Availability MVP (done)

Tasks:

- Add `ProviderCapability`.
- Add `DataAvailability`.
- Add pure `get_data_availability()`.
- Add focused tests.
- Add docs.

Verification:

```powershell
py -3 -m py_compile tools\mcp\snapshot_consumer.py tools\mcp\tests\test_snapshot_consumer.py
py -3 -m pytest tools\mcp\tests\test_snapshot_consumer.py -q
```

Expected:

- `renderdoc_native.available=true` even when `eap_sidecar.available=false`.
- `eap_sidecar.missing="capture.rmeta.json not found"` when absent.
- `limitations[]` includes every unavailable provider.

### Phase 1: Extract Provider Classes (done)

Files:

```text
tools/mcp/providers/__init__.py
tools/mcp/providers/base.py
tools/mcp/providers/snapshot_provider.py
tools/mcp/providers/renderdoc_native_provider.py
tools/mcp/providers/live_renderdoc_provider.py
tools/mcp/providers/eap_sidecar_provider.py
tools/mcp/providers/rules_provider.py
tools/mcp/providers/scout_report_provider.py
tools/mcp/providers/registry.py
tools/mcp/tests/test_provider_registry.py
```

Steps:

1. Move provider constants from `snapshot_consumer.py` into `providers/base.py`.
2. Keep `get_data_availability()` as a compatibility wrapper that builds a default registry.
3. Implement `SnapshotProvider.availability()` from preloaded dict only.
4. Implement `EAPSidecarProvider.availability()` from preloaded dict only.
5. Implement `RulesProvider.availability()` from preloaded dicts only.
6. Implement `LiveRenderDocProvider.availability()` using status payload, not a live bridge call.
7. Add tests for all provider availability states.

Acceptance:

- No provider reads a file path.
- No provider calls RenderDoc in availability calculation.
- All providers return stable JSON and stable `missing` text.

### Phase 2: Query Routing Without Tool Registration (done)

Files:

```text
tools/mcp/providers/registry.py
tools/mcp/tests/test_provider_routing.py
```

Implemented:

1. Implemented `ProviderRegistry.route(method, preferred_provider=None, context=None)`.
   - `context` is optional so existing call shape remains usable.
   - Routing availability is still computed from preloaded dict/status only.
2. Add method ownership map:
   - `get_capture_status`: `live_renderdoc` then `renderdoc_native`
   - `get_frame_summary`: `snapshot` then `live_renderdoc`
   - `get_pipeline_state`: `live_renderdoc` then `snapshot`
   - `get_texture_info`: `snapshot` then `renderdoc_native`
   - `get_eap_command`: `eap_sidecar`
   - `get_eap_resource`: `eap_sidecar`
   - `get_rule_results`: `rules`
3. Return structured `data_unavailable` / `unsupported_api` envelopes when no provider can handle
   the method.
4. Return a route-only `mcp-query.v1` envelope with `data.provider` and `data.method`; no provider
   call is executed.

Acceptance:

- Missing EAP sidecar does not block native/snapshot routes.
- EAP-only method returns `data_unavailable`, not fabricated native data.

### Phase 3: Controlled Sidecar Loader (done, loader-only)

This phase intentionally stops at a pure loader helper:

Files:

```text
tools/mcp/providers/sidecar_loader.py
tools/mcp/tests/test_sidecar_loader.py
```

Implemented:

1. `load_sidecar(path, *, allowlist_dirs=(), max_bytes=256 * 1024 * 1024) -> dict`
   resolves one explicit path, validates it, parses JSON, and returns the dict.
2. `SidecarLoadError(code, message, path=None)` provides stable exception fields for future MCP
   envelope conversion.
3. `looks_like_eap_sidecar(payload)` is public in `eap_sidecar_provider.py` and remains the shared
   EAP shape predicate for provider availability and loader validation.

Rules:

- Only `.rmeta.json`.
- Explicit user path or allowlist directory.
- Size bound.
- Resolve symlinks and reject allowlist escapes.
- Parse JSON only.
- No `.rdc` binary reads.
- No shell/exec/run.
- No directory scanning or sidecar auto-discovery.
- No MCP tool/resource registration.

Acceptance mirrors `docs/EAP/10_TASK_MCP_READONLY_SERVER.md:105-107` and `:170-178`.

### Phase 4: MCP Tool Registration (done, read-only server)

This phase keeps MCP registration separate from Phase 3 loader internals. Loader exceptions are
converted into `mcp-query.v1` envelopes by a pure adapter, then exposed through a new read-only MCP
server that is separate from the legacy RDC open/analyze server.

Implemented Phase 4 tool names:

| Kind | Name | Registration | Notes |
| --- | --- | --- | --- |
| Tool | `get_data_availability` | `tools/mcp/mcp_server/provider_readonly_server.py` | Stateless default availability. Does not read files. |
| Tool | `load_eap_sidecar` | `tools/mcp/mcp_server/provider_readonly_server.py` | Requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; returns sidecar summary plus Data Availability. |

Implementation anchors:

- `tools/mcp/mcp_server/provider_tools.py` maps `load_sidecar()` success/failure into
  `mcp-query.v1` envelopes.
- `tools/mcp/mcp_server/provider_readonly_server.py` registers read-only provider tools through
  FastMCP.
- `tools/mcp/tests/test_provider_mcp_tools.py` covers adapter envelope behavior and allowlist
  parsing.
- `tools/mcp/tests/test_provider_readonly_server.py` covers registration without importing real
  FastMCP.

Boundary:

- This server is separate from `scripts/rdc_mcp/rdc_mcp.py`.
- `load_eap_sidecar` returns a summary and Data Availability, not raw full sidecar JSON.
- Loader errors are mapped to `mcp-query.v1` while preserving `error.details.sidecar_code`.
- Empty MCP allowlist is rejected with `sidecar_code=not_allowed`.

## Test Matrix

| Case | Expected |
| --- | --- |
| No snapshot, no sidecar, no live bridge | `renderdoc_native.available=true`; all missing providers listed in `limitations`. |
| Snapshot only | `snapshot.available=true`; `eap_sidecar.available=false`; native still true. |
| EAP sidecar only | `eap_sidecar.available=true`; capabilities include present sidecar sections. |
| EAP sidecar with `rules.results` | `rules.available=true`. |
| Snapshot with findings | `rules.available=true`. |
| Live bridge IPC absent | `live_renderdoc.available=false`, missing says bridge not probed/unavailable. |
| Live `get_capture_status.loaded=false` | `live_renderdoc.available=false`, missing says capture not loaded. |
| Live `get_capture_status.loaded=true` | `live_renderdoc.available=true`. |
| Sidecar-looking invalid JSON payload | loader rejects before provider; availability receives no sidecar and reports not found/invalid. |
| EAP-only query without EAP provider | `ok=false`, error `data_unavailable`; no native fallback fabrication. |
| Explicit valid `.rmeta.json` path | `load_sidecar()` returns a dict that makes `eap_sidecar.available=true` when passed into `ProviderContext`. |
| Non-sidecar path or payload | `load_sidecar()` raises `SidecarLoadError` with stable codes such as `invalid_extension`, `invalid_json`, `invalid_payload`, or `invalid_sidecar`. |
| Path outside allowlist | `load_sidecar()` raises `not_allowed` after resolving the path. |
| MCP `load_eap_sidecar` without configured allowlist | `ok=false`, `error.code=invalid_argument`, `error.details.sidecar_code=not_allowed`. |
| MCP `load_eap_sidecar` with valid allowlisted sidecar | `ok=true`, `source=provider_readonly`, sidecar summary and Data Availability are returned, raw sidecar payload is omitted. |

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Provider abstraction becomes a second report system | Keep registry as routing/availability only; full reports remain `snapshot.v1` + report pipeline. |
| EAP hard dependency breaks existing MCP | Make `eap_sidecar` optional and report missing explicitly. |
| Old `rdc_mcp` side-effect tools contaminate read-only path | Provider tools are registered in `tools/mcp/mcp_server/provider_readonly_server.py`, not in `scripts/rdc_mcp/rdc_mcp.py`. |
| Arbitrary path reads leak local files | MCP `load_eap_sidecar` requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; the lower-level loader still enforces `.rmeta.json`, size, resolved path, JSON, and EAP shape. |
| Live RenderDoc bridge blocks availability | Availability must be computed from status payload or bridge-state metadata only; no blocking live call. |
| Missing data looks like empty data | Every unavailable provider and field gap must appear in `limitations` or per-query `availability`. |

## Next Recommended Step

Future work should decide whether the read-only server needs persistent context IDs, richer
ProviderContext inputs, or a config file for allowlist roots. Do not add full report generation or
legacy `.rdc` open/analyze behavior to this provider server.
