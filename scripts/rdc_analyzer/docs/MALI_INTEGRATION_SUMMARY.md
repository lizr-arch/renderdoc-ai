# Mali Offline Compiler 集成项目总结

> **版本**: v1.1.0 | **日期**: 2026-02 | **状态**: Active

---

## 一、项目概述

### 1.1 目标
将 Arm Mali Offline Compiler (`malioc`) 集成到 RenderDoc RDC 分析工具中，实现对移动端 Mali GPU 的 Shader 性能预估和瓶颈分析。

### 1.2 核心价值
| 场景 | 价值 |
|------|------|
| **跨平台开发** | 在 PC 上捕获帧，分析移动端 Mali GPU 性能 |
| **性能预估** | 无需真机即可估算 Shader 在 Mali 上的周期数 |
| **瓶颈识别** | 自动识别 Arithmetic/Texture/Load-Store/Varying 瓶颈 |
| **批量分析** | 一次分析 RDC 中所有 Shader，生成汇总报告 |

---

## 二、已完成工作

### 2.1 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| **Shader 转换器** | `converters/shader_converter.py` | HLSL/DXBC → GLSL ES 3.0 转换 |
| **Mali 分析器** | `mali_analyzer.py` | 调用 malioc，解析 JSON 输出 |
| **HTML 报告器** | `generate_sample_report.py` | 生成交互式可折叠报告 |
| **Shell 脚本** | `renderdoc_mali_shell.py` | RenderDoc Python Shell 入口 |

### 2.2 报告功能

