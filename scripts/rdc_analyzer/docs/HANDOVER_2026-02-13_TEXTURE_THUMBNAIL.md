# 任务交接文档：Vulkan 纹理缩略图修复

> **创建日期**: 2026-02-13 12:30  
> **前序工作者**: Codex Agent (Claude)  
> **任务状态**: 代码完成，待验证  
> **紧急程度**: 高

---

## 1. 任务背景

### 1.1 用户原始需求
用户反馈 *Arknights: Endfield* (`ef_r8.rdc`) 的 HTML 报告中纹理缩略图存在问题：
1. 部分纹理无缩略图
2. **有缩略图的显示内容错误**（与实际纹理不匹配）

### 1.2 已确认的根本原因
**Vulkan 内存别名 (Memory Aliasing)**

- Vulkan 允许多个 `VkImage` 绑定到同一 `VkDeviceMemory` 块的不同偏移位置
- RenderDoc 的 `controller.SaveTexture()` API 在这种场景下会返回 Memory 块起始位置的数据
- 结果：请求纹理 B，却返回纹理 A 的内容

**证据**：
```
Texture ID 267 (Texture_5)
- SaveTexture API 输出的 MD5: b755bf9e... (错误)
- ThumbnailGenerator 输出的 MD5: 68286c9c... (正确)
```

---

## 2. 已完成的工作

### 2.1 代码修改

**文件**: `scripts/rdc_analyzer/rdc_to_bundle_report.py`

**修改内容**: 集成 `ThumbnailGenerator` 作为主要缩略图来源

```
Step 0: 打开 RDC
Step 0.5 (新增): 检测 ZIP+XML 导出文件
         ├── ef_r8_export.zip
         └── ef_r8.xml
Step 1 (新增): 初始化 ThumbnailGenerator
Step 2 (新增): 构建 extractable 映射 {res_id: (ImageInfo, MemoryBinding, InitialContents)}
Step 3: 生成缩略图
        ├── 优先: ThumbnailGenerator (offset-aware)
        └── 回退: controller.SaveTexture() (标准 API)
Step 4 (新增): 输出统计
```

**代码位置**: 约 Line 200-350（搜索 `# Step 0.5` 定位）

### 2.2 文档更新

| 文档 | 说明 |
|------|------|
| `docs/VULKAN_TEXTURE_ALIASING_ISSUE.md` | 完整的问题诊断文档 |
| `docs/INDEX.md` | 新增「问题诊断与调试」章节，更新至 v2.6.4 |

### 2.3 验证状态

| 验证项 | 状态 |
|--------|------|
| 语法检查 (`py_compile`) | ✅ 通过 |
| 单元测试 | ✅ 通过（pytest: 819 passed, 6 skipped） |
| 集成测试（headless xml_to_bundle） | ✅ 通过（Endfield sidecar，50/154 thumbnails） |
| 用户验收 | ⏳ 待用户视觉确认 |

---

## 3. 待完成的工作

### 3.1 【必须】在 RenderDoc Python Shell 中验证

**步骤**:
1. 打开 RenderDoc GUI
2. 加载 `D:\RDC\ef_r8.rdc`
3. 打开 Python Shell (Window → Python Shell)
4. 执行以下代码：

```python
import sys
sys.path.insert(0, r"D:\Code\git\renderdoc\scripts\rdc_analyzer")

from rdc_to_bundle_report import generate_bundle_report

rdc_path = r"D:\RDC\ef_r8.rdc"
output_dir = r"D:\RDC\ef_r8_report_fixed"

generate_bundle_report(rdc_path, output_dir)
```

**预期输出**:
```
[INFO] 检测到导出文件: D:\RDC\ef_r8_export.zip
[INFO] ThumbnailGenerator 已初始化，可提取纹理: ~120
[INFO] 缩略图来源统计: ThumbnailGenerator: ~100, API: ~20, 总计: 154
```

### 3.2 【必须】验证缩略图正确性

1. 打开 `D:\RDC\ef_r8_report_fixed\textures.html`
2. 找到 **Texture_5 (ID 267)**
3. 视觉确认：缩略图是否显示正确内容（应该是一个实际的游戏纹理，而非乱码/错误图像）
4. 抽查其他 5-10 个纹理

### 3.3 【可选】排查遗留问题

如果验证失败，可能的问题点：

| 问题 | 排查方向 |
|------|----------|
| `thumb_gen_extractable` 为空 | 检查 XML 解析是否成功，`_parse_vk_image()` 返回值 |
| ID 类型不匹配 | 确保 `int(res_id)` 统一转换 |
| ZIP 路径错误 | 检查 `{rdc_stem}_export.zip` 命名规则 |
| 解码失败 | 检查 `decoders.py` 是否支持该纹理格式 |

**调试代码**（在 RenderDoc Shell 中执行）:
```python
from thumbnail_generator import ThumbnailGenerator
import xml.etree.ElementTree as ET

xml_path = r"D:\RDC\ef_r8.xml"
zip_path = r"D:\RDC\ef_r8_export.zip"

gen = ThumbnailGenerator(xml_path, zip_path)

# 检查解析结果
print(f"Images: {len(gen.images)}")
print(f"Bindings: {len(gen.bindings)}")

image_to_binding = {b.image_id: b for b in gen.bindings}
print(f"InitialContents: {len(gen.initial_contents)}")

# 尝试生成单个缩略图
for img_id, img_info in list(gen.images.items())[:3]:
    binding = image_to_binding.get(img_id)
    if binding:
        ic = gen.initial_contents.get(binding.memory_id)
        if ic:
            result = gen.generate_thumbnail(img_info, binding, ic, max_size=128)
            print(f"ID {img_id}: success={result.success}, error={result.error}")
```

