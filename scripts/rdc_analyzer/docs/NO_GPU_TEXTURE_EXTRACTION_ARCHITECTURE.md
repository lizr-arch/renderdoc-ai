# 无 GPU 纹理提取架构设计

> **版本**: 1.0.0  
> **更新日期**: 2025-01-31  
> **作者**: Codex Agent A  
> **状态**: ✅ 原型验证完成

---

## 1. 问题背景与动机

### 1.1 核心痛点

RenderDoc 作为图形调试工具，传统上需要**与捕获时相同或兼容的 GPU** 才能回放 (Replay) 捕获文件。这带来以下限制：

| 场景 | 问题 |
|------|------|
| **跨平台分析** | 在 Android 设备上捕获的 Vulkan RDC，无法在没有相同 GPU 的 PC 上分析 |
| **团队协作** | 测试人员捕获的 RDC 发给开发人员，开发机可能没有相同显卡 |
| **CI/CD 自动化** | 服务器环境通常没有 GPU，无法自动化分析捕获 |
| **历史捕获分析** | 旧 GPU 淘汰后，历史捕获文件无法再打开 |

### 1.2 用户需求

> **"在没有真机或相同显卡的情况下，实现纹理数据的提取和分析。"**

### 1.3 为什么传统方法需要 GPU？

通过源码分析，我们发现 RenderDoc 的 Replay 机制依赖 GPU 的原因：

```
用户请求查看纹理
       ↓
ReplayController::GetTextureData()
       ↓
GPU Driver 重新执行命令  ← 需要真实 GPU
       ↓
从 GPU 显存读回像素数据
       ↓
返回给用户
```

**关键发现**：RenderDoc 在 Replay 时会**重新执行** GPU 命令来获取纹理数据，而不是直接从 RDC 文件读取。

---

## 2. 技术方案对比

### 2.1 方案一：GPU 仿真层（理论可行，实现复杂）

```
应用程序 → RenderDoc → 软件 GPU 仿真器 → 返回结果
```

- **优点**：完全兼容现有流程
- **缺点**：需要实现完整的 GPU 功能仿真，工作量巨大
- **评估**：❌ 不可行

### 2.2 方案二：跨平台 GPU 转译（Vulkan → OpenGL/Metal）

- **优点**：利用现有 GPU
- **缺点**：转译层复杂，可能丢失精度
- **评估**：⚠️ 有限可行

### 2.3 方案三：直接读取 RDC 中的初始纹理数据 ✅

**核心洞察**：RDC 文件中**已经保存了捕获时刻所有资源的初始状态**！

```
RDC 文件
    ├── FrameCapture Section
    │       ├── API 调用序列 (vkCreateImage, vkBindImageMemory...)
    │       └── InitialContents Chunks  ← 初始像素数据在这里！
    └── 其他 Sections
```

- **优点**：无需 GPU，纯软件实现
- **缺点**：只能获取捕获时刻的初始状态，无法获取中间帧结果
- **评估**：✅ **选定方案**

---

## 3. 解决方案架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     无 GPU 纹理提取系统                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   RDC 文件   │───▶│  转换工具   │───▶│  ZIP + XML  │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                      renderdoccmd                                   │
│                      convert -c zip.xml                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     XML 解析层                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │ vkCreateImage│  │vkBindImage   │  │InitialContents│      │   │
│  │  │   元数据     │  │  Memory 绑定 │  │  数据位置     │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    资源映射层                                │   │
│  │                                                              │   │
│  │   Image ID ──▶ Memory ID + Offset ──▶ Buffer Index          │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据提取层                                │   │
│  │                                                              │   │
│  │   ZIP[buffer_index] ──▶ Raw Bytes ──▶ Texture Data          │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    格式解码层（可选）                         │   │
│  │                                                              │   │
│  │   BC7/BC3/ASTC ──▶ CPU 解压 ──▶ RGBA Pixels ──▶ PNG         │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流详解

```
┌──────────────────────────────────────────────────────────────────────┐
│ 步骤 1: RDC → ZIP + XML 转换                                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   renderdoccmd convert -c zip.xml input.rdc output.zip               │
│                                                                      │
│   输入: input.rdc (1.2 GB)                                           │
│   输出: output.zip (2.8 GB) + output.zip.xml (351 MB)                │
│                                                                      │
│   ZIP 内容:                                                          │
│   ├── 000000 (空)                                                    │
│   ├── 000001 (8 KB)                                                  │
│   ├── 000002 (1.8 KB)                                                │
│   ├── ...                                                            │
│   └── 002324 (67 MB)  ← 共 2325 个 buffer 文件                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ 步骤 2: 解析 XML 建立资源映射                                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   A. 从 vkCreateImage 提取纹理元数据:                                 │
│      - resource_id: 360                                              │
│      - format: VK_FORMAT_R8_UNORM                                    │
│      - size: 2048 x 4096                                             │
│                                                                      │
│   B. 从 vkBindImageMemory 提取绑定关系:                               │
│      - image: 360                                                    │
│      - memory: 116                                                   │
│      - offset: 9212928                                               │
│                                                                      │
│   C. 从 InitialContents 提取数据位置:                                 │
│      - memory_id: 116                                                │
│      - buffer_index: 425                                             │
│      - contents_size: 33554432 (32 MB)                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ 步骤 3: 从 ZIP 提取纹理原始数据                                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   1. 打开 ZIP 文件                                                    │
│   2. 读取 buffer "000425" (32 MB)                                    │
│   3. 根据 offset=9212928 定位纹理起始位置                             │
│   4. 根据 format 计算纹理字节大小:                                    │
│      - R8_UNORM: 2048 * 4096 * 1 = 8 MB                              │
│   5. 提取 data[9212928 : 9212928 + 8MB]                              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 核心数据结构

```python
@dataclass
class ImageInfo:
    """纹理元数据"""
    resource_id: int      # VkImage 资源 ID
    width: int
    height: int
    depth: int
    format: str           # VK_FORMAT_xxx
    format_id: int        # 格式枚举值
    image_type: str       # VK_IMAGE_TYPE_2D 等

