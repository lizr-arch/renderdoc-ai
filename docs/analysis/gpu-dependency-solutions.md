# GPU 依赖约束分析与解决方案

> **创建日期**: 2025-01-20  
> **目的**: 分析 GPU 硬性依赖的技术原因，提供可行的解决方案

---

## 1. 为什么需要 GPU？

### 1.1 技术原因

RenderDoc 的 GPU 回放**不是状态快照恢复**，而是**真实重放 API 调用**：

```
.rdc 文件 → 反序列化 API 调用 → 调用真实 vkCmdDraw() → GPU 执行 → 产生像素数据
```

| 阶段 | 需要 GPU？ | 原因 |
|------|-----------|------|
| 解析 RDC 文件 | ❌ | 纯 CPU 操作 |
| 读取纹理元数据 | ❌ | 从文件读取 |
| 创建 Vulkan/D3D 设备 | ✅ | 需要驱动初始化 |
| 回放绘制调用 | ✅ | 需要 GPU 着色器执行 |
| 导出纹理图像 | ✅ | 需要读回 GPU 内存 |

**核心问题**：RDC 文件中存储的是**压缩/编码**的纹理数据（如 BC 压缩格式），需要 GPU 解码才能得到可视化的 PNG。

---

## 2. 可行的解决方案

### 方案对比速查表

| 方案 | 无 GPU 服务器可用 | 实现难度 | 推荐场景 |
|------|-------------------|----------|----------|
| **A. 软件渲染器** | ✅ | ⭐⭐ | CI/CD 自动化 |
| **B. 远程 GPU 服务器** | ✅ | ⭐ | 企业内网 |
| **C. 预导出嵌入** | ✅ | ⭐⭐⭐ | 离线分析 |
| **D. Docker + GPU** | ❌（需 GPU 主机） | ⭐⭐ | 云服务 |

---

## 3. 方案 A：软件渲染器（推荐）

### 3.1 RenderDoc 已支持的软件渲染器

| 渲染器 | 平台 | Vendor ID | 特点 |
|--------|------|-----------|------|
| **SwiftShader** | 跨平台 | 0x1AE0 | Google 开发，Vulkan 完整支持 |
| **WARP** | Windows | 0x1414 | Microsoft 官方 D3D11/D3D12 |
| **Mesa LLVMPipe** | Linux | N/A | 开源，Vulkan/OpenGL |

### 3.2 使用方法

**通过 ReplayOptions 强制使用软件渲染器**：

```cpp
// C++ API
ReplayOptions opts;
opts.forceGPUVendor = GPUVendor::Software;  // 强制使用软件渲染

IReplayController *ctrl;
file->OpenCapture(opts, &ctrl);
```

```python
# Python API
import renderdoc as rd

opts = rd.ReplayOptions()
opts.forceGPUVendor = rd.GPUVendor.Software

cap = rd.OpenCaptureFile()
cap.OpenFile("capture.rdc", "", None)
status, controller = cap.OpenCapture(opts, None)
```

### 3.3 SwiftShader 安装

**Windows:**
```powershell
# 下载 SwiftShader Vulkan ICD
# 放置到 C:\SwiftShader\vk_swiftshader_icd.json 和 .dll

# 设置环境变量
$env:VK_ICD_FILENAMES = "C:\SwiftShader\vk_swiftshader_icd.json"
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install mesa-vulkan-drivers libvulkan-dev

# 使用 lavapipe (Mesa 软件 Vulkan)
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json
```

### 3.4 命令行工具扩展

```cpp
// renderdoccmd export --software-render -f capture.rdc -o output/
struct ExportCommand : public Command {
    bool useSoftwareRender = false;
    
    virtual void AddOptions(cmdline::parser &parser) {
        parser.add("software-render", '\0', 
            "Force software rendering (SwiftShader/WARP)");
        // ...
    }
    
    virtual int Execute(...) {
        ReplayOptions opts;
        if(useSoftwareRender)
            opts.forceGPUVendor = GPUVendor::Software;
        
        // ... 回放并导出
    }
};
```

---

## 4. 方案 B：远程 GPU 服务器

### 4.1 架构

