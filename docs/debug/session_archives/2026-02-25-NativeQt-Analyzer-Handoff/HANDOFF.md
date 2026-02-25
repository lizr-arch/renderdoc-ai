# Native Qt Analyzer Handoff (2026-02-25)

## 0. 目标上下文（给新会话）

当前主目标是把 RenderDoc 报告能力迁移到 **完全原生 Qt**（不依赖 WebUI 作为 GUI 主承载），并形成：
- GUI 内可用的专业分析报告窗口
- 问题到 GUI 的稳定跳转链路
- 与导出契约一致的数据口径（analysis.json / issues_export）

本次交接用于新 Codex 会话快速恢复，不重复探索。

---

## 1. 已完成任务（Completed)

### 1.1 原生 Qt 报告窗口主路径已打通

已完成从接口到主窗口的完整接线：
- 新增 `IAnalyzerReportViewer` 以及 `Get/Has/Show` 接口
- `CaptureContext` 生命周期管理（创建、显示、关闭回收）
- `MainWindow` 菜单入口 `Window -> Analyzer Report`

关键文件：
- `qrenderdoc/Code/Interface/QRDInterface.h`
- `qrenderdoc/Code/CaptureContext.h`
- `qrenderdoc/Code/CaptureContext.cpp`
- `qrenderdoc/Windows/MainWindow.h`
- `qrenderdoc/Windows/MainWindow.cpp`
- `qrenderdoc/Windows/MainWindow.ui`

对应提交：
- `9e208e617 feat(qrenderdoc): integrate native analyzer report viewer shell`

### 1.2 已创建原生报告窗口骨架并可展示/跳转/导出

已实现 `AnalyzerReportViewer`：
- 页签：Overview / Issues / Events / Resources / Shaders（后两者为占位）
- Issues 表格（模型驱动）
- Events 表格（模型驱动）
- `Jump To EID`（issue -> `SetEventID` -> EventBrowser）
- `Export`（导出 analysis.json / issues_export.csv / issues_export.md）

关键文件：
- `qrenderdoc/Windows/AnalyzerReportViewer.h`
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp`
- `qrenderdoc/Windows/AnalyzerReportViewer.ui`
- `qrenderdoc/Windows/AnalyzerModels.h`
- `qrenderdoc/Windows/AnalyzerModels.cpp`

### 1.3 已实现 native 分析数据链路（首版）

已新增 analyzer 核心模块：
- `AnalyzerTypes`：snapshot/issue/event/summary 数据结构
- `FrameAnalyzer`：采集 summary + events（首版）
- `IssueEngine`：首版规则（PERF_DC_001 / TEX_SIZE_001 / STATE_SWITCH_001 + baseline）
- `AnalyzerContract`：snapshot -> JSON 序列化
- `AnalyzerExporter`：`analysis.json` + `issues_export.csv` + `issues_export.md`

关键文件：
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h`
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.h`
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp`
- `qrenderdoc/Code/Analyzer/IssueEngine.h`
- `qrenderdoc/Code/Analyzer/IssueEngine.cpp`
- `qrenderdoc/Code/Analyzer/AnalyzerContract.h`
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp`
- `qrenderdoc/Code/Analyzer/AnalyzerExporter.h`
- `qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp`
- `qrenderdoc/qrenderdoc.pro`（已注册新增源码）

对应提交：
- `e10a321f6 feat(qrenderdoc-analyzer): add native analyzer snapshot pipeline and export`

### 1.4 旧 WebUI 路径已降级为 legacy（防入口混淆）

已修改：
- Tools 菜单文案：`Open WebUI (Legacy)`
- 文档明确：GUI 主入口为 `Window -> Analyzer Report`
- WebUI 文档保留为兼容/离线分享路径

关键文件：
- `scripts/rdc_analyzer/ui_extension/analyzer_extension.py`
- `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`
- `docs/analysis/codex_rdc_analyzer/report_ui_optimization_v1.md`

对应提交：
- `48c154dcf docs(rdc-analyzer): mark webui gui path as legacy`

### 1.5 计划文件已同步

- `plans/2026-02-25-174102-Agent01-NativeQt-PerfectReport.md`
- 已将本轮完成项打勾并记录当前状态

对应提交：
- `1a8ad4ffa docs(plan): sync native qt /do checklist progress`

---

## 2. 将要做的任务（Next Tasks / 短期）

> 这些是下个会话应立即执行的任务，优先级按顺序。

### 2.1 先做构建与测试验证（必须）

上个会话验证到：
- WSL 内 `cmake` 不存在
- 可用 Windows CMake：`/mnt/d/Program Files/CMake/bin/cmake.exe`
- 但 Windows 分支 CMake 会主动报错：`CMake is not needed on Windows, just open and build renderdoc.sln`
- 已定位可用 MSBuild：`/mnt/e/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe`

下一步应执行：
1. `"/mnt/e/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`
2. 运行 qrenderdoc 单测（若构建产物可用）：`qrenderdoc.exe --unittest`（或按 tag 过滤）
3. 运行至少一轮手工验证：打开 capture -> `Window -> Analyzer Report` -> Refresh/Jump/Export

### 2.2 补齐原生报告能力缺口

1. Issues -> Texture/Shader 的原生跳转（目前只到 EID）
2. Resources/Shaders 页从占位升级为真实 model + 数据
3. busy/progress 异步构建体验

### 2.3 提高规则专业度（首版 -> 生产级）

1. 扩展规则覆盖（纹理格式、带宽、状态抖动、shader 热点）
2. 增加 evidence 字段丰富度与可追溯性
3. 排序/聚合逻辑优化（severity + impact + confidence）

---

## 3. 未来任务计划（Mid/Long-Term Roadmap）

### Phase A: 稳定可用（1-2 次迭代）
- 编译与单测全绿
- 原生窗口主路径手工验收通过
- 导出与展示口径一致

### Phase B: 专业度拉满（2-4 次迭代）
- 引入更完整规则集与证据链
- 完成 Resources/Shaders/Pipeline/Uniforms 页面实装
- 增加可解释性文案（假设、置信度、数据覆盖率）

### Phase C: 对比与扩展（后续）
- baseline vs target 双帧差异报告
- 性能回归定位链路
- 与离线报告/历史工具链做兼容映射

---

## 4. 关键点（Critical Notes）

### 4.1 现有仓库是脏工作区（非本轮引入）
当前分支 `v1.x` 已 `ahead 548`，并且有多处既有未提交改动。继续开发时：
- 只提交本次任务文件
- 不要回滚不相关改动

### 4.2 构建路径关键事实
- Windows 构建应走 `renderdoc.sln + MSBuild`
- 不要在该环境继续走 CMake Windows 分支（会被项目显式拒绝）

### 4.3 当前完成度判断
- 主路径接线：已完成
- 数据链路：已完成首版
- 专业度：仍需明显增强（规则深度、页面完整度、验证覆盖）

### 4.4 下一会话建议开场指令
建议新会话开场直接执行：
1. 读取本文件
2. 执行构建与测试
3. 如果通过，继续完成 `Resources/Shaders` 页面与跳转链路

---

## 5. 快速恢复命令（给新会话）

```bash
# 1) 查看最近状态
cd /mnt/d/Code/git/renderdoc
git log -6 --oneline

# 2) Windows 编译（WSL 调用）
"/mnt/e/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m

# 3) 运行测试（按产物路径调整）
# qrenderdoc.exe --unittest

# 4) 手工验收
# 打开 capture -> Window -> Analyzer Report -> Refresh / Jump To EID / Export
```

