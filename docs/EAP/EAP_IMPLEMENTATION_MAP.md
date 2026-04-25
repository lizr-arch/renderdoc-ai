# EAP Implementation Map

Scope: repository reconnaissance and implementation mapping only. This document does not introduce
EAP runtime code, renderer behavior changes, shader changes, resource-loading changes, MCP server
code, or RenderDoc core modifications.

Evidence note: Context MCP tools were not exposed in this session, so the mapping below is based on
local repository inspection with `git status`, `git grep`, `Select-String`, and targeted file reads.

## 1. Repository Summary

This checkout is a RenderDoc fork / RenderDoc AI tool workspace, not a game engine repository.

| Item | Finding | Evidence |
| --- | --- | --- |
| Repository type | RenderDoc core + qrenderdoc Qt UI + renderdoccmd + Python analyzer/report tooling + MCP helper tooling. It is not an engine/RHI repository. | `CMakeLists.txt:201`, `CMakeLists.txt:486`, `CMakeLists.txt:513`, `CMakeLists.txt:517`, `scripts/rdc_analyzer/docs/INDEX.md:41`, `tools/mcp/mcp_server/bridge/client.py:27` |
| Main languages | C/C++ for RenderDoc and qrenderdoc, Python for analyzer/MCP tooling, Qt/QMake/CMake glue for UI. | `CMakeLists.txt:201`, `CMakeLists.txt:491-503`, `qrenderdoc/CMakeLists.txt:417-421`, `scripts/rdc_analyzer/README.md:400` |
| Main build system | Top-level CMake drives RenderDoc, qrenderdoc, renderdoccmd; qrenderdoc also invokes qmake. Windows project files exist but are not the SSOT for this map. | `CMakeLists.txt:486`, `CMakeLists.txt:513`, `CMakeLists.txt:517`, `qrenderdoc/CMakeLists.txt:417-421`, `renderdoc/renderdoc.vcxproj:172` |
| Main platforms | Windows, Linux, Android, macOS/Metal are represented. Android disables qrenderdoc and Python modules in this build. | `CMakeLists.txt:21`, `CMakeLists.txt:301-306`, `CMakeLists.txt:203-210`, `renderdoc/driver/metal/metal_device.h:51-60` |
| EAP placement judgment | EAP emission belongs in an engine-side runtime/developer module that owns render graph, RHI command recording, resources, materials, meshes, and capture lifecycle. This repository should be used as RenderDoc API reference, backend support evidence, annotation viewer/consumer, analyzer/report consumer, and optional validation/demo surface. | No hits for engine symbols such as `FRDGBuilder`, `FRHICommandList`, `FMeshBatch`, `FMaterial`, `RenderGraph`, `AddPass`, `MaterialId`, `MeshId`, `asset.guid`, `permutation_hash`, `pso_hash` under non-3rdparty repo paths. |

Important boundary: EAP should not start by modifying RenderDoc core. RenderDoc already exposes a
rich application annotation API in `renderdoc/api/app/renderdoc_app.h`, and this repository already
contains backend persistence/display paths for those annotations. The first implementation should
therefore be a bridge in the engine/application process that calls RenderDoc's app API dynamically.

## 2. Relevant Existing RenderDoc Integration

### Existing RenderDoc API and annotation support

| File path | Related class/function | Current role | Reuse for EAP? | Risk |
| --- | --- | --- | --- | --- |
| `renderdoc/api/app/renderdoc_app.h` | `pRENDERDOC_GetAPI`, `RENDERDOC_API_1_7_0`, `SetObjectAnnotation`, `SetCommandAnnotation` | Public in-application API header. API 1.7.0 adds rich object/command annotations. | Yes. This is the primary bridge header for engine-side EAP emission. | Must be dynamically loaded and version checked; older RenderDoc versions will not expose annotation functions. |
| `docs/in_application_api.rst` | `RENDERDOC_GetAPI`, dynamic loading examples, capture functions | Official local docs for app-side API loading and capture lifecycle. | Yes. Use as exact bridge behavior reference. | Do not link against RenderDoc directly; docs recommend dynamic lookup. |
| `renderdoc/replay/app_api.cpp` | `StartFrameCapture`, `IsFrameCapturing`, `EndFrameCapture`, `SetObjectAnnotation`, `SetCommandAnnotation`, `RENDERDOC_GetAPI` | Exported app API implementation; routes annotation calls through an `IFrameCapturer`. | Reference only. Do not modify for EAP MVP. | Changing this would modify RenderDoc core behavior, explicitly out of scope. |
| `renderdoc/core/core.h` / `renderdoc/core/core.cpp` | `IFrameCapturer`, `StartFrameCapture`, `EndFrameCapture`, `IsFrameCapturing` | RenderDoc capture coordinator and backend capturer abstraction. | Reference only. | Core changes are high risk and unnecessary for engine-side EAP. |
| `docs/how/how_annotate_capture.rst` | rich custom annotations overview | Explains rich structured object/command annotations. | Yes, for user-facing protocol docs and acceptance tests. | API details vary by graphics backend. |
| `docs/window/annotation_viewer.rst` | Annotation Viewer, object/command annotation behavior | Documents display behavior and semantics: object annotations are saved at capture end, command annotations are per event. | Yes, for validation and expected UI behavior. | D3D12/Vulkan have queue and command-buffer levels; D3D11/GL are immediate-level only. |
| `util/test/demos/test_common.cpp` | dynamic `RENDERDOC_GetAPI` loading, API 1.7.0 request | Existing app-side dynamic loading example across Windows, Android, Linux, macOS. | Yes, as implementation reference for `FEAPRenderDocBridge`. | Demo code is not an engine module; copy the pattern, not the file ownership. |
| `util/test/demos/d3d11/d3d11_annotations.cpp` | `SetObjectAnnotation`, `SetCommandAnnotation` | D3D11 annotation demo. | Yes, as sample acceptance behavior. | Demo keys are generic; EAP keys must use `eap.*`. |
| `util/test/demos/d3d12/d3d12_annotations.cpp` | `SetObjectAnnotation`, `SetCommandAnnotation` | D3D12 annotation demo. | Yes, as queue/command buffer reference. | D3D12 queue/list split affects command annotation target selection. |
| `util/test/demos/gl/gl_annotations.cpp` | `SetObjectAnnotation`, `SetCommandAnnotation` | GL annotation demo. | Yes, as immediate-level reference. | GL has different object handle conventions. |
| `util/test/demos/vk/vk_annotations.cpp` | `SetObjectAnnotation`, `SetCommandAnnotation` | Vulkan annotation demo. | Yes, as queue/command-buffer reference. | Must pass correct `VkQueue`/`VkCommandBuffer` and device pointer. |

