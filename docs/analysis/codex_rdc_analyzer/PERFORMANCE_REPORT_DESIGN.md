# RenderDoc 性能分析报告设计文档

> **版本**: 1.0.0 | **日期**: 2025-01-22 | **状态**: 草案
> 
> **目标**: 定义 RenderDoc 性能分析报告的数据来源、分析维度、展示结构

---

## 一、概述

本文档基于对 RenderDoc 官方文档、源码、Python API 的全面调研，整理出可用于性能分析的**所有数据来源**，并设计一个结构化的性能分析报告框架。

### 1.1 数据来源分类

| 来源 | 数据类型 | 获取方式 | 是否需要硬件 |
|------|----------|----------|--------------|
| **RDC 文件结构** | 帧元数据、Draw/Dispatch 列表 | `CaptureFile` / XML 导出 | ❌ 否 |
| **回放分析** | Pipeline State、纹理、Shader | `ReplayController` | ⚠️ 部分 |
| **GPU 计时** | 每个 Event 的 GPU 时间 | `FetchCounters(EventGPUDuration)` | ✅ 是 |
| **硬件计数器** | AMD/NVIDIA/ARM 私有指标 | 厂商 SDK 插件 | ✅ 是 |
| **帧统计** | D3D11 绑定/Draw 统计 | `FrameStatistics` | ⚠️ API 限制 |
| **Overlay 分析** | Overdraw/Triangle Size | GUI 可视化 | ✅ 是 |

---

## 二、可分析的性能资源（完整清单）

### 2.1 Draw Call 相关

| 指标 | 描述 | 来源 | 性能含义 |
|------|------|------|----------|
| **总 Draw Call 数** | 帧内所有绘制调用数量 | `ActionDescription` 列表 | 越多开销越大，应合批 |
| **实例化 Draw 数** | 使用 `Instanced` 标志的 Draw | `flags & ActionFlags.Instanced` | 实例化可减少调用次数 |
| **间接 Draw 数** | 使用 GPU 间接参数的 Draw | `flags & ActionFlags.Indirect` | 可减少 CPU/GPU 同步 |
| **索引 vs 非索引 Draw** | 是否使用 Index Buffer | `flags & ActionFlags.Indexed` | 索引绘制通常更高效 |
| **每 Draw 顶点数** | `numIndices` 或 `numVertices` | `ActionDescription` | 小批次应合并 |
| **每 Draw 实例数** | `numInstances` | `ActionDescription` | 过少实例可考虑动态实例化 |

### 2.2 Dispatch Call 相关

| 指标 | 描述 | 来源 | 性能含义 |
|------|------|------|----------|
| **总 Dispatch 数** | 帧内所有 Compute Dispatch 数量 | `ActionFlags.Dispatch` | 大量 Dispatch 增加调度开销 |
| **Workgroup 维度** | `dispatchDimension[3]` | `ActionDescription` | 不合理维度影响占用率 |
| **Thread Group 大小** | `dispatchThreadsDimension[3]` | `ActionDescription` | 64/128/256 是常见最优值 |
| **间接 Dispatch** | GPU 驱动的计算 | `ActionFlags.Indirect` | 减少 CPU 依赖 |

### 2.3 纹理资源

| 指标 | 描述 | 来源 | 性能含义 |
|------|------|------|----------|
| **纹理总数** | 帧内所有纹理资源 | `ReplayController.GetTextures()` | 太多纹理增加内存压力 |
| **纹理尺寸** | Width × Height × Depth | `TextureDescription` | 超大纹理影响带宽 |
| **纹理格式** | RGBA8, BC7, ASTC 等 | `TextureDescription.format` | 未压缩格式浪费带宽 |
| **Mipmap 层级数** | `mips` | `TextureDescription` | 缺少 Mip 导致带宽浪费 |
| **是否 RenderTarget** | `creationFlags` | `TextureDescription` | RT 不适合压缩 |
| **是否 DepthStencil** | `creationFlags` | `TextureDescription` | DS 格式影响写入效率 |
| **显存占用** | 估算字节数 | 计算公式 | 内存预算管理 |
| **MSAA 采样数** | `msSamp` | `TextureDescription` | 高 MSAA 显著增加开销 |

### 2.4 缓冲区资源

