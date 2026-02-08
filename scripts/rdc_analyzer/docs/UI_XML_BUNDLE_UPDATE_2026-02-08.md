# RDC Analyzer UI & xml_to_bundle 更新记录（2026-02-08）

> 适用范围：本轮 textures/shaders UI 统一 + `xml_to_bundle.py` 能力增强  
> 关联提交：`81a4aedcb`、`67bdab6a9`

---

## 0. 30 秒可执行清单

```bash
# 1) 生成 Bundle（仅 XML）
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o out_dir

# 2) 生成 Bundle + 纹理缩略图（推荐）
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml --zip capture.zip -o out_dir

# 3) Vulkan：额外提取 Shader（可选）
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml --zip capture.zip --rdc capture.rdc -o out_dir

# 4) 回归验证（模板契约 + headless smoke）
py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -q
cmd /c "set RDC_UI_SMOKE=1&&set RDC_UI_SMOKE_REPORT_DIR=D:\\backup\\endfield_report&&py -3 -m pytest scripts/rdc_analyzer/tests/test_ui_headless_smoke.py -q"
```

**使用建议**
- 日常优先用第 2 条（XML + ZIP），首屏纹理可读性最好。
- 只有需要 Shader 深挖时再加 `--rdc`（第 3 条）。
- 每次改模板后至少跑第 4 条，避免 UI 回归。

## 1. 本轮目标与结果

### 1.1 目标
- 让 `textures.html` 与 `shaders.html` 风格统一为“专业 + 仪表盘”，并提升可读性。
- 在 `xml_to_bundle.py` 中补齐离线缩略图与 Vulkan Shader 提取能力。
- 保留“仅看 HTML 视觉验证”的工作流，避免强依赖 GUI 手工操作。

### 1.2 结果
- UI 统一已完成并通过视觉验收。
- `xml_to_bundle.py` 已支持 ZIP 缩略图与 RDC Shader 提取参数。
- 对应契约测试/冒烟测试通过。

---

## 2. 代码改动总览

### 2.1 UI（textures / shaders）

#### Textures 页面
文件：`scripts/rdc_analyzer/templates/textures.html`
- 增加摘要栏状态芯片：可见数量、当前选中、筛选/排序状态。
- 默认按 VRAM 排序并自动选中可读纹理，减少首屏“看不懂”的情况。
- 工具栏、滚动条、按钮层级、面板头样式统一为仪表盘风格。
- 右侧操作按钮视觉增强（主次按钮统一、间距与字重调整）。

#### Shaders 页面
文件：`scripts/rdc_analyzer/templates/shaders.html`
- 保留 HLSL 聚焦路径，新增状态徽章：`HLSL OFF / ON / N/A`。
- 新增 AI 模式提示条，切换后可读性更稳定。
- 新增左栏摘要栏：可见数量、筛选/排序、当前选中。
- 工具栏（HLSL / AI / GPU 选择器）统一间距与层级，减少“按钮挤压感”。

#### UI 契约测试
文件：`scripts/rdc_analyzer/tests/test_bundle_report_assets.py`
- 增补摘要栏与状态元素断言，防止后续模板回归。

---

### 2.2 `xml_to_bundle.py` 能力增强
文件：`scripts/rdc_analyzer/xml_to_bundle.py`

#### 新增参数
- `--zip`：指定 ZIP 文件，用于纹理缩略图来源。
- `--max-thumbnails`：控制缩略图生成数量上限。
- `--thumbnail-size`：控制缩略图尺寸上限。
- `--rdc`：指定 RDC 文件，供 Vulkan Shader 提取使用。
- `--spirv-cross`：指定 `spirv-cross` 可执行文件路径。

#### 新增流程
- `generate_thumbnails_from_zip(...)`：从 ZIP 中生成/合并纹理缩略图。
- `extract_vulkan_shaders_from_rdc(...)`：从 Vulkan RDC 中提取 SPIR-V，并尝试转 GLSL。
- 生成统计改为使用实际 Shader 数量写入 `total_shaders`。

---

## 3. 提交记录（可追溯）

- `81a4aedcb`  
  `feat(rdc-analyzer-ui): 统一 textures/shaders 仪表盘视觉风格`

- `67bdab6a9`  
  `feat(rdc-analyzer): xml_to_bundle 支持 ZIP 缩略图与 Vulkan Shader 提取`

---

## 4. 验证记录

执行命令：
```bash
py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -q
cmd /c "set RDC_UI_SMOKE=1&&set RDC_UI_SMOKE_REPORT_DIR=D:\\backup\\endfield_report&&py -3 -m pytest scripts/rdc_analyzer/tests/test_ui_headless_smoke.py -q"
```

结果：
- `test_bundle_report_assets.py`：通过
- `test_ui_headless_smoke.py`：通过

---

## 5. 已知限制与说明

- `--rdc` Shader 提取路径依赖 Vulkan 捕获数据完整性；不同 RDC 文件可提取度不同。
- `spirv-cross` 未就绪时，可保留 SPIR-V 占位信息但无法完整还原 GLSL。
- 本轮重点是 UI 可读性与离线能力补强，未引入新的后端服务依赖。

---

## 6. 推荐使用示例

```bash
# 仅 XML -> Bundle
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o out_dir

# XML + ZIP 缩略图
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml --zip capture.zip -o out_dir

# XML + ZIP + RDC Shader 提取
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml --zip capture.zip --rdc capture.rdc -o out_dir

# 指定 spirv-cross
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml --rdc capture.rdc --spirv-cross C:\\tools\\spirv-cross.exe -o out_dir
```

---

## 7. 文档化状态

本次改动已写入：
- 本文档（变更总览与使用说明）
- `scripts/rdc_analyzer/docs/INDEX.md`（索引入口）

