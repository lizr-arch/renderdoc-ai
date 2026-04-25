# 05_TASK_ENGINE_HOOKS — 任务 3：接入引擎 RenderGraph / Draw / Resource Hooks

目标：把 EAP core types 接到真实引擎路径，让 RenderDoc capture 中出现引擎语义 annotation，并让 sidecar sink 能收到 frame/pass/draw/resource 数据。

---

## 1. 输入文档

Codex 本轮必须读取：

- `02_EAP_PROTOCOL_SPEC.md`
- `03_TASK_RENDERDOC_BRIDGE.md`
- `04_TASK_EAP_CORE_TYPES.md`
- `Docs/EAP/EAP_IMPLEMENTATION_MAP.md`
- 本文件

---

## 2. 本轮范围

本轮允许修改：

- render graph pass 执行入口；
- draw/dispatch submit 入口；
- resource creation / debug name 入口；
- shader/material/mesh metadata extraction helper；
- RHI backend adapter。

本轮不做：

- 完整 sidecar 文件写入；
- UI；
- MCP；
- 网络上传；
- qrenderdoc 修改。

---

## 3. 接入策略

按优先级：

1. **已有 debug marker 封装层**：如果引擎已有 `BeginEvent/EndEvent/SetDebugName`，优先在这里接 EAP。
2. **RenderGraph pass execute**：每个 pass push/pop `PassContext`。
3. **Draw packet / render item 提交**：写 `DrawContext`。
4. **Resource debug name 设置**：写 `ResourceContext` object annotation。
5. **后端 native handle adapter**：只做 handle 转换，不写业务字段。

---

## 4. RenderGraph Pass Hook

### 4.1 目标

每个 pass 执行时创建 `PassContext`：

```cpp
eap::PassContext pass;
pass.passId = BuildPassId(renderGraphNode);
pass.nodeId = BuildRenderGraphNodeId(renderGraphNode);
pass.name = GetPassDebugName(renderGraphNode);
pass.category = InferPassCategory(renderGraphNode);
pass.queue = GetQueueName(renderGraphNode);
pass.viewId = CurrentViewId();
eap::ScopedPass eapPass(pass);
```

### 4.2 放置位置

推荐放在：

```cpp
RenderGraph::ExecutePass(Pass& pass, CommandContext& cmd)
```

或：

```cpp
RHICommandList::BeginEvent(passName)
```

如果两个都有，优先 RenderGraph 层，因为这里有更多语义。

### 4.3 同时写普通 debug marker

不要替代已有 GPU marker。EAP 是附加层。

```cpp
GPU_MARKER_SCOPE(cmd, pass.name.c_str());
eap::ScopedPass eapPass(passContext);
```

### 4.4 Pass category 推断

如果引擎没有 category，首版用名称规则：

| 名称包含 | category |
|---|---|
| shadow | `shadow` |
| depth | `depth` |
| base | `base_pass` |
| gbuffer | `gbuffer` |
| light | `lighting` |
| post | `postprocess` |
| ui / slate / imgui | `ui` |
| compute | `compute` |
| copy / blit | `copy_blit` |
| else | `unknown` |

---

## 5. Draw / Dispatch Hook

### 5.1 目标

在 draw/dispatch 调用前写 command annotation：

```cpp
const eap::FrameContext* frame = eap::EAPRuntime::Get().CurrentFrame();
const eap::PassContext* pass = eap::EAPRuntime::Get().CurrentPass();
if (frame && pass) {
  eap::DrawContext draw = BuildDrawContextFromRenderItem(renderItem, pipelineState);
  auto handles = backendAdapter.GetHandles(commandContext, renderItem);
  eap::EAPRuntime::Get().Writer().WriteDrawCommandAnnotations(
      handles.device,
      handles.command,
      *frame,
      *pass,
      draw);
  eap::EAPRuntime::Get().NotifyCommand(*pass, draw);
}
```

### 5.2 DrawContext 来源

