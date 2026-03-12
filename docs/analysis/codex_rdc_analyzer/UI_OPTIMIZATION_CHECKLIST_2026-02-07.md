# UI 优化开发清单（Textures + Shaders）

> 日期：2026-02-07
> 目标：让 textures.html 与 shaders.html 达到 专业 + 仪表盘风格，并保证可用性稳定（滚动、搜索、布局、失败态、自测闭环）。

---

## 0. 导航证据（Codemap + 目标文件）

### 0.1 Codemap 查询（最多 3 条）
1. codemap textures.html -Num 20
2. codemap AI Shader 优化 -Repo renderdoc -Num 20
3. codemap filterTextures -Repo renderdoc -Num 20

### 0.2 候选命中（示例）
- [renderdoc] scripts/rdc_analyzer/analyze_rdc.py:2375 -> function filterTextures()
- [renderdoc] scripts/rdc_analyzer/analyze_rdc.py:2391 -> gridSearch.addEventListener('input', filterTextures)
- [renderdoc] scripts/rdc_analyzer/generate_simple_report.py:202 -> function filterTextures()

### 0.3 本轮实际跟进文件（Serena/本地定位）
- scripts/rdc_analyzer/templates/textures.html
- scripts/rdc_analyzer/templates/shaders.html
- scripts/rdc_analyzer/report_bundle_generator.py
- scripts/rdc_analyzer/tools/ui_headless_smoke.py
- scripts/rdc_analyzer/tests/test_ui_headless_smoke.py

---

## 1. P0 已完成（功能与可用性）

### 1.1 Textures 页面
- [x] 列表/网格模式切换可用
- [x] 搜索、筛选（含大尺寸）可用
- [x] 纹理项 data-* 数据补齐（resource_id / format / mips / vram）
- [x] 选中纹理后属性区可更新
- [x] 列表区与右侧属性区滚动行为稳定（避免布局抖动）

### 1.2 Shaders 页面
- [x] 搜索覆盖 name/type/id
- [x] 主操作按钮保留查看 HLSL 代码 + AI Shader 优化
- [x] 工具栏主次操作布局优化，避免重叠
- [x] 列表区滚动行为稳定

### 1.3 自动化自测
- [x] 新增 headless 冒烟脚本：scripts/rdc_analyzer/tools/ui_headless_smoke.py
- [x] 修复误报：shaders_list_scrollable 改为搜索前采样，不再因筛选后条目变少误判
- [x] 新增 pytest 集成（默认 skip）：scripts/rdc_analyzer/tests/test_ui_headless_smoke.py

---

## 2. 自动化 UI 冒烟测试（可选 / 默认跳过）

### 2.1 运行方式

默认运行（会 skip，不会失败）：

cmd
py -3 -m pytest scripts/rdc_analyzer/tests/test_ui_headless_smoke.py -v --tb=short

启用 UI 冒烟（需要 bundle 报告目录 + Playwright）：

cmd
set RDC_UI_SMOKE=1
set RDC_UI_SMOKE_REPORT_DIR=D:\backup\endfield_report
py -3 -m pytest scripts/rdc_analyzer/tests/test_ui_headless_smoke.py -v --tb=short

### 2.2 当前判定项
- Textures：有数据、搜索有效、大尺寸筛选有效、列表可滚动、选中后属性更新、网格切换可用
- Shaders：有数据、搜索有效、列表可滚动、HLSL 与 AI 按钮不重叠

### 2.3 结果产物
- JSON/Markdown 报告与截图输出到：
  - docs/analysis/codex_rdc_analyzer/ui_smoke_artifacts/<timestamp>/

---

## 3. 下一阶段建议（P1）

- [ ] 为 textures 列表增加更直观的图像可读性提示（例如低分辨率/压缩格式标签）
- [ ] 为 shaders 空源码场景补齐更明确的失败态文案和引导
- [ ] 将 UI smoke 接入统一回归脚本（保留默认 skip，按环境变量显式启用）

---

## 4. 验收口径（DoD）

- [ ] 用户仅做 HTML 视觉验收，不需要任何手动生成步骤
- [ ] 默认 pytest 不因 UI smoke 失败（未启用时 skip）
- [ ] 启用 RDC_UI_SMOKE=1 后可稳定得到 overall_pass=True
- [ ] 关键交互（滚动/搜索/按钮布局）在 1366x768、1536x864、1920x1080 均通过
