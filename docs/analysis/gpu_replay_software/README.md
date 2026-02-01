# GPU Replay Software Backends (Windows-first)

This folder documents how to run RenderDoc replay using software backends on Windows to reduce
hardware GPU dependency. It is documentation-only: no code changes are applied.

## Goals
- Provide Windows steps for software replay backends.
- Make replay usable for captures when a compatible hardware GPU is not available.
- Focus on exporting color RTs as PNG after replay.

## Backends in scope (Windows)
- WARP (D3D11)
- SwiftShader (Vulkan)
- ANGLE (GLES)

## Out of scope
- Installing dependencies or downloading binaries.
- Linux-only backends (llvmpipe), except for references.
- Any modifications to RenderDoc replay code.

## References
- docs/analysis/gpu-dependency-solutions.md
- docs/analysis/CROSS_GPU_REPLAY_GUIDE.md
- renderdoccmd/renderdoccmd.cpp (software-render flag)
- renderdoc/driver/d3d11/d3d11_replay.cpp (WARP selection)
