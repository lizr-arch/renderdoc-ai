# WebUI + UI Extension 开发说明

> 目标：记录 WebUI 服务器与 GUI 扩展的功能点、数据流、安装方式与人工验证流程。

## 1) 功能点概览

### WebUI（已实现）
- 本地静态服务：读取分析 JSON 并提供 Web 页面访问
- 启动命令：`py -3 -m rdc_analyzer.webui.server --root <output_dir> --port 8765`
- 覆盖数据：`--data <analysis.json>`（可选，优先使用）
- 端口回退：端口被占用时自动选择可用端口

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
```

## 3) 数据流

1. RenderDoc GUI → Python 扩展触发  
2. `renderdoc_shell_analyze.run(...)` 生成 `analysis.json`  
3. WebUI 本地服务器读取 `analysis.json`  
4. GUI 内嵌或外部浏览器展示 WebUI  

> 说明：CLI XML 路线（renderdoccmd → XML）不包含 Shader 细节，`shader_count=0` 属于已知限制。

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
2. 启动 WebUI：
   ```
   py -3 -m rdc_analyzer.webui.server --root <output_dir> --port 8765
   ```

## 5) 人工测试流程

### 5.1 WebUI
1. 生成 `analysis.json`（RenderDoc Python Shell）
2. 启动 WebUI（见 4.3）
3. 浏览器访问 `http://127.0.0.1:<port>/`
4. 验证 shader/texture/event 列表可见

### 5.2 GUI 扩展
1. RenderDoc 打开捕获文件
2. 菜单 `Tools -> RDC Analyzer -> Open WebUI`
3. 内嵌或外部浏览器展示正常

## 6) 测试点检查表

### WebUI
- [ ] `analysis.json` 缺失时应报错
- [ ] `analysis.json` 存在时可正常启动服务
- [ ] 端口占用时自动回退
- [ ] 页面可访问并展示统计/列表

### GUI 扩展
- [ ] 菜单项可见
- [ ] 统计卡片显示 Shader/Texture/Event 数量
- [ ] WebUI 可打开（内嵌/外部浏览器）
- [ ] 关闭捕获后无异常

## 7) 已知限制
- WebUI 目前以基础统计 + 列表为主，详情懒加载尚未接入
- XML 路线缺少 Shader 细节，`shader_count=0` 为已知限制
