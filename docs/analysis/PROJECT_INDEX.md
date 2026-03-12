# RenderDoc 项目索引

> **目的**: 快速定位源码文件，辅助 LLM/MCP 进行 RDC 文件分析
> 
> **更新时间**: 2025-01-16

---

## 1. 顶层目录结构

```
renderdoc/                  # 项目根目录
├── renderdoc/              # 核心库源码 (librenderdoc)
├── qrenderdoc/             # Qt UI 应用
├── renderdoccmd/           # 命令行工具
├── renderdocshim/          # 注入 shim 库
├── util/                   # 构建/打包工具脚本
├── docs/                   # 文档
├── CMakeLists.txt          # CMake 主入口
└── renderdoc.sln           # Visual Studio 解决方案
```

---

## 2. 核心库 `renderdoc/` 目录详解

### 2.1 API 定义层 (`api/`)

| 路径 | 职责 |
|------|------|
| `api/app/renderdoc_app.h` | 应用程序捕获 API (嵌入式) |
| `api/replay/renderdoc_replay.h` | 回放 API 主入口 |
| `api/replay/replay_enums.h` | 枚举定义 (`SectionType`, `RDCDriver` 等) |
| `api/replay/data_types.h` | 数据结构 (`SectionProperties`, `FrameDescription`) |
| `api/replay/control_types.h` | 控制类型 (`ReplayOptions`, `TextureDisplay`) |
| `api/replay/shader_types.h` | Shader 相关类型 |
| `api/replay/*_pipestate.h` | 各 API 管线状态 (d3d11/d3d12/gl/vk) |
| `api/replay/rdcarray.h` | 自定义数组容器 |
| `api/replay/rdcstr.h` | 自定义字符串类型 |
| `api/replay/resourceid.h` | ResourceId 定义 |
| `api/replay/structured_data.h` | SDFile 结构化数据定义 |

### 2.2 序列化层 (`serialise/`) ⭐ RDC 解析核心

| 文件 | 职责 | 关键类/函数 |
|------|------|-------------|
| `rdcfile.h/.cpp` | **RDC 文件读写** | `RDCFile::Open()`, `ReadSection()`, `SectionIndex()` |
| `serialiser.h/.cpp` | 序列化模板 | `Serialiser<>`, `ReadSerialiser`, `WriteSerialiser` |
| `streamio.h/.cpp` | 流式 I/O | `StreamReader`, `StreamWriter` |
| `lz4io.h/.cpp` | LZ4 压缩 | `LZ4Compressor`, `LZ4Decompressor` |
| `zstdio.h/.cpp` | ZSTD 压缩 | `ZSTDCompressor`, `ZSTDDecompressor` |
| `codecs/chrome_json_codec.cpp` | Chrome JSON 导出 | |
| `codecs/xml_codec.cpp` | XML 导出 | |

### 2.3 回放层 (`replay/`) ⭐ 回放控制核心

| 文件 | 职责 | 关键类/函数 |
|------|------|-------------|
| `capture_file.cpp` | CaptureFile 高层封装 | `CaptureFile::OpenFile()`, `OpenCapture()` |
| `replay_controller.h/.cpp` | **回放控制器** | `ReplayController::CreateDevice()`, `GetRootActions()` |
| `replay_driver.h/.cpp` | 驱动抽象接口 | `IReplayDriver` |
| `replay_output.cpp` | 输出窗口管理 | `ReplayOutput` |
| `entry_points.cpp` | 导出函数入口 | `RENDERDOC_CreateCaptureFile()` 等 |
| `dummy_driver.h/.cpp` | 虚拟驱动 (无 GPU) | `DummyDriver` |

### 2.4 图形 API 驱动 (`driver/`)

#### D3D11 (`driver/d3d11/`)
| 文件 | 职责 |
|------|------|
| `d3d11_replay.h/.cpp` | **回放入口** `D3D11Replay::ReadLogInitialisation()` |
| `d3d11_device.h/.cpp` | 设备包装 |
| `d3d11_context.h/.cpp` | 上下文包装 |
| `d3d11_resources.h/.cpp` | 资源管理 |
| `d3d11_serialise.cpp` | 序列化 Chunk 处理 |

#### D3D12 (`driver/d3d12/`)
| 文件 | 职责 |
|------|------|
| `d3d12_replay.h/.cpp` | **回放入口** `D3D12Replay::ReadLogInitialisation()` |
| `d3d12_device.h/.cpp` | 设备包装 |
| `d3d12_command_list.h` | CommandList 包装 |
| `d3d12_resources.h/.cpp` | 资源管理 |
| `d3d12_serialise.cpp` | 序列化 Chunk 处理 |