| 指标 | 描述 | 来源 | 性能含义 |
|------|------|------|----------|
| **缓冲区总数** | 帧内所有 Buffer | `ReplayController.GetBuffers()` | 管理开销 |
| **缓冲区大小** | 字节数 | `BufferDescription.length` | 过大 Buffer 增加带宽 |
| **创建标志** | Vertex/Index/Constant/UAV | `BufferDescription.creationFlags` | 用途影响访问模式 |
| **Constant Buffer 数** | 常量缓冲区统计 | 按标志过滤 | 过多 CB 增加绑定开销 |
| **Structured Buffer 数** | 结构化缓冲区 | 按标志过滤 | 用于 Compute |

### 2.5 Shader 资源

| 指标 | 描述 | 来源 | 性能含义 |
|------|------|------|----------|
| **Shader 总数** | 唯一 Shader 数量 | `GetShaders()` | Shader 变种控制 |
| **Shader 变更次数** | 帧内切换次数 | 追踪 Pipeline State | 过多切换增加开销 |
| **Shader 类型分布** | VS/PS/GS/CS/TS/MS | `ShaderStage` | 特殊阶段使用情况 |
| **Shader 大小** | 字节码大小 | `ShaderReflection` | 过大 Shader 影响编译和缓存 |
| **Shader Debug 信息** | 是否包含 PDB | `debugInfo` | 影响包体大小 |

### 2.6 Pipeline State

| 指标 | 描述 | 来源 | 性能含义 |
|------|------|------|----------|
| **Blend State** | 是否启用 Alpha Blend | `PipelineState.outputMerger` | Blend 比 Test 更慢 |
| **Depth Test** | 深度测试模式 | `PipelineState.outputMerger` | Early-Z 优化 |
| **Depth Write** | 是否写入深度 | `PipelineState.outputMerger` | 影响 Hi-Z 效率 |
| **Stencil Test** | 模板测试配置 | `PipelineState.outputMerger` | 额外开销 |
| **Rasterizer State** | 剔除模式、填充模式 | `PipelineState.rasterizer` | 背面剔除节省开销 |
| **Scissor/Viewport** | 裁剪区域数量 | `PipelineState.rasterizer` | 多视口增加开销 |
| **多 RenderTarget** | 同时绑定 RT 数量 | `PipelineState.outputMerger` | MRT 增加带宽 |

### 2.7 GPU 计时与计数器

#### 2.7.1 通用计数器（跨 GPU）

| 计数器 ID | 描述 | 单位 | 用途 |
|-----------|------|------|------|
| `EventGPUDuration` | 每个 Event 的 GPU 时间 | 秒/毫秒 | **核心指标** |
| `InputVerticesRead` | 输入顶点数 | 个数 | 顶点处理负载 |
| `IAPrimitives` | IA 阶段图元数 | 个数 | 几何复杂度 |
| `RasterizerInvocations` | 光栅化调用数 | 个数 | 填充负载 |
| `RasterizedPrimitives` | 最终光栅化图元 | 个数 | 剔除效率 |
| `SamplesPassed` | 通过深度测试样本数 | 个数 | Early-Z 效率 |
| `VSInvocations` | 顶点着色器调用数 | 个数 | VS 负载 |
| `HSInvocations` | Hull Shader 调用数 | 个数 | 曲面细分负载 |
| `DSInvocations` | Domain Shader 调用数 | 个数 | 曲面细分负载 |
| `GSInvocations` | 几何着色器调用数 | 个数 | GS 负载 |
| `PSInvocations` | 像素着色器调用数 | 个数 | **关键：过度绘制指标** |
| `CSInvocations` | 计算着色器调用数 | 个数 | Compute 负载 |

#### 2.7.2 厂商专有计数器

| 厂商 | 计数器范围 | 库/SDK | 典型指标 |
|------|------------|--------|----------|
| **AMD** | `FirstAMD` - `LastAMD` | AMD GPUOpen GPA | 缓存命中率、占用率 |
| **NVIDIA** | `FirstNvidia` - `LastNvidia` | NvPerfKit / Nsight Perf SDK | SM 占用率、L2 命中率 |
| **ARM Mali** | `FirstARM` - `LastARM` | HWCPipe / Lizard | Tile 命中、带宽 |
| **Intel** | `FirstIntel` - `LastIntel` | Intel GPA | EU 使用率 |
| **Vulkan KHR** | `FirstVulkanExtended` | `VK_KHR_performance_query` | 驱动提供 |

