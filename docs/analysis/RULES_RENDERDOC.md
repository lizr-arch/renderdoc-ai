# RenderDoc 可实现规则

> **版本**: 1.1 | **更新日期**: 2025-01-16
>
> **说明**: 本文档是规则的**权威定义来源**，列出可通过 RenderDoc 截帧数据和 Python API 直接检测的优化规则。
> 
> **文档职责**:
> - `RULES_RENDERDOC.md` (本文档): 定义所有规则、阈值、检测逻辑
> - `RDC_ANALYSIS_SPEC.md`: 定义输出数据格式，引用本文档的规则 ID
> - `rdc_analyzer.py`: 实现本文档定义的规则

---

## 规则 ID 索引

| 规则 ID | 简称 | 类别 | 平台阈值 |
|---------|------|------|----------|
| `RD_DC_001` | HIGH_DRAW_CALL_COUNT | Draw Call | PC>2000, Mobile>200 |
| `RD_DC_002` | FREQUENT_STATE_SWITCH | Draw Call | >80% DC 伴随切换 |
| `RD_DC_003` | UNBATCHED_SAME_MATERIAL | Draw Call | 连续>3 次 |
| `RD_DC_004` | INSTANCING_CANDIDATE | Draw Call | >10 次重复 |
| `RD_DC_005` | EMPTY_DRAW_CALL | Draw Call | 存在即警告 |
| `RD_TEX_001` | LARGE_UNCOMPRESSED_TEXTURE | 纹理 | PC>1024, Mobile>512 |
| `RD_TEX_002` | NON_POT_TEXTURE | 纹理 | 存在即警告 |
| `RD_TEX_003` | NO_MIPMAP | 纹理 | >512 且 mips==1 |
| `RD_TEX_004` | HUGE_TEXTURE | 纹理 | >4096x4096 |
| `RD_TEX_005` | HIGH_TEXTURE_MEMORY | 纹理 | PC>1GB, Mobile>256MB |
| `RD_TEX_006` | DUPLICATE_TEXTURE | 纹理 | 存在即警告 |
| `RD_VERT_001` | HIGH_VERTEX_COUNT | 顶点 | PC>2M, Mobile>100K |
| `RD_VERT_002` | LARGE_SINGLE_DRAW | 顶点 | >65535 |
| `RD_VERT_003` | HIGHPOLY_LOD_ISSUE | 顶点 | 远距离>5000 |
| `RD_VERT_004` | INEFFICIENT_INDEX_FORMAT | 顶点 | 32-bit 非必要 |
| `RD_RT_001` | FREQUENT_RT_SWITCH | RT | PC>15, Mobile>8 |
| `RD_RT_002` | UNUSED_RT | RT | 存在即警告 |
| `RD_RT_003` | OVERSIZED_RT | RT | >2x 屏幕 |
| `RD_RT_004` | MULTIPLE_RT_CLEAR | RT | >2次/帧 |
| `RD_SHADER_001` | FREQUENT_SHADER_SWITCH | Shader | 每 DC 切换 |
| `RD_SHADER_002` | HIGH_SAMPLER_COUNT | Shader | >8 per Pass |
| `RD_SHADER_003` | LARGE_CB | Shader | >64KB |
| `RD_SHADER_004` | UNUSED_CB_SLOT | Shader | 存在即警告 |
| `RD_BUF_001` | HIGH_BUFFER_MEMORY | Buffer | >500MB |
| `RD_BUF_002` | LARGE_DYNAMIC_BUFFER | Buffer | Dynamic>1MB |
| `RD_BUF_003` | UNUSED_BUFFER | Buffer | 存在即警告 |
| `RD_STATE_001` | DEPTH_WRITE_WITH_BLEND | 状态 | 存在即警告 |
| `RD_STATE_002` | BACKFACE_CULL_OFF | 状态 | 非必要时警告 |
| `RD_STATE_003` | SCISSOR_UNUSED | 状态 | UI 场景 |
| `RD_STATE_004` | WIREFRAME_MODE | 状态 | 存在即警告 |
| `RD_OD_001` | HIGH_TRANSPARENT_RATIO | Overdraw | >30% |
| `RD_OD_002` | TRANSPARENT_UNSORTED | Overdraw | 未排序 |
| `RD_OD_003` | EXCESSIVE_FULLSCREEN_PASS | Overdraw | >5 次 |

---

## 一、数据来源分类

RenderDoc 可提供以下数据：

