# Pipeline State 功能调研报告

> **日期**: 2025-07-24  
> **调研目标**: 分析 RenderDoc 和业界图形调试工具的 Pipeline State 功能，为我们的 RDC 分析工具提供改进方向

---

## 1. RenderDoc Pipeline State 功能分析

### 1.1 Tab 页面结构

通过分析 `qrenderdoc/Windows/PipelineState/D3D11PipelineStateViewer.ui`，RenderDoc 将 D3D11 Pipeline State 分为以下 9 个 Tab：

| Tab 名称 | 对应阶段 | 我们当前支持 |
|---------|---------|-------------|
| **Input Assembly** | 顶点输入/索引缓冲 | ⚠️ 部分 (仅 Topology) |
| **Vertex Shader** | 顶点着色器 | ✅ ResourceId |
| **Hull Shader** | 曲面细分控制 | ✅ ResourceId |
| **Domain Shader** | 曲面细分求值 | ✅ ResourceId |
| **Geometry Shader** | 几何着色器 | ✅ ResourceId |
| **Rasterizer** | 光栅化配置 | ⚠️ 部分 (仅 Viewport) |
| **Pixel Shader** | 像素着色器 | ✅ ResourceId |
| **Output Merger** | 输出合并/混合 | ⚠️ 部分 (Blend/Depth) |
| **Compute Shader** | 计算着色器 | ✅ ResourceId |

### 1.2 各阶段详细数据 (from `d3d11_pipestate.h`)

#### 1.2.1 Input Assembly (`D3D11Pipe::InputAssembly`)
```cpp
rdcarray<Layout> layouts;          // 顶点布局描述
rdcarray<VertexBuffer> vertexBuffers;  // VB 绑定
IndexBuffer indexBuffer;           // IB 绑定
Topology topology;                 // 图元拓扑
```

**我们缺失的数据**:
- [ ] Vertex Layout 详情 (semantic name/index, format, slot)
- [ ] Vertex Buffer 绑定信息 (resourceId, stride, offset)
- [ ] Index Buffer 绑定信息

#### 1.2.2 Shader Stages (`D3D11Pipe::Shader`)
```cpp
ResourceId resourceId;             // Shader ID
ShaderReflection *reflection;      // Shader 反射信息
ShaderStage stage;                 // 阶段类型
rdcarray<rdcstr> classInstances;   // 类实例 (D3D11 特有)
```

**我们缺失的数据**:
- [ ] Shader Resources (SRV) 绑定列表
- [ ] Samplers 绑定列表
- [ ] Constant Buffers (CBV) 绑定列表
- [ ] Shader 反射信息 (入参、出参、资源绑定)

#### 1.2.3 Rasterizer (`D3D11Pipe::Rasterizer`)
```cpp
rdcarray<Viewport> viewports;      // 视口列表
rdcarray<Scissor> scissors;        // 裁剪区域
RasterizerState state;             // 光栅化状态
```

**RasterizerState 字段**:
- `FillMode fillMode` (Solid/Wireframe)
- `CullMode cullMode` (None/Front/Back)
- `bool frontCCW` (逆时针正面)
- `int32_t depthBias`
- `float depthBiasClamp`
- `float slopeScaledDepthBias`
- `bool depthClip`
- `bool scissorEnable`
- `bool multisampleEnable`
- `bool antialiasedLines`
- `uint32_t forcedSampleCount`
- `ConservativeRaster conservativeRasterization`

**我们缺失的数据**:
- [ ] FillMode (Wireframe/Solid)
- [ ] CullMode (Front/Back/None)
- [ ] DepthBias 相关参数
- [ ] Scissor 区域
- [ ] MSAA 相关设置

#### 1.2.4 Output Merger (`D3D11Pipe::OutputMerger`)

**DepthStencilState**:
```cpp
bool depthEnable;
CompareFunction depthFunction;
bool depthWrites;
bool stencilEnable;
StencilFace frontFace;   // Stencil 操作
StencilFace backFace;
```

**BlendState**:
```cpp
bool alphaToCoverage;
bool independentBlend;
rdcarray<ColorBlend> blends;  // 每个 RT 的混合配置
float blendFactor[4];
uint32_t sampleMask;
```

**我们缺失的数据**:
- [ ] Stencil 正面/背面操作详情
- [ ] 每个 RenderTarget 的独立混合配置
- [ ] BlendFactor 常量
- [ ] SampleMask
- [ ] RenderTarget 绑定列表
- [ ] DepthStencil Target 绑定

---

## 2. 业界其他工具功能对比

### 2.1 Microsoft PIX

**主要功能**:
- GPU Capture: 完整的 GPU 状态捕获
- Timing Capture: CPU/GPU 时序分析
- TDR 调试: GPU Hang 问题诊断
- 内存分析: Heap 驻留和分页分析

**Pipeline State 特色**:
- 完整的 D3D12 管线状态查看
- 资源绑定的可视化树形结构
- Shader 反汇编/源码查看
- 像素历史追踪 (Pixel History)

### 2.2 NVIDIA Nsight Graphics

**主要功能**:
- 硬件级性能分析
- Ray Tracing Inspector (光追优化)
- Shader Profiler (着色器热点分析)
- C++ Capture Export (独立重放项目)

**Pipeline State 特色**:
- GPU 吞吐量/利用率分析
- 缓存命中率、内存带宽统计
- 加速结构 (BVH) 可视化
- 着色器时序热力图

### 2.3 Intel GPA (Graphics Performance Analyzers)

**主要功能**:
- 帧分析和回放
- 多平台支持 (Intel/AMD/NVIDIA)
- 系统级性能监控

---

## 3. 我们工具当前状态 vs 目标

### 3.1 已实现功能 ✅

