# RDC Analyzer 功能索引

> **版本**: 1.1.0 | **最后更新**: 2026-01-19 20:30
>
> ⚠️ **强制阅读**: 所有 AI Agent 在开发前必须阅读本文档，避免重复实现已有功能
>
> 🎯 **核心目标**: 本项目的核心目标是 **性能分析** 和 **RDC 对比（Diffing）**，而非单纯的数据展示。

---

## 📋 目录

1. [命令行入口](#1-命令行入口)
2. [解析器模块](#2-解析器模块)
3. [分析器模块](#3-分析器模块)
4. [报告生成器](#4-报告生成器)
5. [核心数据类型](#5-核心数据类型)
6. [规则引擎](#6-规则引擎)
7. [工具函数](#7-工具函数)
8. [对比分析模块](#8-对比分析模块)
9. [已完成功能清单](#9-已完成功能清单)
10. [开发路线图](#10-开发路线图)

---

## 1. 命令行入口

### 1.1 主入口 `__main__.py`

| 属性 | 值 |
|------|-----|
| **文件** | `__main__.py` |
| **调用方式** | `python -m rdc_analyzer <command>` |
| **版本** | 2.0.0 |

**子命令**:

| 命令 | 功能 | 示例 |
|------|------|------|
| `analyze` | 分析 RDC 文件 | `python -m rdc_analyzer analyze capture.rdc -o ./output` |
| `rules` | 列出分析规则 | `python -m rdc_analyzer rules --list` |

**关键参数**:
- `-o, --output`: 输出目录
- `-f, --format`: 输出格式 (html, json)
- `-p, --platform`: 目标平台 (pc, mobile)
- `--sample-textures`: 采样纹理生成缩略图
- `--event-range`: 事件 ID 范围过滤

### 1.2 分析管线 `main.py`

| 属性 | 值 |
|------|-----|
| **文件** | `main.py` |
| **核心类** | `AnalysisPipeline`, `AnalysisOptions` |

**入口函数**: `analyze(rdc_path, options) -> AnalysisResult`

### 1.3 端到端测试入口 `test_e2e_real_data.py`

| 属性 | 值 |
|------|-----|
| **文件** | `test_e2e_real_data.py` |
| **调用方式** | `py -3 test_e2e_real_data.py <rdc_file> <output_dir>` |

**功能**: 完整测试 RDC → XML → JSON → HTML 流程

### 1.4 RenderDocCmd 导出命令 ⭐ 基础工具

> **位置**: 编译后的 RenderDoc 安装目录 (如 `build/bin/renderdoccmd.exe`)

| 命令 | 功能 | 示例 |
|------|------|------|
| `export` | 导出 RDC 数据 | `renderdoccmd export --out ./output capture.rdc` |

**export 子选项**:

| 选项 | 说明 | 示例 |
|------|------|------|
| `--out <dir>` | 输出目录 | `--out ./export_output` |
| `--xml` | 导出 XML 格式 (默认) | `renderdoccmd export --out ./out --xml capture.rdc` |
| `--bindings` | 导出资源绑定 JSON | `renderdoccmd export --out ./out --bindings capture.rdc` |

**--bindings 输出格式** (`bindings.json`):

```json
{
  "42": {
    "constantBuffers": [
      {
        "slot": 0,
        "name": "cbPerObject",
        "size": 256,
        "members": [
          {"name": "worldMatrix", "type": "float4x4", "offset": 0, "value": [1.0, 0.0, ...]}
        ]
      }
    ],
    "textures": [...],
    "samplers": [...]
  }
}
```

> **注意**: `--bindings` 需要在 Replay 环境下运行，因此需要有效的图形驱动支持。

---

## 2. 解析器模块

### 2.1 XML 解析器 `parse_rdc_xml.py` ⭐ 核心

| 属性 | 值 |
|------|-----|
| **文件** | `parse_rdc_xml.py` |
| **支持 API** | D3D11, D3D12, Vulkan, OpenGL |
| **输出格式** | Python dict (JSON 兼容) |

**核心函数**:

| 函数 | 功能 | 状态 |
|------|------|------|
| `parse_rdc_xml(xml_path)` | 主入口，解析整个 XML | ✅ 完成 |
| `parse_mesh_info(params, api)` | 解析 Mesh Info (VB/IB) | ✅ 完成 (TASK-002) |
| `parse_pipeline_state_from_related_calls(calls, api)` | 解析 Pipeline State | ✅ 完成 (TASK-001) |
| `parse_resource_bindings(params, api, ds_map)` | 解析资源绑定 | ✅ 完成 (TASK-003) |
| `collect_descriptor_set_contents(events)` | 预扫描 Vulkan DescriptorSet | ✅ 完成 |

**支持的数据提取**:
- ✅ Events (Draw Call, Dispatch, State Set)
- ✅ Textures (名称、尺寸、格式、内存)
- ✅ Buffers (名称、大小、用途)
- ✅ Shaders (VS, PS, CS, GS, HS, DS)
- ✅ Mesh Info (Vertex Buffers, Index Buffer, Input Layout)
- ✅ Pipeline State (Viewport, Scissor, Blend, Depth, Shaders)
- ✅ Resource Bindings (SRV, CBV, Sampler, UAV, DescriptorSet)

### 2.2 二进制解析器 `parsers/binary_parser.py`

| 属性 | 值 |
|------|-----|
| **文件** | `parsers/binary_parser.py` |
| **功能** | 直接解析 RDC 二进制格式 |

### 2.3 API 解析器 `parsers/api_parser.py`

| 属性 | 值 |
|------|-----|
| **文件** | `parsers/api_parser.py` |
| **功能** | API 调用模式识别 |

---

## 3. 分析器模块 ⭐ 已实现

### 3.1 性能分析器 `analyzers/performance_analyzer.py`

| 属性 | 值 |
|------|-----|
| **文件** | `analyzers/performance_analyzer.py` |
| **类** | `PerformanceAnalyzer` |
| **依赖** | `AnalysisContext`, `PerformanceReport` |

**已实现规则**:

| 规则 ID | 名称 | 检测内容 | 状态 |
|---------|------|----------|------|
| PERF001 | 过度绘制 | 同一 RT 被多次绘制 | ✅ |
| PERF002 | 状态冗余 | 连续相同状态设置 | ✅ |
| PERF003 | 小批次绘制 | 顶点数过少的 Draw | ✅ |
| PERF004 | 大纹理 | 超大尺寸纹理 | ✅ |
| PERF005 | 未压缩纹理 | 未使用 BC/DXT 压缩 | ✅ |
| PERF006 | Alpha 混合过度使用 | Blend 比例过高 | ✅ |
| PERF007 | 频繁绑定 | 资源频繁绑定/解绑 | ✅ |

**输出**: `PerformanceReport` (含 `overall_score`, `issues`, `recommendations`)

### 3.2 Mali GPU 分析器 `analyzers/mali_analyzer.py`

| 属性 | 值 |
|------|-----|
| **文件** | `analyzers/mali_analyzer.py` |
| **类** | `MaliAnalyzer` |
| **功能** | Mali GPU 特定性能分析 |

**集成**: 可使用 `malioc` 工具分析 Shader 性能

### 3.3 优化建议器 `analyzers/optimization_advisor.py`

| 属性 | 值 |
|------|-----|
| **文件** | `analyzers/optimization_advisor.py` |
| **类** | `OptimizationAdvisor` |

**功能**: 基于分析结果生成优化建议列表

### 3.4 其他分析器

| 文件 | 类 | 功能 |
|------|-----|------|
| `analyzers/frame.py` | `FrameAnalyzer` | 帧级分析 |
| `analyzers/pass_analyzer.py` | `PassAnalyzer` | Render Pass 分析 |
| `analyzers/resource.py` | `ResourceAnalyzer` | 资源使用分析 |
| `analyzers/state.py` | `StateAnalyzer` | 状态变更分析 |

---

## 4. 报告生成器

### 4.1 HTML 报告 `generate_real_report.py` ⭐ 主要

| 属性 | 值 |
|------|-----|
| **文件** | `generate_real_report.py` |
| **调用方式** | `py -3 generate_real_report.py <xml_file> -o report.html` |

**功能**:
- ✅ 事件列表 (可折叠树形结构)
- ✅ 纹理预览 (Base64 内嵌)
- ✅ Draw Call 详情
- ✅ Pipeline State 显示
- ✅ Mesh Info 显示
- ✅ Resource Bindings 显示

### 4.2 其他报告生成器

| 文件 | 格式 | 功能 |
|------|------|------|
| `reporters/html_reporter.py` | HTML | 框架级 HTML 报告器 |
| `reporters/json_reporter.py` | JSON | JSON 格式输出 |
| `reporters/markdown_reporter.py` | Markdown | 文本报告 |
| `reporters/csv_reporter.py` | CSV | 表格数据导出 |
| `reporters/console_reporter.py` | Console | 终端输出 |

---

## 5. 核心数据类型

### 5.1 类型定义 `core/types.py`

| 类 | 用途 |
|----|------|
| `TextureInfo` | 纹理元数据 (width, height, format, mip_levels, memory_size) |
| `BufferInfo` | 缓冲区元数据 (size, usage, stride) |
| `ShaderInfo` | Shader 元数据 (type, entry_point, resource_id) |
| `DrawCallInfo` | Draw Call 数据 (vertex_count, index_count, instance_count) |
| `PerformanceMetrics` | 性能指标 |
| `PerformanceIssue` | 性能问题描述 |
| `PerformanceReport` | 性能报告汇总 |
| `PerformanceRule` | 性能规则定义 |

### 5.2 分析上下文 `core/context.py`

| 类 | 用途 |
|----|------|
| `AnalysisContext` | 分析过程的共享状态容器 |
| `ParsedData` | 解析结果数据 |
| `FrameSummary` | 帧摘要统计 |

### 5.3 其他核心模块

| 文件 | 功能 |
|------|------|
| `core/pipeline_state.py` | Pipeline State 数据结构 |
| `core/resource_inspector.py` | 资源检查器 |
| `core/duplicate_detector.py` | 重复资源检测 |
| `core/texture_usage_analyzer.py` | 纹理使用分析 |
| `core/thumbnail_extractor.py` | 纹理缩略图提取 |
| `core/optimization_advisor.py` | 优化建议生成 (另一版本) |

---

## 6. 规则引擎

### 6.1 规则注册表 `rules/`

| 文件 | 规则类型 |
|------|----------|
| `rules/texture.py` | 纹理相关规则 |
| `rules/buffer.py` | 缓冲区规则 |
| `rules/draw_call.py` | Draw Call 规则 |
| `rules/render_pass.py` | Render Pass 规则 |
| `rules/state.py` | 状态设置规则 |
| `rules/mobile.py` | 移动端特定规则 |
| `rules/runner.py` | 规则执行器 |

### 6.2 规则定义格式

```python
class TextureSizeRule(BaseRule):
    rule_id = "TEX001"
    name = "Large Texture Detection"
    description = "Detect textures larger than threshold"
    severity = "warning"
    category = "texture"
    platforms = ["pc", "mobile"]
```

---

## 7. 工具函数

### 7.1 工具模块 `utils/`

| 文件 | 功能 |
|------|------|
| `utils/format_utils.py` | 格式化工具 (字节数、时间等) |
| `utils/memory_utils.py` | 内存计算工具 |
| `utils/lz4_utils.py` | LZ4 压缩/解压 |

### 7.2 提取器 `extractors/`

| 文件 | 功能 |
|------|------|
| `extractors/shader_extractor.py` | Shader 源码提取 |
| `extractors/event_parser.py` | 事件解析器 |
| `extractors/replay_wrapper.py` | RenderDoc Replay API 封装 |
| `extractors/d3d11_extractor.py` | D3D11 特定提取 |

### 7.3 独立脚本

| 文件 | 功能 | 调用方式 |
|------|------|----------|
| `extract_pipeline_state.py` | 提取 Pipeline State | `py -3 extract_pipeline_state.py <rdc>` |
| `extract_shaders.py` | 提取所有 Shader | `py -3 extract_shaders.py <rdc>` |
| `export_textures.py` | 导出纹理图片 | `py -3 export_textures.py <rdc>` |
| `analyze_rdc.py` | 快速分析入口 | `py -3 analyze_rdc.py <rdc>` |
| `analyze_rdc_mali.py` | Mali GPU 分析 | `py -3 analyze_rdc_mali.py <rdc>` |
| `batch_analyze.py` | 批量分析多个 RDC | `py -3 batch_analyze.py <dir>` |

---

## 8. 对比分析模块 ⭐ Phase 2 核心

> **状态**: ✅ 已完成 | **目标**: 实现两个 RDC 文件的差异对比，找出性能回归点

### 8.1 DiffEngine 核心引擎 (TASK-010) ✅

| 属性 | 值 |
|------|-----|
| **文件** | `diff/diff_engine.py` |
| **类** | `DiffEngine` |
| **输入** | 两个 `parse_rdc_xml.py` 输出的 dict (baseline, target) |
| **输出** | `DiffReport` 对象 |
| **状态** | ✅ 已完成 (Commit: 48b770712) |

**对比维度**:

| 维度 | 检测内容 | 优先级 |
|------|----------|--------|
| Draw Call 数量 | 新增、删除、顺序变化 | P0 |
| 纹理使用 | 新增、删除、尺寸变化、格式变化 | P0 |
| Buffer 使用 | 大小变化 | P1 |
| Shader 变更 | 新增、删除、修改 | P0 |
| 状态设置 | Blend/Depth/Viewport 差异 | P1 |
| 帧统计 | total_draws, total_triangles, memory_usage | P0 |

### 8.2 DiffReport 数据结构

```python
@dataclass
class DiffReport:
    summary: DiffSummary           # 总体统计
    draw_call_diff: DrawCallDiff   # DC 增减
    texture_diff: TextureDiff      # 纹理变化
    shader_diff: ShaderDiff        # Shader 变化
    state_diff: StateDiff          # 状态设置差异
    
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...
```

### 8.3 RegressionDetector 回归检测 (TASK-013) ✅

| 属性 | 值 |
|------|-----|
| **文件** | `diff/regression_detector.py` |
| **类** | `RegressionDetector` |
| **输入** | `DiffReport` |
| **输出** | `List[RegressionWarning]` |
| **状态** | ✅ 已完成 (Commit: 48b770712) |

**回归规则**:

| 规则 ID | 名称 | 阈值 | 严重度 |
|---------|------|------|--------|
| REG001 | Draw Call 增加 | >10% | high |
| REG002 | 纹理内存增加 | >20 MB | high |
| REG003 | 大尺寸纹理新增 | >2048 px | medium |
| REG004 | 未压缩纹理新增 | 任意 | medium |
| REG005 | Shader 数量增加 | >5 | low |
| REG006 | 状态切换增加 | >20% | medium |

### 8.4 对比报告生成 (TASK-011)

| 文件 | 功能 |
|------|------|
| `generate_diff_report.py` | 生成对比 HTML 报告 |
| `exporters/diff_html_exporter.py` | HTML 模板和渲染逻辑 |

**颜色编码**:
- 🟢 新增 (added)
- 🔴 删除 (removed)  
- 🟡 修改 (changed)

### 8.5 对比工作流

```
┌─────────────┐     ┌─────────────┐
│ baseline.rdc │     │ target.rdc  │
└──────┬──────┘     └──────┬──────┘
       │                    │
       ▼                    ▼
┌─────────────────────────────────┐
│      renderdoccmd export        │
│         (XML 导出)               │
└─────────────────┬───────────────┘
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
┌─────────────┐       ┌─────────────┐
│baseline.json│       │ target.json │
└──────┬──────┘       └──────┬──────┘
       │                     │
       └──────────┬──────────┘
                  ▼
        ┌─────────────────┐
        │   DiffEngine    │
        │   compare()     │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │   DiffReport    │
        └────────┬────────┘
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
┌─────────────┐    ┌─────────────────┐
│ diff.html   │    │ RegressionDetector │
│ (可视化报告) │    │ (回归警告)          │
└─────────────┘    └─────────────────┘
```

---

## 9. 已完成功能清单

### 9.1 核心功能 (TASK-000)

| 功能 | 状态 | Commit |
|------|------|--------|
| `renderdoccmd export` 命令 | ✅ | 67320aa |
| `renderdoccmd export --bindings` | ✅ | a1b2c3d |
| XML 解析器 (D3D11/D3D12/Vulkan) | ✅ | 144b718 |
| HTML 报告生成 | ✅ | 944230c |
| 端到端测试框架 | ✅ | a77eb3d |

### 9.2 数据解析 (TASK-001~003)

| 功能 | 状态 | Commit | 任务 |
|------|------|--------|------|
| Pipeline State 解析 | ✅ | 9e57ac7 | TASK-001 |
| Mesh Info 解析 (VB/IB) | ✅ | 9e57ac7 | TASK-002 |
| Resource Bindings 解析 | ✅ | ac45438 | TASK-003 |
| Vulkan DescriptorSet 展开 | ✅ | 90df72c | TASK-003 |
| State 对象映射表 | ✅ | 84635f6 | - |
| CB 成员数据展示 | ✅ | 97dcc8b | - |

### 9.3 性能分析 (已实现但未集成)

| 功能 | 状态 | 文件 | 说明 |
|------|------|------|------|
| PerformanceAnalyzer (PERF001-007) | ✅ 已实现 | `analyzers/performance_analyzer.py` | ⚠️ 未集成到 HTML 报告 |
| MaliAnalyzer | ✅ 已实现 | `analyzers/mali_analyzer.py` | 需要 malioc 工具 |
| OptimizationAdvisor | ✅ 已实现 | `analyzers/optimization_advisor.py` | ⚠️ 未集成到 HTML 报告 |

### 9.4 对比分析 (TASK-010~013) ✅ 已完成

| 功能 | 状态 | Commit | 任务 |
|------|------|--------|------|
| DiffEngine 对比引擎 | ✅ | 48b770712 | TASK-010 |
| 差异可视化 HTML | ✅ | 48b770712 | TASK-011 |
| CLI 对比入口 `compare_rdc.py` | ✅ | 48b770712 | TASK-012 |
| RegressionDetector 回归检测 | ✅ | 48b770712 | TASK-013 |
| 全局 Shader 列表收集 | ✅ | e95ed2686 | Phase 1 增强 |

---

## 10. 开发路线图

### Phase 1: 性能分析激活 (当前阶段)

> **目标**: 将现有分析器与 HTML 报告集成
> **预计工时**: 2.5 小时

| 任务 | 状态 | 依赖 |
|------|------|------|
| TASK-007: XMLToContextBridge | 🔴 进行中 | 无 |
| TASK-008: PerformanceAnalyzer 集成 | 🟡 待认领 | TASK-007 |
| TASK-009: OptimizationAdvisor 集成 | 🟡 待认领 | TASK-007 |

### Phase 2: RDC 对比分析 ⭐ 已完成

> **目标**: 实现两个 RDC 的差异对比，找出性能回归点
> **完成时间**: 2026-01-19

| 任务 | 状态 | 完成者 |
|------|------|--------|
| TASK-010: DiffEngine 核心实现 | ✅ 已完成 | Flux-0119 |
| TASK-011: 差异可视化 HTML | ✅ 已完成 | Flux-0119 |
| TASK-012: CLI 对比入口 | ✅ 已完成 | Flux-0119 |
| TASK-013: 性能回归检测 | ✅ 已完成 | Flux-0119 |

### Phase 3: 兼容性与扩展

> **目标**: 测试和扩展 API 支持
> **预计工时**: 1.5 小时

| 任务 | 状态 | 依赖 |
|------|------|------|
| TASK-004: Pipeline State 脚本集成 | 🟡 待认领 | TASK-001 |
| TASK-005: OpenGL API 支持测试 | 🟡 待认领 | 无 |
| TASK-006: D3D12 API 支持测试 | 🟡 待认领 | 无 |

### 里程碑时间线

```
┌──────────────────────────────────────────────────────────────┐
│ 2026-01-19 ~ 2026-01-20                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                              │
│ Phase 1 [性能分析]                                           │
│ ├─ TASK-007 Bridge ████░░░░ 50%                             │
│ ├─ TASK-008 Perf   ░░░░░░░░ 0%                              │
│ └─ TASK-009 Opt    ░░░░░░░░ 0%                              │
│                                                              │
│ Phase 2 [对比分析] ⭐ 核心                                   │
│ ├─ TASK-010 Diff   ░░░░░░░░ 0%                              │
│ ├─ TASK-011 HTML   ░░░░░░░░ 0%                              │
│ ├─ TASK-012 CLI    ░░░░░░░░ 0%                              │
│ └─ TASK-013 Reg    ░░░░░░░░ 0%                              │
│                                                              │
│ Phase 3 [兼容性]                                             │
│ └─ TASK-004~006    ░░░░░░░░ 0%                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. 架构依赖图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户入口                                  │
│  __main__.py / test_e2e_real_data.py / generate_real_report.py  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     parse_rdc_xml.py                            │
│  (XML → Python dict: events, textures, buffers, shaders, etc.)  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌─────────────────┐ ┌───────────────┐ ┌───────────────────┐
│ generate_real_  │ │ analyzers/    │ │ core/types.py     │
│ report.py       │ │ performance_  │ │ core/context.py   │
│ (HTML 报告)      │ │ analyzer.py   │ │ (数据结构)         │
└─────────────────┘ └───────────────┘ └───────────────────┘
                          │
                          ▼
               ┌───────────────────┐
               │ ⚠️ 缺失的桥接     │
               │ XMLToContextBridge │
               │ (TASK-007)         │
               └───────────────────┘
```

---

## 12. 快速参考

### 12.1 常用命令

```bash
# 端到端测试
py -3 test_e2e_real_data.py capture.rdc ./output

# 生成 HTML 报告
py -3 generate_real_report.py capture.xml -o report.html

# 导出资源绑定 (含 CB 成员数据)
renderdoccmd export --out ./output --bindings capture.rdc

# 列出所有规则
py -3 -m rdc_analyzer rules --list

# 提取 Shader
py -3 extract_shaders.py capture.rdc

# Mali 分析
py -3 analyze_rdc_mali.py capture.rdc

# [Phase 2] RDC 对比 (计划中)
py -3 scripts/rdc_analyzer/generate_diff_report.py baseline.json target.json -o diff.html
```

### 12.2 关键路径

| 用途 | 路径 |
|------|------|
| 主入口 | `__main__.py` |
| XML 解析 | `parse_rdc_xml.py` |
| 性能分析 | `analyzers/performance_analyzer.py` |
| HTML 报告 | `generate_real_report.py` |
| 数据类型 | `core/types.py` |
| 分析上下文 | `core/context.py` |
| **对比引擎** (计划) | `diff/diff_engine.py` |
| **回归检测** (计划) | `diff/regression_detector.py` |

---

## 📝 维护说明

1. **新增功能时**: 在本文档对应章节添加条目
2. **完成任务时**: 更新"已完成功能清单"
3. **变更入口时**: 更新"命令行入口"章节
4. **添加规则时**: 更新"规则引擎"和"性能分析器"章节
5. **Phase 2 开发时**: 更新"对比分析模块"和"开发路线图"

---

*最后更新: Flux-0119 @ 2026-01-19 20:30*