| 数据类型 | 获取方式 | 说明 |
|----------|----------|------|
| **Draw Call 列表** | `controller.GetRootActions()` | 包含所有绘制/调度命令 |
| **纹理信息** | `controller.GetTextures()` | 格式、尺寸、Mip 级别 |
| **Buffer 信息** | `controller.GetBuffers()` | 大小、用途 |
| **Pipeline State** | `controller.GetPipelineState()` | 当前渲染状态快照 |
| **Shader 反射** | `controller.GetShader()` | 输入/输出、常量缓冲区 |
| **顶点数据** | `controller.GetPostVSData()` | 变换后顶点 |
| **事件 Timing** | `controller.GetDrawcallTimes()` (需 GPU Counter) | GPU 耗时 |

---

## 二、可实现规则列表

### 2.1 Draw Call / 批处理

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_DC_001` | Draw Call 总数过多 | 统计 `ActionFlags.Drawcall` 数量 | PC>2000, Mobile>200 | 🔴 高 |
| `RD_DC_002` | 状态切换频繁 | 检测相邻 Draw 的 Pipeline State 变化 | 每 DC 都切换 | 🟠 中 |
| `RD_DC_003` | 相同材质未合批 | 连续 Draw 使用相同 Shader+纹理 | 连续>3 次 | 🟠 中 |
| `RD_DC_004` | GPU Instancing 候选 | 相同 Mesh + 相同 Shader 重复出现 | >10 次 | 🟡 低 |
| `RD_DC_005` | 空 Draw Call | 顶点数=0 或索引数=0 | 存在即警告 | 🟠 中 |

**实现示例**:
```python
def check_dc_count(controller):
    actions = controller.GetRootActions()
    draw_count = sum(1 for a in actions if a.flags & rd.ActionFlags.Drawcall)
    if draw_count > 2000:
        return Issue("RD_DC_001", f"Draw Call 数量过多: {draw_count}")
```

---

### 2.2 纹理资源

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_TEX_001` | 未压缩纹理 | 检查 `format` 是否为 RGBA32/BGRA32 | 尺寸>256x256 | 🔴 高 |
| `RD_TEX_002` | 纹理尺寸非 2^n | 检查 width/height 是否为 2 的幂 | 存在即警告 | 🟠 中 |
| `RD_TEX_003` | 大纹理无 Mipmap | 尺寸>512 且 `mips==1` | 存在即警告 | 🟠 中 |
| `RD_TEX_004` | 超大纹理 | 单张纹理 >4096x4096 | 存在即警告 | 🟠 中 |
| `RD_TEX_005` | 纹理总显存占用 | 累加所有纹理 `byteSize` | PC>1GB, Mobile>256MB | 🔴 高 |
| `RD_TEX_006` | 冗余纹理 | 相同尺寸+格式+内容哈希 | 存在即警告 | 🟡 低 |

**实现示例**:
```python
def check_uncompressed_textures(controller):
    issues = []
    for tex in controller.GetTextures():
        if tex.format.type == rd.ResourceFormatType.Regular:
            if tex.format.compByteWidth == 4 and tex.format.compCount == 4:
                if tex.width > 256 or tex.height > 256:
                    issues.append(Issue("RD_TEX_001", 
                        f"未压缩大纹理: {tex.name} ({tex.width}x{tex.height})"))
    return issues
```

---

### 2.3 顶点/几何

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_VERT_001` | 单帧顶点数过多 | 累加所有 Draw 的顶点数 | PC>2M, Mobile>100K | 🔴 高 |
| `RD_VERT_002` | 单次 Draw 顶点数过多 | 检查每个 Draw 的 `numIndices` | >65535 | 🟠 中 |
| `RD_VERT_003` | 高模远距离渲染 | 顶点数>5000 但 BoundingBox 距相机远 | 需结合距离 | 🟡 低 |
| `RD_VERT_004` | 索引缓冲使用 32-bit | 顶点数<65535 但用 32-bit 索引 | 存在即警告 | 🟡 低 |

**实现示例**:
```python
def check_total_vertices(controller):
    total = 0
    for action in flatten_actions(controller.GetRootActions()):
        if action.flags & rd.ActionFlags.Drawcall:
            total += action.numIndices  # 或 numVerts
    if total > 2_000_000:
        return Issue("RD_VERT_001", f"单帧顶点数过多: {total:,}")
```

---

### 2.4 渲染目标 / Pass 结构

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_RT_001` | RT 切换过于频繁 | 统计 `OMSetRenderTargets` 调用 | >10次/帧 | 🟠 中 |
| `RD_RT_002` | 未使用的 RT | 创建了 RT 但从未绑定 | 存在即警告 | 🟡 低 |
| `RD_RT_003` | RT 尺寸过大 | RT 尺寸 > 屏幕分辨率 2x | 存在即警告 | 🟠 中 |
| `RD_RT_004` | 过多 RT Clear | 同一 RT 被 Clear 多次 | >2次/帧 | 🟡 低 |

---

