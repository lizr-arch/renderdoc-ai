# 01_REPO_RECON_AND_BOUNDARIES — 仓库侦察任务

用途：让 Codex 在真正写代码前，先理解现有引擎仓库结构。  
原则：这一轮 **只读代码，不修改代码**。

---

## 1. 任务目标

Codex 需要输出一份 `EAP_IMPLEMENTATION_MAP.md`，说明 EAP 应该接入哪里、需要改哪些文件、哪些接口已经存在、哪些需要新增。

不要直接开始写 RenderDoc bridge。先找到现有渲染路径。

---

## 2. Codex 必须回答的问题

### 2.1 构建系统

找到：

- 使用 CMake、Bazel、GN、Premake、Unreal Build Tool、xmake、SCons，还是自研 build？
- 当前 C++ 标准是什么？
- 是否已有 third-party 目录？
- 是否已有 RenderDoc header 或 integration？
- 单测框架是什么？

输出格式：

```md
## Build System
- Type:
- C++ standard:
- Test framework:
- Existing RenderDoc integration:
- Recommended module path:
```

### 2.2 渲染后端

找到：

- D3D11 / D3D12 / Vulkan / OpenGL / Metal / console 后端；
- RHI / graphics abstraction 层名称；
- device、queue、command list / command buffer 类型；
- resource handle 类型；
- debug marker 已有封装。

输出格式：

```md
## Graphics Backends
| Backend | Device type | Command type | Resource handle | Existing debug marker wrapper | File path |
|---|---|---|---|---|---|
```

### 2.3 RenderGraph / Pass 系统

找到：

- render graph 类名；
- pass 创建、执行、debug name 设置位置；
- pass category 或 flags；
- queue 类型；
- pass 输入输出资源声明位置。

输出格式：

```md
## RenderGraph Integration Points
- Pass declaration:
- Pass execution:
- Queue selection:
- Resource declaration:
- Existing pass debug names:
- Recommended EAP pass scope location:
```

### 2.4 Draw / Dispatch 提交路径

找到：

- `DrawIndexed` / `DrawInstanced` / `Dispatch` / ray tracing dispatch；
- pipeline bind；
- descriptor bind；
- material/shader/mesh 信息从哪里可拿到；
- 是否存在 draw packet / render item / mesh batch。

输出格式：

```md
## Draw Dispatch Integration Points
| Operation | Function/class | Available semantic data | Missing data | Recommended hook |
|---|---|---|---|---|
```

### 2.5 Resource 创建路径

找到：

- texture/buffer 创建函数；
- asset path / guid 到 GPU resource 的映射；
- resource debug name 设置位置；
- format/size/mip/usage 信息。

输出格式：

```md
## Resource Integration Points
| Resource kind | Creation function | Metadata available | Debug name path | Recommended EAP object annotation location |
|---|---|---|---|---|
```

### 2.6 Shader / Material / PSO

找到：

- shader object；
- shader bytecode/hash；
- permutation key；
- material asset；
- PSO hash/cache；
- debug symbols/source map 信息。

输出格式：

```md
## Shader Material Pipeline Data
- Shader hash source:
- Permutation key source:
- Material id/path source:
- PSO hash source:
- Debug symbol/source mapping:
```

### 2.7 Capture lifecycle

找到：

- 是否已有截图、profiler capture、RenderDoc capture hotkey；
- frame begin/end；
- 是否能知道 RenderDoc capture 当前正在进行；
- capture 文件输出目录。

输出格式：

```md
## Capture Lifecycle
- Frame begin/end:
- Capture trigger:
- Capture output path:
- Existing profiler hooks:
- Recommended sidecar flush point:
```

---

## 3. Codex 输出文件要求

生成或更新：

```text
Docs/EAP/EAP_IMPLEMENTATION_MAP.md
```

如果仓库没有 `Docs`，就创建：

```text
docs/eap/EAP_IMPLEMENTATION_MAP.md
```

内容必须包含：

1. 上述 7 个小节；
2. 推荐模块目录；
3. 初步文件修改清单；
4. 风险点；
5. 第一批 mock 测试方案；
6. “无需询问用户即可采用的默认选择”。

---

## 4. 禁止事项

这一轮禁止：

- 新增 C++ 代码；
- 修改 build 文件；
- 修改渲染路径；
- 引入 third-party；
- 改动 RenderDoc 源码；
- 写任何网络/上传逻辑。

---

## 5. 默认选择规则

如果仓库存在多个可能接入点，Codex 按以下规则选择：

1. 优先选择已有 debug marker 包装层。
2. 其次选择 render graph pass execute 入口。
3. draw/dispatch 级 hook 优先接在 render item / draw packet 生成或提交处，不要深入每个后端重复写业务逻辑。
4. resource annotation 优先接在 resource debug name 设置处。
5. sidecar flush 优先接在 frame end / capture end；如果无法知道 capture end，就先每帧在 debug 目录写 `last_frame.rmeta.json`。

---

## 6. Codex 完成判定

本轮完成后，应可以回答：

- EAP 模块放在哪里；
- RenderDoc bridge 如何编译进工程；
- 哪个函数可以拿到 command buffer / command list；
- 哪个函数可以拿到 texture/buffer native handle；
- 哪个地方能拿到 material、shader、mesh、PSO 信息；
- sidecar 在哪里写；
- 单测怎么跑。

