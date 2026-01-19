# RenderDoc GPU 回放架构分析

> **创建日期**: 2025-01-20  
> **目的**: 分析 RenderDoc 的 GPU 回放原理，评估命令行插件重构可行性

---

## 1. 执行摘要

| 问题 | 结论 |
|------|------|
| GPU 回放的核心原理是什么？ | **API 调用重放** — 从 RDC 文件读取序列化的 API 调用，在当前 GPU 上重新执行 |
| 是否可以做成命令行插件？ | **已经存在！** `renderdoccmd` 支持本地/远程回放，支持 Headless 模式 |
| 能否纯 CLI 导出纹理？ | **需要扩展** — 当前 CLI 支持回放预览，但缺少纹理导出命令 |

---

## 2. GPU 回放原理（架构图）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RenderDoc GPU Replay Pipeline                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐    ┌───────────────┐    ┌─────────────────┐    ┌───────────┐  │
│  │ .rdc    │───▶│ RDCFile       │───▶│ CaptureFile     │───▶│ Replay    │  │
│  │ File    │    │ (Section I/O) │    │ (ICaptureFile)  │    │ Controller│  │
│  └─────────┘    └───────────────┘    └─────────────────┘    └─────┬─────┘  │
│                                                                   │         │
│                                                                   ▼         │
│                        ┌─────────────────────────────────────────────┐      │
│                        │         RegisterReplayProvider()            │      │
│                        │  (根据 Driver Type 选择正确的 Replay 驱动)  │      │
│                        └─────────────────────────────────────────────┘      │
│                                          │                                   │
│        ┌─────────────────────────────────┼─────────────────────────────────┐ │
│        ▼                   ▼             ▼             ▼                   │ │
│  ┌───────────┐     ┌───────────┐  ┌───────────┐  ┌───────────┐            │ │
│  │ Vulkan    │     │ D3D12     │  │ D3D11     │  │ OpenGL    │  ...       │ │
│  │ Replay    │     │ Replay    │  │ Replay    │  │ Replay    │            │ │
│  │ Driver    │     │ Driver    │  │ Driver    │  │ Driver    │            │ │
│  └─────┬─────┘     └─────┬─────┘  └─────┬─────┘  └─────┬─────┘            │ │
│        │                 │              │              │                   │ │
│        └─────────────────┴──────────────┴──────────────┘                   │ │
│                                   │                                         │
│                                   ▼                                         │
│                        ┌─────────────────────┐                              │
│                        │   IReplayDriver     │  (统一接口)                  │
│                        │   - ReadLogInit     │                              │
│                        │   - CreateResources │                              │
│                        │   - ReplayLog       │                              │
│                        │   - SaveTexture     │ ◀── 导出纹理入口             │
│                        └─────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 关键组件分析

### 3.1 RDCFile (文件解析层)

**位置**: `renderdoc/serialise/rdcfile.cpp`

```cpp
// 文件打开入口
void RDCFile::Open(const rdcstr &path);    // :236

// 核心功能:
// 1. 验证文件 Magic Number
// 2. 解析 Section Index（各数据块的偏移量）
// 3. 提供流式读取 API
```

**RDC 文件结构**:
```
┌────────────────────────────────────┐
│ Magic: "RDOC" + Version            │
├────────────────────────────────────┤
│ Section 0: FrameCapture            │
│   └── Chunks (序列化的 API 调用)   │
│       └── vkCreateBuffer(...)      │
│       └── vkCmdDraw(...)           │
│       └── ...                      │
├────────────────────────────────────┤
│ Section 1: ResolveDatabase         │
│   └── 符号解析信息                 │
├────────────────────────────────────┤
│ Section N: ExtendedThumbnail       │
│   └── 预览图                       │
└────────────────────────────────────┘
```

### 3.2 ReplayController (回放控制器)

**位置**: `renderdoc/replay/replay_controller.cpp`

```cpp
// 创建设备（核心入口）
RDResult ReplayController::CreateDevice(RDCFile *rdc, const ReplayOptions &opts);  // :2167

// 关键步骤:
// 1. 读取 RDC 文件中的 DriverType
// 2. 调用 RegisterReplayProvider 获取对应驱动
// 3. 调用驱动的 CreateReplayDevice()
// 4. 执行 PostCreateInit() 初始化资源
```

**核心 API**:
| 方法 | 功能 |
|------|------|
| `GetTextures()` | 获取所有纹理描述 |
| `GetBuffers()` | 获取所有缓冲区描述 |
| `GetRootActions()` | 获取绘制调用树 |
| `SetFrameEvent(eid)` | 跳转到指定事件 |
| `SaveTexture(save, path)` | **导出纹理到文件** |

### 3.3 IReplayDriver (驱动抽象层)

**位置**: `renderdoc/api/replay/replay_driver.h`

```cpp
// 抽象接口定义
class IReplayDriver {
  virtual RDResult ReadLogInitialisation(...) = 0;  // 读取初始化数据
  virtual void ReplayLog(uint32_t eid) = 0;         // 回放到指定事件
  virtual void SaveTexture(TextureSave &save, const rdcstr &path) = 0;
  // ...
};
```

