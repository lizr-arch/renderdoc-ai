# RenderDoc GUI WebUI Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-23
**Owner:** Agent01
**Last Updated:** 2026-02-23
**Plan File:** plans/2026-02-23-230000-Agent01-RenderDoc-WebUI-Extension.md

**Goal:** 在 RenderDoc GUI 内提供“类 Web”的分析界面入口，自动导出 `analysis.json` 并在 GUI 内/外显示 WebUI（优先内嵌，缺失 PySide2 时降级外部浏览器）。

**Architecture:** 扩展现有 `scripts/rdc_analyzer/ui_extension/analyzer_extension.py` 的 Python UI 扩展，在菜单中添加 WebUI 入口。点击后使用 `renderdoc_shell_analyze.run()` 生成 `analysis.json`，启动 WebUI 服务器（后台线程），并尝试用 PySide2/QtWebEngine 内嵌展示；若不可用则显示提示并打开外部浏览器。

**Tech Stack:** Python (qrenderdoc/renderdoc API), MiniQtHelper, optional PySide2 + QtWebEngine, `rdc_analyzer.webui.server`, Windows.

**Success Criteria (measurable):**
- GUI 内新菜单可用，并能在 1 次点击内生成 `analysis.json`。
- WebUI 页面显示 shader 数量 > 0（样本：`D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`）。
- 若 PySide2 可用：WebUI 可在 RenderDoc 内嵌面板中显示；若不可用：自动提示并打开外部浏览器。

**Acceptance Criteria:**
- RenderDoc 扩展在 `Tools -> Manage Extensions` 中可加载并可“Always Load”。
- 打开捕获后点击菜单项，无崩溃、无阻塞 UI（耗时操作在后台线程执行）。
- WebUI 可刷新（重新导出分析）且 URL 固定可复用（如 `http://127.0.0.1:8765/` 或自动回退端口）。

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests -k ui_extension -v` (Expected: all tests passed)
- `py -3 -m pytest scripts/rdc_analyzer/tests -k webui -v` (Expected: all tests passed)

**Evidence:**
- `D:\backup\endfield_report_webui\analysis.json`
- WebUI URL: `http://127.0.0.1:8765/`（或日志输出的回退端口）

**Estimation:**
- Effort: 1.5–2.5 days
- Story Points: 5
- Original Estimate: 2 days

**Risk Register (impact/likelihood/mitigation):**
- PySide2/QtWebEngine 不可用导致无法内嵌（中/高）→ 提供外部浏览器降级方案 + 明确提示。
- 生成分析耗时导致 UI 卡顿（中/中）→ 后台线程 + UI 线程提示 + 禁止同步阻塞。
- 扩展路径/脚本路径不一致（中/中）→ install 脚本写入 config，提供环境变量覆盖。

---

## Scope
- In: RenderDoc GUI 菜单扩展、自动导出 `analysis.json`、启动 WebUI、内嵌或外部浏览器显示、安装脚本与文档说明。
- Out: C++ 原生 Qt 面板改造、RenderDoc 核心功能修改、HLSL 反编译/转换流程。

## Assumptions
- RenderDoc GUI 允许 Python 扩展并启用 Python 支持。
- `renderdoc_shell_analyze.run` 在 RenderDoc 内嵌 Python 可执行。
- 用户允许在本机 `%APPDATA%\\qrenderdoc\\extensions` 安装扩展。
- **提交需用户确认**（遵循用户指示，尽管项目规则要求自动提交）。

## Repo / File List (with line refs)
- `scripts/rdc_analyzer/ui_extension/analyzer_extension.py:9`（扩展 UI、菜单注册、WebUI 启动逻辑）
- `scripts/rdc_analyzer/ui_extension/__init__.py:1`（如需导出新增入口）
- `scripts/rdc_analyzer/tools/renderdoc_shell_analyze.py:16`（仅复用，不改或最小改动）
- `scripts/rdc_analyzer/webui/server.py:64`（可复用 serve；如需新增后台启动 helper 则修改）
- `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md:1`（文档更新）
- New: `scripts/rdc_analyzer/ui_extension/extension.json`
- New: `scripts/rdc_analyzer/ui_extension/extension_config.json`（安装时生成或模板）
- New: `scripts/rdc_analyzer/tools/install_ui_extension.py`
- New: `scripts/rdc_analyzer/tests/test_ui_extension_config.py`