| 功能 | 状态 | 备注 |
|------|------|------|
| Shader ID 提取 | ✅ | VS/PS/GS/HS/DS |
| Viewport 提取 | ✅ | X/Y/W/H/MinZ/MaxZ |
| Blend State 提取 | ✅ | SrcBlend/DestBlend/BlendOp |
| DepthStencil State 提取 | ✅ | DepthEnable/DepthFunc |
| Topology 提取 | ✅ | TriangleList 等 |

### 3.2 缺失功能 (按优先级排序)

#### P0 - 高优先级 (核心调试功能)

| 功能 | 用户场景 | 实现难度 |
|------|---------|---------|
| **Shader Resources (SRV)** | 查看纹理/缓冲绑定 | 中 |
| **Constant Buffers (CBV)** | 查看 Shader 常量 | 中 |
| **RenderTarget 绑定** | 确认输出目标 | 低 |
| **DepthStencil Target** | 深度缓冲绑定 | 低 |

#### P1 - 中优先级 (完善调试体验)

| 功能 | 用户场景 | 实现难度 |
|------|---------|---------|
| **Sampler 状态** | 纹理采样配置 | 中 |
| **Vertex Layout** | 确认顶点格式 | 中 |
| **Vertex/Index Buffer** | VB/IB 绑定信息 | 中 |
| **Stencil 详细操作** | 模板测试调试 | 低 |
| **Scissor 区域** | 裁剪区域配置 | 低 |

#### P2 - 低优先级 (进阶功能)

| 功能 | 用户场景 | 实现难度 |
|------|---------|---------|
| **Rasterizer FillMode/CullMode** | 线框/剔除模式 | 需解析 CreateRasterizerState |
| **UAV 绑定** | 读写资源绑定 | 中 |
| **Stream Output** | SO 阶段绑定 | 低 |
| **独立 RT Blend** | 多目标混合 | 高 |

---

## 4. 改进建议

### 4.1 短期改进 (1-2 周)

1. **完善 Output Merger 数据**
   - 解析 `OMSetRenderTargets` 获取 RTV 列表
   - 解析 `OMSetDepthStencilState` 的 StencilRef 参数

2. **添加 Shader 资源绑定**
   - 解析 `*SSetShaderResources` (VS/PS/GS/HS/DS/CS)
   - 解析 `*SSetConstantBuffers`
   - 解析 `*SSetSamplers`

3. **完善 Rasterizer 数据**
   - 添加 CreateRasterizerState 解析，获取 FillMode/CullMode
   - 解析 `RSSetScissorRects`

### 4.2 中期改进 (1-2 月)

1. **Input Assembler 完整支持**
   - 解析 `IASetVertexBuffers`
   - 解析 `IASetIndexBuffer`
   - 解析 `CreateInputLayout` 获取 Vertex Layout

2. **HTML 报告 UI 优化**
   - 参考 RenderDoc 的 Tab 式布局
   - 每个 Pipeline 阶段独立展示
   - 添加资源引用链接

3. **资源预览**
   - Texture 缩略图生成
   - Buffer 内容十六进制查看

### 4.3 长期愿景

1. **Shader 源码/反汇编查看**
2. **像素历史追踪 (Pixel History)**
3. **性能热点标记**
4. **资源依赖图可视化**

---

## 5. 技术实现建议

### 5.1 需要新增解析的 D3D11 Chunk 类型

```python
# 高优先级
"ID3D11DeviceContext::PSSetShaderResources"
"ID3D11DeviceContext::PSSetConstantBuffers"
"ID3D11DeviceContext::PSSetSamplers"
"ID3D11DeviceContext::VSSetShaderResources"
"ID3D11DeviceContext::VSSetConstantBuffers"
"ID3D11DeviceContext::VSSetSamplers"
"ID3D11DeviceContext::OMSetRenderTargets"
"ID3D11DeviceContext::RSSetScissorRects"

# 中优先级
"ID3D11DeviceContext::IASetVertexBuffers"
"ID3D11DeviceContext::IASetIndexBuffer"
"ID3D11Device::CreateInputLayout"
"ID3D11Device::CreateRasterizerState"
```

### 5.2 数据结构扩展建议

```python
# pipeline_state 扩展结构
{
    "shaders": {
        "VS": {"resourceId": "...", "resources": [], "cbuffers": [], "samplers": []},
        "PS": {"resourceId": "...", "resources": [], "cbuffers": [], "samplers": []},
        # ...
    },
    "inputAssembler": {
        "topology": "...",
        "vertexBuffers": [{"slot": 0, "resourceId": "...", "stride": 32, "offset": 0}],
        "indexBuffer": {"resourceId": "...", "format": "R32_UINT", "offset": 0},
        "layout": [{"semantic": "POSITION", "format": "R32G32B32_FLOAT", "slot": 0}]
    },
    "rasterizer": {
        "viewports": [...],
        "scissors": [...],
        "fillMode": "Solid",
        "cullMode": "Back",
        "depthClip": True
    },
    "outputMerger": {
        "renderTargets": [{"slot": 0, "resourceId": "..."}],
        "depthStencilTarget": {"resourceId": "..."},
        "blendState": {...},
        "depthStencilState": {...}
    }
}
```

---

## 6. 结论

我们的工具已经实现了 Pipeline State 的核心功能（Shader ID、Viewport、Blend/Depth State），但与 RenderDoc 相比仍有较大差距。

**最有价值的改进方向**：
1. **Shader 资源绑定** - 用户最常用的调试功能
2. **RenderTarget 绑定** - 确认输出目标
3. **完整 Rasterizer 状态** - FillMode/CullMode 对于渲染调试很重要

这些改进可以让我们的 HTML 报告从"基础信息展示"提升到"实用调试工具"的水平。
