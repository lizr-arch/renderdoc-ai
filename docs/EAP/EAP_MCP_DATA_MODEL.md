# EAP MCP Data Availability Model

Date: 2026-04-24

Scope: define the first provider-neutral JSON model that tells an MCP client what capture data is
available before it chooses native RenderDoc, `snapshot.v1`, EAP sidecar, rules, live bridge, or scout
report queries.

This model is not a replacement for:

- `snapshot.v1`: full report fact snapshot.
- `mcp-query.v1`: query-level response envelope.
- EAP `capture.rmeta.json`: engine semantic sidecar.

It is a small routing and disclosure model.

## Version

```json
{
  "schema_version": "mcp-data-availability.v1"
}
```

Implementation anchor:

- `tools/mcp/providers/base.py` defines `DATA_AVAILABILITY_VERSION`, provider IDs,
  `ProviderCapability`, `DataAvailability`, and `ProviderContext`.
- `tools/mcp/providers/registry.py` aggregates provider availability and mirrors unavailable
  providers into top-level `limitations[]`.
- `tools/mcp/providers/sidecar_loader.py` can convert one explicit `.rmeta.json` path into a
  validated EAP sidecar dict before the caller builds `ProviderContext(eap_sidecar=...)`.
- `tools/mcp/snapshot_consumer.py` exposes compatibility wrappers for `get_data_availability()` /
  `build_data_availability()`.

## Top-Level Shape

```json
{
  "schema_version": "mcp-data-availability.v1",
  "capture_id": "cap:...",
  "providers": {
    "renderdoc_native": {},
    "snapshot": {},
    "eap_sidecar": {},
    "rules": {},
    "live_renderdoc": {},
    "scout_report": {}
  },
  "limitations": []
}
```

Required fields:

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `schema_version` | string | Yes | Fixed as `mcp-data-availability.v1`. |
| `capture_id` | string | Yes | Prefer explicit `capture_id`, then EAP sidecar `capture.id`, then snapshot `meta.capture_id` / `meta.capture_name`, else `unknown`. |
| `providers` | object | Yes | Must contain every provider listed below, even when unavailable. |
| `limitations` | string array | Yes | Every unavailable provider or missing required data must be represented here in stable text form. |

## ProviderAvailability Shape

Each entry under `providers` uses this shape:

```json
{
  "available": true,
  "capabilities": [
    {
      "name": "commands",
      "fields": ["commands"]
    }
  ],
  "missing": "optional string when unavailable",
  "notes": ["optional note"]
}
```

Rules:

1. `available` is always boolean.
2. `capabilities` is always an array. Use an empty array when unavailable.
3. `missing` is required when `available=false`.
4. Every `missing` string must also be mirrored into top-level `limitations` as
   `<provider>: <missing>`.
5. No provider may imply EAP data when EAP sidecar is absent.

## ProviderCapability Shape

```json
{
  "name": "native_capture_queries",
  "fields": ["capture_status", "actions", "textures", "buffers"],
  "notes": ["Existing RenderDoc Python/bridge surfaces; independent from EAP sidecar."]
}
```

Fields:

| Field | Type | Required | Notes |
| --- | --- | ---: | --- |
| `name` | string | Yes | Stable capability ID. |
| `fields` | string array | No | Fact fields or logical resources that the provider can supply. |
| `notes` | string array | No | Human-readable constraints, never used as parser-critical data. |

Implementation anchor: `tools/mcp/providers/base.py`.

## Required Providers

### `renderdoc_native`

Meaning: RenderDoc-native facts available without EAP sidecar. This includes legacy RenderDoc Python
worker facts and future native/live bridge facts.

Minimum capability when available:

```json
{
  "name": "native_capture_queries",
  "fields": ["capture_status", "actions", "textures", "buffers"]
}
```

Availability rule:

- Available by default in the MVP because current MCP-native surfaces exist and must remain useful
  without EAP.
- May be explicitly disabled by caller when the native layer is unavailable.

Evidence:

- Legacy FastMCP registers native query tools at `scripts/rdc_mcp/rdc_mcp.py:104-193`.
- Worker reads actions/textures/buffers through RenderDoc Python API at
  `scripts/rdc_mcp/rdc_worker.py:133-190`.

### `snapshot`

Meaning: a `snapshot.v1` payload is present and can be consumed as the report fact layer.

Available if:

- `snapshot` is provided.
- `snapshot.schema_version == "snapshot.v1"`.

Missing states:

- `snapshot.v1 payload not provided`
- `payload is not snapshot.v1`

Capabilities are derived from non-empty sections such as `actions`, `resources`, `timings`,
`pipelines`, `shaders`, `findings`, `recommendations`, and `evidence_index`.

Evidence:

- GUI exporter writes `snapshot.v1.json` at `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp:45-65`.
- Snapshot adapter sets `schema_version=snapshot.v1` and root availability at
  `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:888-925`.
