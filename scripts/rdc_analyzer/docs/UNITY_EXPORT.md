# Unity Export (EventId)

This tool exports a single draw (by eventId) into a Unity-ready folder layout.

## Usage

```bash
py -3 scripts/rdc_analyzer/export_unity_assets.py --rdc <path> --event <id> --api d3d11 --out <dir>
py -3 scripts/rdc_analyzer/export_unity_assets.py --rdc <path> --event <id> --api vulkan --out <dir>
```

## Output Layout

```
<out>/
  manifest.json
  mesh/
  textures/
  shaders/
```

`manifest.json` records the eventId, API, and asset paths.

## Notes

- This is a scaffold exporter; mesh/texture/shader extraction is implemented in later steps.
- Vulkan shader HLSL conversion is expected via SPIRV-Cross if available.