### 2.5 Shader 相关

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_SHADER_001` | Shader 切换频繁 | 相邻 Draw 使用不同 Shader | 每 DC 切换 | 🟠 中 |
| `RD_SHADER_002` | 纹理采样器数量 | 检查绑定的纹理槽数 | 单 Pass >8 | 🟠 中 |
| `RD_SHADER_003` | 常量缓冲区过大 | CB 大小 > 64KB | 存在即警告 | 🟡 低 |
| `RD_SHADER_004` | 未使用的 CB Slot | 绑定了 CB 但 Shader 未引用 | 存在即警告 | 🟡 低 |

**注意**: Shader 源码分析（如 `discard`、动态分支）需要反编译 DXBC/SPIRV，属于进阶功能。

---

### 2.6 Buffer 资源

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_BUF_001` | Buffer 总显存占用 | 累加所有 Buffer `byteSize` | >500MB | 🟠 中 |
| `RD_BUF_002` | 大型动态 Buffer | Buffer 标记为 Dynamic 且 >1MB | 存在即警告 | 🟠 中 |
| `RD_BUF_003` | 未使用的 Buffer | 创建了但从未绑定 | 存在即警告 | 🟡 低 |

---

### 2.7 渲染状态

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_STATE_001` | Depth Write + Alpha Blend | 同时开启 DepthWrite 和 AlphaBlend | 存在即警告 | 🟠 中 |
| `RD_STATE_002` | 背面剔除关闭 | CullMode = None | 非必要时警告 | 🟡 低 |
| `RD_STATE_003` | Scissor 未启用 | UI 元素未使用 Scissor 裁剪 | 可选检测 | 🟡 低 |
| `RD_STATE_004` | 线框模式 | FillMode = Wireframe (发布版) | 存在即警告 | 🔴 高 |

---

### 2.8 Overdraw 分析

| 规则ID | 规则名称 | 检测逻辑 | 阈值 | 优先级 |
|--------|----------|----------|------|--------|
| `RD_OD_001` | 透明物体数量 | 统计 AlphaBlend 开启的 Draw | >30% | 🟠 中 |
| `RD_OD_002` | 透明物体渲染顺序 | 检查是否按后→前排序 | 未排序 | 🟠 中 |
| `RD_OD_003` | 全屏后处理过多 | 统计全屏 Quad Draw | >5 次 | 🟠 中 |

**注意**: 精确 Overdraw 统计需使用 RenderDoc 的 Overlay 功能或像素历史。

---

## 三、API 参考

### 3.1 核心类

```python
import renderdoc as rd

# 打开 RDC 文件
cap = rd.OpenCaptureFile()
cap.OpenFile("capture.rdc", "", None)
controller = cap.OpenCapture(rd.ReplayOptions(), None)

# 遍历 Actions
def flatten_actions(actions, out=None):
    if out is None:
        out = []
    for a in actions:
        out.append(a)
        flatten_actions(a.children, out)
    return out

# 获取纹理列表
textures = controller.GetTextures()

# 获取 Pipeline State (需先 SetFrameEvent)
controller.SetFrameEvent(event_id, False)
state = controller.GetPipelineState()
```

### 3.2 常用属性

| 对象 | 属性 | 说明 |
|------|------|------|
| `ActionDescription` | `eventId`, `flags`, `numIndices`, `numInstances` | 绘制信息 |
| `TextureDescription` | `name`, `width`, `height`, `format`, `mips`, `byteSize` | 纹理元数据 |
| `BufferDescription` | `name`, `length`, `creationFlags` | Buffer 元数据 |
| `PipeState` | `GetShader()`, `GetBindpointMapping()` | 渲染状态 |

---

## 四、实现优先级

| 阶段 | 规则范围 | 预计工作量 |
|------|----------|------------|
| **Phase 1** | `RD_DC_001~005`, `RD_TEX_001~005`, `RD_VERT_001~002` | 2-3 天 |
| **Phase 2** | `RD_RT_001~004`, `RD_SHADER_001~002`, `RD_STATE_001~004` | 3-4 天 |
| **Phase 3** | `RD_OD_*`, `RD_BUF_*`, 进阶分析 | 1 周 |

---

## 五、限制说明

以下功能在 RenderDoc 中**无法直接实现**，需要外部工具：

1. **GPU 硬件计数器** (SM/TEX/L2 利用率) → 需 NVIDIA Nsight / AMD RGP
2. **Shader 源码分析** (discard/动态分支) → 需 DXBC/SPIRV 反编译器
3. **CPU 侧性能** (Draw Call 提交耗时) → 需 PIX / Superluminal
4. **运行时 Profiling** (帧间变化) → 需引擎内 Profiler
5. **TBDR 特定分析** (Tile 利用率) → 需 Mali Offline Compiler / PowerVR Tools

详见 `RULES_EXTERNAL.md`。