Key line evidence:

- `renderdoc/api/app/renderdoc_app.h:678-684` declares annotation function pointer types.
- `renderdoc/api/app/renderdoc_app.h:717` defines `eRENDERDOC_API_Version_1_7_0`.
- `renderdoc/api/app/renderdoc_app.h:748` says 1.7.0 added `SetObjectAnnotation()` /
  `SetCommandAnnotation()`.
- `renderdoc/api/app/renderdoc_app.h:831-832` places the annotation functions in the API table.
- `renderdoc/api/app/renderdoc_app.h:871` defines `pRENDERDOC_GetAPI`.
- `docs/in_application_api.rst:10-14` says the app should fetch `RENDERDOC_GetAPI`
  dynamically instead of linking against the DLL.
- `docs/in_application_api.rst:35-48` shows `GetModuleHandleA("renderdoc.dll")`,
  `dlopen("librenderdoc.so", RTLD_NOW | RTLD_NOLOAD)`, and Android replacement with
  `libVkLayer_GLES_RenderDoc.so`.
- `renderdoc/replay/app_api.cpp:254-331` validates and routes object/command annotations.
- `renderdoc/replay/app_api.cpp:386-401` fills the app API function table.
- `renderdoc/replay/app_api.cpp:404-409` exports `RENDERDOC_GetAPI`.

### Backend annotation persistence/display support

| Backend | Relevant files | Finding | EAP implication |
| --- | --- | --- | --- |
| D3D11 | `renderdoc/driver/d3d11/d3d11_context_wrap.cpp`, `renderdoc/driver/d3d11/d3d11_device.cpp` | `SetCommandAnnotation` and `SetObjectAnnotation` are serialized; markers/events/draws/dispatch are already captured. | EAP can use app API without D3D11 core changes. |
| D3D12 | `renderdoc/driver/d3d12/d3d12_command_list_wrap.cpp`, `renderdoc/driver/d3d12/d3d12_command_queue_wrap.cpp`, `renderdoc/driver/d3d12/d3d12_device.cpp` | Command-list and queue markers exist; `SetCommandAnnotation` / `SetObjectAnnotation` are implemented; `ExecuteIndirect` and raytracing paths exist. | EAP must choose queue vs command-list annotation target carefully. |
| Vulkan | `renderdoc/driver/vulkan/wrappers/vk_misc_funcs.cpp`, `vk_draw_funcs.cpp`, `vk_cmd_funcs.cpp`, `vk_queue_funcs.cpp` | Object and command annotations exist; DebugMarker/DebugUtils labels and queue submit paths are captured. | EAP can annotate queues/command buffers, but command-buffer lifetime and submit timing matter. |
| OpenGL | `renderdoc/driver/gl/wrappers/gl_debug_funcs.cpp`, `gl_draw_funcs.cpp`, `gl_buffer_funcs.cpp`, `gl_texture_funcs.cpp` | Object and command annotations exist; debug groups and labels are captured. | EAP has immediate-level annotation behavior only. |
| Metal | `renderdoc/driver/metal/metal_device.h` | `SetObjectAnnotation` and `SetCommandAnnotation` currently return `2`. | Treat Metal annotation support as unsupported for MVP; bridge should no-op or sidecar-only. |

### Analyzer/report/MCP surfaces already present

| File path | Current role | Reuse for EAP? | Risk |
| --- | --- | --- | --- |
| `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp` | Writes `analysis.json`, `issues_export.csv`, `issues_export.md`, `capture_context.json`, and `snapshot.v1.json` through Qt JSON/files. | Later GUI/export consumer can read EAP sidecar or annotations and fold them into `snapshot.v1`; not the first emission point. | `WriteBytes` directly truncates target files; engine sidecar should use temp-write-then-rename instead. |
| `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp` | Converts analyzer snapshot data to JSON. | Later mapping target for EAP-derived fields if they become snapshot facts. | Must not create a second snapshot schema. |
| `qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp` | Builds `snapshot.v1` sections and evidence index. | Later consumer if EAP annotations/sidecar become report facts. | Current snapshot availability says several pipeline/binding fields are partial; do not overpromise. |
| `scripts/rdc_analyzer/docs/EXPORT_ROUTES.md` | Documents `.rdc/.xml/.zip.xml` to bundle/snapshot report routes. | Later CLI/offline consumer for `capture.rmeta.json`. | Keep sidecar consumption as input to existing report routes; do not create another report system. |
| `tools/mcp/mcp_server/bridge/client.py` | Python IPC client named `RenderDocBridge` for MCP communication with a RenderDoc extension socket server. | Reuse only for MCP/live-query consumer work. It is not an engine-side `renderdoc_app.h` bridge. | Naming collision risk: do not call the engine runtime bridge the same thing in Python/MCP namespaces without qualification. |
| `tools/mcp/snapshot_consumer.py` | Consumes `snapshot.v1` and optionally imports MCP `RenderDocBridge`. | Later AI/MCP consumer can query EAP-derived gaps after snapshot mapping exists. | MCP contract explicitly says it is not a full report generator. |