## Approach (Pseudo-code)
```python
# analyzer_extension.py (核心流程示意)
def _resolve_scripts_root():
    env = os.getenv("RDC_ANALYZER_SCRIPTS")
    if env:
        return Path(env)
    config = _load_config_json()  # contains scripts_root
    if config:
        return Path(config["scripts_root"])
    return Path(__file__).resolve().parents[2]  # dev fallback

def _ensure_scripts_path():
    root = _resolve_scripts_root()
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))

def _run_analysis(capture_path, output_dir):
    _ensure_scripts_path()
    from rdc_analyzer.tools import renderdoc_shell_analyze as shell
    return shell.run(capture_path, output_dir)

def _start_webui_server(output_dir, analysis_file):
    # pick port, start ThreadingHTTPServer in daemon thread
    return url

def open_webui_callback(ctx, _data):
    capture = ctx.GetCaptureFilename()
    output_dir = derive_output_dir(capture)
    analysis_file = _run_analysis(capture, output_dir)
    url = _start_webui_server(output_dir, analysis_file)
    if _has_webengine():
        _show_webview_dock(ctx, url)
    else:
        ctx.Extensions().MessageDialog("PySide2 not available, opening external browser.")
        webbrowser.open(url)
```

## Impact Analysis
- UI 线程安全：分析与启动服务需后台执行，UI 更新使用 `MiniQtHelper.InvokeOntoUIThread`。
- 兼容性：不同 RenderDoc 构建是否包含 PySide2/QtWebEngine，需要降级策略。
- 运行路径：扩展安装在用户目录，必须提供稳定的脚本路径发现机制。

## Game Dev: Memory & Resource Budget (Leak Checks)
- 在 GUI 内长时间使用扩展后检查内存增长（重复打开/关闭面板 20 次）；记录前后内存变化。
- 若需更深检查：在 `/do` 后续阶段考虑在 Debug 构建中启用 CRT leak checks 或 ASan（需用户授权构建）。

## Game Dev: Asset Pipeline
- 资产为 `analysis.json` + WebUI 静态资源（`scripts/rdc_analyzer/webui/`）。
- 约定输出目录：以 capture 文件名为基准建立输出子目录（避免覆盖）。
- 安装时不修改 WebUI 静态资源，仅运行时读取。

## Game Dev: Crash Repro + Dumps/Symbols
- 如果 RenderDoc GUI 崩溃：记录复现步骤 + capture 文件路径 + 扩展版本。
- Windows 上建议启用 WER/procdump 收集 minidump，保留 PDB（若自编译）。

## Build/Test/Lint Quick Guide (commands only)
- 单测（仅扩展相关）：`py -3 -m pytest scripts/rdc_analyzer/tests -k ui_extension -v`
- 单测（WebUI 相关）：`py -3 -m pytest scripts/rdc_analyzer/tests -k webui -v`
- 全量（可选）：`py -3 -m pytest scripts/rdc_analyzer/tests -v`

## Task Checklist (2-5 min each, TDD)
- [x] 写失败测试：`test_ui_extension_config.py` 覆盖 `resolve_scripts_root()` 环境变量与配置优先级
- [x] 运行测试并确认失败：`py -3 -m pytest scripts/rdc_analyzer/tests -k ui_extension -v`（期望失败）
- [x] 最小实现：在 `analyzer_extension.py` 中添加 config 解析与路径解析函数
- [x] 复跑测试确认通过：`py -3 -m pytest scripts/rdc_analyzer/tests -k ui_extension -v`
- [x] **提交（需用户确认）**：`feat(ui-extension): add config-driven scripts path resolution`

- [x] 写失败测试：端口选择逻辑（如 `pick_port`）在被占用时回退
- [x] 运行测试并确认失败
- [x] 最小实现：后台 WebUI 服务启动 + 端口回退
- [x] 复跑测试确认通过
- [x] **提交（需用户确认）**：`feat(webui): add background server startup with port fallback`

- [x] 写失败测试：`derive_output_dir(capture_path)` 生成稳定目录名
- [x] 运行测试并确认失败
- [x] 最小实现：输出目录推导
- [x] 最小实现：`renderdoc_shell_analyze.run` 集成
- [x] 复跑测试确认通过
- [x] **提交（需用户确认）**：`feat(ui-extension): export analysis.json for current capture`

- [x] UI 集成：菜单项 + 面板/外部浏览器降级逻辑
- [ ] 手工验证（见下方“Verification / DoD”）
- [x] **提交（需用户确认）**：`feat(ui-extension): add WebUI launcher panel`

- [x] 更新文档：`WEBUI_AND_UI_EXTENSION.md` 扩展安装/使用说明
- [x] **提交（需用户确认）**：`docs(ui-extension): document install and usage`

## Risks & Blockers
- RenderDoc 版本无 PySide2/QtWebEngine → 仅外部浏览器可用。
- 扩展加载路径与脚本路径不一致 → 需安装脚本写入配置。

## Decisions
- 优先复用现有 `analyzer_extension.py`，避免新建第二套扩展。
- WebUI 内嵌为优先路径，缺失时降级外部浏览器。

## Verification / DoD
- 通过扩展菜单生成 `analysis.json`，并在 WebUI 看到 shader 列表非 0。
- RenderDoc GUI 不冻结、无异常弹窗。
- 文档与测试更新完成，手工验证记录补充到文档。

## Open Questions
- 你是否允许 **每个任务完成后提交**？（当前按“需确认”执行）
- 默认输出目录是否固定为 `capture_dir/rdc_analyzer/<capture_name>`？
