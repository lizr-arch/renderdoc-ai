# WebUI + UI Extension 开发说明

> 目标：记录 WebUI 服务器与 GUI 扩展的功能点、数据流、安装方式与人工验证流程。

## 1) 功能点概览

### WebUI（已实现）
- 本地静态服务：优先提供报告包页面（index/events/textures/shaders）；缺失时回退到轻量 WebUI 页面
- 启动命令：`py -3 -m rdc_analyzer.webui.server --root <output_dir> --port 8765`
- 覆盖数据：`--data <analysis.json>`（可选，优先使用）
- 端口回退：端口被占用时自动选择可用端口
- 事件跳转：`/api/jump?eid=<id>`（仅当内嵌 WebUI server 可用时）

### GUI 扩展（已实现）
- RenderDoc GUI 内部面板（MiniQtHelper）
- 统计卡片：Shader / Texture / Event 计数
- WebUI 启动入口：Tools 菜单 `RDC Analyzer -> Open WebUI`
- 内嵌优先：若 PySide2/QtWebEngine 可用，内嵌显示；否则外部浏览器打开

## 2) 模块结构

```
scripts/rdc_analyzer/webui/
  ├── server.py           # 本地静态服务器
  ├── __init__.py          # 导出 serve/resolve_webui_root
  ├── index.html          # WebUI 入口
  ├── app.js              # WebUI 渲染逻辑
  └── styles.css          # WebUI 样式

scripts/rdc_analyzer/ui_extension/
  ├── analyzer_extension.py  # RenderDoc GUI 扩展
  ├── __init__.py
  └── extension.json         # RenderDoc 扩展清单

scripts/rdc_analyzer/tools/
  ├── renderdoc_shell_analyze.py  # RenderDoc Python Shell 导出脚本
  └── install_ui_extension.py     # 扩展安装脚本
  
scripts/rdc_analyzer/
  ├── report_from_analysis.py      # analysis.json → 报告包生成
  ├── bridge/analysis_to_bundle.py # analysis.json → 报告数据桥接
  └── templates/                   # 报告模板（index/events/textures/shaders 等）
```

## 3) 数据流

1. RenderDoc GUI → Python 扩展触发  
2. `renderdoc_shell_analyze.run(...)` 生成 `analysis.json`  
3. `report_from_analysis.generate_report_from_analysis(...)` 生成报告包页面  
4. WebUI 本地服务器优先提供报告包页面（index/events/textures/shaders）  
5. GUI 内嵌或外部浏览器展示 WebUI  
6. 报告包导出 `issues_export.json` / `issues_export.csv` 供问题追踪与分享  


> Schema 参考：docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md  
> UI 优化建议：docs/analysis/codex_rdc_analyzer/report_ui_optimization_v1.md

## 3.1) Shader 列表来源与回退

- **首选**：Mali 分析报告中的 Shader 条目（如存在）
- **次选**：Pipeline samples + `shader_extractor` 生成 `ShaderInfo`
- **回退**：仅采样到的 Shader IDs（VS/PS/CS）生成最小条目
- **仅 XML 路线**：renderdoccmd → XML 不包含 Shader 细节，`shader_count=0` 属于已知限制

## 4) 安装与使用

### 4.1 安装扩展
1. 运行安装脚本：
   ```
   py -3 scripts/rdc_analyzer/tools/install_ui_extension.py
   ```
2. 扩展目录（Windows）：
   `%APPDATA%\qrenderdoc\extensions\rdc_analyzer`
3. 生成配置：
   - `extension_config.json` 会写入 `scripts_root`，用于定位 `rdc_analyzer` 包

> 如需覆盖路径：
```
py -3 scripts/rdc_analyzer/tools/install_ui_extension.py --scripts-root D:\Code\git\renderdoc\scripts
```

### 4.2 GUI 使用
1. 打开 RenderDoc，加载 `.rdc`
2. 菜单：`Tools -> RDC Analyzer -> Open WebUI`
3. 若可内嵌：直接在 GUI 中打开；否则外部浏览器打开

### 4.3 WebUI 独立使用
1. 生成 `analysis.json`（RenderDoc Python Shell）：
   ```
   import rdc_analyzer.tools.renderdoc_shell_analyze as shell
   shell.run(r"<capture.rdc>", r"<output_dir>")
   ```
