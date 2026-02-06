# RDC Analyzer 文档索引



> **更新日期**: 2025-02-05 | **版本**: 2.4.0 | **维护**: Codex Agent



本目录包含 `rdc_analyzer` 工具的技术文档。



---



## 快速导航（按主题）



### 🏗️ 架构与设计

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) | 模块架构与数据流 | 架构, 模块, 数据流 |

| [REFACTOR_ANALYSIS.md](REFACTOR_ANALYSIS.md) | 重构分析与优化建议 | 重构, 分析, 优化 |



### 📊 功能指南

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [EXPORT_ROUTES.md](EXPORT_ROUTES.md) | **RDC 报告导出路线图** - 三条导出路线 + 新组件（v2.2.0）⭐ | 导出路线, Bundle, XML, 无GPU, RdcAdapter, JsonRenderer |
| [BATCH_EXPORT.md](BATCH_EXPORT.md) | **纹理批量导出 CLI** - 一键导出所有纹理 (v1.4.0) | 批量导出, CLI, gallery, manifest |
| [D3D11_SUPPORT.md](D3D11_SUPPORT.md) | **D3D11 纹理提取** - 支持 DirectX 11 离线提取 (v1.5.0) | D3D11, DirectX, DXGI, 离线提取 |

| [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) | **纹理提取三方案速查** | 纹理, 导出, SaveTexture, renderdoccmd |

| [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) | **纹理解码器模块** (v1.3.0) - 48种格式支持 | 解码, BCn, ASTC, ETC2, PNG, decode_texture |

| [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) | **无 GPU 纹理提取技术分析** | 无GPU, GetStructuredData, SDFile, buffers |

| [UNITY_EXPORT.md](UNITY_EXPORT.md) | Unity 资产导出指南 | Unity, 导出, mesh, shader |
| [FBX_EXPORT.md](FBX_EXPORT.md) | **FBX 导出流水线**（OBJ 中间态 → Unity/Unreal） | FBX, OBJ, Unity, Unreal |
| [UNITY_IMPORT.md](UNITY_IMPORT.md) | **Unity 导入需求**（官方文档要点） | Unity, 导入, FBX, ShaderLab |
| [UNREAL_IMPORT.md](UNREAL_IMPORT.md) | **Unreal 导入需求**（官方文档要点） | Unreal, 导入, FBX, PBR |
| [MESH_SHADER_EXTRACTION.md](MESH_SHADER_EXTRACTION.md) | Mesh/Shader 导出指南 | mesh, vb, ib, shader |
| [INTERMEDIATE_FORMAT.md](INTERMEDIATE_FORMAT.md) | **XML/ZIP 中间态格式** - 单 Event 输出 | intermediate, schema, zip.xml |

| [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) | Mali GPU 分析集成 | Mali, GPU, 性能分析 |



### 🚀 无 GPU 纹理提取（新）

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) | **架构设计**：问题背景、方案对比、三步提取流程 | 无GPU, 架构, ZIP+XML, InitialContents |

| [RDC_STRUCTURE_DEEP_ANALYSIS.md](RDC_STRUCTURE_DEEP_ANALYSIS.md) | **RDC 结构深度分析**：Chunk/Section 布局、Vulkan 资源映射链路 | RDC, Chunk, SystemChunk, vkCreateImage |

| [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) | **实现指南**：工具使用、API 示例、格式处理、常见问题 | extract_texture_from_zipxml, BC7, 实现 |

| [NO_GPU_EXTRACTION_ROADMAP.md](NO_GPU_EXTRACTION_ROADMAP.md) | **功能路线图**：当前状态、短期/中期/长期目标、技术挑战 | 路线图, v1.x, v2.x, D3D11, 软件回放 |



### � 证据链与交互 (v2.4.0 新增)

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [EVIDENCE_CHAIN.md](EVIDENCE_CHAIN.md) | **跨页面证据链** - M1/M2/M3 里程碑实现 | 证据链, 跨页跳转, URL参数, 高亮 |

**功能摘要**：
- **M1** (Texture → Event)：纹理卡片点击跳转到 Events 页面对应 Draw Call
- **M2** (Event → Shader)：Events 页面跳转到 Shaders 页面对应 Shader
- **M3** (Shader → Event/Texture)：Shader 详情跳转回关联的 Event 或 Texture

**技术实现**：
- URL 参数传递：`?id=468&highlight=true`
- 自动滚动定位 + CSS 脉冲高亮动画
- 支持离线 HTML 报告

### �📝 格式与规范

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [rdc_format_spec.md](rdc_format_spec.md) | RDC 文件格式规范 | RDC, 二进制, Section, Chunk |

| [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) | **GPU 兼容性分析**：为什么 RDC 无法跨 GPU 解析（源码证据） | GPU, 兼容性, 跨平台, APIHardwareUnsupported |



### 🔧 环境与验证

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [P4_ENVIRONMENT_VERIFICATION.md](P4_ENVIRONMENT_VERIFICATION.md) | P4 环境验证流程 | 环境, P4, 验证 |

| [MILESTONE_SUMMARY.md](MILESTONE_SUMMARY.md) | 里程碑总结 | 里程碑, 进度, 总结 |

| [PROGRESS_REPORT.md](PROGRESS_REPORT.md) | 进度报告 | 进度, 报告 |



### 📋 待办与规划

| 文档 | 说明 | 关键词 |

|------|------|--------|