**各驱动实现**:
| 驱动 | 位置 | 入口函数 |
|------|------|----------|
| Vulkan | `renderdoc/driver/vulkan/vk_replay.cpp` | `Vulkan_CreateReplayDevice()` |
| D3D12 | `renderdoc/driver/d3d12/d3d12_replay.cpp` | `D3D12_CreateReplayDevice()` |
| D3D11 | `renderdoc/driver/d3d11/d3d11_replay.cpp` | `D3D11_CreateReplayDevice()` |
| OpenGL | `renderdoc/driver/gl/gl_replay.cpp` | `GL_CreateReplayDevice()` |

### 3.4 WrappedVulkan (以 Vulkan 为例)

**位置**: `renderdoc/driver/vulkan/wrappers/vk_device_funcs.cpp`

```cpp
// 初始化入口
RDResult WrappedVulkan::Initialise(VkInitParams &params, uint64_t sectionVersion,
                                   const ReplayOptions &opts);  // :223

// 核心流程:
// 1. 枚举本机支持的 Layers/Extensions
// 2. 与捕获时的配置对比，剔除不支持的
// 3. 创建 VkInstance（使用 RenderDoc 的 AppInfo）
// 4. 创建 VkDevice
// 5. 重建所有资源（从 RDC 的 System Chunks 读取）
```

---

## 4. 回放执行流程

```
用户操作: SetFrameEvent(eventId)
              │
              ▼
┌──────────────────────────────────────────────┐
│ ReplayController::SetFrameEvent()            │
│   └── m_Replay->ReplayLog(endEventID)        │
└──────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────┐
│ WrappedVulkan::ReplayLog()                   │
│   for each Chunk in [0, endEventID]:         │
│     └── ProcessChunk(chunk)                  │
│         └── 调用对应的 vkXxx() 真实 API      │
│             例: vkCmdDraw() → 物理 GPU 执行  │
└──────────────────────────────────────────────┘
              │
              ▼
         GPU 状态达到 eventId 时刻的快照
```

**关键洞察**: RenderDoc 的回放**不是**简单的状态恢复，而是**真正重新执行** GPU 命令。这意味着：
- ✅ 可以在不同 GPU 上回放（只要 API 兼容）
- ✅ 可以修改状态（如改变 Shader）并观察结果
- ⚠️ 需要 GPU 驱动支持（不能在无 GPU 环境运行）

---

## 5. 命令行支持现状

### 5.1 已有的 renderdoccmd 功能

**位置**: `renderdoccmd/renderdoccmd.cpp`

| 命令 | 功能 | 代码位置 |
|------|------|----------|
| `renderdoccmd replay <file>` | 本地回放 + 窗口预览 | `:620-652` |
| `renderdoccmd replay --remote` | 远程服务器回放 | `:594-617` |
| `renderdoccmd convert` | 格式转换 | `:691-744` |
| `renderdoccmd cap` | 捕获命令 | (各平台) |

**回放代码示例** (`renderdoccmd.cpp:620-642`):
```cpp
ICaptureFile *file = RENDERDOC_OpenCaptureFile();
ResultDetails res = file->OpenFile(conv(filename), "rdc", NULL);

IReplayController *renderer = NULL;
rdctie(result, renderer) = file->OpenCapture(ReplayOptions(), NULL);

if(result.OK()) {
    DisplayRendererPreview(renderer, width, height, loops);
    renderer->Shutdown();
}
```

### 5.2 Headless 支持

RenderDoc 已经支持 **Headless 回放**（无窗口）：

```cpp
// renderdoc/api/replay/renderdoc_replay.h:86-101
WindowingData CreateHeadlessWindowingData(int width = 64, int height = 64) {
    WindowingData ret;
    ret.system = WindowingSystem::Headless;
    ret.headless.width = width;
    ret.headless.height = height;
    return ret;
}
```

这意味着可以在**没有显示器**的环境中执行回放（如 CI 服务器）。

### 5.3 缺失的功能：纹理导出命令

当前 `renderdoccmd` **没有** 直接的纹理导出命令。需要扩展。

---

## 6. 命令行插件可行性评估

### 6.1 方案对比

| 方案 | 难度 | 优点 | 缺点 |
|------|------|------|------|
| **A. 扩展 renderdoccmd** | ⭐⭐ | 复用现有架构，最稳定 | 需要编译 RenderDoc |
| **B. 独立 CLI 插件** | ⭐⭐⭐⭐ | 独立分发 | 需要链接 renderdoc.dll，复杂 |
| **C. Python + pyrenderdoc** | ⭐ | 无需编译，Python 脚本 | 需要 GUI 环境加载模块 |

### 6.2 推荐方案：扩展 renderdoccmd

**实现路径**:

1. **新增 `export` 子命令**:
```cpp
// renderdoccmd/renderdoccmd.cpp
struct ExportCommand : public Command {
    virtual int Execute(...) {
        ICaptureFile *file = RENDERDOC_OpenCaptureFile();
        file->OpenFile(filename, "rdc", NULL);
        
        IReplayController *ctrl = file->OpenCapture(...);
        
        // 遍历纹理并导出
        for(auto &tex : ctrl->GetTextures()) {
            TextureSave save;
            save.resourceId = tex.resourceId;
            save.destType = FileType::PNG;
            // ...
            ctrl->SaveTexture(save, outputPath);
        }
        ctrl->Shutdown();
    }
};
```

