# Scope / Assumptions
- In scope: 路线 C（renderdoccmd export）导出 + 生成 HTML；Zoekt/codemap 索引 renderdoc 仓库；补充文档验证点。
- Out of scope: 修改 RenderDoc 源码/功能；新增依赖；改动第三方库。
- 假设：`D:\renderdoc\goog pixel-9\g145.rdc` 可用；编译工具链已安装；允许执行构建命令（需再次确认）。

# Build/Test/Lint Quick Guide (只记录不执行)
- 构建（Windows/VS）：`msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64 /t:renderdoccmd`
- 验证 renderdoccmd：`D:\Code\git\renderdoc\x64\Development\renderdoccmd.exe --help`
- 导出 XML（convert）：`renderdoccmd convert -f <capture.rdc> -o <capture.xml> -c xml`
- 导出资源/元数据（export）：`renderdoccmd export --out <out_dir> --bindings --metadata <capture.rdc>`
- 生成 HTML：`py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o <report.html>`
- codemap 验证：`codemap -Query "rdc_to_html" -Num 20`

# Repo / File List (预期读取/修改)
- 读取：`renderdoccmd/renderdoccmd.cpp`（确认 export 参数与输出）
- 读取：`renderdoc/replay/capture_exporter.cpp`（export 实现）
- 读取：`scripts/rdc_analyzer/analyze_xml_report.py`（XML->HTML 入口）
- 读取：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`
- 修改：`docs/analysis/codex_rdc_analyzer/README.md`（记录导出与验证点）
- 新增：`plans/2026-01-24-193124-Agent01-ExportCompile-Codemap.md`

# Approach (Pseudo-code)
```
if renderdoccmd convert supports xml:
  run convert -> capture.xml
  run analyze_xml_report.py -> html
  verify html (exists, size,关键指标)
  optionally run export -> out_dir (bindings + metadata)
else:
  fall back to existing XML (from UI/export) and document gap

if codemap has no renderdoc hits:
  find zoekt-index + index dir in WSL
  run zoekt-index on /mnt/d/Code/git/renderdoc
  verify codemap query returns results
```

# Impact Analysis
- 风险：renderdoccmd export 的 XML 参数可能与文档不一致 → 需要先读源码确认。
- 风险：renderdoccmd 编译时间长/依赖缺失 → 需要明确错误日志并回填计划。
- 风险：Zoekt/OpenGrok 服务未配置 renderdoc → 需补索引并验证。

# Action Items (2–5 分钟粒度)
- [x] 1. 读取 `renderdoccmd/renderdoccmd.cpp`，确认 export 参数与输出结构（仅纹理/metadata/bindings，无 XML）。
      - 备注：`renderdoc/replay/capture_exporter.cpp` 在本仓库不存在。
- [x] 2. 验证 `renderdoccmd convert` 是否可用（`renderdoccmd convert --list-formats`），确认 `xml` 格式。
      - 结果：`C:\Program Files\RenderDoc\renderdoccmd.exe` 支持 `xml`/`zip.xml`。
- [x] 3. 确认 renderdoccmd 二进制路径与构建目标（系统安装版无 export；源码版需编译）。
- [ ] 4. 执行构建：`msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64 /t:renderdoccmd`（失败：缺少 VS Build Tools，`Microsoft.Cpp.Default.props` 未找到）。
- [x] 5. 运行导出：`renderdoccmd convert -f <rdc> -o <xml> -c xml`（使用已安装 RenderDoc 版本）。
      - 结果：`D:\renderdoc\goog pixel-9\g145_from_convert.xml` 已生成。
- [x] 6. 生成 HTML：`py -3 scripts/rdc_analyzer/analyze_xml_report.py g145_capture.xml -o g145_report_reexport.html`。
- [x] 7. 验证点检查（HTML 存在 + 关键统计匹配）。
- [x] 8. 更新 `docs/analysis/codex_rdc_analyzer/README.md`（记录 re-export 与验证点）。
- [x] 9. Zoekt 索引：使用 `/home/lizhirui01/go/bin/zoekt-index` 建立 renderdoc 索引（输出 shard: `renderdoc_v16.*.zoekt`）。
- [x] 10. codemap 验证：`codemap -Query "rdc_to_html" -Num 20` 已命中 renderdoc 路径。

# Verification / DoD
- HTML 报告存在且非空：`<report.html>` 文件 > 0 字节。
- HTML 基本结构存在：包含 `<!DOCTYPE html>` 与核心模块标题（如 “Report/分析/Textures/Events” 任一）。
- 关键统计输出记录：events / draw calls / textures / score（与脚本输出一致）。
- codemap 对 renderdoc 关键字可检索（至少返回 3 条命中）。

# Risks & Blockers
- renderdoccmd export 与文档不一致（参数/输出文件名差异）。
- renderdoccmd 编译失败（缺少 VS Build Tools，`Microsoft.Cpp.Default.props` 未找到）。
- 预期文件缺失：`renderdoc/replay/capture_exporter.cpp` 未在本仓库找到（路线图需修正）。
- 现状：convert 已通过安装版 RenderDoc 验证，export 仍需源码编译支持。

# Open Questions
- 导出流程产物的命名与目录结构是否有团队约定（XML 文件名是否固定）？

# Next Steps
- 用户确认后进入 /do 执行构建、导出、HTML 生成与索引。