### 2.8 帧级统计（D3D11 专有）

> **注意**: `FrameStatistics` 目前仅在 D3D11 捕获中可用

| 统计项 | 描述 | 类 |
|--------|------|-----|
| **DrawcallStats** | Draw 调用次数、实例化、间接 | `DrawcallStats` |
| **DispatchStats** | Dispatch 次数、间接 | `DispatchStats` |
| **ConstantBindStats** | 每阶段 CB 绑定次数/大小分布 | `ConstantBindStats` |
| **SamplerBindStats** | 采样器绑定统计 | `SamplerBindStats` |
| **ResourceBindStats** | SRV/UAV 绑定统计 | `ResourceBindStats` |
| **ShaderChangeStats** | Shader 切换次数、冗余次数 | `ShaderChangeStats` |
| **BlendStats** | Blend 状态绑定、冗余 | `BlendStats` |
| **DepthStencilStats** | DS 状态绑定、冗余 | `DepthStencilStats` |
| **RasterizationStats** | 光栅化状态绑定 | `RasterizationStats` |
| **OutputTargetStats** | RT/UAV 绑定统计 | `OutputTargetStats` |
| **ResourceUpdateStats** | 资源更新/映射统计 | `ResourceUpdateStats` |

### 2.9 Overlay 可视化分析

| Overlay 类型 | 描述 | 性能问题检测 |
|--------------|------|--------------|
| **Highlight Drawcall** | 高亮当前 Draw | 定位绘制范围 |
| **Wireframe Mesh** | 线框模式 | 网格密度检查 |
| **Depth Test** | 深度测试通过/失败 | Early-Z 失效区域 |
| **Stencil Test** | 模板测试通过/失败 | 模板剔除效率 |
| **Backface Cull** | 背面剔除区域 | 剔除效率 |
| **Viewport/Scissor** | 视口/裁剪区域 | 无效渲染区域 |
| **NaN/Inf/-ve** | 异常数值检测 | 数值错误 |
| **Clipping** | 超范围值 | HDR 范围问题 |
| **Clear before Pass/Draw** | 清除后效果 | 混合叠加效果 |
| **Quad Overdraw (Pass)** | Pass 级 2x2 Quad 过度绘制 | **核心：Overdraw 热点** |
| **Quad Overdraw (Draw)** | Draw 级 Quad 过度绘制 | 单次绘制过度绘制 |
| **Triangle Size (Pass)** | Pass 级三角形像素覆盖 | 小三角形问题 |
| **Triangle Size (Draw)** | Draw 级三角形大小 | 几何效率 |

---

## 三、性能问题检测规则（增强版）

### 3.1 现有规则

| 规则 ID | 名称 | 检测逻辑 | 已实现 |
|---------|------|----------|--------|
| `PERF001` | 过度绘制 | RT 被多次绘制 | ✅ |
| `PERF002` | 状态冗余 | 连续相同状态设置 | ✅ |
| `PERF003` | 小批次绘制 | 顶点数过少 | ✅ |
| `PERF004` | 大纹理 | 超过尺寸阈值 | ✅ |
| `PERF005` | 未压缩纹理 | 大纹理未使用 BC/ASTC | ✅ |
| `PERF006` | Alpha 混合过度 | Blend 比例过高 | ✅ |
| `PERF007` | 频繁绑定 | 资源绑定次数过多 | ✅ |

### 3.2 待新增规则

