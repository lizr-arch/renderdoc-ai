# Mesh/Shader 导出文档与 CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 1.0.0  
**Owner:** Agent01 (Codex)  
**Last Updated:** 2026-02-01  

## Plan Metadata
- Version: 1.0.0
- Owner: Agent01 (Codex)
- Last Updated: 2026-02-01
- Plan File: plans/2026-02-01-120000-Agent01-MeshShaderDocs.md

## Goal
- 更新文档索引与 Unity 导出说明，并新增一份“Mesh/Shader 导出指南”文档，清晰说明数据来源与使用方法；同时为 `extract_mesh_shader.py` 补齐 CLI 入口与示例，保证新人可直接使用。

## Architecture
- 文档侧：在 `INDEX.md` 与 `UNITY_EXPORT.md` 增加入口与说明；新增 `MESH_SHADER_EXTRACTION.md` 作为“教程+数据来源链路”主文档。
- 代码侧：在 `extract_mesh_shader.py` 增加 CLI（参数解析/帮助/输出布局），复用现有 `_extract_buffers/_extract_shaders`，输出清晰的 manifest。

## Tech Stack
- Python 3 (`py -3`), RenderDoc Python API (`renderdoc` module)
- `scripts/rdc_analyzer` 文档体系（Markdown）

## Success Criteria (measurable)
- `INDEX.md` 新增 Mesh/Shader 导出文档入口与关键词。
- `UNITY_EXPORT.md` 与新工具/脚本路径一致，且包含“数据来源”说明。
- 新文档包含：用途、前置条件、命令示例、输出目录结构、数据来源链路、常见问题。
- `extract_mesh_shader.py --help` 能正确显示参数说明，并生成预期输出目录与 manifest。

## Acceptance Criteria
- 新人照文档执行命令可得到 `vertex_buffers/`, `index_buffers/`, `shaders/`, `manifest.json`。
- 文档中明确指出 VB/IB 与 Shader 反汇编来自哪个 API/结构。

## Verification Commands
- `py -3 scripts/rdc_analyzer/extract_mesh_shader.py --help` (Expected: 显示帮助)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py` (Expected: PASS)

## Evidence
- 更新后的 `scripts/rdc_analyzer/docs/INDEX.md`
- 新增 `scripts/rdc_analyzer/docs/MESH_SHADER_EXTRACTION.md`
- CLI 运行输出目录与 `manifest.json`

## Estimation
- Effort: 0.5-1 day
- Story Points: 2
- Original Estimate: 0.5 day

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| CLI 参数设计与现有导出脚本冲突 | 中 | 低 | 独立脚本名 + 明确参数 |
| 无 GPU 回放导致 CLI 失败 | 中 | 中 | 文档注明依赖 ReplayController |
| 文档与实现不一致 | 中 | 中 | 先改 CLI，再更新文档示例 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 脚本单次运行，重点在磁盘占用；文档注明输出目录与大小估算方式。

## Game Dev: Asset Pipeline
- 输出目录结构固定：`vertex_buffers/`, `index_buffers/`, `shaders/`, `manifest.json`。
- 明确“网格文件需要后续转换（如 .max / Unity 导入）”。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 传入 RDC + eventId 运行 CLI
- Dump/Core: Python traceback 记录
- Symbols: 记录 RenderDoc 版本
- Build identity: 记录 git commit hash

---

## Scope
- **In**: 更新 INDEX 与 UNITY_EXPORT 文档；新增 Mesh/Shader 导出文档；补齐 CLI + 测试。
- **Out**: 纹理解析逻辑（由你提供），D3D12/GLES 扩展，max/fbx 直接导出。

## Assumptions
- 运行环境具备 RenderDoc Python API（renderdoc.pyd）。
- 回放可用（GPU 或软件回放），否则仅生成说明性错误。

## Repo / File List (line ranges)
- `scripts/rdc_analyzer/docs/INDEX.md` (新增入口)
- `scripts/rdc_analyzer/docs/UNITY_EXPORT.md` (更新说明)
- New: `scripts/rdc_analyzer/docs/MESH_SHADER_EXTRACTION.md`
- `scripts/rdc_analyzer/extract_mesh_shader.py` (CLI/manifest)
- New: `scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py`

## Data Provenance (数据从何而来)
| 输出数据 | 来源 API/结构 | 说明 |
|---|---|---|
| VB/IB 绑定信息 | `ReplayController::GetPipelineState()` → `PipeState` → `D3D11Pipe/VKPipe` | 绑定 ID/offset/stride |
| VB/IB 原始字节 | `ReplayController::GetBufferData(resourceId, offset, len)` | 按绑定取字节 |
| Shader 反汇编 | `ReplayController::DisassembleShader(...)` | 生成汇编文本 |

## Approach (Pseudo-code)
```python
def main():
    args = parse_args()
    cap = rd.OpenCaptureFile()
    cap.OpenFile(args.rdc, "", None)
    controller = cap.OpenCapture(rd.ReplayOptions(), None)

    _extract_buffers(controller, args.event, args.out)
    _extract_shaders(controller, args.out)
    write_manifest(args.out, event_id=args.event)
