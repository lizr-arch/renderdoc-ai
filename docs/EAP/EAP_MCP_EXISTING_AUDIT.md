# EAP MCP Existing Audit

Date: 2026-04-24

Scope: audit the existing RenderDoc AI MCP/tooling surfaces before introducing EAP provider support.
This document is evidence-first and intentionally does not propose RenderDoc core, qrenderdoc, capture,
or replay behavior changes.

## Executive Summary

The current repository has three separate MCP-adjacent surfaces:

| Surface | Best provider classification | Current role | Providerization risk |
| --- | --- | --- | --- |
| `tools/mcp/snapshot_consumer.py` | `snapshot` plus optional `live_renderdoc` adapter | Consumes `snapshot.v1`, detects gaps, plans MCP queries, and can call a RenderDoc GUI bridge. | Low for pure data-availability helpers; medium if promoted to a full MCP server because it currently has no server registration layer. |
| `tools/mcp/mcp_server/bridge/client.py` | `live_renderdoc` adapter | File-IPC client for a qrenderdoc-side MCP bridge using `%TEMP%/renderdoc_mcp/request.json` and `response.json`. | Medium: live GUI bridge is optional and environment-sensitive. |
| `scripts/rdc_mcp/rdc_mcp.py` + `rdc_worker.py` | legacy `renderdoc_native` provider | Older FastMCP server that opens arbitrary `.rdc` paths, queries actions/textures/buffers, and can run analyzer output. | High for this task: it has path-based tools and a report-generating `rdc_analyze` path, so it should not be the first EAP availability insertion point. |

Conclusion: the safest first step is a provider-neutral Data Availability model under `tools/mcp`, with
no direct registration in legacy FastMCP yet. That keeps existing MCP behavior intact, avoids EAP hard
dependency, and gives the next refactor a stable JSON contract.

## Contract Boundaries

Product boundary:

- MCP belongs to the intelligent collaboration line and should read realtime facts or fill missing
  fields, not generate complete reports. Evidence: `docs/product/development_charter.md:59-64`,
  `docs/product/development_charter.md:112-124`.
- MCP responses must use a stable envelope and map back to `snapshot.v1`. Evidence:
  `docs/product/mcp_query_contract_v1.md:30-56`, `docs/product/mcp_query_contract_v1.md:201-207`.
- `snapshot.v1` is the GUI/offline/Skill fact snapshot and explicitly requires availability to be
  explicit when fields are missing. Evidence: `docs/product/snapshot_schema_v1.md:13-35`,
  `docs/product/snapshot_schema_v1.md:91-99`.

EAP boundary:

- EAP sidecar is `*.rmeta.json` and carries frame/build/device/render graph/assets/materials/shaders/
  resources/draws/rules. Evidence: `docs/EAP/02_EAP_PROTOCOL_SPEC.md:29-30`.
- The sidecar top-level structure includes `render_graph`, `commands`, `resources`, `rules`,
  `diagnostics`, and `security`. Evidence: `docs/EAP/02_EAP_PROTOCOL_SPEC.md:251-310`.
- EAP readonly MCP is documented as post-sidecar/post-rules/post-analyzer CLI, must remain read-only,
  and must not implement upload/delete/remote capture/open arbitrary file. Evidence:
  `docs/EAP/10_TASK_MCP_READONLY_SERVER.md:1-3`, `docs/EAP/10_TASK_MCP_READONLY_SERVER.md:24-26`,
  `docs/EAP/10_TASK_MCP_READONLY_SERVER.md:71-80`.

## Existing Data Sources

| Data source | Evidence | What it provides | Current availability semantics |
| --- | --- | --- | --- |
| `snapshot.v1` | `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp:34-65` writes `analysis.json`, `capture_context.json`, and `snapshot.v1.json`; `AnalyzerSnapshotAdapter::ToSnapshotV1` sets `schema_version=snapshot.v1` and root availability at `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:888-925`. | GUI/export fact snapshot with actions/resources/shaders/findings/evidence index. | Explicit but partial: pipelines are currently emitted as an empty array and marked unavailable. Evidence: `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:85-94`, `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:156`, `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:921-925`. |
| Offline snapshot builder | `scripts/rdc_analyzer/providers/offline_snapshot_builder.py:7-27`, `:59-82`, `:253-291`. | Builds `snapshot.v1` from offline XML/provider data, with `timings`, `passes`, and `pipelines` marked missing. | Partial by design, with MCP hint for missing offline fields. |
| Snapshot MCP consumer | `tools/mcp/snapshot_consumer.py:113-244`, `:393-426`, `:629-865`. | Gap detection, query planning, mcp-query envelope normalization, health probe, and bridge execution. | Query-level `availability` envelope exists, but provider-level availability did not exist before this change. |
| Live RenderDoc bridge client | `tools/mcp/mcp_server/bridge/client.py:15-18`, `:27-41`, `:53-89`. | File-IPC bridge client that calls a GUI extension method by writing request JSON and reading response JSON. | Optional and environment-sensitive. If `%TEMP%/renderdoc_mcp` is absent or response times out, the caller must report bridge unavailable. |
| Legacy FastMCP native worker | `scripts/rdc_mcp/rdc_mcp.py:28-35`, `:63-64`, `:85-193`; `scripts/rdc_mcp/rdc_worker.py:69-86`, `:133-190`, `:201-226`. | Opens `.rdc` via RenderDoc Python API, reads actions/textures/buffers, and can run analyzer output. | Not safe as an EAP MVP insertion point because it accepts `rdc_path`, opens files, and `rdc_analyze` writes output. |
| EAP sidecar | `docs/EAP/02_EAP_PROTOCOL_SPEC.md:229-310`; `tools/mcp/providers/sidecar_loader.py`; `tools/mcp/providers/eap_sidecar_provider.py`. | Engine semantic metadata from `capture.rmeta.json`: render graph, commands, resources, materials, shaders, pipelines, rules, diagnostics, security. | A controlled explicit-path loader can now produce a preloaded dict for `ProviderContext(eap_sidecar=...)`; no real EAP runtime or MCP registration is connected in this task. |
| Rules | `docs/EAP/07_TASK_RULE_ENGINE_MVP.md:23`, `docs/EAP/07_TASK_RULE_ENGINE_MVP.md:268-289`; existing snapshot findings in `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:702-726`. | Deterministic findings/rule results. | Present in snapshot; EAP rule runtime remains future work. |
| Scout report | `tools/eap_scout/eap_scout.py` and `docs/EAP/EAP_SCOUT_CLI.md`. | Repo reconnaissance reports and candidate hook discovery. | Not part of current MCP runtime; should be an optional provider only. |

