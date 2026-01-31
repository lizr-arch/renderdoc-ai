# Mesh/Shader Extraction Implementation Plan (D3D11/Vulkan First)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 1.0.0  
**Owner:** Agent01 (Codex)  
**Last Updated:** 2026-01-31  

## Plan Metadata
- Version: 1.0.0
- Owner: Agent01 (Codex)
- Last Updated: 2026-01-31
- Plan File: plans/2026-01-31-210800-Agent01-IB-VB-Shader-Extraction.md

## Goal
- 从 RDC 中导出 **D3D11/Vulkan** 的 VB/IB 数据与 Shader 汇编（或反汇编文本），并给出清晰的“数据来源链路”；纹理解析由你提供 RGBA bytes，我负责输出可渲染图片文件（TGA/BMP）。

## Architecture
- 以 **ReplayController + PipeState** 为唯一数据来源，提取当前事件的 VB/IB 绑定与 shader 资源，再通过 `GetBufferData` 与 `DisassembleShader` 获取字节与汇编文本。
- 导出统一 manifest（JSON）记录数据来源：事件、API、资源 ID、偏移、stride、格式等，确保可追溯。
- 图片输出采用 **无第三方依赖** 的 TGA/BMP 写入器（Python 标准库），避免新增依赖。

## Tech Stack
- Python 3 (`py -3`), RenderDoc Python API (`renderdoc` module)
- 现有 `scripts/rdc_analyzer` 工具链
- 输出：`.bin` (VB/IB), `.asm/.txt` (shader), `.tga/.bmp` (texture)

## Success Criteria (measurable)
- 能从指定 eventId 导出 **VB/IB 原始字节** 与 **对应布局/绑定元数据**，并在 manifest 中可定位来源。
- 能导出每个 shader stage 的 **反汇编文本**（D3D11/D3D12/Vulkan 任选目标）。
- RGBA bytes 输入后可输出 **可被 Unity 导入** 的图片（TGA/BMP）。

## Acceptance Criteria
- D3D11/Vulkan 至少 1 个 eventId 的 VB/IB/Shader 导出完整且有 manifest。
- 输出图片能被 Unity 1.6.9 正确加载且可渲染。
- 文档明确“数据从何而来”并可复现导出流程。