Product-contract boundary evidence:

- `docs/product/development_charter.md:51-53` says GUI/offline must reuse the same fact
  structure/template contract and report output is deterministic facts plus rules.
- `docs/product/development_charter.md:59-64` says MCP is for realtime query/fill only and
  does not generate whole reports.
- `docs/product/development_charter.md:81-90` says Analyzer Report is the report product line's
  fact/rule engine, not another parallel system.
- `docs/product/snapshot_schema_v1.md:3-4` makes `snapshot.v1` the GUI/offline/Skill fact
  snapshot and excludes MCP realtime responses.
- `docs/product/mcp_query_contract_v1.md:3-5` defines MCP as loaded-capture realtime query and
  not full report export.

### Existing EAP-specific code

未发现 existing EAP implementation.

Searches performed:

- `FEAP`, `Engine Annotation Protocol`, `ENABLE_EAP`: no hits under repository paths excluding
  `renderdoc/3rdparty`, `qrenderdoc/3rdparty`, and `scripts/rdc_analyzer/test_captures`.
- `FRDGBuilder`, `FRHICommandList`, `RHICommandList`, `FMeshBatch`, `FMaterial`, `UMaterial`,
  `RenderGraph`, `AddPass`, `ExecutePass`, `MaterialId`, `MeshId`, `asset.guid`,
  `permutation_hash`, `pso_hash`: no hits under the same scope.
- `RenderDocBridge`: found `tools/mcp/mcp_server/bridge/client.py:27`, but that is MCP IPC,
  not a C++ application-side RenderDoc API bridge.

## 3. Proposed EAP Module Layout

Because this repository is not an engine repository, EAP emission modules should not be placed under
RenderDoc core directories such as `renderdoc/driver/*`, `renderdoc/core/*`, or shader/resource
loading paths. Recommended layout is split into current-repo consumer/reference surfaces and target
engine-side emission surfaces.

### Current repository layout

| Directory | Purpose | Runtime? | Editor-only? | Shipping disabled? | Depends on RenderDoc? | Depends on renderer/RHI? |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `Docs/EAP/` | EAP design, implementation maps, protocol notes, handoff docs. | No | No | Not applicable | No direct code dependency | No |
| `util/test/demos/` | Later optional annotation sample validation using existing demo harness. | Test/demo runtime only | No | Not production | Yes, via `renderdoc_app.h` | Yes, via API-specific demos |
| `scripts/rdc_analyzer/` | Later offline analyzer/report sidecar consumer, if `capture.rmeta.json` must feed bundle/snapshot reports. | No | No | Not shipped in app | Consumes captures/XML/snapshots | No direct engine RHI |
| `qrenderdoc/Code/Analyzer/` | Later GUI/export consumer if EAP facts are integrated into `snapshot.v1`. | Desktop tool runtime | Tool-only | Not game shipping | Yes, internal RenderDoc/qrenderdoc | Replay data, not engine RHI |
| `tools/mcp/` | Later MCP/local live-query gap filler mapped to `snapshot.v1`. | Tool runtime | Tool-only | Not game shipping | Yes, via IPC bridge | No engine RHI |

### Target engine-side layout to add later

The exact paths depend on the actual engine repository. This checkout does not contain module
descriptors or engine source roots, so these are placement rules rather than current files:

| Suggested engine path | Purpose | Runtime? | Editor-only? | Shipping disabled? | Depends on RenderDoc? | Depends on renderer/RHI? |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `Source/Developer/EAP/` or engine equivalent | Developer-only EAP feature flag, bridge, capture session coordinator, sidecar writer. | Development runtime | Usually yes/development | Yes by default | Dynamically only | Light dependency on renderer/RHI bridge |
| `Source/Runtime/EAP/` only if engine needs runtime capture in non-editor builds | Minimal no-op-safe facade used by renderer code without pulling editor dependencies. | Yes | No | Compiled out or no-op in shipping | Header-only/dynamic | Facade only |
| `Source/Renderer/EAP/` or renderer plugin equivalent | Thin hook adapters for render graph pass/draw/resource events. | Yes in dev builds | No | Yes | Through bridge facade only | Yes |
| `Tools/EAPAnalyzer/` only if sidecar validation is engine-local | Validate `capture.rmeta.json` and redaction/budget rules before ingest into RenderDoc tooling. | No | Tool-only | Not shipped | Optional | No |

Rule: renderer code should call an EAP facade (`EAP::AnnotatePass`, `EAP::AnnotateDraw`,
`EAP::AnnotateResource`) and should not know about `RENDERDOC_API_1_7_0` layout details.

## 4. RenderDocBridge Insertion Point

Best later implementation point: an engine-side developer/runtime bridge class such as
`FEAPRenderDocBridge`, owned by the engine module that already coordinates debug markers, frame
capture, or RHI diagnostic tooling. This repository does not contain that engine module, so no
current RenderDoc source file should be modified for the MVP.

### Dynamic library loading

Use dynamic lookup, not static linking:

- Windows: query already-loaded `renderdoc.dll` with `GetModuleHandleA`, then `GetProcAddress`.
  Evidence: `docs/in_application_api.rst:14`, `docs/in_application_api.rst:35-39`,
  `util/test/demos/test_common.cpp:631-633`.
- Linux: use `dlopen("librenderdoc.so", RTLD_NOW | RTLD_NOLOAD)`, then `dlsym`.
  Evidence: `docs/in_application_api.rst:14`, `docs/in_application_api.rst:45-48`,
  `util/test/demos/test_common.cpp:639-641`.
- Android: use `libVkLayer_GLES_RenderDoc.so` instead of `librenderdoc.so`.
  Evidence: `docs/in_application_api.rst:44`, `util/test/demos/test_common.cpp:635-637`.
- macOS: existing demo also looks for `librenderdoc.dylib`.
  Evidence: `util/test/demos/test_common.cpp:643-645`.

