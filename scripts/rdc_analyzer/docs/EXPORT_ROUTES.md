# RDC 报告导出路线图

> **更新日期**: 2026-02-11 | **版本**: 2.3.0

## 概述

本文档列出从 RDC 文件生成分析报告的所有可用路线，帮助用户根据环境和需求选择最佳方案。

---

## 路线总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          RDC 报告导出路线                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  路线 A: 完整回放（需 GPU + renderdoc 模块）                              │
│  ═══════════════════════════════════════════                            │
│  .rdc ──[renderdoc API]──> ReplayController ──> Bundle 报告 (4页)        │
│                                                                         │
│  路线 B: XML 中转（无需 GPU）⭐ 推荐                                      │
│  ════════════════════════════════════                                   │
│  .rdc ──[renderdoccmd]──> .zip.xml + .zip ──[xml_to_bundle.py]──> Bundle 报告 │
│                                                                         │
│  路线 C: 简化报告（无需 GPU）                                             │
│  ══════════════════════════════                                         │
│  .rdc ──[renderdoccmd]──> .xml ──[report 命令]──> 单页 HTML               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 路线 A: 完整回放（需 GPU）

### 前置条件
- ✅ 安装 RenderDoc（含 Python 模块）
- ✅ 匹配的 GPU 硬件（与捕获时相同的 GPU 类型）
- ✅ 对应的图形驱动

### 命令
```bash
py -3 -m rdc_analyzer analyze input.rdc -o output_dir/
```

### 输出
- `index.html` - 仪表盘
- `events.html` - 事件列表
- `textures.html` - 纹理浏览器
- `shaders.html` - Shader 查看器
- `recommendations.html` - 优化建议

### 适用场景
- 本地开发环境
- 需要完整 Shader 源码
- 需要纹理缩略图

---

## 路线 B: XML 中转（无需 GPU）⭐ 推荐

### 前置条件
- ✅ 安装 RenderDoc CLI（`renderdoccmd.exe`）
- ❌ **不需要** GPU 或 Python renderdoc 模块

### 步骤

#### 步骤 1: RDC → ZIP+XML（优先，含纹理资产）
```bash
renderdoccmd.exe convert -f input.rdc -o output.zip.xml -c zip.xml
```

#### 步骤 2: ZIP+XML → Bundle 报告
```bash
# 兼容路径（默认 legacy）
py -3 scripts/rdc_analyzer/xml_to_bundle.py output.zip.xml -o bundle_output/ --zip output.zip --rdc input.rdc --renderer-mode legacy

# 推荐路径（snapshot + shared renderer）
py -3 scripts/rdc_analyzer/xml_to_bundle.py output.zip.xml -o bundle_output/ --zip output.zip --rdc input.rdc --emit-snapshot-v1 --renderer-mode snapshot
```

#### 失败回退（自动化脚本内置）
```bash
# 如果 zip.xml 转换失败，回退到纯 XML
renderdoccmd.exe convert -f input.rdc -o output.xml -c xml
py -3 scripts/rdc_analyzer/xml_to_bundle.py output.xml -o bundle_output/ --rdc input.rdc --renderer-mode legacy
```

### 一键自动化（推荐，无手动串联）
```bash
# Python 入口（推荐）
py -3 scripts/rdc_analyzer/one_click_bundle_report.py input.rdc -o bundle_output/ --smoke-no-fail --smoke-no-screenshots

# Windows 包装（等价）
scripts\rdc_analyzer\one_click_bundle_report.bat input.rdc -o bundle_output/ --smoke-no-fail --smoke-no-screenshots

# Windows 预设入口（双击即可，默认 Endfield + D:\backup\endfield_report）
scripts\rdc_analyzer\one_click_bundle_preset.bat
```

脚本行为：
- 自动探测 `renderdoccmd.exe`
- 先尝试 `zip.xml`（带缩略图资产），失败自动回退 `xml`
- 自动拼接 `xml_to_bundle.py` 参数（`--zip` / `--rdc`）
- 可选执行 `ui_headless_smoke.py` 做无 GUI 验收

### 输出（按路由区分）
- `index.html` - 仪表盘
- `events.html` - 事件列表
- `textures.html` - 纹理浏览器
- `shaders.html` - Shader 查看器
- `recommendations.html` - 优化建议
- `manifest.json` - 页面元数据
- `snapshot.v1.json` - 仅 snapshot 路由输出（开启 `--emit-snapshot-v1` 或 `--renderer-mode snapshot`）

### 适用场景
- CI/CD 自动化流程
- 无 GPU 的服务器环境
- 跨平台批量分析

### 实测案例
```bash
# 2.35GB Vulkan 捕获 → 32MB XML → 4 页面报告
renderdoccmd.exe convert -c xml -o D:\backup\人物入水.xml D:\backup\人物入水.rdc
py -3 xml_to_bundle.py D:\backup\人物入水.xml -o D:\backup\人物入水_bundle

# 结果: 1240 事件, 569 纹理, 1585 Buffer
```

---

## 路线 C: 简化报告（无需 GPU）

### 前置条件
- ✅ 安装 RenderDoc CLI
- ❌ **不需要** GPU

### 命令
```bash
# 生成单页 HTML
py -3 -m rdc_analyzer report input.xml -o report.html
```

### 输出
- 单个 `report.html` 文件（传统样式）

### 适用场景
- 快速预览
- 简单统计需求
- 兼容旧版工作流

---

## 路线对比