## Verification Commands
- `py -3 scripts/rdc_analyzer/extract_mesh_shader.py --rdc <file> --event <id> --out <dir>` (Expected: 输出 VB/IB/shader + manifest)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_rgba_image_writer.py` (Expected: PASS)

## Evidence
- `<out>/manifest.json`
- `<out>/vertex_buffers/*.bin`, `<out>/index_buffers/*.bin`
- `<out>/shaders/*.asm`
- `<out>/textures/*.tga`

## Estimation
- Effort: 1-2 days
- Story Points: 3
- Original Estimate: 1.5 days

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 依赖 ReplayController（需要可回放环境） | 高 | 中 | 提供清晰提示与降级路径（只导出 manifest/资源 ID） |
| VB/IB 解释依赖输入布局 | 中 | 中 | 导出 input layout 元数据，交由下游解析 |
| RGBA 颜色空间/翻转不一致 | 中 | 中 | 在 manifest 中记录 sRGB/Linear 与 origin，默认不翻转 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 离线脚本不常驻，主要关注导出峰值内存与磁盘占用；记录导出前后 RSS 差异（可选）。

## Game Dev: Asset Pipeline
- 统一输出目录结构：`mesh/`, `shaders/`, `textures/`, `manifest.json`。
- 只输出可导入的 TGA/BMP（Unity 支持）；纹理 RGBA 由上游解析提供。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 提供 RDC 文件与 eventId，执行导出脚本
- Dump/Core: 若 Python 崩溃，记录 traceback 与输出目录
- Symbols: 无需 PDB，但记录 RenderDoc 版本与脚本 commit
- Build identity: 记录 git commit hash

---

## Scope
- **In**: D3D11/Vulkan VB/IB + Shader 反汇编导出；RGBA -> TGA/BMP 图片输出；数据来源清单。
- **Out**: D3D12/GLES；纹理解析与压缩解码；max/.fbx 直接导出。

## Assumptions
- 需要可回放环境（GPU 或软件回放）才能调用 ReplayController。
- 你会提供 RGBA bytes 与必要元数据（格式、尺寸、行距、颜色空间等）。

## Repo / File List (line ranges)
- `renderdoc/api/replay/renderdoc_replay.h:540-603, 831-1107` (GetPipelineState, GetBuffers, GetBufferData, DisassembleShader)
- `renderdoc/api/replay/d3d11_pipestate.h:221-231` (D3D11 VB/IB bindings)
- `renderdoc/api/replay/vk_pipestate.h:306-480` (Vulkan VB/IB bindings)
- `renderdoc/api/replay/d3d12_pipestate.h:220-230` (D3D12 VB/IB; later)
- `renderdoc/api/replay/gl_pipestate.h:191-197` (GL/GLES VB bindings; later)
- New: `scripts/rdc_analyzer/extract_mesh_shader.py`
- New: `scripts/rdc_analyzer/rgba_image_writer.py`
- New: `scripts/rdc_analyzer/tests/test_rgba_image_writer.py`
- Update: `scripts/rdc_analyzer/docs/INDEX.md` (新增功能入口)

## Data Provenance (数据从何而来)

| 输出数据 | 来源 API/结构 | 说明 |
|---|---|---|
| VB/IB 绑定信息 | `ReplayController::GetPipelineState()` → `PipeState` → `D3D11Pipe/VKPipe` | 获取 resourceId/offset/stride/format |
| VB/IB 原始字节 | `ReplayController::GetBufferData(resourceId, offset, len)` | 按绑定信息拉取 bytes |
| Shader ResourceId | `PipeState::GetShader(stage)` | 获取对应 shader 资源 |
| Shader 反汇编文本 | `ReplayController::DisassembleShader(...)` | 生成汇编/反汇编文本 |
| RGBA 图片输出 | 上游解析输出 + `rgba_image_writer.py` | 使用 width/height/rowPitch/origin |

## Approach (Pseudo-code)

### VB/IB 导出
```python
cap = rd.OpenCaptureFile()
cap.OpenFile(rdc_path, "", None)
controller = cap.OpenCapture(rd.ReplayOptions(), None)

controller.SetFrameEvent(event_id, True)
pipe = controller.GetPipelineState()

if controller.GetAPIProperties().pipelineType == rd.GraphicsAPI.D3D11:
    vbs = pipe.GetD3D11PipelineState().inputAssembly.vertexBuffers
    ib = pipe.GetD3D11PipelineState().inputAssembly.indexBuffer
elif controller.GetAPIProperties().pipelineType == rd.GraphicsAPI.Vulkan:
    vbs = pipe.GetVulkanPipelineState().vertexInput.vertexBuffers
    ib = pipe.GetVulkanPipelineState().inputAssembly.indexBuffer

for vb in vbs:
    data = controller.GetBufferData(vb.resourceId, vb.byteOffset, vb.byteSize)
    save_bin(data, out_dir / f"vb_{vb.resourceId}.bin")

ib_data = controller.GetBufferData(ib.resourceId, ib.byteOffset, ib.byteSize)
save_bin(ib_data, out_dir / f"ib_{ib.resourceId}.bin")
```

### Shader 反汇编导出
```python
pipe = controller.GetPipelineState()
pipeline = pipe.GetGraphicsPipelineObject()
for stage in [rd.ShaderStage.Vertex, rd.ShaderStage.Fragment]:
    shader_id = pipe.GetShader(stage)
    refl = controller.GetShader(pipeline, shader_id, rd.ShaderEntryPoint())
    asm = controller.DisassembleShader(pipeline, refl, "")
    save_text(asm, out_dir / f"{stage.name}.asm")
```

### RGBA -> TGA
```python
def write_tga(path, width, height, rgba_bytes, origin_top_left=True):
    # 32-bit BGRA TGA header + data (swap R/B if needed)
    # write bytes using struct + file.write
```

## Build/Test/Lint Quick Guide (commands only)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_rgba_image_writer.py` (Expected: PASS)

## Task Checklist

### Task 1: VB/IB 导出脚本骨架 ✅
**Files:**
- Create: `scripts/rdc_analyzer/extract_mesh_shader.py`

**Step 1: Write failing test**
```python
def test_extract_mesh_shader_requires_event():
    with pytest.raises(ValueError):
        extract_mesh_shader(rdc_path="x.rdc", event_id=None, out_dir="out")
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader.py -k requires_event`
Expected: FAIL (extract_mesh_shader not implemented)

**Step 3: Write minimal implementation**
```python
def extract_mesh_shader(rdc_path, event_id, out_dir):
    if event_id is None:
        raise ValueError("event_id required")
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader.py -k requires_event`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extract_mesh_shader.py scripts/rdc_analyzer/tests/test_extract_mesh_shader.py
git commit -m "feat(rdc-analyzer): add mesh/shader extractor skeleton

- add extract_mesh_shader entrypoint + basic validation
- add initial test for required event id"
```

### Task 2: 获取 VB/IB 绑定与字节 ✅
**Files:**
- Modify: `scripts/rdc_analyzer/extract_mesh_shader.py`
- Create: `scripts/rdc_analyzer/tests/test_extract_mesh_shader.py`

**Step 1: Write failing test**
```python
def test_extract_mesh_shader_writes_vb_ib(tmp_path, fake_controller):
    result = _extract_buffers(fake_controller, event_id=100, out_dir=tmp_path)
    assert (tmp_path / "vertex_buffers").exists()
    assert (tmp_path / "index_buffers").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader.py -k writes_vb_ib`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def _extract_buffers(controller, event_id, out_dir):
    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    # branch by API, pull vbs/ib, call GetBufferData
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader.py -k writes_vb_ib`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extract_mesh_shader.py scripts/rdc_analyzer/tests/test_extract_mesh_shader.py
git commit -m "feat(rdc-analyzer): export VB/IB bytes from pipeline state

- read bound buffers via PipeState
- save raw bytes + metadata manifest"
```

### Task 3: Shader 反汇编导出 ✅
**Files:**
- Modify: `scripts/rdc_analyzer/extract_mesh_shader.py`

**Step 1: Write failing test**
```python
def test_extract_shader_disassembly(fake_controller, tmp_path):
    _extract_shaders(fake_controller, out_dir=tmp_path)
    assert (tmp_path / "shaders" / "vertex.asm").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader.py -k disassembly`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def _extract_shaders(controller, out_dir):
    pipe = controller.GetPipelineState()
    pipeline = pipe.GetGraphicsPipelineObject()
    for stage in STAGES:
        refl = controller.GetShader(pipeline, shader_id, rd.ShaderEntryPoint())
        asm = controller.DisassembleShader(pipeline, refl, "")
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader.py -k disassembly`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extract_mesh_shader.py scripts/rdc_analyzer/tests/test_extract_mesh_shader.py
git commit -m "feat(rdc-analyzer): export shader disassembly

- disassemble shader stages via ReplayController
- save .asm outputs"
```

### Task 4: RGBA -> TGA/BMP 输出
**Files:**
- Create: `scripts/rdc_analyzer/rgba_image_writer.py`
- Create: `scripts/rdc_analyzer/tests/test_rgba_image_writer.py`

**Step 1: Write failing test**
```python
def test_write_tga_roundtrip(tmp_path):
    rgba = bytes([255, 0, 0, 255]) * 4  # 2x2 red
    out = tmp_path / "tex.tga"
    write_tga(out, 2, 2, rgba, origin_top_left=True)
    assert out.exists() and out.stat().st_size > 18
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_rgba_image_writer.py`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def write_tga(path, width, height, rgba_bytes, origin_top_left=True):
    # 18-byte TGA header + BGRA data
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_rgba_image_writer.py`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/rgba_image_writer.py scripts/rdc_analyzer/tests/test_rgba_image_writer.py
git commit -m "feat(rdc-analyzer): add RGBA image writer for Unity import

- add TGA/BMP writer without external deps
- add tests"
```

## Risks & Blockers
- ReplayController 需要可回放环境；若无 GPU 或软件回放不支持，将无法直接导出 VB/IB/Shader。
- 不同 API 的布局/格式字段可能不一致，需要逐个适配。

## Decisions
- **D3D11/Vulkan 优先**，D3D12/GLES 后续再扩展。
- **无第三方依赖**，RGBA 输出使用 TGA/BMP。

## Verification / DoD
- 脚本可在至少 1 个 D3D11 与 1 个 Vulkan RDC 上导出 VB/IB/Shader。
- RGBA -> TGA/BMP 输出可被 Unity 1.6.9 导入并正确渲染。
- manifest 中包含完整数据来源链路（eventId、resourceId、offset/stride/format）。

## Next Steps
- 用户确认 /do 执行顺序与输出格式（TGA/BMP/PNG 取舍）。
- 若需要 D3D12/GLES，另起 plan 文件。