- Offline builder also emits `snapshot.v1` with partial availability at
  `scripts/rdc_analyzer/providers/offline_snapshot_builder.py:59-82`.

### `eap_sidecar`

Meaning: a preloaded EAP `capture.rmeta.json` sidecar payload is present.

Available if:

- `eap_sidecar` is provided; and
- it has `schema.name == "EngineAnnotationProtocol"` or one of the expected EAP sidecar top-level
  keys.

Missing states:

- `capture.rmeta.json not found`
- `payload is not an EAP sidecar`

Capability map:

| Capability | Field source |
| --- | --- |
| `eap_schema` | `schema`, `capture` |
| `render_graph` | `render_graph.nodes` |
| `commands` | `commands` |
| `resources` | `resources` |
| `assets` | `assets` |
| `materials` | `materials` |
| `shaders` | `shaders` |
| `pipelines` | `pipelines` |
| `rules` | `rules.results` |
| `diagnostics` | `diagnostics` |
| `security` | `security` |

Evidence:

- EAP protocol defines sidecar as `*.rmeta.json` and lists its data classes at
  `docs/EAP/02_EAP_PROTOCOL_SPEC.md:29-30`.
- Top-level sidecar fields are shown at `docs/EAP/02_EAP_PROTOCOL_SPEC.md:251-310`.

Security rule:

- The ProviderRegistry itself does not read sidecar paths. It accepts only a preloaded dict.
- `load_sidecar()` is the controlled Phase 3 helper for producing that dict from one explicit path:
  `.rmeta.json` only, size bounded, resolved path, optional allowlist, JSON object only, and EAP
  shape validation.
- MCP tool/resource registration for sidecar loading remains a later phase.

### `rules`

Meaning: deterministic rule/finding data is available from one of these inputs:

- external `rules_payload`;
- `eap_sidecar.rules.results`;
- `snapshot.findings`.

Missing state:

- `No rules payload, EAP rule results, or snapshot findings provided`

Evidence:

- `snapshot.v1` declares deterministic `findings[]` / `recommendations[]` at
  `docs/product/snapshot_schema_v1.md:259-289`.
- EAP sidecar reserves `rules.results` at `docs/EAP/02_EAP_PROTOCOL_SPEC.md:303-305`.

### `live_renderdoc`

Meaning: a loaded live RenderDoc GUI/bridge provider can answer realtime queries.

Available if:

- a `live_renderdoc_status` payload is provided; and
- it reports a loaded capture via the existing `get_capture_status` shape.

Missing states:

- `live RenderDoc capture is not loaded`
- `live RenderDoc bridge IPC present but capture status not loaded/probed`
- `live RenderDoc bridge not probed`

Evidence:

- Bridge IPC files are defined at `tools/mcp/mcp_server/bridge/client.py:15-18`.
- Bridge call and timeout behavior is at `tools/mcp/mcp_server/bridge/client.py:36-89`.
- Existing snapshot consumer already probes `get_capture_status` before detail queries at
  `tools/mcp/snapshot_consumer.py:629-719`.

### `scout_report`

Meaning: an optional EAP scout/recon report is available for implementation planning or provider
recommendations.

Missing state:

- `scout report not provided`

This provider is not required for capture analysis.

## Examples

### No EAP Sidecar

```json
{
  "schema_version": "mcp-data-availability.v1",
  "capture_id": "cap:no-sidecar",
  "providers": {
    "renderdoc_native": {
      "available": true,
      "capabilities": [
        {
          "name": "native_capture_queries",
          "fields": ["capture_status", "actions", "textures", "buffers"],
          "notes": ["Existing RenderDoc Python/bridge surfaces; independent from EAP sidecar."]
        }
      ]
    },
    "snapshot": {
      "available": false,
      "capabilities": [],
      "missing": "snapshot.v1 payload not provided"
    },
    "eap_sidecar": {
      "available": false,
      "capabilities": [],
      "missing": "capture.rmeta.json not found"
    },
    "rules": {
      "available": false,
      "capabilities": [],
      "missing": "No rules payload, EAP rule results, or snapshot findings provided"
    },
    "live_renderdoc": {
      "available": false,
      "capabilities": [],
      "missing": "live RenderDoc bridge not probed"
    },
    "scout_report": {
      "available": false,
      "capabilities": [],
      "missing": "scout report not provided"
    }
  },
  "limitations": [
    "snapshot: snapshot.v1 payload not provided",
    "eap_sidecar: capture.rmeta.json not found",
    "rules: No rules payload, EAP rule results, or snapshot findings provided",
    "live_renderdoc: live RenderDoc bridge not probed",
    "scout_report: scout report not provided"
  ]
}
```

### EAP Sidecar Present