| 特性 | 路线 A (完整回放) | 路线 B (XML中转) | 路线 C (简化) |
|------|-------------------|------------------|---------------|
| **需要 GPU** | ✅ 是 | ❌ 否 | ❌ 否 |
| **需要 renderdoc 模块** | ✅ 是 | ❌ 否 | ❌ 否 |
| **报告样式** | Bundle (4页) | Bundle (4页) | 单页 HTML |
| **Shader 源码** | ✅ 完整 | ⚠️ 仅名称 | ⚠️ 仅名称 |
| **纹理缩略图** | ✅ 有 | ✅ 有（zip.xml + --zip，默认前 50 张） | ❌ 无 |
| **适合 CI/CD** | ⚠️ 需配置 | ✅ 推荐 | ✅ 可用 |
| **处理速度** | 慢（需回放） | 快（仅解析） | 最快 |

---

## API 支持矩阵

| 图形 API | 路线 A | 路线 B | 路线 C |
|----------|--------|--------|--------|
| Vulkan | ✅ | ✅ (v1.6.0+) | ✅ |
| D3D11 | ✅ | ✅ | ✅ |
| D3D12 | ✅ | ✅ | ✅ |
| OpenGL | ✅ | ✅ | ✅ |
| OpenGL ES | ✅ | ✅ | ✅ |

---

## 工具文件位置

| 工具 | 路径 | 说明 |
|------|------|------|
| `one_click_bundle_report.py` | `scripts/rdc_analyzer/one_click_bundle_report.py` | RDC 一键导出（含回退与 smoke） |
| `one_click_bundle_preset.bat` | `scripts/rdc_analyzer/one_click_bundle_preset.bat` | 双击预设入口（默认 Endfield 路径） |
| `xml_to_bundle.py` | `scripts/rdc_analyzer/xml_to_bundle.py` | XML / ZIP+XML → Bundle 转换器 |
| `rdc_analyzer` CLI | `scripts/rdc_analyzer/` | 主分析工具包 |
| `report_bundle_generator.py` | `scripts/rdc_analyzer/report_bundle_generator.py` | Bundle 生成引擎 |

### 新增组件 (v2.2)

| 组件 | 路径 | 说明 |
|------|------|------|
| `RdcAdapter` | `report_engine/adapters/rdc_adapter.py` | 直接从 .rdc 加载（需 `renderdoc` 模块） |
| `JsonRenderer` | `report_engine/renderers/json_renderer.py` | JSON 格式报告输出 |
| `Schemas` | `report_engine/schemas.py` | 字段结构定义（Shader/Pipeline/Texture/Event） |

#### RdcAdapter 说明

`RdcAdapter` 需要 RenderDoc Python 模块才能工作：

```python
# 需要 renderdoc.pyd (Windows) 或 renderdoc.so (Linux) 在 Python 路径中
import renderdoc  # 如果失败，RdcAdapter 会优雅降级
```

**获取方式**：
1. 从源码编译 RenderDoc（启用 Python 绑定）
2. 使用官方发布包中的 `pyrenderdoc` 目录

**无模块时的行为**：返回空的 `ReportDataContract`，打印警告信息

#### JsonRenderer 使用示例

```python
from report_engine import ReportDataContract, JsonRenderer

contract = ReportDataContract(...)
renderer = JsonRenderer(indent=2)
json_str = renderer.render(contract)

# 保存到文件
renderer.render_to_file(contract, "report.json")
```

---

## 故障排查

### 问题: Vulkan 捕获显示 0 Draw Calls

**原因**: XML 解析器未识别 `vkCmd*` 开头的调用

**解决**: 升级到 v1.6.0+ 版本，或手动检查 `parsers/rdc_xml_parser.py` 是否包含 Vulkan 映射

### 问题: renderdoccmd 提示 `Need an input filename (-f)`

**原因**: 当前 RenderDoc CLI 要求显式传入 `-f <input.rdc>`，旧命令把输入文件放在末尾会失败。

**解决**:
```bash
# ✅ 正确
renderdoccmd.exe convert -f input.rdc -o output.zip.xml -c zip.xml

# ❌ 旧写法（可能失败）
# renderdoccmd.exe convert -c xml -o output.xml input.rdc
```

### 问题: 如何选择 legacy / snapshot 路由

- 默认不加参数时走 `--renderer-mode legacy`（兼容 fallback）。
- 需要统一事实快照和新页面集合时，使用 `--emit-snapshot-v1 --renderer-mode snapshot`。
- one_click 当前仍按兼容策略调用 legacy 路由。

### 问题: xml_to_bundle.py 报 ImportError

**原因**: 相对导入路径问题

**解决**: 
```bash
# 从仓库根目录运行
cd d:\Code\git\renderdoc
py -3 scripts/rdc_analyzer/xml_to_bundle.py ...
```

### 问题: Bundle 页面样式错误

**原因**: 资源文件未正确生成

**解决**: 检查输出目录是否包含完整的 5 个 HTML 文件 + manifest.json

---

## 相关文档

- [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) - 模块架构
- [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) - 纹理提取方案
- [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) - 无 GPU 提取技术

---

## 更新历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.3.0 | 2026-02-11 | 新增 one_click_bundle_report 一键导出（zip.xml 优先 + xml 回退 + headless smoke） |
| 2.2.0 | 2025-07-25 | 新增 RdcAdapter、JsonRenderer、Schemas 组件说明 |
| 1.0.0 | 2025-01-31 | 初始版本：三条导出路线 |