#### Vulkan (`driver/vulkan/`)
| 文件 | 职责 |
|------|------|
| `vk_replay.h/.cpp` | **回放入口** `VulkanReplay::ReadLogInitialisation()` |
| `vk_core.h/.cpp` | 核心逻辑 |
| `vk_manager.h/.cpp` | 资源管理器 |
| `vk_info.h/.cpp` | 信息查询 |
| `vk_dispatchtables.h/.cpp` | 调度表 |

#### OpenGL (`driver/gl/`)
| 文件 | 职责 |
|------|------|
| `gl_replay.h/.cpp` | **回放入口** `GLReplay::ReadLogInitialisation()` |
| `gl_driver.h/.cpp` | 驱动核心 |
| `gl_manager.h/.cpp` | 资源管理器 |
| `gl_dispatch_table.h` | 调度表 |

#### Shader 解析 (`driver/shaders/`)
| 子目录 | 职责 |
|--------|------|
| `dxbc/` | DXBC (D3D11 shader bytecode) 解析 |
| `dxil/` | DXIL (D3D12 shader IL) 解析 |
| `spirv/` | SPIR-V (Vulkan/GL) 解析 |

### 2.5 核心基础设施 (`core/`)

| 文件 | 职责 |
|------|------|
| `core.h/.cpp` | 全局单例 `RenderDoc` |
| `resource_manager.h/.cpp` | 资源管理抽象基类 |
| `replay_proxy.h/.cpp` | 远程回放代理 |
| `remote_server.h/.cpp` | 远程服务器 |
| `settings.h/.cpp` | 配置管理 |
| `plugins.h/.cpp` | 插件系统 |

### 2.6 公共工具 (`common/`, `maths/`, `strings/`)

| 目录 | 职责 |
|------|------|
| `common/` | 基础类型、线程、DDS 读写 |
| `maths/` | 矩阵、向量、格式转换 |
| `strings/` | 字符串工具、grisu2 浮点转换 |

### 2.7 平台抽象 (`os/`)

| 文件 | 职责 |
|------|------|
| `os_specific.h` | 平台抽象接口 |
| `win32/` | Windows 实现 |
| `posix/` | Linux/macOS 实现 |

---

## 3. Qt UI `qrenderdoc/` 目录详解

### 3.1 核心代码 (`Code/`)

| 文件 | 职责 |
|------|------|
| `CaptureContext.h/.cpp` | **UI 上下文管理器** |
| `ReplayManager.h/.cpp` | 回放管理器 (多线程) |
| `QRDUtils.h/.cpp` | Qt 工具函数 |
| `BufferFormatter.cpp` | 缓冲区格式化 |

### 3.2 Python 接口 (`Code/pyrenderdoc/`) ⭐ Python API

| 文件 | 职责 |
|------|------|
| `renderdoc.i` | **SWIG 主接口文件** |
| `qrenderdoc.i` | Qt 扩展接口 |
| `PythonContext.h/.cpp` | Python 执行上下文 |
| `container_handling.i` | 容器类型转换 |
| `pyconversion.h/.i` | Python 类型转换 |

### 3.3 窗口 (`Windows/`)

| 文件 | 职责 |
|------|------|
| `MainWindow.h/.cpp` | 主窗口 |
| `TextureViewer.h/.cpp` | 纹理查看器 |
| `BufferViewer.h/.cpp` | 缓冲区查看器 |
| `EventBrowser.h/.cpp` | 事件浏览器 |
| `PythonShell.h/.cpp` | Python 控制台 |
| `ShaderViewer.h/.cpp` | Shader 查看器 |
| `PipelineState/` | 管线状态查看器 |

---

## 4. 关键数据结构速查

### 4.1 RDC 文件相关