```
┌─────────────────┐         ┌────────────────────┐
│  CI 服务器      │  网络   │  GPU 服务器        │
│  (无 GPU)       │ ◀─────▶ │  (有 GPU)          │
│                 │         │                    │
│  renderdoccmd   │         │  renderdoccmd      │
│  --remote       │         │  --server          │
└─────────────────┘         └────────────────────┘
```

### 4.2 使用方法

**在 GPU 服务器上启动 RenderDoc 服务**：
```bash
# 服务器端（有 GPU）
renderdoccmd remoteserver --listen 0.0.0.0 --port 39920
```

**在 CI 客户端连接并执行**：
```bash
# 客户端（无 GPU）
renderdoccmd replay --remote <gpu-server>:39920 -f capture.rdc
```

### 4.3 Python API 远程连接

```python
import renderdoc as rd

# 连接远程服务器
result, remote = rd.CreateRemoteServerConnection("192.168.1.100:39920")

if result.code == rd.ResultCode.Succeeded:
    # 上传 RDC 到服务器
    remote_path = remote.CopyCaptureToRemote("capture.rdc", None)
    
    # 在远程 GPU 上回放
    status, controller = remote.OpenCapture(0, remote_path, rd.ReplayOptions(), None)
    
    # 导出纹理（在服务器执行，结果传回）
    textures = controller.GetTextures()
    for tex in textures:
        save = rd.TextureSave()
        save.resourceId = tex.resourceId
        # ...
        controller.SaveTexture(save, f"/tmp/{tex.resourceId}.png")
    
    # 下载结果
    remote.CopyCaptureFromRemote("/tmp/*.png", "./output/", None)
    
    remote.CloseCapture(controller)
    remote.ShutdownConnection()
```

---

## 5. 方案 C：预导出嵌入（零 GPU 依赖）

### 5.1 概念

在**捕获时**或**首次回放时**，将纹理预览嵌入 RDC 文件：

```
┌────────────────────────────────────────┐
│ .rdc 文件                              │
├────────────────────────────────────────┤
│ Section: FrameCapture                  │
│ Section: ResolveDatabase               │
│ Section: ExtendedThumbnail (现有)      │
│ Section: TexturePreviews (新增!)       │  ◀── 预渲染的 PNG
│     └── texture_0x1234.png (base64)    │
│     └── texture_0x5678.png (base64)    │
└────────────────────────────────────────┘
```

### 5.2 实现流程

```
1. 用户首次在 GUI 打开 RDC
2. GUI 自动导出所有纹理缩略图
3. 将缩略图作为新 Section 写入 RDC
4. 之后的 CLI 工具直接读取嵌入的预览，无需 GPU
```

### 5.3 代码示例

```python
# 嵌入纹理预览到 RDC
def embed_texture_previews(rdc_path: str, previews_dir: str):
    """将预渲染的纹理写入 RDC 文件"""
    import json
    import base64
    
    cap = rd.OpenCaptureFile()
    cap.OpenFile(rdc_path, "", None)
    
    # 读取所有预览图，打包为 JSON
    previews = {}
    for png_file in Path(previews_dir).glob("*.png"):
        res_id = png_file.stem
        with open(png_file, 'rb') as f:
            previews[res_id] = base64.b64encode(f.read()).decode()
    
    # 创建自定义 Section
    props = rd.SectionProperties()
    props.name = "TexturePreviews"
    props.type = rd.SectionType.Unknown  # 自定义类型
    props.flags = rd.SectionFlags.ZstdCompressed
    
    content = json.dumps(previews).encode('utf-8')
    cap.WriteSection(props, content)
    cap.Shutdown()
```

```python
# CLI 工具读取嵌入的预览（无需 GPU）
def extract_embedded_previews(rdc_path: str) -> dict:
    """从 RDC 读取嵌入的纹理预览"""
    import json
    
    cap = rd.OpenCaptureFile()
    cap.OpenFile(rdc_path, "", None)
    
    idx = cap.FindSectionByName("TexturePreviews")
    if idx >= 0:
        content = cap.GetSectionContents(idx)
        return json.loads(content.decode('utf-8'))
    
    return {}  # 没有嵌入预览
```

### 5.4 优缺点