2. 生成报告包（可选，但建议）：
   ```
   from rdc_analyzer.report_from_analysis import generate_report_from_analysis
   generate_report_from_analysis(r"<output_dir>/analysis.json", r"<output_dir>", "capture.rdc")
   ```
3. 启动 WebUI：
   ```
   py -3 -m rdc_analyzer.webui.server --root <output_dir> --port 8765
   ```

## 5) 人工测试流程

### 5.1 WebUI
1. 生成 `analysis.json`（RenderDoc Python Shell）
2. 启动 WebUI（见 4.3）
3. 浏览器访问 `http://127.0.0.1:<port>/`
4. 验证 index/events/textures/shaders 页面可访问且样式一致
5. 验证 shader/texture/event 列表可见（使用 RenderDoc GUI 可见 shader 的样本）

### 5.2 GUI 扩展
1. RenderDoc 打开捕获文件
2. 菜单 `Tools -> RDC Analyzer -> Open WebUI`
3. 内嵌或外部浏览器展示正常
4. 在 events 页面点击 “↗ GUI” 按钮，RenderDoc 选中对应事件

## 6) 测试点检查表

### WebUI
- [ ] `analysis.json` 缺失时应报错
- [ ] `analysis.json` 存在时可正常启动服务
- [ ] 端口占用时自动回退
- [ ] 页面可访问并展示统计/列表
- [ ] `issues_export.json` / `issues_export.csv` 可下载
- [ ] `/api/jump?eid=` 可返回成功（内嵌 server 可用时）
- [ ] RenderDoc GUI 可见 shader 的样本，WebUI 中 shaders 数量 > 0

### GUI 扩展
- [ ] 菜单项可见
- [ ] 统计卡片显示 Shader/Texture/Event 数量
- [ ] WebUI 可打开（内嵌/外部浏览器）
- [ ] 关闭捕获后无异常

## 7) 已知限制
- WebUI 目前以基础统计 + 列表为主，详情懒加载尚未接入
- 仅 XML 路线缺少 Shader 细节，`shader_count=0` 为已知限制
- GUI 扩展依赖内嵌 Python 的标准库；若提示缺失 `dataclasses`，请确保 Python >= 3.7 且运行时完整
- 若嵌入 Python 缺失 `_socket` 导致使用外部 WebUI server，`/api/jump` 将不可用
- 日志路径：`%APPDATA%\qrenderdoc\extensions\rdc_analyzer_ext\rdc_analyzer_<timestamp>.log`
- 最新日志：`%APPDATA%\qrenderdoc\extensions\rdc_analyzer_ext\rdc_analyzer_latest.log`

## 7.1) 缺失 dataclasses 的修复（Python 3.6 运行时）
如果 RenderDoc 内嵌 Python 版本为 3.6（日志中可见），需安装 `dataclasses` backport 到脚本目录：

```
py -3 -m pip download dataclasses==0.8 --no-deps --platform any --python-version 36 --implementation py --abi none -d scripts/rdc_analyzer/_vendor/_downloads
py -3 -c "import zipfile, pathlib; wheel=pathlib.Path('scripts/rdc_analyzer/_vendor/_downloads/dataclasses-0.8-py3-none-any.whl'); target=pathlib.Path('scripts/rdc_analyzer/_vendor/dataclasses'); target.mkdir(parents=True, exist_ok=True); zipfile.ZipFile(wheel).extractall(target)"
```

扩展会自动从 `scripts/rdc_analyzer/_vendor/dataclasses` 加载该 backport。

## 7.2) 缺失 _socket 的修复（WebUI 回退）
如果日志显示 `ModuleNotFoundError: No module named '_socket'`，说明嵌入 Python 无法启动内置 WebUI 服务器。
扩展会自动改用系统 Python (`py -3`) 启动外部 WebUI 服务。

## 8) Roadmap: 完美版本
1. PC 回放移动端 Vulkan 截帧（修改版 RenderDoc 1.43+）
2. RenderDoc 内部性能分析面板（卡片/表格/筛选/搜索/联动）
3. 报告对比（baseline vs target，差异聚合与定位）

## 9) 扩展包名更新（2026-02-24）
- 扩展目录改为 `%APPDATA%\qrenderdoc\extensions\rdc_analyzer_ext`
- 安装命令：`py -3 scripts/rdc_analyzer/tools/install_ui_extension.py --name rdc_analyzer_ext`
- 如存在旧目录 `rdc_analyzer`，请在扩展管理器禁用或手动删除以避免冲突