2. **命令行接口设计**:
```bash
# 导出所有纹理
renderdoccmd export textures -f capture.rdc -o ./output_dir/

# 导出指定纹理
renderdoccmd export texture -f capture.rdc --id 0x1234 -o texture.png

# 导出到特定事件时刻
renderdoccmd export textures -f capture.rdc --event 150 -o ./output/
```

3. **预计工作量**:
   - 代码量: ~200-300 行 C++
   - 测试: 需要在 Windows/Linux 分别验证
   - 构建: 需要完整编译 RenderDoc

### 6.3 实现清单

| 步骤 | 任务 | 文件 |
|------|------|------|
| 1 | 添加 `ExportCommand` 类 | `renderdoccmd/renderdoccmd.cpp` |
| 2 | 注册到命令解析器 | `renderdoccmd/renderdoccmd.cpp` main() |
| 3 | 实现 Headless 输出窗口 | 复用 `CreateHeadlessWindowingData()` |
| 4 | 添加纹理遍历逻辑 | 调用 `GetTextures()` |
| 5 | 调用 `SaveTexture()` | 设置 `TextureSave` 参数 |
| 6 | 测试 Vulkan/D3D12 | 不同 API 的 RDC 文件 |

---

## 7. 替代方案：无 GUI 的 Python 脚本

虽然 `renderdoc` Python 模块通常需要 GUI 环境，但存在一种 **理论可行** 的方法：

### 7.1 使用 renderdoc.dll 直接加载

```python
# 需要正确的 DLL 路径和依赖
import ctypes
import sys

# 加载 RenderDoc DLL（需要在 PATH 中或指定完整路径）
sys.path.append("C:/Program Files/RenderDoc")
import renderdoc as rd

# 打开文件
cap = rd.OpenCaptureFile()
cap.OpenFile("capture.rdc", "", None)

# 获取回放控制器
status, controller = cap.OpenCapture(rd.ReplayOptions(), None)

# 导出纹理
for tex in controller.GetTextures():
    save = rd.TextureSave()
    save.resourceId = tex.resourceId
    save.destType = rd.FileType.PNG
    controller.SaveTexture(save, f"tex_{tex.resourceId}.png")
```

**限制**: 
- Windows: 需要 `renderdoc.pyd` 在 Python 路径中
- Linux: 需要正确编译的 `.so` 文件
- **GPU 驱动必须可用**（这是硬性要求）

### 7.2 Docker 容器方案

```dockerfile
# 使用带 GPU 支持的 Docker 镜像
FROM nvidia/vulkan:1.3

# 安装 RenderDoc
RUN apt-get install renderdoc

# 运行导出脚本
CMD ["renderdoccmd", "export", "textures", "-f", "/data/capture.rdc"]
```

---

## 8. 结论与建议

### 8.1 对于当前项目

| 场景 | 推荐方案 |
|------|----------|
| **临时使用/测试** | 使用 `export_textures_rdoc.py` 在 GUI 中运行 |
| **自动化流水线** | 考虑扩展 `renderdoccmd` 添加 `export` 命令 |
| **跨平台分发** | 等待官方支持或贡献 PR |

### 8.2 技术结论

1. **GPU 回放原理**: RenderDoc 通过重新执行序列化的 API 调用来回放帧，这需要真实的 GPU 和驱动支持。

2. **命令行插件可行性**: ✅ **可行**，RenderDoc 架构已经支持：
   - `IReplayDriver` 抽象层可脱离 GUI 使用
   - `Headless` 模式支持无窗口回放
   - `renderdoccmd` 已有回放基础设施
   
3. **实现难度**: ⭐⭐ 中等
   - 需要 C++ 开发能力
   - 需要能够编译 RenderDoc
   - 代码量约 200-300 行

### 8.3 下一步行动

| 优先级 | 任务 |
|--------|------|
| 🔴 高 | 使用 `export_textures_rdoc.py` 完成当前纹理导出需求 |
| 🟡 中 | 评估是否值得投入开发 `renderdoccmd export` 扩展 |
| 🟢 低 | 向 RenderDoc 官方提交 Feature Request 或 PR |

---

## 附录：关键代码引用

| 文件 | 行号 | 功能 |
|------|------|------|
| `renderdoc/serialise/rdcfile.cpp` | 236 | `RDCFile::Open()` |
| `renderdoc/replay/replay_controller.cpp` | 2167 | `CreateDevice()` |
| `renderdoc/driver/vulkan/vk_replay.cpp` | 199 | `ReadLogInitialisation()` |
| `renderdoc/driver/vulkan/wrappers/vk_device_funcs.cpp` | 223 | `Initialise()` |
| `renderdoccmd/renderdoccmd.cpp` | 620-652 | 本地回放命令 |
| `renderdoc/api/replay/renderdoc_replay.h` | 86-101 | `CreateHeadlessWindowingData()` |