| 规则 ID | 名称 | 检测逻辑 | 数据来源 | 优先级 |
|---------|------|----------|----------|--------|
| `PERF008` | **GPU 热点** | 单个 Event 占用 >5% 帧时间 | `EventGPUDuration` | 🔴 高 |
| `PERF009` | **小三角形** | 平均三角形 <16 像素² | `Triangle Size Overlay` 或启发式 | 🔴 高 |
| `PERF010` | **深度预处理缺失** | Opaque 物体未开启深度写入 | Pipeline State 分析 | 🟡 中 |
| `PERF011` | **GS/TS 使用** | 检测几何/曲面细分着色器 | Shader Stage 检查 | 🟡 中 |
| `PERF012` | **过度 MSAA** | MSAA > 4x 且面积大 | Texture MSAA 检测 | 🟡 中 |
| `PERF013` | **MRT 带宽** | MRT 数量 > 4 | OutputMerger 检查 | 🟡 中 |
| `PERF014` | **高频 CB 更新** | 每帧 CB Map/Update 过多 | ResourceUpdateStats | 🟡 中 |
| `PERF015` | **Mipmap 缺失** | 大纹理无 Mipmap | TextureDescription.mips | 🟢 低 |
| `PERF016` | **NPOT 纹理** | 非 2 的幂纹理 | 尺寸检查 | 🟢 低 |
| `PERF017` | **空 Draw** | 0 顶点/0 实例绘制 | ActionDescription | 🟢 低 |
| `PERF018` | **VS Output 膨胀** | VS 输出属性过多 | ShaderReflection | 🟡 中 |
| `PERF019` | **Texture 采样瓶颈** | PS 内大量纹理采样 | Shader 分析 | 🔴 高 |
| `PERF020` | **RW 资源冲突** | UAV 读写依赖链 | Resource Usage 分析 | 🟡 中 |

---

## 四、报告输出结构设计

### 4.1 JSON Schema（核心结构）

```json
{
  "version": "1.0",
  "generated_at": "2025-01-22T12:00:00Z",
  "capture_info": {
    "filename": "scene.rdc",
    "api": "Vulkan",
    "frame_number": 1,
    "capture_time": "2025-01-22T10:30:00Z"
  },
  
  "summary": {
    "overall_score": 72,
    "total_draw_calls": 1200,
    "total_dispatches": 45,
    "total_triangles": 3500000,
    "total_vertices": 4200000,
    "total_textures": 860,
    "total_texture_memory_mb": 512.5,
    "total_buffer_memory_mb": 128.3,
    "gpu_frame_time_ms": 16.5,
    "issue_counts": {
      "critical": 2,
      "warning": 8,
      "info": 15
    }
  },
  
  "timing": {
    "available": true,
    "frame_total_ms": 16.5,
    "top_10_events": [
      {"event_id": 450, "name": "Draw Shadow Map", "time_ms": 2.3, "percentage": 13.9},
      ...
    ],
    "by_pass": [
      {"pass_name": "GBuffer", "time_ms": 5.2, "draw_count": 320},
      ...
    ]
  },
  
  "issues": [
    {
      "rule_id": "PERF001",
      "severity": "warning",
      "category": "overdraw",
      "title": "过度绘制",
      "message": "RenderTarget 被绘制 12 次",
      "resource_id": "RT_GBuffer0",
      "related_events": [100, 120, 145, ...],
      "actual_value": 12,
      "threshold_value": 4,
      "impact_score": 35,
      "suggestion": "考虑合并绘制调用或优化渲染顺序",
      "verification_plan": {
        "check_type": "overlay",
        "overlay_type": "quad_overdraw_pass",
        "target_event": 145
      }
    },
    ...
  ],
  
  "resource_analysis": {
    "textures": {
      "by_format": {"BC7": 120, "RGBA8": 45, "R16G16B16A16_FLOAT": 12},
      "by_size": {"<256": 200, "256-1024": 400, "1024-2048": 180, ">2048": 80},
      "compression_rate": 0.72,
      "uncompressed_large": [...],
      "no_mipmap": [...]
    },
    "buffers": {
      "vertex_buffer_total_mb": 64.2,
      "index_buffer_total_mb": 12.5,
      "constant_buffer_total_mb": 8.3,
      "structured_buffer_total_mb": 43.3
    },
    "shaders": {
      "total_count": 180,
      "unique_vs": 45,
      "unique_ps": 120,
      "unique_cs": 15,
      "change_count": 420,
      "redundant_sets": 85
    }
  },
  
  "pass_analysis": [
    {
      "pass_id": 1,
      "name": "Shadow Map",
      "event_range": [10, 150],
      "draw_count": 140,
      "time_ms": 2.3,
      "render_targets": ["RT_ShadowMap"],
      "avg_triangle_per_draw": 8500,
      "issues": ["PERF003"]
    },
    ...
  ],
  
  "recommendations": [
    {
      "priority": "high",
      "rule": "PERF008",
      "title": "GPU 热点优化",
      "detail": "Event #450 (Shadow Map) 占用 13.9% 帧时间",
      "action": "检查阴影贴图分辨率，考虑使用级联阴影或采样优化",
      "impact": "预计减少 1-2ms 帧时间"
    },
    ...
  ]
}
```