## Data Flow Today

```text
GUI Analyzer
  -> AnalyzerExporter::WriteAll()
  -> analysis.json + capture_context.json + snapshot.v1.json
  -> snapshot_consumer detects gaps
  -> optional live RenderDoc bridge query

Legacy FastMCP
  -> rdc_mcp.py
  -> rdc_worker.py
  -> RenderDoc Python API opens an rdc_path
  -> actions/textures/buffers or analyzer output

EAP sidecar
  -> not connected yet
  -> future capture.rmeta.json provider
```

## Provider Classification

| Provider name | Should exist in Data Availability? | Current implementation status | Notes |
| --- | ---: | --- | --- |
| `renderdoc_native` | Yes | Legacy native worker exists under `scripts/rdc_mcp`; live bridge may also expose native RenderDoc facts. | This provider must not require EAP. It is the fallback that keeps MCP useful when no sidecar exists. |
| `snapshot` | Yes | Existing `snapshot.v1` consumer and GUI/offline snapshot producers exist. | This is the cleanest current provider adapter surface. |
| `eap_sidecar` | Yes | Not implemented as runtime input yet. | Must report unavailable with `capture.rmeta.json not found` when absent. |
| `rules` | Yes | Snapshot findings exist; EAP sidecar rules are future. | Rules should be data-only and deterministic. |
| `live_renderdoc` | Yes, optional | File-IPC bridge client exists; server-side handler is not visible in this checkout. | Should never be a hard dependency for availability. |
| `scout_report` | Yes, optional | EAP scout tooling exists outside MCP runtime. | Useful for planning and repo recon, not required for capture queries. |

## Key Gaps

| Gap | Layer | Evidence | Required response |
| --- | --- | --- | --- |
| Provider registry now exists for availability and route selection | Implementation | `tools/mcp/providers/registry.py` aggregates `renderdoc_native`, `snapshot`, `eap_sidecar`, `rules`, `live_renderdoc`, and `scout_report` availability, and returns route-only `mcp-query.v1` envelopes; `tools/mcp/snapshot_consumer.py` keeps compatibility wrappers. | Keep provider query execution, sidecar path loading, and MCP tool registration as later phases. |
| No MCP-registered EAP sidecar runtime provider | Implementation | The safe loader is a separate helper under `tools/mcp/providers/sidecar_loader.py`; EAP MCP task still says sidecar/rules/analyzer CLI are prerequisites for the read-only server. Evidence: `docs/EAP/10_TASK_MCP_READONLY_SERVER.md:3-14`. | Do not hard-depend on EAP; report sidecar unavailable unless a caller explicitly loads a valid sidecar dict and passes it to `ProviderContext`. |
| Legacy FastMCP has path and report side effects | Implementation/security | `rdc_open_capture(rdc_path)` and `rdc_analyze(...)` are tools at `scripts/rdc_mcp/rdc_mcp.py:104-193`; worker creates output dir at `scripts/rdc_mcp/rdc_worker.py:220-226`. | Do not add the first EAP provider MVP here. Refactor later behind read-only, allowlisted semantics. |
| Live RenderDoc server-side handler is not visible in this checkout | Configuration/implementation | Client expects `renderdoc_extension/socket_server.py` and `%TEMP%/renderdoc_mcp`, evidence `tools/mcp/mcp_server/bridge/client.py:14-18`. | Keep `live_renderdoc` optional and expose bridge health as limitations. |
| `snapshot.v1` pipelines are known partial/unavailable | Implementation | `BuildGlobalMissingFieldPaths()` includes pipelines and source fields at `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp:85-94`; root pipelines output is empty at `:921`. | Availability must keep missing pipeline/shader details visible instead of fabricating empty facts. |

## Audit Decision

This task can safely keep the Data Availability path as pure Python data modeling under
`tools/mcp/providers/`, with compatibility wrappers in `tools/mcp/snapshot_consumer.py`. Phase 3 adds
only a controlled explicit `.rmeta.json` loader that returns a dict for `ProviderContext`; it should
not register a new FastMCP tool yet because the only visible FastMCP server is the older path-based
`scripts/rdc_mcp` surface, and registering there would mix the new provider contract into a
side-effect-capable server before routing and server ownership are separated.

The existing MCP surface is best described as:

```text
snapshot-first MCP supplement layer
  + optional live_renderdoc bridge client
  + separate legacy renderdoc_native FastMCP worker
```

It is not an EAP-native MCP server yet.