```

## Build/Test/Lint Quick Guide (commands only)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py` (Expected: PASS)

## Task Checklist

### Task 1: 新增 CLI 测试（失败→通过） ✅
**Files:**
- Create: `scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py`

**Step 1: Write failing test**
```python
def test_cli_help_outputs_usage():
    result = run_cli(["--help"])
    assert "extract_mesh_shader" in result
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py -k help`
Expected: FAIL (CLI missing)

**Step 3: Write minimal implementation**
```python
if __name__ == "__main__":
    print("usage: extract_mesh_shader.py --rdc ... --event ... --out ...")
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py -k help`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extract_mesh_shader.py scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py
git commit -m "feat(rdc-analyzer): add CLI skeleton for mesh/shader export

- add minimal argparse + help output
- add CLI test for usage"
```

### Task 2: CLI 参数解析 + manifest ✅
**Files:**
- Modify: `scripts/rdc_analyzer/extract_mesh_shader.py`
- Modify: `scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py`

**Step 1: Write failing test**
```python
def test_cli_writes_manifest(tmp_path):
    run_cli(["--rdc", "x.rdc", "--event", "100", "--out", str(tmp_path)], expect_fail=True)
    assert (tmp_path / "manifest.json").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py -k manifest`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def write_manifest(out_dir, event_id, api):
    # JSON with event_id/api/output paths
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py -k manifest`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extract_mesh_shader.py scripts/rdc_analyzer/tests/test_extract_mesh_shader_cli.py
git commit -m "feat(rdc-analyzer): add CLI args + manifest output

- parse --rdc/--event/--out
- write manifest with data provenance fields"
```

### Task 3: 新增文档（Mesh/Shader 导出指南） ✅
**Files:**
- Create: `scripts/rdc_analyzer/docs/MESH_SHADER_EXTRACTION.md`

**Step 1: Write doc skeleton**
```markdown
# Mesh/Shader Extraction (EventId)
## 1. 用途
## 2. 依赖与前置条件
## 3. 命令示例
## 4. 输出结构
## 5. 数据来源链路
## 6. 常见问题
```

**Step 2: Fill details with examples**
```markdown
py -3 scripts/rdc_analyzer/extract_mesh_shader.py --rdc <file> --event <id> --out <dir>
```

**Step 3: Commit**
```bash
git add scripts/rdc_analyzer/docs/MESH_SHADER_EXTRACTION.md
git commit -m "docs(rdc-analyzer): add mesh/shader extraction guide"
```

### Task 4: 更新 INDEX 与 UNITY_EXPORT ✅
**Files:**
- Modify: `scripts/rdc_analyzer/docs/INDEX.md`
- Modify: `scripts/rdc_analyzer/docs/UNITY_EXPORT.md`

**Step 1: Update INDEX**
```markdown
| [MESH_SHADER_EXTRACTION.md](MESH_SHADER_EXTRACTION.md) | Mesh/Shader 导出指南 | mesh, vb, ib, shader |
```

**Step 2: Update UNITY_EXPORT**
```markdown
- Mesh/Shader 导出可使用 extract_mesh_shader.py（见 MESH_SHADER_EXTRACTION.md）
```

**Step 3: Commit**
```bash
git add scripts/rdc_analyzer/docs/INDEX.md scripts/rdc_analyzer/docs/UNITY_EXPORT.md
git commit -m "docs(rdc-analyzer): index mesh/shader export docs"
```

## Risks & Blockers
- CLI 需要 renderdoc Python API；无 renderdoc.pyd 会失败。
- 若 eventId 不合法，脚本需返回清晰错误。

## Decisions
- 文档“既写 Unity 导出总览，也写独立 Mesh/Shader 说明”。
- CLI 与文档同步更新，保证可直接使用。

## Verification / DoD
- CLI 帮助/manifest 测试通过。
- INDEX 与 UNITY_EXPORT 更新完成。
- 新文档包含数据来源链路说明。

## Next Steps
- 用户确认 /do 执行。
