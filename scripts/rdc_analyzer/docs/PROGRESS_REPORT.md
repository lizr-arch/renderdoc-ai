# RDC Analyzer 项目进度报告

> **更新日期**: 2025-01-17
> **版本**: v2.6
> **作者**: Codex Agent

---

## 1. 项目概述

RDC Analyzer 是一个离线 RenderDoc 捕获文件（`.rdc`）分析工具，专注于：
- **Shader 性能分析**：提取 SPIR-V/GLSL 着色器并使用 Mali Offline Compiler 进行性能评估
- **纹理元数据提取**：解析 Vulkan `vkCreateImage` 数据获取分辨率、格式信息
- **多捕获对比**：SHA256 哈希匹配跨帧/跨场景的相同着色器
- **HTML 报告生成**：可视化展示性能数据和资源使用情况

---

## 2. 已完成功能

### 2.1 核心解析能力

| 功能 | 状态 | 文件 | 说明 |
|------|------|------|------|
| RDC 二进制解析 | ✅ | `rdc_parser.py` | 支持 Section 索引、Chunk 提取 |
| SPIR-V 元数据解析 | ✅ | `rdc_parser.py` | `OpEntryPoint` + `OpName` 提取 |
| vkCreateImage 解析 | ✅ | `rdc_parser.py` | 支持 112/136 字节两种格式 |
| VkFormat 映射 | ✅ | `rdc_parser.py` | 200+ 格式枚举完整覆盖 |
| LZ4 解压缩 | ✅ | `utils/lz4_utils.py` | Chunk 数据解压 |

### 2.2 分析与报告

| 功能 | 状态 | 文件 | 说明 |
|------|------|------|------|
| 多 RDC 对比分析 | ✅ | `analyze_rdc.py` | SHA256 哈希匹配 |
| HTML 报告生成 | ✅ | `analyze_rdc.py` | Bootstrap 5 响应式设计 |
| Shader Tab | ✅ | 报告 v2.6 | Stage/Hash/Resource Hint/Size 列 |
| Textures Tab | ✅ | 报告 v2.6 | ResourceID/尺寸/格式/来源文件 |
| Mali 性能分析 | ✅ | `mali_analyzer.py` | Cycles/Registers/Spilling |

### 2.3 技术突破

| 问题 | 解决方案 |
|------|----------|
| 136 字节 Chunk 偏移问题 | 多偏移扫描 + 2的幂次方评分 |
| Resource Hint 误导命名 | 明确标注为 SPIR-V OpName 变量名 |
| Shader 名称不可获取 | 文档说明需要 Debug Symbol |

---

## 3. 技术发现

### 3.1 SPIR-V OpName 机制

**结论**：`OpName` 是调试符号，包含变量名而非 Shader 名称。

```
OpName 数据示例（一个 PS 可能包含 50+ 条）:
- ID 10: SceneColorTextureSampler
- ID 11: SceneColorTexture
- ID 15: Material_Texture2D_0
- ID 20: View (UBO)
- ID 21: Primitive (UBO)
```

**当前实现**：`friendly_label` 使用评分机制选择"最有意义"的一个名称显示。

**待优化**：提取完整资源列表，分类为 Texture/Sampler/Buffer/UBO。

### 3.2 Shader 名称限制

| 信息类型 | 能否获取 | 来源 |
|----------|----------|------|
| Entry Point | ✅ | `OpEntryPoint`（如 `main_00000f3c_6409666b`） |
| 资源变量名 | ✅ | `OpName`（如 `SceneColorTexture`） |
| **原始 Shader 名** | ❌ | 需要 PDB/UE Symbol |

---

## 4. 代码架构分析

### 4.1 文件规模统计（>500 行）

| 文件 | 行数 | 职责 | 重构建议 |
|------|------|------|----------|
| `exporters/html_exporter.py` | 3866 | HTML 模板生成 | ⚠️ 需拆分 |
| `rdc_parser.py` | 2144 | RDC 二进制解析 | ⚠️ 需拆分 |
| `main.py` | 1194 | CLI 入口 | 考虑精简 |
| `analyze_rdc.py` | 1158 | 分析脚本 | 保持现状 |
| `renderdoc_mali_shell.py` | 1042 | Mali Shell 集成 | 保持现状 |
| `converters/shader_converter.py` | 935 | Shader 转换 | 保持现状 |
| `core/pipeline_state.py` | 815 | 管线状态 | 保持现状 |
| `analyzers/mali_analyzer.py` | 801 | Mali 分析器 | 保持现状 |

### 4.2 重构优先级

1. **html_exporter.py (3866 行)** - 最高优先级
   - 问题：HTML 模板字符串内嵌，难以维护
   - 建议：模板分离到 `templates/` 目录

2. **rdc_parser.py (2144 行)** - 高优先级
   - 问题：单文件包含多种解析器
   - 建议：拆分为 `spirv_parser.py`、`texture_parser.py`、`chunk_parser.py`

---

## 5. 下一步计划

### P0 - 高优先级

| 任务 | 描述 | 预计工时 |
|------|------|----------|
| 提取完整资源列表 | 从 SPIR-V 提取所有 OpName，分类为 Texture/Sampler/Buffer | 2h |
| 资源详情视图 | 点击 Shader 跳转显示完整资源列表 | 1h |

### P1 - 中优先级

| 任务 | 描述 | 预计工时 |
|------|------|----------|
| 代码重构 | 拆分 `rdc_parser.py` 和 `html_exporter.py` | 4h |
| 资源使用统计 | 统计每帧渲染的资源数量，评估渲染压力 | 2h |

### P2 - 低优先级

| 任务 | 描述 | 预计工时 |
|------|------|----------|
| ResourceRenames 解析 | 读取用户自定义资源名称 | 1h |
| 性能基准测试 | 建立 Mali G715 性能基线数据 | 2h |

---

## 6. 输出文件说明

| 文件 | 说明 |
|------|------|
| `output/comparison_report_v2.6.html` | 最新 HTML 报告 |
| `output/comparison_data_v2.5.json` | JSON 格式分析数据 |
| `extracted_shaders/` | 提取的 SPIR-V/GLSL 文件 |

---

## 7. 使用示例

```bash
# 单文件分析
py -3 analyze_rdc.py --rdc path/to/capture.rdc

# 多文件对比
py -3 analyze_rdc.py --rdc file1.rdc file2.rdc --output report.html

# Mali 性能分析
py -3 mali_analyzer.py --shader extracted_shaders/ps_001.glsl --gpu Mali-G715
```

---

*报告生成于 2025-01-17 by Codex Agent*