```
┌─────────────────────────────────────────────────────────────┐
│  Mali Shader Analysis Report                                │
├─────────────────────────────────────────────────────────────┤
│  [Summary Cards]                                            │
│  Total: 11 | VS: 4 | PS: 7 | Arith: 12.5 cyc | Tex: 3.2 cyc │
├─────────────────────────────────────────────────────────────┤
│  [Bottleneck Distribution]                                  │
│  Arithmetic: 5 | Load/Store: 4 | Texture: 1 | Varying: 1    │
├─────────────────────────────────────────────────────────────┤
│  [Filter Bar]                                               │
│  Type: [All ▼] Bound: [All ▼] Sort: [Cycles ▼]              │
├─────────────────────────────────────────────────────────────┤
│  [Shader List - Collapsible]                                │
│  ▶ VS_Main_EID100    [VE] [Load/Store]     3.00 cyc        │
│  ▼ PS_PBR_EID500     [FR] [Arithmetic]     3.94 cyc        │
│    ┌──────────────────────────────────────────────────┐    │
│    │ Performance Cycles (Shortest Path)                │    │
│    │ Arith: 3.94 | FMA: 3.94 | CVT: 0.44 | SFU: 2.50  │    │
│    │ L/S: 0.00 | Tex: 1.25 | Vary: 1.00               │    │
│    ├──────────────────────────────────────────────────┤    │
│    │ Shader Properties                                 │    │
│    │ Work Registers: 31 | Occupancy: 100% | FP16: 1%  │    │
│    └──────────────────────────────────────────────────┘    │
│  ▶ PS_GaussBlur_EID700 [FR] [Texture]      2.25 cyc        │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 malioc 数据解析

默认 malioc 路径（repo-first）：
- `tools/malioc/2026.0/mali_offline_compiler/malioc.exe`
- 可通过环境变量 `MALIOC_PATH` 覆盖

完整解析 malioc v8.8.1 JSON Schema v2 输出：

| 数据类别 | 字段 |
|----------|------|
| **Pipelines** | `arith_total`, `arith_fma`, `arith_cvt`, `arith_sfu`, `load_store`, `texture`, `varying` |
| **Cycle Paths** | `shortest_path_cycles`, `longest_path_cycles`, `total_cycles` |
| **Bound** | `bound_pipelines` (瓶颈识别) |
| **Properties** | `work_registers_used`, `uniform_registers_used`, `thread_occupancy`, `fp16_arithmetic`, `has_stack_spilling` |
| **Flags** | `has_uniform_computation`, `has_side_effects`, `modifies_coverage` |

### 2.4 交互功能

- ✅ **折叠/展开** - 点击 Shader 行查看详情
- ✅ **筛选** - 按 Vertex/Fragment 类型筛选
- ✅ **筛选** - 按 Arithmetic/Texture/L-S/Varying 瓶颈筛选
- ✅ **排序** - 按名称、Cycle 数升序/降序
- ✅ **批量操作** - Expand All / Collapse All

---

## 三、当前不足与限制

### 3.1 技术限制

| 问题 | 影响 | 优先级 |
|------|------|--------|
| **DXBC → GLSL 转换不完整** | 无法精确转换 DX Shader，只能生成复杂度等价的 Stub | P1 |
| **未集成真实 RDC 提取** | 当前使用硬编码 Shader 示例，未连接 RenderDoc API | P0 |
| **Python 环境隔离** | RenderDoc 内嵌 Python 3.6，外部脚本无法直接调用 | P1 |
| **无 SPIR-V 直通** | Vulkan Shader 应直接传给 malioc，当前未实现 | P2 |

### 3.2 功能缺失

| 功能 | 状态 | 说明 |
|------|------|------|
| **RDC Shader 自动提取** | ❌ 未完成 | 需在 RenderDoc Shell 中实现 |
| **Draw Call 关联** | ❌ 未完成 | 应显示 Shader 被哪些 EID 使用 |
| **优化建议** | ❌ 未完成 | 根据瓶颈类型给出具体建议 |
| **Shader 源码查看** | ❌ 未完成 | 展开时显示反汇编/源码 |
| **对比分析** | ❌ 未完成 | 多个 RDC 或修改前后对比 |
| **导出 JSON** | ⚠️ 部分 | 可导出，但格式未标准化 |

### 3.3 已知 Bug

1. **终端 Emoji 编码问题** - Windows GBK 终端无法显示 ✅ 等符号（已修复为 `[OK]`）
2. **路径硬编码** - malioc 路径写死，需改为配置或自动检测（已修复：repo-first + env override）

---

## 四、文件结构

```
scripts/rdc_analyzer/
├── mali_analyzer.py              # Mali 分析器核心
├── converters/
│   └── shader_converter.py       # HLSL/DXBC → GLSL 转换
├── docs/
│   └── MALI_INTEGRATION_SUMMARY.md  # 本文档
├── output/
│   └── mali_shader_report.html   # 生成的报告
├── generate_sample_report.py     # 报告生成器（主入口）
├── renderdoc_mali_shell.py       # RenderDoc Shell 脚本
└── USAGE_MALI_ANALYZER.md        # 用户使用说明
```

---

## 五、后续规划

### Phase 1: 核心功能完善 (P0)

| 任务 | 描述 | 预估工时 |
|------|------|----------|
| **RDC Shader 真实提取** | 在 `renderdoc_mali_shell.py` 中实现从 RDC 提取所有 Shader | 4h |
| **SPIR-V 直通** | 检测 Vulkan Shader，直接传给 malioc | 2h |
| **路径配置化** | 将 malioc 路径移到配置文件或环境变量 | ✅ 完成 |

### Phase 2: 转换器增强 (P1)

| 任务 | 描述 | 预估工时 |
|------|------|----------|
| **DXBC 指令解析** | 解析 DXBC 反汇编，提取寄存器/指令信息 | 8h |
| **复杂度估算** | 根据指令类型生成更准确的 GLSL Stub | 4h |
| **HLSL 直接解析** | 如果有 HLSL 源码，直接转换（限简单 Shader） | 8h |

### Phase 3: 报告增强 (P2)

| 任务 | 描述 | 预估工时 |
|------|------|----------|
| **Draw Call 关联** | 显示每个 Shader 被哪些 Event ID 使用 | 4h |
| **优化建议引擎** | 根据瓶颈类型和属性生成具体优化建议 | 6h |
| **Shader 源码显示** | 展开时显示反汇编或转换后的 GLSL | 3h |
| **对比模式** | 支持两个分析结果并排对比 | 6h |

### Phase 4: 工具化 (P3)

| 任务 | 描述 | 预估工时 |
|------|------|----------|
| **CLI 支持** | 命令行批量分析多个 RDC | 4h |
| **CI 集成** | 提供 JSON 输出，支持自动化测试 | 4h |
| **配置文件** | 支持多 GPU 目标、阈值配置 | 3h |

---

## 六、技术决策记录

### ADR-001: Shader 转换策略

**背景**: Mali 只支持 OpenGL ES/Vulkan Shader，不支持 DirectX DXBC。

**决策**: 生成"复杂度等价"的 GLSL Stub，而非精确转换。

**理由**:
1. 精确转换需要完整的 DXBC 编译器，工作量巨大
2. 目标是识别瓶颈类型，不需要精确周期数
3. Stub 方法可快速得到可用结果

**后果**:
- ✅ 快速可用
- ❌ 周期数为估算值，非精确值
- ⚠️ 文档需明确说明此限制

### ADR-002: 报告格式

**背景**: 需要展示大量 Shader 分析结果。

**决策**: 使用可折叠列表 + 顶部汇总。

**理由**:
1. 用户首先关心哪些 Shader 最慢
2. 详细数据按需展开，不干扰全局视图
3. 筛选/排序帮助快速定位问题

---

## 七、参考资料

- [Mali Offline Compiler 文档](https://developer.arm.com/Tools%20and%20Software/Mali%20Offline%20Compiler)
- [Mali Valhall 架构白皮书](https://developer.arm.com/documentation/102546/latest)
- [RenderDoc Python API](https://renderdoc.org/docs/python_api/index.html)

---

## 八、贡献者

- 初始开发: AI Assistant (2025-01)
- 需求方: 用户

---

*最后更新: 2026-02*
