# RDC Analyzer 规则文档

> 自动生成于 2026-01-24 16:25:50，共 **36 条** 规则

**数据来源**: rules/*.py + config/thresholds.py

## 目录

- [Buffer 规则](#buffer-规则-6-条)
- [Draw Call 规则](#draw-call-规则-5-条)
- [Mobile 规则](#mobile-规则-6-条)
- [Pass 规则](#pass-规则-7-条)
- [State 规则](#state-规则-6-条)
- [Texture 规则](#texture-规则-6-条)

---

## Buffer 规则 (6 条)

### RD_BUF_001: Large Buffer
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测单个 Buffer 内存占用过大
- **阈值**:
  - max_buffer_size_mb: PC=64.0, Mobile=16.0

### RD_BUF_002: Dynamic Buffer Update
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测频繁更新的动态 Buffer
- **阈值**:
  - max_buffer_updates: 10

### RD_BUF_003: Constant Buffer Packing
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测 Constant Buffer 是否高效打包
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_BUF_004: Index Buffer Format
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测 Index Buffer 是否使用最优格式
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_BUF_005: Vertex Buffer Layout
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测顶点属性是否过度使用
- **阈值**:
  - max_vertex_stride: 64

### RD_BUF_006: Unused Buffer
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测创建但未使用的 Buffer
- **阈值**: 规则内部固定条件（无配置阈值）

---

## Draw Call 规则 (5 条)

### RD_DC_001: Draw Call Count
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测每帧 Draw Call 数量是否超过阈值
- **阈值**:
  - draw_call_count: PC=3000, Mobile=500

### RD_DC_002: Low Poly Draw Call
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测顶点数过少的 Draw Call，建议合批
- **阈值**:
  - min_vertices_per_draw: PC=100, Mobile=50

### RD_DC_003: Non-Instanced Draw
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测重复绘制相同网格但未使用 Instancing
- **阈值**:
  - instancing_threshold: 50

### RD_DC_004: Empty Draw Call
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测顶点数为 0 的无效 Draw Call
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_DC_005: High Vertex Count
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测单次 Draw Call 顶点数过多
- **阈值**:
  - max_vertices_per_draw: 100000

---

## Mobile 规则 (6 条)

### RD_MOBILE_001: TBDR Flush
- **严重程度**: warning
- **平台**: mobile
- **描述**: 检测可能导致 Tile 提前 Flush 的操作
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_MOBILE_002: Mobile Overdraw
- **严重程度**: warning
- **平台**: mobile
- **描述**: 检测移动端严重的过度绘制
- **阈值**:
  - mobile_max_overdraw: 3.0

### RD_MOBILE_003: Mobile Precision
- **严重程度**: info
- **平台**: mobile
- **描述**: 检测移动端是否合理使用 half/float16
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_MOBILE_004: Mobile Bandwidth
- **严重程度**: warning
- **平台**: mobile
- **描述**: 检测移动端带宽敏感操作
- **阈值**:
  - mobile_texture_size: 1024

### RD_MOBILE_005: Alpha Test Usage
- **严重程度**: info
- **平台**: mobile
- **描述**: 检测 Alpha Test/Clip 对 TBDR 的影响
- **阈值**:
  - mobile_max_alpha_test: 50

### RD_MOBILE_006: Load Store Action
- **严重程度**: warning
- **平台**: mobile
- **描述**: 检测是否正确使用 Load/Store Action
- **阈值**: 规则内部固定条件（无配置阈值）

---

## Pass 规则 (7 条)

### RD_PASS_001: Pass Count
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测渲染 Pass 数量是否过多
- **阈值**:
  - max_pass_count: PC=30, Mobile=15

### RD_PASS_002: RT Switch
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测 Render Target 切换次数过多
- **阈值**:
  - max_rt_switches: PC=50, Mobile=20

### RD_PASS_003: Empty Pass
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测没有 Draw Call 的空 Pass
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_PASS_004: Fullscreen Pass
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测重复的全屏 Pass (可能可以合并)
- **阈值**:
  - max_fullscreen_passes: PC=10, Mobile=5

### RD_PASS_005: Clear Optimization
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测不必要的 Clear 操作
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_PASS_006: Depth PrePass
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测复杂场景是否使用 Depth PrePass
- **阈值**:
  - depth_prepass_threshold: 500

### RD_PASS_007: Shadow Map
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测 Shadow Map 的尺寸和更新频率
- **阈值**:
  - max_shadowmap_size: 4096

---

## State 规则 (6 条)

### RD_STATE_001: Excessive State Changes
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测渲染状态切换次数过多
- **阈值**:
  - max_shader_changes: PC=500, Mobile=200
  - max_blend_changes: 100
  - max_depth_changes: 200
  - max_rasterizer_changes: 200

### RD_STATE_002: Shader Thrashing
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测频繁切换相同 Shader 组合
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_STATE_003: Redundant State
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测设置相同状态的冗余调用
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_STATE_004: Scissor Test Usage
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测 UI 绘制未启用 Scissor Test
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_STATE_005: Depth Test Issues
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测不当的深度测试配置
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_STATE_006: Alpha Blend Overdraw
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测过多的透明混合绘制
- **阈值**:
  - max_blend_draws: 200

---

## Texture 规则 (6 条)

### RD_TEX_001: Large Texture
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测超过 2048x2048 的大纹理
- **阈值**:
  - max_texture_size: 2048

### RD_TEX_002: Texture Memory
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测单张纹理内存占用过大
- **阈值**:
  - max_texture_memory_mb: PC=16.0, Mobile=4.0

### RD_TEX_003: Missing Mipmap
- **严重程度**: warning
- **平台**: 全平台
- **描述**: 检测 256+ 纹理缺少 Mipmap
- **阈值**:
  - mipmap_required_size: PC=256, Mobile=128

### RD_TEX_004: Uncompressed Texture
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测使用未压缩格式的大纹理
- **阈值**:
  - compression_required_size: 512

### RD_TEX_005: NPOT Texture
- **严重程度**: info
- **平台**: mobile
- **描述**: 检测非2次幂尺寸的纹理
- **阈值**: 规则内部固定条件（无配置阈值）

### RD_TEX_006: Texture Array Candidate
- **严重程度**: info
- **平台**: 全平台
- **描述**: 检测相同尺寸格式的纹理，建议使用 Texture Array
- **阈值**:
  - texture_array_threshold: 8

---

## 规则配置

阈值内置于 `scripts/rdc_analyzer/config/thresholds.py`。

示例（仅展示部分键，实际以源码为准）：
```python
DEFAULT_THRESHOLDS = {
  "max_draw_calls": 3000,
  "large_texture_threshold_mb": 16.0,
  "max_pass_count": 30,
}
MOBILE_THRESHOLDS = {
  **DEFAULT_THRESHOLDS,
  "max_draw_calls": 500,
  "large_texture_threshold_mb": 4.0,
  "max_pass_count": 15,
}
```

*Generated by rdc_analyzer script*