# RDC Analyzer 端到端工作流指南

> **版本**: 1.0.0 | **更新日期**: 2025-02-07 | **Phase**: 7A E2E 验证

本指南描述从原始 RDC 捕获到最终 HTML 报告的完整工作流程。

---

## 📋 前置条件

| 工具 | 用途 | 获取方式 |
|------|------|----------|
| `renderdoccmd.exe` | RDC → XML 转换 | RenderDoc 安装目录 |
| Python 3.8+ | 运行分析脚本 | [python.org](https://python.org) |
| `malioc` (可选) | Shader 性能分析 | Arm Performance Studio |
| `spirv-cross` (可选) | SPIR-V → GLSL 转换 | [GitHub](https://github.com/KhronosGroup/SPIRV-Cross) |

---

## 🔄 工作流概览

```
┌─────────────────────────────────────────────────────────────┐
│                    RDC Capture File                         │
│                    (.rdc 原始捕获)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: RDC → XML 转换 (renderdoccmd convert)              │
│  - 输出: capture.xml (结构化数据)                           │
│  - 输出: capture.zip (纹理/Shader 二进制, 可选)             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: XML → Bundle 报告 (xml_to_bundle.py)               │
│  - 输出: index.html (仪表盘)                                │
│  - 输出: events.html (事件时间线)                           │
│  - 输出: textures.html (纹理浏览器)                         │
│  - 输出: shaders.html (Shader 分析)                         │
│  - 输出: manifest.json (元数据)                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 多帧对比 (compare-multi-frame, 可选)               │
│  - 输入: baseline/ 和 target/ 目录 (多个 JSON 文件)         │
│  - 输出: comparison.html + JUnit XML (CI 集成)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📖 详细步骤

### Step 1: RDC → XML 转换

使用 RenderDoc 命令行工具导出结构化 XML：

```bash
# Windows 示例
"C:\Program Files\RenderDoc\renderdoccmd.exe" convert -c xml -o output.xml input.rdc

# 包含纹理/Shader 二进制 (ZIP 格式)
"C:\Program Files\RenderDoc\renderdoccmd.exe" convert -c xml -o output.xml --export-all input.rdc
```

**输出文件**:
| 文件 | 内容 |
|------|------|
| `output.xml` | Draw Call 结构、Pipeline State、资源引用 |
| `output.zip` | 纹理数据 (InitialContents)、Shader 二进制 |

**注意**:
- XML 仅包含元数据，纹理像素需从 ZIP 提取
- 某些 Vulkan Shader 需要 RenderDoc Python API 获取

---

### Step 2: XML → Bundle 报告

使用 `xml_to_bundle.py` 生成多页面 HTML 报告：

```bash
# 基础用法（legacy fallback，默认）
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o output_dir/ --renderer-mode legacy

# 推荐：snapshot 主路径（共享 renderer + snapshot.v1）
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o output_dir/ --emit-snapshot-v1 --renderer-mode snapshot

# 指定纹理 ZIP 文件（可与 snapshot/legacy 路由组合）
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o output_dir/ --zip capture.zip

# 指定 RDC 文件 (用于 Vulkan Shader 提取)
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o output_dir/ --rdc capture.rdc
```

**输出目录结构**:
```
output_dir/
├── index.html          # 仪表盘概览
├── events.html         # 事件时间线
├── textures.html       # 纹理浏览器
├── shaders.html        # Shader 分析
├── manifest.json       # 报告元数据
├── events_data.json    # 事件数据
├── textures_data.json  # 纹理数据
├── shaders_data.json   # Shader 数据
└── thumbnails/         # 纹理缩略图 (如有)
```

> 路由差异说明：
> - `--renderer-mode legacy`（默认）输出兼容页面集合。
> - `--renderer-mode snapshot` 输出 `index/events/textures/shaders/recommendations/manifest`，并建议配合 `--emit-snapshot-v1` 产出 `snapshot.v1.json`。

**关键选项**:
| 选项 | 说明 |
|------|------|
| `--emit-snapshot-v1` | 输出 `snapshot.v1.json` |
| `--renderer-mode snapshot` | 走 snapshot + shared renderer 路由 |
| `--renderer-mode legacy` | 走 legacy fallback 路由（默认） |
| `--zip PATH` | 指定纹理 ZIP 文件路径 |
| `--rdc PATH` | 指定 RDC 文件 (Vulkan Shader) |
| `--spirv-cross PATH` | SPIR-V 转 GLSL 工具路径 |

---

### Step 2.5: 单 Event 资产包（Import Bundle）批处理（可选）

当目标是后续引擎导入（Unity/Unreal/Messiah）时，建议从 capture 直接一键导出 Import Bundle：

```bash
py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py --xml "D:/backup/rdc_test_agent/大远景_auto.zip.xml" --zip "D:/backup/rdc_test_agent/大远景_auto.zip" --out "D:/backup/rdc_test_agent/batch_one_click_top3" --events-from-scan "D:/backup/rdc_test_agent/vulkan_draw_texture_scan.json" --top-textured 3 --min-textures 1 --scan-rank mesh_likely
```

关键参数：
- `--scan-rank mesh_likely|texture_count`：
  - `mesh_likely`（默认）优先选择更可能 mesh 导出的 draw，可显著降低 skip。
  - `texture_count` 维持旧行为，按纹理数量优先。
- `--strict-mesh`：把 mesh 不兼容从 skip 提升为 hard error。
- `--texture-mode auto|decoded|raw` + `--raw-source-kinds`：控制纹理落盘策略。

输出中可重点检查：
- `batch_import_bundle_summary.json`
- `selection.scan_rank` / `options.scan_rank`
- `skipped_count` / `skipped_event_ids`

### Step 3: 多帧统计对比 (可选)

对比多个捕获样本，检测性能回归：

```bash
# 准备目录结构
baseline/
├── frame_001.json
├── frame_002.json
└── frame_003.json
target/
├── frame_001.json
├── frame_002.json
└── frame_003.json

# 执行对比
py -3 -m rdc_analyzer compare-multi-frame \
    --baseline-dir baseline/ \
    --target-dir target/ \
    -o comparison.html \
    --junit-xml results.xml
```

**输出**:
- `comparison.html` - 可视化对比报告
- `results.xml` - JUnit 格式 (CI 集成)

---

## 🔧 JSON Schema 验证

Phase 6 引入了 JSON Schema 验证，确保数据完整性：

```bash
# 验证报告数据
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o output/ --emit-snapshot-v1 --renderer-mode snapshot
```

**Schema 文件位置**: `scripts/rdc_analyzer/schema/`

| Schema | 验证目标 |
|--------|----------|
| `textures_data.schema.json` | 纹理数据结构 |
| `events_data.schema.json` | 事件数据结构 |
| `shaders_data.schema.json` | Shader 数据结构 |
| `report_bundle.schema.json` | Bundle 报告结构 |
| `comparison_result.schema.json` | 对比结果结构 |

---

## 🔌 CI/CD 集成

### GitHub Actions 示例

```yaml
name: RDC Analysis

on:
  push:
    paths:
      - 'captures/*.rdc'

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install Dependencies
        run: pip install pillow scipy
      
      - name: Convert RDC to XML
        run: |
          renderdoccmd convert -c xml -o capture.xml captures/latest.rdc
      
      - name: Generate Report
        run: |
          python scripts/rdc_analyzer/xml_to_bundle.py capture.xml -o report/ --emit-snapshot-v1 --renderer-mode snapshot
      
      - name: Run Regression Check
        run: |
          python -m rdc_analyzer compare-multi-frame \
            --baseline-dir baselines/ \
            --target-dir captures/ \
            --junit-xml test-results.xml \
            --fail-on-regression
      
      - name: Publish Test Results
        uses: dorny/test-reporter@v1
        if: always()
        with:
          name: RDC Regression Tests
          path: test-results.xml
          reporter: java-junit
```

---

## ❓ 常见问题

### Q1: XML 中纹理数据为空？

**原因**: 标准 XML 导出不含像素数据  
**解决**: 使用 `--export-all` 生成 ZIP，或使用 JSON 路径 (`rdc_to_bundle_standalone.py`)

### Q2: Vulkan Shader 源码缺失？

**原因**: SPIR-V 需要额外转换  
**解决**: 指定 `--rdc` 和 `--spirv-cross` 参数

### Q3: 多帧对比报错 "No matching events"？

**原因**: 事件对齐策略不匹配  
**解决**: 尝试 `--align-strategy marker` 或 `--align-strategy signature`

### Q4: Schema 验证失败？

**原因**: 数据格式与 Schema 不兼容  
**解决**: 检查警告信息，可能需要更新数据提取逻辑

---

## 📚 相关文档

- [EXPORT_ROUTES.md](EXPORT_ROUTES.md) - 三条导出路线详解
- [MULTI_FRAME_GUIDE.md](MULTI_FRAME_GUIDE.md) - 多帧统计分析指南
- [API_REFERENCE.md](API_REFERENCE.md) - API 接口参考