### 4.2 HTML 报告页面设计

```
┌──────────────────────────────────────────────────────────────┐
│  📊 Performance Analysis Report                               │
│  capture.rdc | Vulkan | 2025-01-22                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Score Gauge: 72/100]                                       │
│                                                              │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Draw Calls  │  Triangles  │  Textures   │  GPU Time   │  │
│  │    1,200    │    3.5M     │    860      │   16.5ms    │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  ⚠️ Issues (2 Critical, 8 Warning, 15 Info)                   │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ 🔴 PERF001: Overdraw on RT_GBuffer0                      ││
│  │    • 12 draws to same render target (threshold: 4)       ││
│  │    • Related Events: #100, #120, #145...                 ││
│  │    [Verify in RenderDoc] [View Details]                  ││
│  │──────────────────────────────────────────────────────────││
│  │ 🟡 PERF003: Small Batches Detected                       ││
│  │    • 85 draws with <100 vertices                         ││
│  │    • Consider instancing or batching                     ││
│  │    [View Affected Draws]                                 ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  ⏱️ GPU Timing Analysis                                       │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ [Timeline Bar: Shadow | GBuffer | Lighting | Post ]      ││
│  │                                                          ││
│  │ Top 5 Hotspots:                                          ││
│  │ 1. Draw Shadow Map (#450)     2.3ms  ███████████ 13.9%   ││
│  │ 2. GBuffer Fill (#680)        1.8ms  █████████   10.9%   ││
│  │ 3. SSAO Compute (#1050)       1.2ms  ██████       7.3%   ││
│  │ 4. Lighting Pass (#1100)      1.1ms  █████        6.7%   ││
│  │ 5. Bloom (#1250)              0.9ms  ████         5.5%   ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  📦 Resource Analysis                                        │
│  ┌─────────────────────┐  ┌─────────────────────┐           │
│  │ Texture Formats     │  │ Buffer Usage        │           │
│  │ [Pie Chart]         │  │ [Bar Chart]         │           │
│  │ BC7: 72%            │  │ VB: 64MB            │           │
│  │ RGBA8: 15%          │  │ IB: 12MB            │           │
│  │ Float: 13%          │  │ CB: 8MB             │           │
│  └─────────────────────┘  └─────────────────────┘           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  📝 Recommendations                                          │
│  1. [HIGH] Optimize Shadow Map rendering - save ~2ms        │
│  2. [MED]  Batch small draw calls - reduce 85 → 15 draws    │
│  3. [MED]  Compress 12 large uncompressed textures          │
│  4. [LOW]  Add mipmaps to 8 large textures                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 五、实现路线图

### Phase 1: 基础分析（无硬件依赖）✅ 已完成

- [x] Draw/Dispatch 统计
- [x] 纹理/缓冲区资源分析
- [x] Pipeline State 状态检测
- [x] PERF001-007 规则实现

### Phase 2: GPU 计时集成 🔄 进行中

- [ ] 集成 `EventGPUDuration` 计数器
- [ ] 实现 PERF008 (GPU 热点) 规则
- [ ] 生成时间线可视化数据
- [ ] 按 Pass 汇总时间

### Phase 3: Overlay 数据集成

- [ ] 实现 Quad Overdraw 数据提取
- [ ] 实现 Triangle Size 分析
- [ ] 集成到报告中

### Phase 4: 厂商计数器支持

- [ ] AMD GPA 集成
- [ ] NVIDIA Nsight Perf SDK 集成
- [ ] ARM Mali HWCPipe 集成

### Phase 5: AI 增强分析

- [ ] Shader 复杂度分析
- [ ] 自动优化建议生成
- [ ] 与对比报告集成

---

## 六、附录

### A. 参考资源

- [RenderDoc 官方文档](https://renderdoc.org/docs/)
- [Python API: Performance Counters](https://renderdoc.org/docs/python_api/renderdoc/counters.html)
- [Python API: Frame Statistics](https://renderdoc.org/docs/python_api/renderdoc/frame_stats.html)
- [Texture Viewer Overlays](https://renderdoc.org/docs/window/texture_viewer.html)
- [Performance Counter Viewer](https://renderdoc.org/docs/window/performance_counter_viewer.html)

### B. 现有代码路径

| 组件 | 路径 |
|------|------|
| 性能分析器 | `scripts/rdc_analyzer/analyzers/performance_analyzer.py` |
| 性能规则定义 | `scripts/rdc_analyzer/core/types.py` (`PERFORMANCE_RULES`) |
| GPU 计数器枚举 | `renderdoc/api/replay/replay_enums.h` (`GPUCounter`) |
| 帧统计结构 | `renderdoc/api/replay/data_types.h` (`FrameStatistics`) |
| Vulkan 计数器 | `renderdoc/driver/vulkan/vk_replay.h` (`EnumerateCounters`) |

### C. RenderDoc 官方性能分析工具对标（GUI 能力，记录用）

> 目的：作为“GUI 内 Analyzer Report 的对标清单”，后续逐项补齐/融合。

- **Performance Counter Viewer（GPU 硬件计数器采样）**  
  采样每个事件的 GPU counters；用于定量瓶颈定位。  
  参考：`docs/offline_reference/docs/window/performance_counter_viewer.html`
- **Event Browser - Timing actions（GPU 动作计时）**  
  可显示每个 action 的 GPU duration（可快速定位热点）。  
  参考：`docs/offline_reference/docs/window/event_browser.html`
- **Timeline Bar（全帧时间轴 + 资源使用分布）**  
  全帧鸟瞰 + 选中资源在帧内的读/写分布；用于快速定位与依赖理解。  
  参考：`docs/offline_reference/docs/window/timeline_bar.html`
- **Pixel History（逐像素历史）**  
  追踪单像素所有修改事件；用于发现过度绘制与遮挡路径。  
  参考：`docs/offline_reference/docs/how/how_inspect_pixel.html`
- **Statistics Viewer（统计报告）**  
  Draw/Dispatch/绑定/光栅/输出等统计分区；用于宏观结构诊断。  
  参考：`qrenderdoc/Windows/StatisticsViewer.cpp`
- **RGP 集成（AMD Radeon GPU Profiler）**  
  从 RenderDoc 捕获生成 RGP profile，并可互选事件。  
  参考：`docs/offline_reference/docs/how/how_rgp_profile.html`

> 设计落点：GUI 内 Analyzer Report 应优先覆盖 **计时、计数器、事件热点、资源使用** 四类快速定位能力。

### D. Analyzer Report 当前可分析项（代码快照）

> 目的：明确“当前可输出的数据边界”，避免 GUI/HTML 展示过度承诺。

- **性能规则（PERF001~PERF007）**：过度绘制（启发式）、状态冗余、小批次绘制、大纹理、未压缩纹理、Alpha 混合过度、频繁绑定。  
  参考：`scripts/rdc_analyzer/analyzers/performance_analyzer.py`
- **PerformanceReport 指标**：  
  总 draw/dispatch/triangles/vertices、状态变更统计、资源统计、overall_score、recommendations 等。  
  参考：`scripts/rdc_analyzer/core/types.py`
- **主报告输出字段**：  
  `overall_score / issues / metrics / recommendations` 写入 performance_report。  
  参考：`scripts/rdc_analyzer/main.py`
- **FrameSummary（帧级统计）**：  
  draw/dispatch/vertex/primitive、pass/RT 切换、shader/blend/depth/rasterizer 变化、资源内存、viewport 等。  
  参考：`scripts/rdc_analyzer/core/types.py`
- **Mali Shader 性能分析（可选）**：  
  依赖 `malioc` 时输出 Mali 报告（指令周期/寄存器等）。  
  参考：`scripts/rdc_analyzer/main.py`, `docs/analysis/codex_rdc_analyzer/README.md`

> 备注：GUI 内 Analyzer Report 用于“快速定位”，HTML 报告用于“导出/对比”。两者共享同一事实来源与规则输出。

---

**文档状态**: 草案，待评审

**下一步**: 用户确认优先级后，开始 Phase 2 实现
