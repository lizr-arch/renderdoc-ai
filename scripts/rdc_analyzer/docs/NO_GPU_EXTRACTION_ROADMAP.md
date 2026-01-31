# 无 GPU 纹理提取功能路线图

> **版本**: 1.0.0  
> **更新日期**: 2025-01-31  
> **作者**: Codex Agent A

---

## 📋 目录

- [1. 当前状态](#1-当前状态)
- [2. 短期目标 (v1.x)](#2-短期目标-v1x)
- [3. 中期目标 (v2.x)](#3-中期目标-v2x)
- [4. 长期愿景 (v3.x+)](#4-长期愿景-v3x)
- [5. 技术挑战与风险](#5-技术挑战与风险)
- [6. 贡献指南](#6-贡献指南)

---

## 1. 当前状态

### 1.1 已完成功能 (v1.0.0)

| 功能 | 状态 | 说明 |
|------|------|------|
| ZIP+XML 转换集成 | ✅ 完成 | 通过 `renderdoccmd convert` |
| Vulkan 纹理元数据解析 | ✅ 完成 | vkCreateImage / vkBindImageMemory |
| InitialContents 数据提取 | ✅ 完成 | VkDeviceMemory → buffer 映射 |
| 高性能 XML 解析 | ✅ 完成 | 正则表达式，支持 300MB+ 文件 |
| 命令行工具 | ✅ 完成 | `extract_texture_from_zipxml.py` |
| 纹理列表展示 | ✅ 完成 | 格式化表格输出 |

### 1.2 验证结果

| 测试项 | 结果 |
|--------|------|
| 测试 RDC | `D:\backup\大远景.rdc` (Unity/Vulkan) |
| 总纹理数 | 1087 |
| 可提取纹理 | 1022 (94%) |
| 不可提取原因 | SwapChain (~40), 延迟创建 (~25) |
| 验证纹理 | texture_360 (R8_UNORM, 2048×4096) |
| 字节验证 | ✅ 8,388,608 bytes = 预期值 |

### 1.3 当前限制

| 限制 | 影响 | 优先级 |
|------|------|--------|
| 仅支持 Vulkan RDC | 不支持 D3D11/D3D12/GL | 高 |
| 仅提取原始字节 | BC 压缩格式无法查看 | 高 |
| 无 Mipmap 支持 | 仅提取 level 0 | 中 |
| 无数组/3D 纹理 | 仅 2D 纹理 | 中 |
| 无 GUI | 仅命令行 | 低 |

---

## 2. 短期目标 (v1.x)

### v1.1: 格式解码支持

**目标发布**: 2025 Q1

| 任务 | 描述 | 复杂度 |
|------|------|--------|
| BC1 解码器 | DXT1/RGB/RGBA | 中 |
| BC3 解码器 | DXT5 | 中 |
| BC7 解码器 | BPTC | 高 |
| BC5 解码器 | 法线贴图 | 中 |
| PNG 输出 | 解码后保存为 PNG | 低 |

**技术方案**:
```python
# 选项 1: 纯 Python 实现（慢但无依赖）
from texture_decoders import decode_bc7

# 选项 2: 调用外部工具
subprocess.run(['texconv', '-ft', 'PNG', input_file])

# 选项 3: 使用 texture2ddecoder 库（需 pip install）
import texture2ddecoder
```

**验收标准**:
- [ ] BC7 纹理可解码为 RGBA 数据
- [ ] 输出 PNG 可在图像查看器中正常显示
- [ ] 性能: 4K 纹理 < 5秒

### v1.2: D3D11 支持

**目标发布**: 2025 Q1

| 任务 | 描述 |
|------|------|
| D3D11 XML 解析 | `CreateTexture2D`, `CreateTexture3D` |
| DXGI 格式映射 | DXGI_FORMAT → 解码器 |
| InitialContents 适配 | D3D11 的 buffer 结构差异 |

**关键差异**:
```
Vulkan: VkImage → VkDeviceMemory (共享内存池)
D3D11: ID3D11Texture2D → 独立 InitialContents (直接存储)
```

**验收标准**:
- [ ] D3D11 RDC 纹理列表正确解析
- [ ] 至少 80% 纹理可提取
- [ ] BC 格式解码正常

### v1.3: Mipmap 与数组支持

**目标发布**: 2025 Q2

| 任务 | 描述 |
|------|------|
| Mipmap 链提取 | 提取所有 mip levels |
| 纹理数组支持 | ArrayLayers > 1 |
| Cubemap 支持 | 6 面提取 |
| DDS 输出 | 完整 DDS 文件（含 header） |

---

## 3. 中期目标 (v2.x)

### v2.0: Buffer 与 Shader 提取

**目标发布**: 2025 Q2

| 任务 | 描述 |
|------|------|
| Vertex Buffer 提取 | 提取顶点数据 |
| Index Buffer 提取 | 提取索引数据 |
| Shader 二进制提取 | SPIR-V / DXBC |
| Shader 反编译集成 | SPIRV-Cross / DXC |

**用例**: 
- 导出 3D 模型（网格 + 纹理）
- 分析 Shader 性能

### v2.1: 软件回放原型

**目标发布**: 2025 Q3

| 任务 | 描述 | 风险 |
|------|------|------|
| 调用序列解析 | 从 XML 重建 API 调用顺序 | 中 |
| 资源状态跟踪 | 跟踪 Bind/Unbind | 高 |
| 简单回放验证 | 对比 GPU 回放结果 | 高 |

**注意**: 完整软件回放是极高复杂度任务，v2.1 仅作为概念验证。

### v2.2: MCP Server 集成

**目标发布**: 2025 Q3

| 任务 | 描述 |
|------|------|
| MCP Tool 封装 | `extract_texture`, `list_textures` |
| 批量处理 API | 多 RDC 文件支持 |
| 报告生成 | HTML 纹理报告 |

---

## 4. 长期愿景 (v3.x+)

### v3.0: 跨平台软件回放

**愿景**: 在任意平台上完整回放 RDC，无需 GPU

| 组件 | 描述 |
|------|------|
| 软件光栅化 | CPU 实现的基础光栅化 |
| Shader 解释器 | SPIR-V/DXBC 软件执行 |
| 像素级验证 | 与 GPU 回放对比 |

**技术路线**:
- SwiftShader / Mesa llvmpipe 集成
- WARP (Windows 软件渲染)
- 自定义轻量级软件渲染器

### v3.1: 自动化性能分析

| 功能 | 描述 |
|------|------|
| OverDraw 检测 | 识别过度绘制区域 |
| 纹理优化建议 | 压缩格式、分辨率建议 |
| DrawCall 批处理建议 | 合批优化 |

---

## 5. 技术挑战与风险

### 5.1 高风险项

| 挑战 | 描述 | 缓解措施 |
|------|------|----------|
| BC7 解码性能 | 纯 Python 太慢 | 使用 C 扩展或外部工具 |
| D3D12 ResourceBarrier | 复杂的资源状态机 | 增量支持，先处理简单情况 |
| 软件回放正确性 | GPU 行为差异难以完全模拟 | 定义"功能子集"，不追求 100% |

### 5.2 中风险项

| 挑战 | 描述 | 缓解措施 |
|------|------|----------|
| 大文件处理 | 10GB+ RDC 内存占用 | 流式处理，分块加载 |
| 版本兼容性 | RDC 格式版本差异 | 检测版本，适配解析逻辑 |
| 稀疏资源 | VirtualAlloc 纹理 | v1.x 暂不支持 |

### 5.3 低风险项

| 挑战 | 描述 | 状态 |
|------|------|------|
| XML 解析 | 已使用正则优化 | ✅ 解决 |
| Vulkan 内存绑定 | 映射关系已理清 | ✅ 解决 |

---

## 6. 贡献指南

### 6.1 如何贡献

1. **选择任务**: 从上方路线图选择感兴趣的任务
2. **创建分支**: `feature/no-gpu-v1.1-bc7-decoder`
3. **提交 PR**: 包含测试和文档

### 6.2 代码规范

- Python: PEP 8 + 类型注解
- 测试: `scripts/rdc_analyzer/tests/`
- 文档: `scripts/rdc_analyzer/docs/`

### 6.3 测试数据

| 文件 | 描述 | 大小 |
|------|------|------|
| `test_vulkan.rdc` | Vulkan 测试用例 | 待提供 |
| `test_d3d11.rdc` | D3D11 测试用例 | 待提供 |
| `test_d3d12.rdc` | D3D12 测试用例 | 待提供 |

### 6.4 联系方式

- 相关文档: `scripts/rdc_analyzer/docs/INDEX.md`
- 主仓库: `d:\Code\git\renderdoc`

---

## 📜 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2025-01-31 | 初始版本，Vulkan 基础功能完成 |

---

## 📎 相关文档

- [架构设计](./NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md)
- [RDC 结构分析](./RDC_STRUCTURE_DEEP_ANALYSIS.md)
- [实现指南](./NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md)
- [工具索引](./INDEX.md)