### Header inclusion

- Use `renderdoc_app.h` as the only bridge header. In this repo it is
  `renderdoc/api/app/renderdoc_app.h`.
- `renderdoc/CMakeLists.txt:102` includes `api/app/renderdoc_app.h` in the RenderDoc source list.
- `renderdoc/CMakeLists.txt:685` installs it as public `include/renderdoc_app.h`.
- In an engine repository, prefer a vendored/public include copy or installed RenderDoc SDK include
  path. Do not include private RenderDoc core headers.

### API version

Request `eRENDERDOC_API_Version_1_7_0` first:

- `renderdoc/api/app/renderdoc_app.h:717` defines `eRENDERDOC_API_Version_1_7_0`.
- `renderdoc/api/app/renderdoc_app.h:748` says API 1.7.0 added rich object/command annotations.
- `util/test/demos/test_common.cpp:652` requests `eRENDERDOC_API_Version_1_7_0`.

Fallback policy:

1. If RenderDoc library is absent: bridge initializes as unavailable and all calls are no-op.
2. If `RENDERDOC_GetAPI` is missing: unavailable/no-op.
3. If requesting API 1.7.0 fails: keep capture-control fallback optional only if the engine needs it,
   but disable EAP annotation emission because `SetObjectAnnotation`/`SetCommandAnnotation` are not
   guaranteed.
4. If annotation calls return unsupported, record a per-frame counter and optionally emit sidecar-only
   metadata.
5. If `IsFrameCapturing()` is false and `eap.capture_only=true`, skip command/object annotations.

### Platform conditions

The bridge should be compiled behind platform gates matching the engine build system:

- Windows: `ENABLE_EAP && PLATFORM_WINDOWS` or equivalent.
- Linux: `ENABLE_EAP && PLATFORM_LINUX`.
- Android: `ENABLE_EAP && PLATFORM_ANDROID`, with RenderDoc layer library naming and remote-capture
  expectations.
- macOS/Metal: build can compile, but annotation emission should be treated unsupported unless a
  backend proves otherwise. Evidence: `renderdoc/driver/metal/metal_device.h:51-60` returns `2` for
  both annotation calls.

No-op fallback must be the default state. Renderer/RHI code should be able to call the EAP facade
unconditionally in development builds without requiring RenderDoc to be installed.

## 5. RenderGraph / Pass Hook Points

### Current repository findings

未发现 engine render graph pass creation/execution points in this checkout.

Searches performed:

- `RenderGraph`, `FRDGBuilder`, `AddPass`, `ExecutePass`, `FRHICommandList`, `RHICommandList`
  under non-3rdparty repo paths: no hits.

Current RenderDoc backend marker/annotation evidence is still useful as consumer behavior:

| Backend | Marker/pass-like capture points | Evidence |
| --- | --- | --- |
| D3D11 | `SetMarker`, `BeginEvent`, `EndEvent`, thread-safe marker queue, `SetCommandAnnotation`. | `renderdoc/driver/d3d11/d3d11_context_wrap.cpp:45`, `:140`, `:193`, `:231`, `:304-337` |
| D3D12 | Command-list `SetMarker`/`BeginEvent`/`EndEvent`, queue marker/event paths, command annotations. | `renderdoc/driver/d3d12/d3d12_command_list_wrap.cpp:3143-3346`, `renderdoc/driver/d3d12/d3d12_command_queue_wrap.cpp:1231-1386`, `renderdoc/driver/d3d12/d3d12_device.cpp:3466-3520` |
| Vulkan | DebugMarker/DebugUtils command-buffer labels, queue labels, command annotations. | `renderdoc/driver/vulkan/wrappers/vk_cmd_funcs.cpp:6704-6906`, `renderdoc/driver/vulkan/wrappers/vk_queue_funcs.cpp:2095-2245`, `renderdoc/driver/vulkan/wrappers/vk_misc_funcs.cpp:2851-2937` |
| OpenGL | `glPushDebugGroup`, `glPopDebugGroup`, `SetCommandAnnotation`. | `renderdoc/driver/gl/wrappers/gl_debug_funcs.cpp:239-317`, `:557-652` |

### Recommended engine hook points

In the actual engine repo, hook pass annotations at:

1. Render graph pass creation: assign stable EAP pass node IDs and pass category metadata.
2. Pass execute/record: emit `SetCommandAnnotation` on the active command list/command buffer/queue.
3. GPU marker wrapper: mirror existing engine marker names into EAP keys, but do not replace normal
   GPU debug markers.
4. Queue submit boundary: attach queue-level annotation for queue and view when a backend supports it.

### Multi-threading and safety

- D3D11 shows explicit thread-safe marker handling in `WrappedID3D11DeviceContext::ThreadSafe_*`.
  Evidence: `renderdoc/driver/d3d11/d3d11_context_wrap.cpp:304-337`.
- D3D12 and Vulkan have command list / command buffer and queue-level concepts. Evidence:
  `docs/window/annotation_viewer.rst:60` says Vulkan and D3D12 have both queue-level and
  command-buffer-level annotations, while OpenGL and D3D11 have one immediate level.
- Command annotation should be emitted on the thread that owns command recording or through the
  engine's existing command-list enqueue mechanism. Do not write EAP annotations from arbitrary game
  thread code against command objects whose lifetime is owned by the render thread.

Recommended pass keys:

- `eap.rg.node_id`
- `eap.pass.name`
- `eap.pass.category`
- `eap.pass.queue`
- `eap.view.id`

## 6. Draw / Dispatch Hook Points

### Current repository findings

未发现 engine draw/dispatch semantic ownership points such as materials, mesh batches, PSO hashes, or
shader permutation hashes.

Searches performed:

- `FMeshBatch`, `FMaterial`, `UMaterial`, `MaterialId`, `MeshId`, `permutation_hash`, `pso_hash`
  under non-3rdparty repo paths: no hits.