| 字段 | 优先来源 |
|---|---|
| kind | RHI draw function name |
| reason | render item type / pass category / mesh batch type |
| material id/name/path | material proxy / material instance / asset registry |
| mesh id/name/path/lod | mesh batch / geometry proxy / asset registry |
| shader hashes | bound shader objects / shader map / shader bytecode hash |
| permutation hash/key | shader permutation object / material shader map |
| pso hash | pipeline cache key / pipeline desc hash |
| counts | draw arguments |
| resources_read/write | descriptor bindings / render graph pass inputs/outputs，首版可 sidecar-only |

### 5.3 只在有语义数据的层接一次

不要在 D3D12、Vulkan、OpenGL backend 每个 API draw 处重复采集 material/mesh，因为那时语义经常丢失。

正确位置通常是：

```text
MeshDrawCommand / DrawPacket / RenderItem / MaterialBatch submit
```

后端 API draw 处只负责：

- 提供 native command handle；
- 作为兜底写 `cmd.kind` / draw counts。

---

## 6. Dispatch Hook

Compute dispatch 写：

```cpp
eap::DrawContext ctx;
ctx.kind = "dispatch";
ctx.reason = InferComputeReason(passName, computeShaderName);
ctx.shaderCsHash = GetShaderHash(computeShader);
ctx.permutationHash = GetPermutationHash(computeShader);
ctx.psoHash = GetPipelineHash(computePipeline);
ctx.dispatchX = groupsX;
ctx.dispatchY = groupsY;
ctx.dispatchZ = groupsZ;
```

Dispatch 必填：

- `eap.cmd.kind = dispatch`
- `eap.pass.name`
- `eap.shader.cs.hash`
- `eap.pso.hash`
- `eap.dispatch.group_x/y/z`

---

## 7. Resource Hook

### 7.1 目标

Texture / buffer 创建后，拿到 native handle 时写 object annotation：

```cpp
eap::ResourceContext res = BuildResourceContext(textureDesc, assetInfo, ownerSystem);
void* device = backendAdapter.GetRenderDocDeviceHandle();
void* object = backendAdapter.GetRenderDocObjectHandle(texture);
eap::EAPRuntime::Get().Writer().WriteResourceObjectAnnotations(device, object, res);
eap::EAPRuntime::Get().NotifyResource(res);
```

### 7.2 推荐接入点

优先顺序：

1. resource debug name 设置函数；
2. texture/buffer 创建函数返回 native handle 后；
3. asset streaming 创建 GPU resource 处；
4. render graph transient resource 创建处。

### 7.3 资源分类

| 引擎资源 | `resource.kind` |
|---|---|
| 2D texture | `texture2d` |
| cube texture | `texturecube` |
| texture array | `texture2d_array` |
| 3D texture | `texture3d` |
| vertex/index/structured/constant buffer | `buffer` |
| render target | `render_target` 或 `texture2d` + usage |
| depth target | `depth_stencil` |
| acceleration structure | `accel_struct` |
| swapchain backbuffer | `swapchain_backbuffer` |

### 7.4 Streaming 信息

如果纹理 streaming 数据可用，写：

- resident mip；
- wanted mip；
- budget group；
- priority。

不可用就跳过，不要写 `0`。

---

## 8. Backend Adapter

### 8.1 通用接口

```cpp
class IRenderDocBackendAdapter {
public:
  virtual ~IRenderDocBackendAdapter() = default;
  virtual void* GetDeviceHandle() const = 0;
  virtual void* GetCommandHandle(void* commandContext) const = 0;
  virtual void* GetObjectHandle(void* resource) const = 0;
};
```

### 8.2 D3D12 预期

- device：`ID3D12Device*`
- command：`ID3D12GraphicsCommandList*` 或引擎当前 command list
- object：`ID3D12Resource*` / `ID3D12PipelineState*`

### 8.3 D3D11 预期