```json
{
  "schema_version": "mcp-data-availability.v1",
  "capture_id": "cap:eap",
  "providers": {
    "renderdoc_native": {"available": true, "capabilities": [{"name": "native_capture_queries"}]},
    "snapshot": {"available": true, "capabilities": [{"name": "snapshot_meta"}]},
    "eap_sidecar": {
      "available": true,
      "capabilities": [
        {"name": "eap_schema"},
        {"name": "render_graph"},
        {"name": "commands"},
        {"name": "resources"},
        {"name": "rules"},
        {"name": "diagnostics"}
      ]
    },
    "rules": {"available": true, "capabilities": [{"name": "eap_sidecar_rule_results"}]},
    "live_renderdoc": {"available": false, "capabilities": [], "missing": "live RenderDoc bridge not probed"},
    "scout_report": {"available": false, "capabilities": [], "missing": "scout report not provided"}
  },
  "limitations": [
    "live_renderdoc: live RenderDoc bridge not probed",
    "scout_report: scout report not provided"
  ]
}
```

## Relationship To `mcp-query.v1`

`mcp-data-availability.v1` is called before or beside `mcp-query.v1`:

```text
get_data_availability()
  -> tells client which providers can answer
  -> ProviderRegistry.route() selects a provider-specific query path
  -> query result still uses mcp-query.v1 envelope
```

It does not replace per-query `availability` in `mcp-query.v1`. If a provider is available but a
particular field is missing, the query response must still return `availability.status=partial` or
`unavailable`.

The current router is route-only:

- `ProviderRegistry.route(method, preferred_provider=None, context=None)` returns an `mcp-query.v1`
  envelope naming the selected provider, or a structured `data_unavailable` / `unsupported_api`
  envelope.
- It does not execute provider calls.
- It does not register MCP tools or resources.
- It does not load `capture.rmeta.json` paths; callers must pass already-loaded dicts, optionally
  from `load_sidecar()`.

## Read-Only MCP Tool Output

The Phase 4 read-only server registers provider tools under
`tools/mcp/mcp_server/provider_readonly_server.py`. It is separate from the legacy
`scripts/rdc_mcp/rdc_mcp.py` server.

Registered tools:

| Tool | Output contract | Notes |
| --- | --- | --- |
| `get_data_availability` | `mcp-data-availability.v1` JSON | Stateless default availability; does not read files. |
| `load_eap_sidecar` | `mcp-query.v1` envelope | Requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; returns sidecar summary plus Data Availability. |
| `summarize_eap_sidecar` | `mcp-query.v1` envelope | Requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; returns bounded sidecar summary/counts plus Data Availability. |
| `search_eap_commands` | `mcp-query.v1` envelope | Requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; returns bounded command summaries for query/pass/resource/material/shader/pipeline filters. |
| `get_eap_rule_results` | `mcp-query.v1` envelope | Requires `RENDERDOC_EAP_SIDECAR_ALLOWLIST`; returns bounded summaries from existing `rules.results`. |

`load_eap_sidecar` success shape:

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

Rules:

- The full sidecar payload is not returned by default.
- Loader-specific errors are preserved in `error.details.sidecar_code`.
- Empty or missing `RENDERDOC_EAP_SIDECAR_ALLOWLIST` returns `sidecar_code=not_allowed`.
- Current acceptance is limited to synthetic fixtures under `tools/eap_validator/fixtures/`.
- A real EAP capture is not considered connected until a future bound `<capture>.rdc` plus
  `<capture>.rmeta.json` pair passes validator/rules/MCP summary/search gates.

## Validation

Current focused tests:

- `tools/mcp/tests/test_provider_registry.py` verifies provider ordering, missing-provider
  `limitations[]`, snapshot-only, EAP-sidecar-only, external rules payload, sidecar rules,
  snapshot findings, live RenderDoc loaded/unloaded states, and wrapper equivalence.
- `tools/mcp/tests/test_provider_routing.py` verifies live/native fallback, snapshot routing without
  EAP sidecar, EAP-only `data_unavailable`, unknown-method `unsupported_api`, and preferred-provider
  failures.
- `tools/mcp/tests/test_sidecar_loader.py` verifies controlled `.rmeta.json` loading, stable
  `SidecarLoadError` codes, resolved allowlist enforcement, and ProviderRegistry compatibility.
- `tools/mcp/tests/test_provider_mcp_tools.py` verifies MCP envelope conversion, sidecar summaries,
  allowlist parsing, and loader error mapping.
- `tools/mcp/tests/test_provider_readonly_server.py` verifies read-only FastMCP registration without
  importing a real MCP runtime.
- `tools/mcp/tests/test_snapshot_consumer.py` keeps compatibility coverage for
  `get_data_availability()` beside the existing snapshot gap/planner/enricher tests.

Validated command:

```powershell
py -3 -m pytest tools\mcp\tests\test_snapshot_consumer.py tools\mcp\tests\test_provider_registry.py tools\mcp\tests\test_provider_routing.py tools\mcp\tests\test_sidecar_loader.py tools\mcp\tests\test_provider_mcp_tools.py tools\mcp\tests\test_provider_readonly_server.py -q
```

Current Phase 4 result:

```text
49 passed
```