RenderDoc does contain low-level API draw/dispatch wrappers. These are capture/replay implementation
points, not the right place to infer engine semantics for EAP MVP:

| Backend | Draw/dispatch evidence | Special paths seen |
| --- | --- | --- |
| D3D11 | `DrawIndexedInstanced`, `DrawIndexed`, `Draw`, `DrawIndexedInstancedIndirect`, `Dispatch`. Evidence: `renderdoc/driver/d3d11/d3d11_context_wrap.cpp:3949-4223`, `:4379-4502`, `:5146-5217`. | Instancing and indirect draw are present. |
| D3D12 | `DrawInstanced`, `DrawIndexedInstanced`, `Dispatch`, `ExecuteIndirect`; raytracing dispatch appears in command/device handling. Evidence: `renderdoc/driver/d3d12/d3d12_command_list_wrap.cpp:3388-3611`, `:4285-4726`, `renderdoc/driver/d3d12/d3d12_device.cpp:5265-5268`. | Instancing, execute-indirect, indirect ray dispatch, raytracing dispatch paths. |
| Vulkan | `vkCmdDraw`, `vkCmdDrawIndexed`, indirect draw, `vkCmdDispatch`, dispatch indirect. Evidence: `renderdoc/driver/vulkan/wrappers/vk_draw_funcs.cpp:166-337`, `:345-1120`, `:1134-1292`. | Indirect draw/dispatch are present. |
| OpenGL | `glDrawArrays`, `glDrawElements`, instanced/multi/indirect variants, `glDispatchCompute`. Evidence: `renderdoc/driver/gl/wrappers/gl_draw_funcs.cpp:297-550`, `:945-1427`, `:2468-3606`, `:4963-5021`. | Multi-draw and indirect draw variants are present. |

### Recommended engine hook points

Hook in the engine renderer where draw/dispatch commands are still associated with high-level
semantic objects:

1. Draw packet / mesh batch build: capture `mesh id`, `mesh lod`, material pointer/name, shader
   permutation hash, draw reason.
2. PSO creation/cache lookup: capture `pso hash`, shader stage hashes, and pipeline category.
3. Command submission wrapper: emit the final draw/dispatch command annotation immediately before
   or as part of command recording.
4. Compute dispatch wrapper: emit `eap.draw.kind=dispatch` and compute shader/permutation fields.
5. Indirect draw/dispatch wrappers: record `eap.draw.kind=indirect_*` and sidecar map entries,
   because per-command argument expansion may not be CPU-visible at annotation time.

Fields directly available in this RenderDoc repo:

- Low-level API event kind/count/dispatch dimensions are available during capture/replay wrappers.
- API resource/shader/pipeline objects are available as RenderDoc resources.

Fields not available here and requiring engine-side mapping:

- `eap.draw.reason`
- `eap.material.id`
- `eap.material.name`
- `eap.shader.*.hash` as engine permutation identity rather than API shader object ID
- `eap.shader.permutation_hash`
- `eap.pso.hash` as engine cache key
- `eap.mesh.id`
- `eap.mesh.lod`
- asset GUID/path ownership

Recommended draw/dispatch keys:

- `eap.draw.kind`
- `eap.draw.reason`
- `eap.material.id`
- `eap.material.name`
- `eap.shader.vs.hash`
- `eap.shader.ps.hash`
- `eap.shader.cs.hash`
- `eap.shader.permutation_hash`
- `eap.pso.hash`
- `eap.mesh.id`
- `eap.mesh.lod`

## 7. Resource Annotation Hook Points

### Current repository findings

RenderDoc captures API-level resource creation and supports object annotations, but this repo does
not know engine asset ownership, streaming residency, imported-resource ownership, or transient
render graph resource identity.

API-level creation/reference points:

| Resource kind | Existing low-level points | Evidence |
| --- | --- | --- |
| D3D11 textures/buffers/shaders/views | `CreateTexture*`, `CreateBuffer`, shader creation chunks. | `renderdoc/driver/d3d11/d3d11_device.cpp:1062-1083`, `:1091-1095` |
| D3D12 resources/pipelines | `CreateCommittedResource*`, `CreateGraphicsPipelineState`, `CreateComputePipelineState`, raytracing AS entries. | `renderdoc/driver/d3d12/d3d12_device.cpp:5089-5149`, `:3708`, `:3799`, `:4244-4312` |
| Vulkan images/buffers/pipelines | `vkCreateImage`, `vkCreateBuffer`, graphics/compute pipelines, object names/tags. | `renderdoc/driver/vulkan/wrappers/vk_misc_funcs.cpp:2769-2851`, `:2969-3262`; `renderdoc/driver/vulkan/wrappers/vk_draw_funcs.cpp:69` |
| OpenGL textures/buffers/labels | `glBufferData`, `glTexImage*`, `glObjectLabel`, object annotation. | `renderdoc/driver/gl/wrappers/gl_buffer_funcs.cpp:789-813`, `renderdoc/driver/gl/wrappers/gl_texture_funcs.cpp:2687-5471`, `renderdoc/driver/gl/wrappers/gl_debug_funcs.cpp:118-198`, `:317` |

Object annotation behavior:

- `docs/window/annotation_viewer.rst:33-44` says object annotations are visible in Resource
  Inspector.
- `docs/window/annotation_viewer.rst:56` says object annotations can be set at any time and latest
  contents are saved when capture ends.
- `docs/window/annotation_viewer.rst:99` documents special object properties like `resource`,
  `resource.__offset`, and `resource.__size` for buffer subranges.

### Recommended engine hook points

Hook resources after the backend handle exists and before the capture ends:

| Resource category | Recommended hook | Direct fields | Requires later mapping |
| --- | --- | --- | --- |
| Texture creation | Engine RHI texture create wrapper, render graph texture allocation, import wrapper. | kind, format, width, height, mips, API object pointer/handle. | owner, asset GUID/path, streaming mip state, transient/imported identity. |
| Buffer creation | Engine RHI buffer create wrapper and upload/streaming buffer allocator. | kind, size, usage, API object pointer/handle. | owner, mesh/material/asset association, subrange names. |
| Render target creation | Render graph render-target allocation and swapchain/backbuffer wrapping. | dimensions, format, sample count, transient flag. | pass producer/consumer list, view id. |
| Transient render graph resource | Render graph resource allocator. | transient id/name, pass lifetime. | mapping to API object after allocation aliasing. |
| Imported external resource | Import/wrap API handle function. | external handle and dimensions if known. | external owner redaction, lifetime guarantees. |
| Asset-backed resource | Asset streaming/resource manager registration. | asset path/GUID/name before redaction. | privacy policy and stable asset IDs. |
| Streaming resource | Streaming manager residency updates. | resident/wanted mips. | frame-specific history and budget reasons. |

Recommended resource keys:

- `eap.resource.kind`
- `eap.resource.owner`
- `eap.resource.name`
- `eap.resource.format`
- `eap.resource.width`
- `eap.resource.height`
- `eap.resource.mips`
- `eap.asset.guid`
- `eap.asset.path`
- `eap.streaming.resident_mip`
- `eap.streaming.wanted_mip`

## 8. Sidecar Metadata Output Point

Best later output point: the engine's capture session coordinator, immediately around
`StartFrameCapture` / `EndFrameCapture`, not RenderDoc core.

Relevant RenderDoc app API:

- `renderdoc/api/app/renderdoc_app.h:409` declares `SetCaptureFilePathTemplate`.
- `renderdoc/api/app/renderdoc_app.h:419` declares `GetNumCaptures`.
- `renderdoc/api/app/renderdoc_app.h:435` declares `GetCapture`.
- `renderdoc/api/app/renderdoc_app.h:565` declares `SetCaptureTitle`.
- `docs/in_application_api.rst:302-343` documents path template and capture query behavior.
- `docs/in_application_api.rst:398-436` documents `StartFrameCapture`, `IsFrameCapturing`, and
  `EndFrameCapture`.

### Recommended sidecar lifecycle

1. On capture begin:
   - Open a frame-scoped EAP session.
   - Record project/build/branch/commit/map/camera/platform if the engine can provide them.
   - Start bounded in-memory counters/maps for annotations.
2. During frame:
   - Collect pass/draw/resource metadata in engine-owned stable IDs.
   - Emit RenderDoc annotations only when `eap.emit_annotations=true` and bridge is available.
   - Keep sidecar data independent of annotation success.
3. On capture end:
   - Call `EndFrameCapture`.
   - Use `GetNumCaptures` / `GetCapture` when available to identify the actual `.rdc` path, or use
     the engine's configured capture path template if the engine owns it.
   - Write `capture.rmeta.json` next to the `.rdc`, using the same base name.

### Artifact/output directory

Preferred ordering:

1. Explicit EAP output directory config.
2. RenderDoc capture path returned by `GetCapture`.
3. Engine project/saved/profiling/captures directory.
4. Current process working directory only as a development fallback.

### JSON writer availability

- qrenderdoc has Qt JSON support via `QJsonDocument` and `QJsonObject`.
  Evidence: `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp:27-28`,
  `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp:133-150`.
- Python analyzer tooling can naturally use Python JSON, but that is offline/tooling only.
- For an engine runtime sidecar writer, prefer the engine's native JSON writer. If absent, implement
  a minimal deterministic writer for strings/numbers/bools/arrays/objects with strict escaping and
  a fixed schema. Do not add a third-party JSON library for MVP.

### Crash-safe write strategy

The current qrenderdoc exporter writes directly with truncation:

- `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp:153-170` opens `QFile` with
  `QIODevice::WriteOnly | QIODevice::Truncate`, writes, closes, and validates byte count.

Engine-side sidecar should be stricter:

1. Write to `capture.rmeta.json.tmp.<pid>`.
2. Flush and close.
3. Atomically rename/replace to `capture.rmeta.json`.
4. Include `capture_path`, `capture_basename`, `frame_index`, `eap_schema_version`, annotation
   counts, and `complete=true` only after successful close.
5. On crash/partial write, leave `.tmp` or `complete=false` for diagnostics.

### Privacy and redaction

Asset paths, user names, branch names, and map/camera metadata can leak private project structure.
Default to:

- stable GUIDs/hashes in annotations,
- optional redacted asset path in sidecar,
- full local paths only behind a development opt-in flag.

## 9. Feature Flag / Runtime Toggle

Recommended flags belong in the engine/application module, not RenderDoc core.

| Toggle | Suggested name | Default | Purpose |
| --- | --- | --- | --- |
| Compile-time flag | `ENABLE_EAP` | Off for shipping, on for editor/development if enabled by project | Compiles EAP facade/bridge and renderer hook calls. |
| Runtime master | `eap.enabled` | Off unless developer enables | Master runtime gate. |
| Annotation emission | `eap.emit_annotations` | On only when `eap.enabled` | Calls `SetObjectAnnotation` / `SetCommandAnnotation`. |
| Sidecar emission | `eap.emit_sidecar` | On only when `eap.enabled` | Writes `capture.rmeta.json`. |
| Capture-only | `eap.capture_only` | On | Skip per-command/object annotations unless `IsFrameCapturing()` is true. |
| Budget | `eap.max_annotations_per_frame` | Bounded, e.g. 10k for MVP | Prevents runaway annotation overhead. |

Recommended build policy:

- Editor/development builds: compile bridge and facade; runtime default off.
- Test builds: compile and allow forced no-op/mock bridge for tests.
- Shipping builds: compile out or no-op by default; never emit asset paths or capture metadata unless
  a project explicitly creates an internal development shipping profile.

Overhead strategy:

1. Cheap branch first: `if(!EAPEnabled) return;`.
2. Cache RenderDoc API availability and `IsFrameCapturing()` state per frame.
3. Emit stable IDs and hashes, not large strings, on hot draw paths.
4. Move heavy string/path formatting to sidecar aggregation outside the draw-call hot path.
5. Enforce annotation count and string length limits.

## 10. Build System Changes Needed Later

No build files should be changed in this reconnaissance round. Later changes depend on whether work
is performed in the engine repository or in this RenderDoc/tooling repository.

| File/path | Expected later modification | Platform-related? | Risk |
| --- | --- | ---: | --- |
| Target engine module build descriptor, not present in this repo | Add EAP source files, `ENABLE_EAP`, include path for `renderdoc_app.h`, and platform libraries for dynamic loading if needed. | Yes | Medium. Wrong module ownership can pull renderer dependencies into shipping builds. |
| Target engine renderer/RHI module build descriptor, not present in this repo | Add dependency on lightweight EAP facade only, not full bridge implementation. | Yes | Medium. Avoid circular renderer/developer-tool dependency. |
| `CMakeLists.txt` | No change for bridge MVP in this repo. Only change later if adding repo-local tooling/tests. Current build already defines RenderDoc project and platform options. | Yes | Low if untouched; high if EAP is incorrectly added to RenderDoc core. |
| `renderdoc/CMakeLists.txt` | No change for engine bridge MVP. It already includes and installs `renderdoc_app.h`. | Yes | High if modified unnecessarily because it affects RenderDoc core library. |
| `qrenderdoc/CMakeLists.txt` | Later only if GUI Analyzer consumes EAP sidecar into `snapshot.v1`. | Desktop only; Android qrenderdoc is disabled. | Medium. Qt/Python build coupling is non-trivial. |
| `scripts/rdc_analyzer/` packaging/tests | Later only if offline analyzer reads `capture.rmeta.json` or validates EAP schema. | Python version/path-sensitive | Low to medium. Keep schema compatibility with `snapshot.v1`. |
| `tools/mcp/` | Later only if MCP query contract exposes EAP-derived facts. | Desktop tool only | Medium. Must map to `snapshot.v1` and not generate separate reports. |

Build evidence:

- `CMakeLists.txt:203-210` defines major feature options for GL/GLES/EGL/Vulkan/Metal/renderdoccmd/qrenderdoc/Python.
- `CMakeLists.txt:301-306` disables qrenderdoc and Python modules for Android.
- `CMakeLists.txt:382-383` sets C++14 for the general build.
- `renderdoc/CMakeLists.txt:685` installs `renderdoc_app.h`.
- `qrenderdoc/CMakeLists.txt:417-421` drives the `QRenderDoc` custom target.

## 11. Test Plan

### Unit tests

- Bridge dynamic loading:
  - RenderDoc library absent -> no-op bridge, no crash.
  - `RENDERDOC_GetAPI` missing -> no-op bridge, diagnostic counter.
  - API 1.7.0 unavailable -> annotations disabled, optional capture-only API fallback if implemented.
  - Null device/command pointer behavior matches chosen backend policy.
- EAP value encoding:
  - string/int/uint/float/bool/object handles encoded into `RENDERDOC_AnnotationValue`.
  - invalid key/type/vector width rejected before calling RenderDoc.
- Sidecar writer:
  - success writes complete JSON.
  - failure leaves temp/partial state.
  - atomic rename path.
  - redaction of asset paths.
- Budget:
  - `eap.max_annotations_per_frame` clamps annotations and records dropped count.

### Integration tests

- Engine sample frame with RenderDoc installed:
  - Begin capture, emit pass/draw/resource annotations, end capture.
  - Open `.rdc` and verify annotations in Annotation Viewer / Resource Inspector.
- Engine sample frame without RenderDoc:
  - Same render path runs with no crash and sidecar-only behavior if enabled.
- API version too old:
  - Bridge detects lack of API 1.7.0 and emits no annotations.
- Sidecar consistency:
  - `capture.rmeta.json` base name matches `.rdc`.
  - sidecar `capture_id` / frame index / timestamp are consistent with capture metadata.
- Multithreaded recording:
  - worker command-list recording emits annotations on valid command objects only.
  - no data races in sidecar aggregation.
- Android:
  - dynamic lookup uses `libVkLayer_GLES_RenderDoc.so`.
  - remote capture path and sidecar path are explicitly resolved.
- Linux:
  - `dlopen(... RTLD_NOLOAD)` path works; no unwanted library load.
- Windows:
  - `GetModuleHandleA("renderdoc.dll")` path works; no static DLL dependency.

### Current repository validation surfaces

- Existing RenderDoc demo references:
  - `util/test/demos/test_common.cpp:628-652` for dynamic API loading.
  - `util/test/demos/d3d11/d3d11_annotations.cpp:48-170`.
  - `util/test/demos/d3d12/d3d12_annotations.cpp:49-179`.
  - `util/test/demos/gl/gl_annotations.cpp:53-168`.
  - `util/test/demos/vk/vk_annotations.cpp:74-209`.
- Existing analyzer tests:
  - `scripts/rdc_analyzer/tests/test_analysis_schema_contract.py`
  - `scripts/rdc_analyzer/tests/test_bridge.py`
  - `scripts/rdc_analyzer/tests/test_bridge_integration.py`
  - `scripts/rdc_analyzer/tests/test_bridge_standalone.py`
  - `scripts/rdc_analyzer/tests/test_compare_rdc.py`
- Existing C++ test locations:
  - `renderdoc/common/jobsystem_tests.cpp`
  - `renderdoc/common/threading_tests.cpp`
  - `renderdoc/serialise/serialiser_tests.cpp`
  - `renderdoc/driver/vulkan/imagestate_tests.cpp`

Suggested later commands:

- Python/offline analyzer tests, if sidecar parser is added:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py -q`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_bridge.py scripts/rdc_analyzer/tests/test_bridge_integration.py -q`
- RenderDoc/qrenderdoc build commands require explicit user authorization under this project's rules.