---

## 4. 关键文件清单

| 文件 | 用途 | 重要程度 |
|------|------|----------|
| `scripts/rdc_analyzer/rdc_to_bundle_report.py` | 报告生成主脚本（已修改） | ⭐⭐⭐ |
| `scripts/rdc_analyzer/thumbnail_generator.py` | 缩略图生成器（offset-aware） | ⭐⭐⭐ |
| `scripts/rdc_analyzer/decoders.py` | 纹理解码器（BC7/ASTC等） | ⭐⭐ |
| `scripts/rdc_analyzer/docs/VULKAN_TEXTURE_ALIASING_ISSUE.md` | 问题诊断文档 | ⭐⭐ |
| `D:\RDC\ef_r8.rdc` | 测试用 RDC 文件 | 测试数据 |
| `D:\RDC\ef_r8_export.zip` | 测试用 ZIP 导出 | 测试数据 |
| `D:\RDC\ef_r8.xml` | 测试用 XML 导出 | 测试数据 |

---

## 5. 技术要点速查

### 5.1 Vulkan 内存别名结构

```xml
<!-- vkBindImageMemory：建立 Image → Memory 绑定 -->
<chunk id="vkBindImageMemory">
    <image>ResourceId::267</image>      <!-- Texture ID -->
    <memory>ResourceId::37</memory>     <!-- Memory 块 ID -->
    <memoryOffset>1048576</memoryOffset> <!-- 关键：偏移量 -->
</chunk>

<!-- InitialContents：Memory 块数据位置 -->
<initial_contents>
    <resource_id>37</resource_id>
    <buffer_index>5</buffer_index>       <!-- ZIP 中的 buffer_0005 -->
</initial_contents>
```

### 5.2 正确的提取逻辑

```python
# 从 ZIP 读取 Memory 块
buffer_data = zip_file.read(f"buffer_{buffer_index:04d}")

# 使用正确的偏移量切片
texture_data = buffer_data[offset : offset + size]

# 解码压缩格式
rgba_data = decode_texture(texture_data, width, height, format)
```

### 5.3 ID 类型注意

```python
# XML 解析出的是 str
xml_id = "267"

# RenderDoc API 返回 int
api_id = 267

# 必须统一转换
if int(xml_id) == api_id:  # ✅ 正确
    pass
```

---

## 6. 项目上下文

### 6.1 MCP 工具
项目配置了 `RenderDocContext` MCP，可用于查询文档：
- `get_project_index` - 获取项目索引
- `search_docs` - 搜索文档
- `read_doc` - 读取文档

### 6.2 相关文档入口
- **文档索引**: `scripts/rdc_analyzer/docs/INDEX.md`
- **问题诊断**: `scripts/rdc_analyzer/docs/VULKAN_TEXTURE_ALIASING_ISSUE.md`
- **项目总配置**: `AGENTS.md`

### 6.3 测试数据位置
```
D:\RDC\
├── ef_r8.rdc           # 原始 RDC 捕获
├── ef_r8.xml           # XML 导出 (renderdoccmd convert -c xml)
├── ef_r8_export.zip    # ZIP 导出 (renderdoccmd convert -c zip.xml)
└── ef_r8_report_fixed/ # 输出目录（待生成）
```

---

## 7. 联系信息

如有疑问，可参考：
- 详细诊断文档: `docs/VULKAN_TEXTURE_ALIASING_ISSUE.md`
- 代码注释: `rdc_to_bundle_report.py` 中的 `# Step 0.5` 起始区块

---

**祝顺利！** 🚀

## 8. 2026-02-13 后续进展（方向3，已完成）

### 8.1 新发现的根因补充
在 zip.xml 导出里，Internal::Initial Contents 同时可能包含两类数据：
- eResImage：每个 VkImage 自己的初始内容（通常可离线解码）
- eResDeviceMemory：整段 VkDeviceMemory dump（对 VK_IMAGE_TILING_OPTIMAL 往往是 GPU 平铺布局）

旧逻辑只要拿到 memory 就优先用 memory，会导致两类问题：
- 错图：memory aliasing offset 用错或未命中
- 花屏条纹：把 optimal tiling 的 memory 当线性布局解码

### 8.2 已落地修复
- 文件：scripts/rdc_analyzer/thumbnail_generator.py
- 规则：优先 eResImage；缺失时再回退 eResDeviceMemory + binding offset
- 回归测试：scripts/rdc_analyzer/tests/test_thumbnail_generator_prefers_image_ic.py

### 8.3 Headless 验证结果（本机）
- py -3 -m pytest scripts/rdc_analyzer/tests/test_thumbnail_generator_prefers_image_ic.py -v --tb=short：通过
- py -3 -m pytest scripts/rdc_analyzer/tests -q：通过（819 passed, 6 skipped）
- 重新生成报告后，D:\backup\endfield_report\textures_data.json 中缩略图数量为 50/154（使用 --max-thumbnails 50）

### 8.4 视觉验收路径
- 打开 file:///D:/backup/endfield_report/textures.html
- 建议重点抽查：Texture_69 / Texture_70 及大尺寸 BC7 纹理

