# Unity Export (EventId)

This tool exports a single draw (by eventId) into a Unity-ready folder layout.

## Usage

```bash
py -3 scripts/rdc_analyzer/export_unity_assets.py --rdc <path> --event <id> --api d3d11 --out <dir>
py -3 scripts/rdc_analyzer/export_unity_assets.py --rdc <path> --event <id> --api vulkan --out <dir> --spirv-cross <path>
```

## Output Layout

```
<out>/
  manifest.json
  mesh/
  textures/
  shaders/
```

`manifest.json` records the eventId, API, and asset paths (mesh, textures, shaders).

## Notes

- Mesh is exported as `mesh/mesh.obj` (+ optional `mesh/mesh.mtl`) and a `mesh/to_max.ms` MaxScript stub.
- Sampler-bound textures are exported as PNGs in `textures/`.
- Shader disassembly is exported per-stage in `shaders/` (HLSL/GLSL if available).
- Vulkan shader export requires SPIRV-Cross: pass `--spirv-cross <path>` or set `SPIRV_CROSS`.
