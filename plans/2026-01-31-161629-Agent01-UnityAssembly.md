# Scope
## In
- Validate whether we can extract all data needed to assemble a viewable mesh/shader/material in Unity (Unity China 1.6.9) for a single draw event.
- Focus APIs: D3D11 + Vulkan first (D3D12/GLES later).
- Use existing Unity export pipeline and verify gaps with the provided RDC (`D:\backup\大远景.rdc`).

## Out
- Implementing D3D12/GLES export.
- Full asset reconstruction across multiple draws/batches.
- Automated Unity import (manual verification is acceptable for now).

# Assumptions
- We target a single `eventId` (draw call) that represents the character mesh.
- Capture API is Vulkan (per user confirmation).
- RenderDoc replay data is accessible for that event (buffers, textures, shaders, pipeline state).
- SPIRV-Cross is available for Vulkan shader decompile to HLSL.

# Build/Test/Lint Quick Guide (commands only, do not run)
- Python tests: `py -3 -m pytest`
  - Expected: `= ... passed, ... skipped` (no failures)
- Unity import: Manual (open Unity 1.6.9, import exported assets)

# Repo / File List (candidate touch points)
- `scripts/rdc_analyzer/export_unity_assets.py:1-40` (CLI entry; args & validation)
- `scripts/rdc_analyzer/exporters/unity_exporter.py:118` (export_mesh)
- `scripts/rdc_analyzer/exporters/unity_exporter.py:204` (export_textures)
- `scripts/rdc_analyzer/exporters/unity_exporter.py:250` (export_shaders)
- `scripts/rdc_analyzer/exporters/unity_exporter.py:324-356` (export_unity_assets main flow)
- `scripts/rdc_analyzer/exporters/spirv_cross_bridge.py:8-40` (SPIRV-Cross path + invocation)
- `scripts/rdc_analyzer/docs/UNITY_EXPORT.md:1-120` (usage guide)

# Approach (Pseudo-code)
```python
# Given: rdc_path, event_id, api, out_dir
cap = OpenCaptureFile()
controller = OpenCapture(...)
SetFrameEvent(event_id)
pipe = controller.GetPipelineState()

# Mesh: VB/IB + input layout + topology
mesh = export_mesh(controller, action, out_dir)

# Textures: bound SRVs + samplers from pipeline state
textures = export_textures(controller, pipe, out_dir)

# Shaders:
# - Vulkan: SPIR-V -> HLSL via SPIRV-Cross
# - D3D11: DXBC disassembly (future: DXBC->HLSL)
shaders = export_shaders(controller, pipe, out_dir, api, spirv_cross_path)

# Material assembly:
manifest = build_manifest(event_id, api, mesh, textures, shaders)
write(manifest.json)
```

# Impact Analysis
- **Data completeness**: We can access VB/IB, input layout, topology, bound textures/samplers, shader bytecode, and pipeline state for the event.  
  - Missing high-level semantics (e.g., material parameter names, skinning/morph targets) may require heuristics.
- **Shader fidelity**:
  - Vulkan: SPIRV-Cross output HLSL is usually usable but may need manual cleanup.
  - D3D11: DXBC disassembly is not HLSL; needs a converter if required for Unity.
- **Material parameters**:
  - Constant buffers are accessible, but mapping to Unity property names is not guaranteed.
- **Unity import**:
  - Unity can import OBJ/MTL; MaxScript stub exists for .max workflow. Full .max binary is not produced.
- **Offline texture extraction**:
  - Current codebase only provides “offline HTML report” generation; texture pixels still come from `export_textures.py` via RenderDoc API replay.

# Action Items (2–5 min granularity)
- [ ] Identify target `eventId` (character draw) in `D:\backup\大远景.rdc`.
- [x] Validate RenderDoc texture access via Python API (GetTextures + GetTextureData / SaveTexture).  
  - Result: `OpenCapture failed (no replay context)` on this machine.
- [ ] Run unity exporter for Vulkan (with SPIRV-Cross path).
- [ ] Inspect outputs: mesh files, textures, shaders, `manifest.json`.
- [ ] Manual Unity 1.6.9 import + assemble material; record any missing data.
- [ ] If gaps found, update manifest schema to include extra bindings (CB data, sampler state, resource slots).

# TDD Steps (if code changes are needed)
1. Write a failing test for new manifest fields or shader/texture mapping.
2. Run `py -3 -m pytest` → expect failure in new test.
3. Implement minimal change in exporter.
4. Re-run tests → expect pass.

# Risks & Blockers
- No automatic DXBC → HLSL conversion for D3D11 yet.
- Unity material property names cannot be inferred reliably from bytecode alone.
- Some data (skin weights, blend shapes) may be present but not trivially detectable.
- Replay verification requires Python 3.6 + RenderDoc DLL path; import works after adding DLL path.
- Current machine cannot open capture (`OpenCapture failed (no replay context)`), so texture export cannot proceed locally.
- No built-in “no-replay texture pixel extraction” found in code/docs; would require new offline parser or replay on a compatible device.

# Verification / Definition of Done
- Exported assets include: mesh (OBJ/MTL + MaxScript stub), textures, shaders, manifest.
- Unity 1.6.9 can import and display the mesh with assigned textures/shader.
- Any missing data is explicitly logged in `manifest.json`.

# Open Questions
- Confirm the exact `eventId` for the character draw.
- If texture extraction fails, what is the exact error message / symptom?
- Do we need to target Unity URP/HDRP shader formats, or a generic surface shader?

# Next Steps
- Wait for approval to proceed with `/do`.
