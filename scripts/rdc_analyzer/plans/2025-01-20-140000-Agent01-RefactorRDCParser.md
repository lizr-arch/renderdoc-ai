# TASK-R01: rdc_parser.py 拆分重构计划

> **Created**: 2025-01-20 14:00:00  
> **Agent**: Agent01  
> **Status**: In Progress

## Scope

将 `rdc_parser.py` (2899行) 拆分为模块化的 `parsers/` 包，提高可维护性和可测试性。

## Assumptions

1. 保持公开 API 向后兼容 (`parse_rdc`, `extract_shaders`, `extract_textures` 等)
2. 不改变解析逻辑，仅重组代码结构
3. 原文件最终改为薄 wrapper，导入新模块

## Source Structure Analysis

| 行号范围 | 内容 | 行数 | 目标文件 |
|---------|------|-----|---------|
| L19-87 | 常量 (RDC_MAGIC, SPIRV_*, CHUNK_*) | ~70 | `parsers/constants.py` |
| L88-397 | 枚举 (VulkanChunk, VkFormat, SectionType等) | ~310 | `parsers/enums.py` |
| L405-545 | 基础数据类 (FileHeader, SectionInfo, ChunkInfo等) | ~140 | `parsers/models/base.py` |
| L548-922 | ShaderInfo + ShaderResource | ~375 | `parsers/models/shader.py` |
| L923-1065 | TextureInfo | ~143 | `parsers/models/texture.py` |
| L1066-1107 | RDCFileInfo | ~42 | `parsers/models/rdc_file.py` |
| L1113-1175 | RDCParser: IO helpers | ~62 | `parsers/io_utils.py` |
| L1176-1420 | RDCParser: Header/Section parsing | ~245 | `parsers/section_parser.py` |
| L1471-1575 | RDCParser: Chunk parsing | ~105 | `parsers/chunk_parser.py` |
| L1575-1730 | RDCParser: Shader extraction | ~155 | `parsers/shader_extractor.py` |
| L1730-2430 | RDCParser: Texture extraction | ~700 | `parsers/texture_extractor.py` |
| L2432-2760 | RDCParser: Draw events | ~328 | `parsers/draw_event_parser.py` |
| L2765-2899 | 工具函数 | ~135 | `parsers/__init__.py` |

## Target Directory Structure

```
scripts/rdc_analyzer/
├── rdc_parser.py           # 薄 wrapper，兼容性导入
└── parsers/
    ├── __init__.py         # 公开 API: parse_rdc, extract_shaders, etc.
    ├── constants.py        # RDC/SPIRV 常量
    ├── enums.py            # VulkanChunk, VkFormat, SectionType 等
    ├── io_utils.py         # BinaryReader 辅助类
    ├── models/
    │   ├── __init__.py     # 导出所有 model
    │   ├── base.py         # FileHeader, SectionInfo, ChunkInfo
    │   ├── shader.py       # ShaderInfo, ShaderResource, SPIRVEntryPoint
    │   ├── texture.py      # TextureInfo
    │   └── rdc_file.py     # RDCFileInfo
    ├── section_parser.py   # Section 头和数据解析
    ├── chunk_parser.py     # Chunk 头解析
    ├── shader_extractor.py # SPIR-V 提取逻辑
    ├── texture_extractor.py# vkCreateImage 解析
    ├── draw_event_parser.py# Draw/Dispatch 事件解析
    └── rdc_parser.py       # 精简版 RDCParser 类 (组合各模块)
```

## Task Checklist

### Step 1: 创建目录结构 (~2min)
- [ ] 创建 `parsers/` 目录
- [ ] 创建 `parsers/models/` 子目录
- [ ] 创建各空文件占位

### Step 2: 提取常量 (~3min)
- [ ] 创建 `parsers/constants.py`，移入 L19-87
- [ ] 添加必要的 import

### Step 3: 提取枚举 (~5min)
- [ ] 创建 `parsers/enums.py`，移入 L88-397
- [ ] 添加对 constants.py 的导入

### Step 4: 提取基础模型 (~5min)
- [ ] 创建 `parsers/models/base.py`，移入 FileHeader, SectionInfo, ChunkInfo 等
- [ ] 创建 `parsers/models/__init__.py` 导出

### Step 5: 提取 Shader 模型 (~5min)
- [ ] 创建 `parsers/models/shader.py`，移入 ShaderInfo, ShaderResource, SPIRVEntryPoint
- [ ] 更新 `parsers/models/__init__.py`

### Step 6: 提取 Texture 模型 (~3min)
- [ ] 创建 `parsers/models/texture.py`，移入 TextureInfo

### Step 7: 提取 RDCFileInfo (~2min)
- [ ] 创建 `parsers/models/rdc_file.py`

### Step 8: 创建 IO 工具类 (~5min)
- [ ] 创建 `parsers/io_utils.py`，提取 BinaryReader 辅助方法

### Step 9: 提取 Section Parser (~5min)
- [ ] 创建 `parsers/section_parser.py`

### Step 10: 提取 Chunk Parser (~5min)
- [ ] 创建 `parsers/chunk_parser.py`

### Step 11: 提取 Shader Extractor (~10min)
- [ ] 创建 `parsers/shader_extractor.py`

### Step 12: 提取 Texture Extractor (~15min)
- [ ] 创建 `parsers/texture_extractor.py` (最复杂的部分)

### Step 13: 提取 Draw Event Parser (~10min)
- [ ] 创建 `parsers/draw_event_parser.py`

### Step 14: 创建精简版 RDCParser (~10min)
- [ ] 创建 `parsers/rdc_parser.py`，组合各模块

### Step 15: 创建公开 API (~5min)
- [ ] 创建 `parsers/__init__.py`，导出公开函数

### Step 16: 更新原文件为 wrapper (~3min)
- [ ] 修改原 `rdc_parser.py` 为薄 wrapper

### Step 17: 验证 (~5min)
- [ ] 运行测试确保功能正常
- [ ] 确认导入路径正确

## Risks / Blockers

1. **循环导入**: models 之间可能有相互引用，需要延迟导入或重组
2. **类型注解**: 需要使用 `TYPE_CHECKING` 或字符串形式
3. **测试覆盖**: 当前缺少单元测试，重构后需补充

## Verification / Acceptance (Definition of Done)

1. `py -3 -c "from parsers import parse_rdc, extract_shaders"` 无报错
2. 原 `rdc_parser.py` 的导入仍可用（向后兼容）
3. 现有调用方（如 `simple_analyzer.py`）无需修改

## Next Steps

开始执行 Step 1-3，创建目录结构和提取常量/枚举。

---

## Execution Log

*（执行过程中更新）*
