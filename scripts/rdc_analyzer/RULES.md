# RDC Analyzer 性能规则文档

> 自动生成于 rdc_analyzer 包，共 **36 条** 规则

## 目录

- [Draw Call 规则](#draw-call-规则-5-条)
- [Texture 规则](#texture-规则-6-条)
- [Buffer 规则](#buffer-规则-6-条)
- [Pass 规则](#pass-规则-7-条)
- [State 规则](#state-规则-6-条)
- [Mobile 规则](#mobile-规则-6-条)

---

## Draw Call 规则 (5 条)

### RD_DC_001: Draw Call Count
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测每帧 Draw Call 数量是否超过阈值
- **阈值**: 
  - PC: 3000
  - Mobile: 500
- **建议**: 使用 GPU Instancing、合批、LOD 减少 Draw Call

### RD_DC_002: Low Poly Draw Call
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测顶点数过少的 Draw Call，建议合批
- **阈值**:
  - PC: 顶点数 < 100
  - Mobile: 顶点数 < 50
- **建议**: 合并小型网格，使用 Static/Dynamic Batching

### RD_DC_003: Non-Instanced Draw
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测重复绘制相同网格但未使用 Instancing
- **阈值**: 相同网格绘制 >= 50 次
- **建议**: 启用 GPU Instancing

### RD_DC_004: Empty Draw Call
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测顶点数为 0 的无效 Draw Call
- **建议**: 检查 frustum culling 或网格生成逻辑

### RD_DC_005: High Vertex Count
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测单次 Draw Call 顶点数过多
- **阈值**: 顶点数 > 100,000
- **建议**: 考虑网格分割或 LOD

---

## Texture 规则 (6 条)

### RD_TEX_001: Large Texture
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测超过 2048x2048 的大纹理
- **阈值**: 2048x2048
- **建议**: 使用 Mipmap、纹理流式加载或降低分辨率

### RD_TEX_002: Texture Memory
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测单张纹理内存占用过大
- **阈值**:
  - PC: 16 MB
  - Mobile: 4 MB
- **建议**: 使用压缩格式 (BC/ASTC/ETC)

### RD_TEX_003: Missing Mipmap
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测 256+ 尺寸的纹理缺少 Mipmap
- **阈值**:
  - PC: 纹理尺寸 >= 256
  - Mobile: 纹理尺寸 >= 128
- **建议**: 为非 UI 纹理生成 Mipmap

### RD_TEX_004: Uncompressed Texture
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测使用未压缩格式的大纹理
- **阈值**: 512x512 以上
- **建议**: 使用 BC7/BC1 (PC) 或 ASTC/ETC2 (Mobile)

### RD_TEX_005: NPOT Texture
- **严重程度**: ℹ️ INFO
- **平台**: Mobile
- **描述**: 检测非 2 次幂尺寸的纹理
- **建议**: 调整为 2 次幂尺寸以优化采样性能

### RD_TEX_006: Texture Array Candidate
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测相同尺寸格式的纹理，建议使用 Texture Array
- **阈值**: >= 8 张相同规格纹理
- **建议**: 使用 Texture2DArray 减少绑定切换

---

## Buffer 规则 (6 条)

### RD_BUF_001: Large Buffer
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测单个 Buffer 内存占用过大
- **阈值**:
  - PC: 64 MB
  - Mobile: 16 MB
- **建议**: 考虑数据分块或流式加载

### RD_BUF_002: Dynamic Buffer Update
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测频繁更新的动态 Buffer
- **阈值**: 每帧更新 > 10 次
- **建议**: 使用 Ring Buffer 或 Persistent Mapping

### RD_BUF_003: Constant Buffer Packing
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测 Constant Buffer 是否高效打包
- **阈值**: 小于 64B 的 Constant Buffer > 20 个
- **建议**: 合并小型 CB，按 16 字节对齐打包

### RD_BUF_004: Index Buffer Format
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测 Index Buffer 是否使用最优格式
- **建议**: 顶点数 <= 65535 时使用 16-bit 索引

### RD_BUF_005: Vertex Buffer Layout
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测顶点属性是否过度使用
- **阈值**: stride > 64 字节
- **建议**: 分离动态/静态属性，使用半精度

### RD_BUF_006: Unused Buffer
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测创建但未使用的 Buffer
- **阈值**: 未使用 Buffer > 10 个
- **建议**: 清理未使用的资源

---

## Pass 规则 (7 条)

### RD_PASS_001: Pass Count
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测渲染 Pass 数量是否过多
- **阈值**:
  - PC: 30
  - Mobile: 15
- **建议**: 合并相似 Pass，使用 MRT

### RD_PASS_002: RT Switch
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测 Render Target 切换次数过多
- **阈值**:
  - PC: 50
  - Mobile: 20
- **建议**: 重排绘制顺序，合并输出

### RD_PASS_003: Empty Pass
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测没有 Draw Call 的空 Pass
- **建议**: 移除无效 Pass

### RD_PASS_004: Fullscreen Pass
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测重复的全屏 Pass (可能可以合并)
- **阈值**:
  - PC: 全屏 Pass > 10
  - Mobile: 全屏 Pass > 5
- **建议**: 合并后处理 Pass，使用 Compute Shader

### RD_PASS_005: Clear Optimization
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测不必要的 Clear 操作
- **阈值**: 连续 Clear 同一目标 > 5 次
- **建议**: 如果后续完全覆盖则跳过 Clear

### RD_PASS_006: Depth PrePass
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测复杂场景是否使用 Depth PrePass
- **阈值**: Draw Call > 500 且无 Depth PrePass
- **建议**: 添加 Depth PrePass 减少 overdraw

### RD_PASS_007: Shadow Map
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测 Shadow Map 的尺寸和更新频率
- **阈值**: > 4096x4096
- **建议**: 使用级联阴影、缓存静态阴影

---

## State 规则 (6 条)

### RD_STATE_001: Excessive State Changes
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测渲染状态切换次数过多
- **阈值**:
  - Shader 切换 > 500 (PC) / 200 (Mobile)
  - Blend 状态切换 > 100
  - Depth 状态切换 > 200
  - Rasterizer 状态切换 > 200
- **建议**: 按材质排序，使用状态缓存

### RD_STATE_002: Shader Thrashing
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测频繁切换相同 Shader 组合
- **阈值**: 相同组合切换 > 50 次
- **建议**: 按 Shader 分组绘制

### RD_STATE_003: Redundant State
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测设置相同状态的冗余调用
- **阈值**: 冗余状态设置 > 100 次
- **建议**: 使用状态追踪避免重复设置

### RD_STATE_004: Scissor Test Usage
- **严重程度**: ℹ️ INFO
- **平台**: 全平台
- **描述**: 检测 UI 绘制未启用 Scissor Test
- **建议**: 为 UI 裁剪启用 Scissor

### RD_STATE_005: Depth Test Issues
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测不当的深度测试配置
- **场景**: 
  - 不透明物体关闭深度写入
  - Early-Z 失效 (PS 中 discard 或修改深度)
- **阈值**: 非 UI 绘制中禁用深度测试占比 > 30%
- **建议**: 分离不透明/透明物体管线

### RD_STATE_006: Alpha Blend Overdraw
- **严重程度**: ⚠️ WARNING
- **平台**: 全平台
- **描述**: 检测过多的透明混合绘制
- **阈值**: 透明混合 Draw Call > 200
- **建议**: 使用 Alpha Test 替代，从后向前排序

---

## Mobile 规则 (6 条)

### RD_MOBILE_001: TBDR Flush
- **严重程度**: ⚠️ WARNING
- **平台**: Mobile
- **描述**: 检测可能导致 Tile 提前 Flush 的操作
- **触发条件**: 
  - 读取当前 RT
  - 在 Pass 中间切换 RT
  - 使用 UAV 读写同一资源
- **建议**: 重组渲染顺序，避免中途读回

### RD_MOBILE_002: Mobile Overdraw
- **严重程度**: ⚠️ WARNING
- **平台**: Mobile
- **描述**: 检测移动端严重的过度绘制
- **阈值**: 平均每像素绘制 > 3.0 次
- **建议**: 启用 Depth PrePass，优化粒子

### RD_MOBILE_003: Mobile Precision
- **严重程度**: ℹ️ INFO
- **平台**: Mobile
- **描述**: 检测移动端是否合理使用 half/float16
- **场景**: 
  - Shader 中全用 float 而非 half
  - RT 使用 R32G32B32A32_FLOAT
- **建议**: 尽可能使用 half 精度

### RD_MOBILE_004: Mobile Bandwidth
- **严重程度**: ⚠️ WARNING
- **平台**: Mobile
- **描述**: 检测移动端带宽敏感操作
- **阈值**:
  - 大纹理尺寸 > 1024
  - 大纹理数量 > 20
- **建议**: 降低 RT 分辨率，使用 ASTC 压缩

### RD_MOBILE_005: Alpha Test Usage
- **严重程度**: ℹ️ INFO
- **平台**: Mobile
- **描述**: 检测 Alpha Test/Clip 对 TBDR 的影响
- **阈值**: Alpha Test Draw > 50
- **说明**: Alpha Test 会破坏 Early-Z 优化
- **建议**: 分离不透明/Alpha Test 绘制

### RD_MOBILE_006: Load Store Action
- **严重程度**: ⚠️ WARNING
- **平台**: Mobile
- **描述**: 检测是否正确使用 Load/Store Action
- **场景**: 
  - Clear 后立即 Load (应 DontCare)
  - 临时 RT 未设置 DontCare Store
- **建议**: 优化 Load/Store Action 减少带宽

---

## 规则配置

当前阈值内置于 `scripts/rdc_analyzer/config/thresholds.py`。

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

## 命令行使用

```bash
# 列出所有规则
python -m rdc_analyzer --list-rules

# 分析 RDC 文件 (PC 模式)
python -m rdc_analyzer capture.rdc

# 分析 RDC 文件 (Mobile 模式)
python -m rdc_analyzer capture.rdc --platform mobile

# 二进制模式 (无需 RenderDoc)
python -m rdc_analyzer capture.rdc --binary
```

---

*Generated by rdc_analyzer v1.0*
