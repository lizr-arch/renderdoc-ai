# RenderDoc 项目概览（repo: D:\\Code\\git\\renderdoc）

## 项目目的
- RenderDoc 是一个基于“帧捕获（frame-capture）”的图形调试器（graphics debugger），用于 Vulkan、D3D11、D3D12、OpenGL、OpenGL ES。见 `README.md`。

## 顶层结构（仓库根目录）
- `renderdoc/`：核心运行时 + 各图形 API driver 后端（如 Vulkan/D3D/OpenGL）。
- `qrenderdoc/`：Qt UI 层（GUI），构建在 `renderdoc/` 之上。
- `renderdoccmd/`：命令行工具。
- `renderdocshim/`：Windows hooking 用的小 DLL。
- `docs/`：文档（贡献指南、编译、开发规范等）。
- `util/` / `scripts/`：工具脚本、CI/打包等支撑。

（结构出处：`docs/CONTRIBUTING/Code-Explanation.md`）

## RDC（.rdc）读取与回放的关键入口（面向“RDC 文件分析”）
如果你要从“打开一个 .rdc”一路追到“驱动回放初始化”，推荐按以下路径阅读：

1) 高层封装（CaptureFile）
- `renderdoc/replay/capture_file.cpp:201`：`CaptureFile::OpenFile`（对外的 capture 文件打开流程）。

2) RDC 文件底层读写（RDCFile）
- `renderdoc/serialise/rdcfile.h`：`RDCFile` 类型声明（Open/Init/ReadSection/WriteSection 等）。
- `renderdoc/serialise/rdcfile.cpp:236`：`RDCFile::Open`（打开并读取/初始化 capture 文件的关键入口）。

3) Section 类型枚举（文件结构索引）
- `renderdoc/api/replay/replay_enums.h:120`：`enum class SectionType : uint32_t`（RDC 中各 section 的类型定义）。

4) Replay 设备创建与初始化
- `renderdoc/replay/replay_controller.cpp:2167`：`ReplayController::CreateDevice`（创建回放设备 + 进入各 API replay 初始化）。

5) 各 driver 的初始化入口（ReadLogInitialisation）
- Vulkan：`renderdoc/driver/vulkan/vk_replay.cpp:199`：`VulkanReplay::ReadLogInitialisation`
- D3D12：`renderdoc/driver/d3d12/d3d12_replay.cpp:275`：`D3D12Replay::ReadLogInitialisation`
- D3D11：`renderdoc/driver/d3d11/d3d11_replay.cpp:1694`：`D3D11Replay::ReadLogInitialisation`
- OpenGL：`renderdoc/driver/gl/gl_replay.cpp:114`：`GLReplay::ReadLogInitialisation`

## 重要约束（来自本仓库 Agents.md）
- 不要修改 `renderdoc/3rdparty/` 和 `build*/`（构建输出）目录。
- 构建类命令（msbuild/cmake/make 等）需要用户明确授权后再执行。
