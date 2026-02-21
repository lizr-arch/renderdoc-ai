# WebUI + UI Extension 开发说明

> 目标：记录 WebUI 服务器与 GUI 扩展骨架的功能点、数据流、人工测试流程与测试点。

## 1) 功能点概览

### WebUI（已实现）
- 本地静态服务：读取分析 JSON 并提供 Web 页面访问
- 启动命令：`py -3 -m rdc_analyzer.webui.server --root <output_dir> --port 8765`
- 覆盖数据：`--data <analysis.json>`（可选，优先使用）
- 访问地址：`http://127.0.0.1:8765/`
- 约束：未提供 `--data` 时，`--root` 目录必须包含 `analysis.json`

### GUI 扩展（已实现：基础统计）
- RenderDoc GUI 内部面板（MiniQtHelper）
- 数据来源：`QRenderDocProvider`
- 目标：显示统计卡片（Shader/Texture/Event）

## 2) 模块结构

```
scripts/rdc_analyzer/webui/
  ├── server.py           # 本地静态服务器
  ├── __init__.py          # 导出 serve/resolve_webui_root
  ├── index.html          # WebUI 入口
  ├── app.js              # WebUI 渲染逻辑
  └── styles.css          # WebUI 样式

scripts/rdc_analyzer/ui_extension/
  ├── analyzer_extension.py  # RenderDoc GUI 扩展（基础统计）
  └── __init__.py

scripts/rdc_analyzer/tools/
  └── renderdoc_shell_analyze.py  # RenderDoc Python Shell 导出脚本
```

## 3) 数据流

1. RenderDoc Python Shell 生成数据（含 Shader）  
   调用 `renderdoc_shell_analyze.run(...)` 输出 `analysis.json`
2. CLI 生成数据（XML 路线，Shader=0）  
   `py -3 -m rdc_analyzer.parsers.rdc_loader <capture.rdc> <analysis.json>`
3. WebUI 读取  
   `analysis.json` → WebUI 前端渲染
4. GUI 扩展  
   `CaptureContext` → `QRenderDocProvider` → UI 统计卡片

## 4) 人工测试流程

### 4.1 WebUI
1. 生成 `analysis.json`（RenderDoc Python Shell）
   - 命令：
     ```
     import rdc_analyzer.tools.renderdoc_shell_analyze as shell
     shell.run(r"<capture.rdc>", r"<output_dir>")
     ```
2. CLI 生成 `analysis.json`（XML 路线，Shader=0，可选）
   - 命令：`py -3 -m rdc_analyzer.parsers.rdc_loader <capture.rdc> <analysis.json>`
3. 启动 WebUI
   - 命令：`py -3 -m rdc_analyzer.webui.server --root <output_dir> --port 8765`
   - 覆盖数据：`py -3 -m rdc_analyzer.webui.server --root <output_dir> --data <analysis.json> --port 8765`
4. 打开页面
   - 浏览器访问：`http://127.0.0.1:8765/`
5. 观察结果
   - 页面能加载并显示基础统计/列表

### 4.2 GUI 扩展（实现后）
1. 在 RenderDoc GUI 中打开捕获文件
2. 通过菜单打开 Analyzer 面板
3. 验证卡片与列表展示正常

## 5) 测试点检查表

### WebUI 测试点
- [ ] `analysis.json` 缺失时应报错
- [ ] `analysis.json` 存在时可正常启动服务
- [ ] 页面能访问并展示统计/列表

### GUI 扩展测试点
- [ ] 面板可打开、关闭
- [ ] 卡片显示 Shader/Texture/Event 数量
- [ ] 关闭捕获后无异常

## 6) 已知限制
- WebUI 仅提供基础统计与列表渲染，详情懒加载尚未接入
- XML 路线（renderdoccmd → XML）不包含 Shader 细节，`shader_count=0` 属于已知限制
