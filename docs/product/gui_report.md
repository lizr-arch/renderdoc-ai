# GUI 报告（主路径）设计案

> 2026-04-23 delta：当前“设计案”已部分落入候选实现。
> 当前最可信的 GUI HTML 主路径是：`AnalyzerExporter::WriteAll()` 落 `snapshot.v1.json` sidecar，再由 `AnalyzerReportViewer` 调 `scripts/rdc_analyzer/render_snapshot_bundle.py` 驱动 shared `SnapshotTemplateRenderer`。
> 当前剩余缺口：B 线 `msbuild` 与 GUI export smoke 仍未完成。
> 当前状态总入口：`docs/product/delivery_surfaces_status.md`

## 角色与场景
- 角色：渲染程序员、游戏程序员、TA、技术美术。
- 场景：交互调试、问题复盘、分享/评审、培训。

## 目标
- 在 RenderDoc 内一键生成官方 HTML 报告：可信、可视化、可跳转。
- 统一模板（与离线共享），减少学习和维护成本。

## 当前实现状态（2026-04-23）

- sidecar 导出已不是纯设计目标，当前候选实现已明确包含：
  - `analysis.json`
  - `issues_export.csv`
  - `issues_export.md`
  - `capture_context.json`
  - `snapshot.v1.json`
- HTML bundle 的当前候选输出目标是：
  - `index.html`
  - `events.html`
  - `textures.html`
  - `shaders.html`
  - `pipelines.html`
  - `manifest.json`
- 关键工程决策已经明确：
  - GUI 不应回退到 `analysis.json -> legacy ReportBundleGenerator` 作为 canonical HTML 主路径
  - GUI 应复用 shared snapshot renderer，而不是在 Qt 内再写第二套模板
- 仍未完成：
  - `qrenderdoc_local.vcxproj` 编译验证
  - 真实 GUI export smoke

## 数据来源
- ReplayController + CaptureContext（全字段、含截图/缩略、管线状态、计时）。
- 生成时附带轻量 JSON 快照，供对比/AI/CI 使用。

## 主要内容
- Overview：API、资源计数、事件统计、热点摘要（计时 Top-N）。
- Events：可折叠树，支持跳转到 GUI 对应 event_id；链接证据链。
- Textures：缩略、格式/尺寸/用途；可筛选（RT/Depth/MSAA）。
- Shaders：反汇编/入口点/资源绑定；支持搜索。
- Pipelines：关键状态摘要（深度/混合/采样/顶点布局）。
- Evidence Links：跳转到 RenderDoc 内同一事件/资源。

## 交互
- GUI 按钮：Export Report（默认模板 + 可选高级设置）。
- 高级设置：是否包含截图、缩略数量限制、是否生成 JSON 快照。
- 报告内跳转：事件/资源/shader 双向链接；可复制 event_id。

## 模板与结构
- 模板文件：统一 HTML/JS/CSS（与离线共用）。
- 数据适配层：GUI 使用 ReplayController 适配器；缺失字段用安全降级（标记为 “N/A，使用 MCP 查询”）。

## 非目标
- 不在 GUI 报告内直接做 AI 生成；AI 分析通过 Skill 或外部调用。

## 验收指标
- 与离线报告字段一致性 ≥95%（差异项列清单）。
- 生成耗时可接受（目标 < 5s，视捕获大小）。
- 用户跳转/查找关键事件的平均点击 ≤3 次。
