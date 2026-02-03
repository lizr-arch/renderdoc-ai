# RDC 报告导出路线图

> **更新日期**: 2025-01-31 | **版本**: 1.0.0

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
│  .rdc ──[renderdoccmd]──> .xml ──[xml_to_bundle.py]──> Bundle 报告 (4页) │
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

#### 步骤 1: RDC → XML
```bash
renderdoccmd.exe convert -c xml -o output.xml input.rdc
```

#### 步骤 2: XML → Bundle 报告
```bash
py -3 scripts/rdc_analyzer/xml_to_bundle.py output.xml -o bundle_output/
```

### 输出（与路线 A 相同）
- `index.html` - 仪表盘
- `events.html` - 事件列表
- `textures.html` - 纹理浏览器
- `shaders.html` - Shader 查看器
- `recommendations.html` - 优化建议
- `manifest.json` - 页面元数据

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
| **纹理缩略图** | ✅ 有 | ❌ 无 | ❌ 无 |
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
| `xml_to_bundle.py` | `scripts/rdc_analyzer/xml_to_bundle.py` | XML → Bundle 转换器 |
| `rdc_analyzer` CLI | `scripts/rdc_analyzer/` | 主分析工具包 |
| `report_bundle_generator.py` | `scripts/rdc_analyzer/report_bundle_generator.py` | Bundle 生成引擎 |

---

## 故障排查

### 问题: Vulkan 捕获显示 0 Draw Calls

**原因**: XML 解析器未识别 `vkCmd*` 开头的调用

**解决**: 升级到 v1.6.0+ 版本，或手动检查 `parsers/rdc_xml_parser.py` 是否包含 Vulkan 映射

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
| 1.0.0 | 2025-01-31 | 初始版本：三条导出路线 |