- device：`ID3D11Device*`
- command：通常可用 immediate/deferred context，按 RenderDoc 识别要求适配；
- object：`ID3D11Resource*` / shader / state object。

### 8.4 Vulkan 预期

- device：`VkDevice` 对应 RenderDoc device pointer；
- command：`VkCommandBuffer` 或 queue/command buffer；
- object：`VkImage` / `VkBuffer` / `VkPipeline` 等。

注意：Vulkan handle 与 `void*` 转换必须遵循当前 RenderDoc API 要求和引擎已有 debug utils 实现。不要盲目 reinterpret_cast 所有 handle。Codex 应优先复用已有 RenderDoc/debug utils handle 包装。

### 8.5 OpenGL 预期

OpenGL object annotation 需要 `RENDERDOC_GLResourceReference`。如果首版不支持 GL object annotation，可以：

- command annotation 仍写；
- resource object annotation 对 GL 后端 no-op；
- 在 diagnostics 中记录 `gl_object_annotation_not_implemented`。

---

## 9. Frame lifecycle

在 frame begin：

```cpp
eap::FrameContext frame = BuildFrameContext();
eap::EAPRuntime::Get().BeginFrame(frame);
```

在 frame end：

```cpp
eap::EAPRuntime::Get().EndFrame();
```

FrameContext 至少写：

- frame index；
- project name；
- branch / commit / build id，如可用；
- map/world；
- camera，如可用。

如果仓库已有 profiler frame hooks，优先接那里。

---

## 10. Capture-only 优化

默认不应每帧每 draw 都写 RenderDoc API。策略：

```text
r.EAP.OnlyWhenCapturing = 1
```

如果 `RenderDocBridge::IsCapturing()` 不可靠，使用轻量开关：

```text
r.EAP.ForceWriteAnnotations = 1
```

用于调试。默认关闭。

Sidecar 收集也建议只在：

- RenderDoc 正在 capture；或
- 用户开启 `r.EAP.RecordLastFrame`；或
- QA 一键上报模式。

---

## 11. 失败兜底

如果某路径拿不到 material/shader/mesh：

- 仍写 pass/cmd；
- sidecar diagnostics 记录缺失；
- 不阻断 draw。

示例：

```json
"diagnostics": {
  "missing_fields": [
    { "command": "draw:8251", "field": "material.path", "reason": "not available in this submit path" }
  ]
}
```

---

## 12. 本轮最小验收

用 mock 或真实渲染场景：

1. 编译通过。
2. EAP 开关关闭时，没有任何行为变化。
3. EAP 开关打开但无 RenderDoc 时，不崩溃。
4. RenderGraph pass 执行时 push/pop 正常。
5. draw hook 能构建 `DrawContext`。
6. resource hook 能构建 `ResourceContext`。
7. 如果 RenderDoc 可用，抓帧后至少能在一个 draw 上看到：
   - `eap.pass.name`
   - `eap.cmd.kind`
   - `eap.material.name` 或 `eap.material.id`
   - `eap.shader.*.hash` 或 `eap.pso.hash`
8. 至少一个 texture object 能看到：
   - `eap.resource.kind`
   - `eap.resource.format`
   - `eap.resource.width/height`
   - `eap.asset.path` 或 `eap.asset.id`

---

## 13. Codex 禁止事项

- 不要为了拿语义重构整个 renderer。
- 不要在每个 backend 复制粘贴完整业务 extraction。
- 不要把 full material parameter dump 写进 annotation。
- 不要在 render hot path 做大量字符串拼接；优先用已有 debug strings 或 capture-only。
- 不要在 shipping build 默认启用。
- 不要引入网络逻辑。

---

## 14. 本轮完成输出

Codex 最终输出：

1. 接入点列表；
2. 新增/修改文件；
3. 每个字段来自哪里；
4. 当前缺失字段；
5. 性能风险；
6. 手动抓帧验证步骤；
7. 下一轮进入 `06_TASK_SIDECAR_WRITER.md`。