```cpp
// renderdoc/serialise/rdcfile.h
class RDCFile {
  void Open(const rdcstr &filename);     // 打开文件
  int SectionIndex(SectionType type);    // 查找 Section
  StreamReader *ReadSection(int index);  // 读取 Section
  RDCDriver GetDriver();                 // 获取驱动类型
  const RDCThumb &GetThumbnail();        // 获取缩略图
};

// renderdoc/api/replay/replay_enums.h
enum class SectionType : uint32_t {
  Unknown = 0,
  FrameCapture,        // 主数据 (API 调用 + 资源)
  ResolveDatabase,     // 符号解析数据库
  Bookmarks,           // 书签
  Notes,               // 注释
  ResourceRenames,     // 资源重命名
  AMDRGPProfile,       // AMD RGP 配置
  ExtendedThumbnail,   // 扩展缩略图
  EmbeddedLogfile,     // 嵌入日志
  EditedShaders,       // 编辑过的 Shader
  D3D12Core,           // D3D12 核心 DLL
  D3D12SDKLayers,      // D3D12 SDK 层
  EmbeddedExternalFiles, // 嵌入外部文件
};

// renderdoc/api/replay/replay_enums.h
enum class RDCDriver : uint32_t {
  Unknown, Image, Vulkan, OpenGL, D3D11, D3D12, ...
};
```

### 4.2 回放相关

```cpp
// renderdoc/replay/replay_controller.h
struct ReplayController : public IReplayController {
  RDResult CreateDevice(RDCFile *rdc, const ReplayOptions &opts);
  const SDFile &GetStructuredFile();           // 获取结构化数据
  const rdcarray<ActionDescription> &GetRootActions(); // 获取所有操作
  const rdcarray<TextureDescription> &GetTextures();   // 获取纹理列表
  const rdcarray<BufferDescription> &GetBuffers();     // 获取缓冲区列表
};

// renderdoc/api/replay/data_types.h
struct ActionDescription {
  uint32_t eventId;           // 事件 ID
  ActionFlags flags;          // 操作标志
  rdcstr customName;          // 自定义名称
  rdcarray<ActionDescription> children; // 子操作
};
```

---

## 5. 搜索速查命令

```bash
# 文件结构
rg --files renderdoc/ | rg "\.h$"              # 所有头文件
rg --files renderdoc/driver/ | rg "_replay"    # 所有回放驱动

# 关键入口
rg -n "RDCFile::Open" renderdoc/               # RDC 打开逻辑
rg -n "ReadLogInitialisation" renderdoc/       # 各驱动读取入口
rg -n "CreateDevice.*RDCFile" renderdoc/       # 设备创建入口

# Python 绑定
rg -n "CaptureFile|ReplayController" qrenderdoc/Code/pyrenderdoc/

# Section 类型
rg -n "SectionType::" renderdoc/

# Chunk 定义
rg -n "SERIALISE_ELEMENT|BEGIN_CHUNK" renderdoc/driver/
```

---

## 6. 文件命名约定

| 模式 | 含义 |
|------|------|
| `*_replay.cpp` | 回放驱动实现 |
| `*_serialise.cpp` | 序列化/反序列化 |
| `*_device.cpp` | 设备包装 |
| `*_resources.cpp` | 资源管理 |
| `*_common.cpp` | 公共工具 |
| `*_hooks.cpp` | API Hook 实现 |
| `*_wrap.cpp` | 接口包装 |
| `*.i` | SWIG 接口定义 |

---

## 7. 跨文件引用图 (简化)

```
应用程序
    │
    ▼
┌─────────────────┐
│ CaptureFile     │ ← Python API 入口
│ (capture_file)  │
└────────┬────────┘
         │ Open()
         ▼
┌─────────────────┐
│ RDCFile         │ ← 二进制文件解析
│ (rdcfile)       │
└────────┬────────┘
         │ ReadSection()
         ▼
┌─────────────────┐
│ StreamReader    │ ← 流式读取 + 解压
│ (streamio)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ReplayController│ ← 回放控制
│ (replay_ctrl)   │
└────────┬────────┘
         │ CreateDevice()
         ▼
┌─────────────────────────────────────────┐
│         IReplayDriver (抽象)            │
├─────────────┬───────────┬───────────────┤
│ D3D11Replay │ D3D12Replay│ VulkanReplay │
│             │           │ GLReplay     │
└─────────────┴───────────┴───────────────┘
```

---

## 附录: 文件行数统计 (核心模块)

| 模块 | 主要文件 | 估计行数 |
|------|----------|----------|
| rdcfile | rdcfile.cpp | ~800 |
| serialiser | serialiser.cpp | ~2000 |
| replay_controller | replay_controller.cpp | ~3000 |
| d3d11_replay | d3d11_replay.cpp | ~2500 |
| d3d12_replay | d3d12_replay.cpp | ~3500 |
| vk_replay | vk_replay.cpp | ~4000 |
| gl_replay | gl_replay.cpp | ~2500 |
