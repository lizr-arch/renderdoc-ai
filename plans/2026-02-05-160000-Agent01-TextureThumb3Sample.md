# Plan: Texture 3-sample export (test-only)

## Scope
In:
- Add a texture-export limit that restricts PNG output to N textures for quick testing.
- Keep existing output layout and mapping logic unchanged.
Out:
- Fix XML+ZIP decode correctness (rowPitch/layout).
- UI layout changes.

## Assumptions
- We will set `RDC_TEX_EXPORT_LIMIT=3` only for the test run.
- We will use `D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc` for the test run.
- If only XML+ZIP is available (no `.rdc`), the 3 PNGs may still be unreadable (**假设（待验证）**).
- MCP 文档检索未找到行距/缩略图导出的官方说明（search_docs=0 结果），以下以源码与实测为准。

## Repo / File List (line ranges)
- `scripts/rdc_analyzer/analyze_xml_report.py:1938-2050` (bundle 分支 + 纹理导出调用)
- `scripts/rdc_analyzer/exporters/texture_batch_exporter.py:148-280` (export_all / _export_single)
- `scripts/rdc_analyzer/exporters/texture_batch_exporter.py:120-180` (BaseExportEngine 定义区)
- `scripts/rdc_analyzer/tests/test_texture_export_limit.py` (new)

## Approach (Pseudo-code)

```python
# scripts/rdc_analyzer/exporters/texture_batch_exporter.py
def select_textures_for_export(textures, limit):
    # 稳定排序：面积大优先，resource_id 小优先
    ordered = sorted(
        textures,
        key=lambda t: (-(t.width * t.height), t.resource_id),
    )
    return ordered[:limit]

def export_all(self, output_dir, save_png=True, save_bin=False, limit=None):
    textures = self.scan_textures()
    if limit is not None:
        textures = select_textures_for_export(textures, limit)
    ...
```

```python
# scripts/rdc_analyzer/analyze_xml_report.py (bundle branch)
import os
limit_env = os.getenv("RDC_TEX_EXPORT_LIMIT")
texture_export_limit = int(limit_env) if (limit_env and limit_env.isdigit()) else None

summary = engine.export_all(
    export_dir,
    save_png=True,
    save_bin=False,
    limit=texture_export_limit,
)
log(f"  [Texture Export] Done: {summary.success}/{summary.total} (limit={texture_export_limit})")
```

## Impact Analysis
- 默认行为不变；只有设置环境变量才限制导出数量。
- 只影响“导出数量”，不改变文件命名、HTML 映射或其他报告内容。
- 不解决 XML+ZIP 数据布局问题，仅用于“快速测试产出 3 张图”。
  - 通过 `.rdc` + RenderDoc `SaveTexture` 走回放路径，可绕开 XML+ZIP 布局问题（来源：`renderdoc/replay/replay_controller.cpp:587`）。

## Action Items (2–5 min each)
- [x] **TDD-1** 新增测试用例：给定 5 个 TextureInfo，limit=3 时只取 3 个且排序稳定。
- [x] **TDD-2** 运行测试，确认失败（函数尚不存在）。
- [x] **Impl-1** 在 `texture_batch_exporter.py` 添加 `select_textures_for_export()` + `export_all(limit=...)`。
- [x] **Impl-2** 在 `analyze_xml_report.py` 读取 `RDC_TEX_EXPORT_LIMIT` 并传入 export_all。
- [x] **Verify-1** 重新运行测试，期望通过。
- [ ] **Verify-2** 生成报告：仅输出 3 张 PNG（日志显示 limit=3）。
- [x] **Commit** 提交一次 `fix(rdc-analyzer): add texture export limit for quick testing`.

## Risks & Blockers
- 若没有对应 `.rdc`，XML+ZIP 仍可能导出“不可读”PNG（根因未修）。
- RenderDoc API 的可用性/驱动环境可能影响后续切换到 `.rdc` 方案。
- 运行验证命令失败：无法加载 renderdoc 模块。请在 RenderDoc 的 Python Shell 中运行或配置模块路径。

## Build/Test/Lint Quick Guide (do not run automatically)
- Test:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_texture_export_limit.py -v --tb=short`
  - 期望输出包含：`1 passed`
- Manual run (PowerShell 避免变量赋值问题，用 cmd):
  - `cmd /c "set RDC_TEX_EXPORT_LIMIT=3&& py -3 -m rdc_analyzer analyze \"D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc\" -o D:\backup\endfield_report_test --format html"`
  - 期望日志包含：`[Texture Export] Done: 3/3 (limit=3)`

## Verification / DoD
- 测试通过，且输出目录仅有 3 张 `tex_<id>_<w>x<h>.png`。
- HTML 能映射到这 3 张缩略图（其余纹理仍为空/无缩略图）。

## Open Questions
- 无（已确认使用 `D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`）。
