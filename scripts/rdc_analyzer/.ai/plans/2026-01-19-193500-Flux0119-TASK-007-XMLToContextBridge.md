# TASK-007: XMLToContextBridge 实现计划

> **任务 ID**: TASK-007
> **优先级**: P0
> **创建时间**: 2026-01-19 19:35
> **Agent**: Flux-0119
> **阶段**: /spec 完成 → 待 /plan

---

## Scope (范围)

创建 `XMLToContextBridge` 模块，将 `parse_rdc_xml.py` 的输出 dict 转换为 `AnalysisContext`，使 `PerformanceAnalyzer` 能够直接使用 XML 解析结果。

---

## Assumptions (假设)

1. `parse_rdc_xml.py` 输出格式稳定，字段名不会频繁变化
2. `PerformanceAnalyzer` 已支持 dict 和 dataclass 两种输入格式
3. 不需要完整填充所有 `AnalysisContext` 字段，只需填充 `PerformanceAnalyzer` 使用的字段

---

## /spec 阶段分析结果

### 1. 数据流

```
parse_rdc_xml.py        XMLToContextBridge         PerformanceAnalyzer
       │                        │                          │
       ▼                        │                          │
  dict {                        │                          │
    apiType,                    │                          │
    events,          ────────►  AnalysisContext  ────────► analyze()
    textures,                   │                          │
    buffers,                    │                          ▼
    statistics                  │                   PerformanceReport
  }                             │
```

### 2. 字段映射表

#### 2.1 根级字段

| XML Dict | ParsedData | 说明 |
|----------|------------|------|
| `apiType` | `api` | D3D11/D3D12/Vulkan/OpenGL |
| `events` | `draws` | 过滤 type="draw" 的事件 |
| `events` | `dispatches` | 过滤 type="dispatch" 的事件 |
| `textures` | `textures` | 直接映射 |
| `buffers` | `buffers` | 直接映射 |
| `statistics.totalEvents` | `total_events` | 直接映射 |

#### 2.2 Event → DrawCallInfo 映射

| Event 字段 | DrawCallInfo 字段 | 转换规则 |
|------------|-------------------|----------|
| `eventId` | `event_id` | 直接 |
| `type` | `type` | 直接 ("draw" / "dispatch") |
| `params[*Count]` | `index_count`, `vertex_count`, `instance_count` | 解析 params 列表 |
| `pipelineState.vs.resourceId` | `vs_id` | 从嵌套结构提取 |
| `pipelineState.ps.resourceId` | `ps_id` | 从嵌套结构提取 |
| `pipelineState.blendState.enabled` | `blend_enabled` | 布尔转换 |
| `pipelineState.depthState.writeEnabled` | `depth_write` | 布尔转换 |
| `resourceBindings.rtvs[*].resourceId` | `rt_ids` | 列表映射 |

#### 2.3 Texture 字段映射

| XML Texture | TextureInfo | 转换规则 |
|-------------|-------------|----------|
| `resourceId` | `resource_id` | 直接 |
| `name` | `name` | 直接 |
| `width`, `height`, `depth` | 同名 | 直接 (int) |
| `format` | `format` | 直接 (str) |
| `memorySize` | `memory_size` | 直接 (int) |
| `mipLevels` | `mip_levels` | 直接 (int) |
| - | `is_render_target` | 从 usage 推断 |
| - | `is_depth_stencil` | 从 format 推断 |

#### 2.4 Statistics → FrameSummary 映射

| XML Statistics | FrameSummary | 转换规则 |
|----------------|--------------|----------|
| `totalDrawCalls` | `draw_call_count` | 直接 |
| `totalDispatches` | `dispatch_count` | 直接 |
| `totalTextures` | `texture_count` | 直接 |
| `totalBuffers` | `buffer_count` | 直接 |
| `totalTextureMemory` | `total_texture_memory` | 直接 |

### 3. PerformanceAnalyzer 数据需求

分析 `performance_analyzer.py` 后，确认需要的字段：

| 方法 | 访问的字段 | 必需 |
|------|-----------|------|
| `_collect_statistics()` | `result.draws`, `result.textures`, `result.buffers`, `result.shaders` | ✅ |
| `_check_overdraw()` | `result.draws[*].rt_ids`, `result.draws[*].event_id` | ✅ |
| `_check_state_redundancy()` | `result.draws[*].vs_id`, `result.draws[*].ps_id`, `result.draws[*].blend_enabled` | ✅ |
| `_check_small_batches()` | `result.draws[*].vertex_count`, `result.draws[*].index_count` | ✅ |
| `_check_large_textures()` | `result.textures[*].width`, `result.textures[*].height`, `result.textures[*].memory_size` | ✅ |
| `_check_uncompressed_textures()` | `result.textures[*].format`, `result.textures[*].is_render_target` | ✅ |
| `_check_alpha_blend_usage()` | `result.draws[*].blend_enabled` | ✅ |
| `_check_frequent_binding()` | `result.draws[*].bound_textures` | ⚠️ (可选) |

---

## /plan 阶段

### Task Checklist

- [ ] **Step 1**: 创建 `core/bridge.py` 文件，定义 `XMLToContextBridge` 类
- [ ] **Step 2**: 实现 `_convert_events()` 方法 (Event → DrawCallInfo dict)
- [ ] **Step 3**: 实现 `_convert_textures()` 方法 (Texture → TextureInfo dict)
- [ ] **Step 4**: 实现 `_convert_statistics()` 方法 (Statistics → FrameSummary)
- [ ] **Step 5**: 实现 `convert()` 主入口方法
- [ ] **Step 6**: 添加单元测试验证转换正确性
- [ ] **Step 7**: 集成测试 - 连通 XML 解析 → Bridge → PerformanceAnalyzer

### Impact Analysis

| 影响范围 | 说明 |
|----------|------|
| 新增文件 | `core/bridge.py` |
| 修改文件 | 无 (Bridge 为独立模块) |
| 依赖变更 | 无 |
| API 变更 | 新增 `XMLToContextBridge.convert()` |

### Risks / Blockers

| 风险 | 缓解措施 |
|------|----------|
| XML 字段名不一致 (camelCase vs snake_case) | 转换时处理两种命名 |
| 部分字段缺失 (如 Shader 未完整解析) | 使用默认值，不阻塞分析 |
| PerformanceAnalyzer 未测试 dict 输入 | 先用 dict 跑一轮，确认兼容 |

### Verification / Acceptance

**Definition of Done**:
1. `XMLToContextBridge.convert(xml_data)` 返回有效的 `AnalysisContext`
2. `PerformanceAnalyzer(context).analyze()` 执行成功
3. `context.performance_report` 包含有效的问题列表
4. 单元测试覆盖核心转换逻辑

**验证命令** (由用户执行):
```bash
cd scripts/rdc_analyzer
py -3 -m pytest tests/test_bridge.py -v
```

### Next Steps

1. 用户确认 `/plan` 后，进入 `/do` 阶段实现代码
2. 完成 TASK-007 后，继续 TASK-008 (集成到 HTML 报告)

---

*Created by Flux-0119 @ 2026-01-19 19:35*