## 12. Risk Register

| Risk | Impact | Mitigation | Blocks MVP? |
| --- | --- | --- | ---: |
| RenderDoc is not installed or not injected/loaded. | Annotation calls unavailable; capture metadata may be incomplete. | Dynamic lookup only; no-op fallback; sidecar-only path. | No |
| RenderDoc API version is older than 1.7.0. | `SetObjectAnnotation`/`SetCommandAnnotation` unavailable. | Request 1.7.0; disable annotation emission if unavailable; log capability state. | No |
| Annotation overhead on hot draw paths. | Frame hitches during capture/development. | Capture-only gate, per-frame availability cache, budgets, stable IDs instead of long strings. | No |
| Multithreaded command recording races. | Crashes or annotations on wrong command buffer. | Emit only through render-command ownership path; aggregate sidecar data in thread-safe queues. | Yes for command annotations |
| Resource handle lifetime mismatch. | Object annotations point at destroyed/reused objects or aliasing resources. | Annotate after handle creation; use engine stable IDs in sidecar; account for transient aliasing. | Yes for resource annotations |
| Asset path leakage. | Private project/user paths appear in captures/sidecars. | Redact by default; emit GUID/hash; full path requires opt-in. | No |
| Shipping build leakage. | Debug metadata or RenderDoc bridge ships to users. | `ENABLE_EAP` shipping off; runtime hard gate; CI check for shipping disabled. | Yes |
| Sidecar and `.rdc` mismatch. | Analyzer reads metadata for the wrong capture. | Use actual path from `GetCapture`; include capture basename/timestamp/frame id; write next to `.rdc`. | Yes |
| Android remote capture path ambiguity. | Sidecar written on device while `.rdc` copied to host, or vice versa. | Explicit Android path policy; include device/host path fields; copy sidecar with capture artifact. | No |
| Backend differences: D3D11/GL immediate vs D3D12/Vulkan queue/command-buffer. | Incorrect command annotation lifetime or inheritance. | Backend-specific target selection; use docs/window behavior as contract. | Yes for cross-backend MVP |
| Metal returns unsupported for rich annotations. | EAP appears missing on Metal captures. | Mark Metal unsupported; sidecar-only fallback; no claim of Metal MVP. | No |
| Existing MCP `RenderDocBridge` name collision. | Future agents may reuse wrong bridge or mix IPC with app API. | Name engine bridge `EAPRenderDocAppBridge` or qualify as C++ app API bridge. | No |
| Duplicate report/schema creation. | EAP forks RenderDoc AI reporting instead of feeding `snapshot.v1`. | Keep EAP sidecar as input to existing Analyzer/CLI paths; update product contracts before report integration. | No |
| Annotation key explosion. | Annotation Viewer becomes noisy and capture size grows. | Strict `eap.*` schema, max count, max string length, sidecar for verbose metadata. | No |
| Indirect draw/dispatch lacks CPU-visible per-draw semantic data. | Per-command annotation may be incomplete. | Emit high-level indirect command metadata plus sidecar table; avoid pretending each generated draw is semantically resolved. | No |
| Captures without `IsFrameCapturing()` gate. | EAP overhead occurs every frame. | Default `eap.capture_only=true`; sidecar collection only inside capture session unless explicitly profiling. | No |

## 13. Proposed Next Codex Task

- Task name: RenderDocBridge MVP
- Goal: Implement a minimal engine-side C++ bridge that dynamically obtains `RENDERDOC_API_1_7_0`,
  exposes no-op-safe `IsAvailable`, `IsFrameCapturing`, `AnnotateObject`, and `AnnotateCommand`
  methods, and does not modify RenderDoc core or renderer behavior beyond opt-in calls through an
  EAP facade.
- Files to modify:
  - Current RenderDoc repo: none for the engine bridge MVP.
  - Target engine repo, to be located next: module build descriptor that owns developer/render
    diagnostics; existing capture/debug marker coordinator if one exists; existing renderer/RHI
    debug-marker facade if one exists.
- Files to add:
  - Target engine repo, expected: `EAPRenderDocAppBridge.h`, `EAPRenderDocAppBridge.cpp`, and a
    tiny `EAPConfig` / feature-flag file in the selected engine module.
  - Current RenderDoc repo: none unless the next task is explicitly changed to add demo/reference
    tests under `util/test/demos/` or analyzer consumers under `scripts/rdc_analyzer/`.
- Exact acceptance criteria:
  - Bridge compiles on Windows and Linux; Android path is compiled or clearly gated.
  - No static link dependency on RenderDoc.
  - When RenderDoc is absent, all public methods are no-op and return safe status.
  - When API 1.7.0 is present, bridge can call `SetObjectAnnotation` and `SetCommandAnnotation`
    with one string key/value in a sample capture.
  - Feature flags `ENABLE_EAP`, `eap.enabled`, `eap.emit_annotations`, and `eap.capture_only`
    are wired.
  - Shipping build either excludes bridge code or hard-disables emission.
  - No RenderDoc core, shader, renderer behavior, or resource loading changes are required for the
    bridge itself.
- Commands to build/test:
  - Engine repo, Windows: run the engine's normal focused developer/editor target build after user
    authorization.
  - Engine repo, Linux: run the focused CMake/Ninja or Make target after user authorization.
  - Unit/smoke: run bridge unit tests for absent library, missing symbol, old API, and no-op calls.
  - Manual RenderDoc smoke: inject/load RenderDoc, capture one frame, verify one command annotation
    and one object annotation in Annotation Viewer / Resource Inspector.
- Rollback plan:
  - Remove the added bridge/config files.
  - Remove `ENABLE_EAP` build flag and module include path.
  - Remove facade call sites if any were added.
  - No RenderDoc core rollback should be needed because the MVP must not modify RenderDoc core.