@dataclass
class MemoryBinding:
    """图像到内存的绑定"""
    image_id: int         # VkImage ID
    memory_id: int        # VkDeviceMemory ID
    offset: int           # 在内存中的偏移

@dataclass
class InitialContents:
    """内存初始内容"""
    resource_type: str    # eResDeviceMemory, eResBuffer 等
    resource_id: int      # 内存资源 ID
    is_sparse: bool
    contents_size: int    # 内存块大小
    buffer_index: int     # ZIP 中的文件索引
```

---

## 4. 当前实现状态

### 4.1 已完成功能

| 功能 | 状态 | 说明 |
|------|------|------|
| RDC → ZIP+XML 转换 | ✅ | 使用 `renderdoccmd convert` |
| XML 元数据解析 | ✅ | 正则表达式高效解析 |
| 资源映射建立 | ✅ | Image → Memory → Buffer |
| 原始数据提取 | ✅ | 从 ZIP 精确提取纹理字节 |

### 4.2 已验证的测试用例

```
测试文件: D:\backup\大远景.rdc (Unity/Vulkan 捕获)
- 捕获设备: NVIDIA RTX 2060 SUPER
- 纹理总数: 1087 个
- 可提取纹理: 1022 个 (94%)
- 成功提取示例:
  - ID 360: 2048x4096 R8_UNORM → 8 MB 原始数据
```

### 4.3 工具使用示例

```bash
# 步骤 1: 转换 RDC 为 ZIP+XML
renderdoccmd convert -c zip.xml capture.rdc output.zip

# 步骤 2: 列出所有可提取纹理
py -3 extract_texture_from_zipxml.py output.zip.xml --list-textures

# 步骤 3: 提取指定纹理
py -3 extract_texture_from_zipxml.py output.zip.xml --extract 360 --output ./textures/
```

---

## 5. 限制与边界条件

### 5.1 可提取的数据

| 数据类型 | 可提取性 | 说明 |
|----------|----------|------|
| **初始纹理数据** | ✅ 完全支持 | 捕获时刻的纹理内容 |
| **初始 Buffer 数据** | ✅ 完全支持 | VBO/IBO/UBO 等 |
| **渲染目标 (RT)** | ⚠️ 部分支持 | 仅初始内容，不含渲染结果 |
| **中间帧结果** | ❌ 不支持 | 需要 GPU Replay |
| **动态生成的纹理** | ❌ 不支持 | 如程序化生成的噪声图 |

### 5.2 65 个不可提取纹理的原因分析

在测试中，1087 个纹理中有 65 个无法提取：

| 原因 | 数量 | 说明 |
|------|------|------|
| 无内存绑定 | ~40 | SwapChain Image 等由驱动管理 |
| 无 InitialContents | ~25 | 延迟创建或动态资源 |

---

## 6. 未来路线图

### 6.1 短期目标 (v1.1)

- [ ] **格式解码器**：实现 BC7/BC3/BC5 压缩格式的 CPU 解压
- [ ] **PNG 导出**：将 RGBA/R8 等简单格式导出为图像
- [ ] **批量提取**：一次性导出所有纹理及其元数据 JSON

### 6.2 中期目标 (v1.5)

- [ ] **MCP Tool 集成**：封装为 Claude 可调用的工具
- [ ] **Buffer 分析**：提取顶点/索引/Uniform 数据
- [ ] **Shader 提取**：导出 SPIR-V / DXBC 字节码

### 6.3 长期目标 (v2.0)

- [ ] **软件 Replay**：实现部分 Draw Call 的 CPU 模拟
- [ ] **跨 API 支持**：扩展到 D3D11/D3D12/OpenGL
- [ ] **Web UI**：基于浏览器的 RDC 分析工具

---

## 7. 参考资料

### 7.1 相关源码文件

| 文件 | 说明 |
|------|------|
| `renderdoc/serialise/rdcfile.h` | RDC 文件格式定义 |
| `renderdoc/core/core.h:216` | SystemChunk 枚举（InitialContents = 3） |
| `renderdoc/driver/vulkan/vk_initstate.cpp` | Vulkan 初始状态序列化 |
| `renderdoc/replay/capture_file.cpp` | CaptureFile::GetStructuredData() |

### 7.2 相关文档

- [NO_GPU_TEXTURE_EXTRACTION.md](./NO_GPU_TEXTURE_EXTRACTION.md) - 技术背景分析
- [TEXTURE_EXTRACTION_METHODS.md](./TEXTURE_EXTRACTION_METHODS.md) - 方案对比
- [RDC_FORMAT_SPEC.md](./RDC_FORMAT_SPEC.md) - RDC 文件格式规范

### 7.3 工具脚本

- `scripts/rdc_analyzer/extract_texture_from_zipxml.py` - 主提取工具