| 优点 | 缺点 |
|------|------|
| CLI 完全不需要 GPU | 需要预处理步骤 |
| 文件自包含，分发方便 | 增加 RDC 文件大小 |
| 读取速度极快 | 只有预览质量，非原始数据 |

---

## 6. 方案 D：Docker + GPU 透传

### 6.1 Docker 容器

```dockerfile
# Dockerfile
FROM nvidia/vulkan:1.3-470

# 安装 RenderDoc
RUN apt-get update && apt-get install -y \
    renderdoc \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# 复制导出脚本
COPY export_textures.py /app/

WORKDIR /app
ENTRYPOINT ["python3", "export_textures.py"]
```

### 6.2 运行

```bash
# 需要 NVIDIA GPU + nvidia-docker
docker run --gpus all \
    -v $(pwd)/captures:/data \
    -v $(pwd)/output:/output \
    renderdoc-exporter \
    --input /data/capture.rdc \
    --output /output/
```

### 6.3 云服务选项

| 云服务 | GPU 实例 | 适用场景 |
|--------|----------|----------|
| AWS EC2 | g4dn.xlarge | 按需分析 |
| Azure VM | NC 系列 | CI/CD 流水线 |
| GCP Compute | T4 | 批量处理 |

---

## 7. 推荐实现路径

### 7.1 短期（1-2 周）

```
┌──────────────────────────────────────────────────────────┐
│  阶段 1：软件渲染器 + CLI 扩展                           │
├──────────────────────────────────────────────────────────┤
│  1. 在 Windows 安装 SwiftShader                          │
│  2. 测试 ReplayOptions.forceGPUVendor = Software         │
│  3. 扩展 renderdoccmd 添加 export 命令                   │
│  4. 添加 --software-render 选项                          │
└──────────────────────────────────────────────────────────┘
```

### 7.2 中期（2-4 周）

```
┌──────────────────────────────────────────────────────────┐
│  阶段 2：远程服务器模式                                  │
├──────────────────────────────────────────────────────────┤
│  1. 部署 GPU 服务器运行 renderdoccmd remoteserver        │
│  2. CLI 添加 --remote 选项连接远程服务器                 │
│  3. 实现纹理下载回传                                     │
└──────────────────────────────────────────────────────────┘
```

### 7.3 长期（1-2 月）

```
┌──────────────────────────────────────────────────────────┐
│  阶段 3：预导出嵌入 + 增量更新                           │
├──────────────────────────────────────────────────────────┤
│  1. GUI 首次打开时自动嵌入纹理预览                       │
│  2. CLI 直接读取嵌入 Section，完全离线                   │
│  3. 支持选择性嵌入（按大小/类型过滤）                    │
└──────────────────────────────────────────────────────────┘
```

---

## 8. 结论

| 问题 | 答案 |
|------|------|
| 能否完全不需要 GPU？ | **可以**，使用软件渲染器（SwiftShader/WARP） |
| 性能如何？ | 软件渲染慢 10-100x，但纹理导出可接受 |
| 最推荐方案？ | **方案 A（软件渲染器）**，开箱即用 |
| 最灵活方案？ | **方案 B（远程服务器）**，适合企业环境 |
| 最快速方案？ | **方案 C（预导出嵌入）**，零运行时开销 |

### 下一步行动

1. ✅ 验证 SwiftShader 是否可用于 Vulkan RDC 回放
2. ⏳ 实现 `renderdoccmd export` 命令 + `--software-render` 选项
3. ⏳ 测试完整流水线

---

## 附录：关键代码引用

| 功能 | 文件 | 行号 |
|------|------|------|
| ReplayOptions.forceGPUVendor | `renderdoc/api/replay/control_types.h` | 1294-1315 |
| GPUVendor::Software 检测 | `renderdoc/api/replay/replay_enums.h` | 1960-1961 |
| 远程服务器协议 | `renderdoc/core/remote_server.cpp` | 全文件 |
| 软件渲染器识别 | `renderdoc/driver/gl/gl_debug.cpp` | 1106-1108 |
| Mesa LLVMPipe 支持 | `renderdoc/driver/vulkan/vk_common.cpp` | 1230-1242 |