| [TODO.md](TODO.md) | 待办事项列表 | TODO, 任务, 待办 |



---



## 常见问题速查



| 问题 | 答案位置 |

|------|----------|

| 如何从 RDC 提取纹理？ | [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) |

| RDC 文件结构是什么？ | [rdc_format_spec.md](rdc_format_spec.md) |

| 如何导出 Unity 资产？ | [UNITY_EXPORT.md](UNITY_EXPORT.md) |
| 如何导出 FBX 资产？ | [FBX_EXPORT.md](FBX_EXPORT.md) |
| 如何导入 Unity 资产？ | [UNITY_IMPORT.md](UNITY_IMPORT.md) |
| 如何导入 Unreal 资产？ | [UNREAL_IMPORT.md](UNREAL_IMPORT.md) |
| 如何导出 Mesh/Shader？ | [MESH_SHADER_EXTRACTION.md](MESH_SHADER_EXTRACTION.md) |

| Mali 分析如何集成？ | [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) |

| 代码架构是什么？ | [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) |

| **为什么 RDC 无法跨 GPU 解析？** | [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) |

| **如何无 GPU 提取纹理？** | [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) |
| **如何提取 D3D11 纹理？** | [D3D11_SUPPORT.md](D3D11_SUPPORT.md) |

| **无 GPU 提取的详细架构？** | [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) |

| **RDC 内部结构详解？** | [RDC_STRUCTURE_DEEP_ANALYSIS.md](RDC_STRUCTURE_DEEP_ANALYSIS.md) |

| **如何使用提取工具？** | [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) |

| **无 GPU 提取未来规划？** | [NO_GPU_EXTRACTION_ROADMAP.md](NO_GPU_EXTRACTION_ROADMAP.md) |

| **如何解码压缩纹理？** | [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) |

| **支持哪些纹理格式？** | [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) (48种: BC1-7, ASTC, ETC2等) |
| **如何选择报告导出路线？** | [EXPORT_ROUTES.md](EXPORT_ROUTES.md) ⭐ |



---



## 关联文档（其他目录）



| 路径 | 说明 |

|------|------|

| [docs/analysis/codex_rdc_analyzer/DOC_INDEX.md](../../../docs/analysis/codex_rdc_analyzer/DOC_INDEX.md) | **总索引入口**（推荐先读） |

| [docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_*.md](../../../docs/analysis/codex_rdc_analyzer/) | 工作总结系列文档 |

| [docs/analysis/gpu-replay-architecture.md](../../../docs/analysis/gpu-replay-architecture.md) | GPU 回放架构 |

| [docs/analysis/gpu-dependency-solutions.md](../../../docs/analysis/gpu-dependency-solutions.md) | GPU 依赖解决方案 |



---



## 📁 Assets 资源目录结构

> **v2.3.0 新增**：CSS/JS 从 Python 中分离，实现关注点分离

```
scripts/rdc_analyzer/assets/
├── styles/                          # CSS 样式文件
│   ├── html_reporter.css            # html_reporter.py 使用
│   ├── simple_report.css            # generate_simple_report.py 使用
│   ├── sample_report.css            # generate_sample_report.py 使用（Mali Shader）
│   └── texture_gallery.css          # export_textures.py 使用
│
├── scripts/                         # JavaScript 文件
│   ├── simple_report.js             # generate_simple_report.py 使用
│   └── sample_report.js             # generate_sample_report.py 使用（Mali Shader）
│
└── fonts/                           # 字体文件（预留）
```

### 资源加载模式

所有独立脚本使用统一的 `_load_asset()` 辅助函数：

```python
from pathlib import Path

_ASSETS_DIR = Path(__file__).parent / "assets"

def _load_asset(relative_path: str, fallback: str = "") -> str:
    """加载 assets 目录下的资源文件"""
    try:
        return (_ASSETS_DIR / relative_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return fallback
```

**使用示例**：
```python
css = _load_asset("styles/simple_report.css", "/* CSS not found */")
js = _load_asset("scripts/simple_report.js", "// JS not found")
```

---



## 维护约定



1. **新增文档**必须更新本索引

2. **每条索引**包含：链接、说明、关键词

3. **关键词**用于搜索（`rg "关键词" docs/`）



## 自动同步（未归类）

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [GPU_COMPATIBILITY_ANALYSIS.md](GPU_COMPATIBILITY_ANALYSIS.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [MALI_INTEGRATION_SUMMARY.md](MALI_INTEGRATION_SUMMARY.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [MILESTONE_SUMMARY.md](MILESTONE_SUMMARY.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_EXTRACTION_ROADMAP.md](NO_GPU_EXTRACTION_ROADMAP.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_TEXTURE_EXTRACTION.md](NO_GPU_TEXTURE_EXTRACTION.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [P4_ENVIRONMENT_VERIFICATION.md](P4_ENVIRONMENT_VERIFICATION.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [PROGRESS_REPORT.md](PROGRESS_REPORT.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [rdc_format_spec.md](rdc_format_spec.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [RDC_STRUCTURE_DEEP_ANALYSIS.md](RDC_STRUCTURE_DEEP_ANALYSIS.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [REFACTOR_ANALYSIS.md](REFACTOR_ANALYSIS.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [TODO.md](TODO.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
| [UNITY_EXPORT.md](UNITY_EXPORT.md) | 未标注（原因：源文档无 WHAT 段） | 未标注（原因：源文档无关键词段） |
