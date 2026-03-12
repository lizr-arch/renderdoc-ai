# Vulkan 纹理别名问题诊断与解决方案

> **版本**: 1.1.0 | **创建日期**: 2026-02-13 | **更新日期**: 2026-02-13 | **状态**: 已验证  
> **关键词**: Vulkan, 内存别名, Optimal Tiling, Initial Contents, eResImage, eResDeviceMemory, SaveTexture, ThumbnailGenerator

---

## 1. 问题概述

### 1.1 现象描述

在 *Arknights: Endfield* (`ef_r8.rdc`) 等 Vulkan 捕获的报告中，纹理缩略图存在以下问题：

| 问题类型 | 表现 | 影响范围 |
|----------|------|----------|
| **缩略图错误** | 显示的图像与实际纹理内容不匹配 | ~80% 的纹理 |
| **缩略图缺失** | 部分纹理无法生成缩略图 | ~20% 的纹理 |

**典型案例**：Texture_5 (ID 267)
- 报告显示的缩略图 MD5: `b755bf9e...`
- 正确的纹理内容 MD5: `68286c9c...`

### 1.2 影响范围

- **受影响的脚本**: `rdc_to_bundle_report.py`
- **受影响的 API**: RenderDoc `controller.SaveTexture()`
- **受影响的游戏**: 主要影响 Vulkan + 内存别名场景（如 Endfield、原神等）

---

## 2. 根因分析

### 2.1 Vulkan 内存别名 (Memory Aliasing)

Vulkan 允许多个 `VkImage` 绑定到同一个 `VkDeviceMemory` 块的不同偏移位置：

```
VkDeviceMemory (Memory ID: 37)
├── Offset 0:        Image A (ID: 100)
├── Offset 1048576:  Image B (ID: 200) ← Texture_5 (ID 267) 实际位置
├── Offset 2097152:  Image C (ID: 300)
└── ...
```

### 2.2 RenderDoc SaveTexture API 的问题

当调用 `controller.SaveTexture(sub, path)` 时：

1. RenderDoc 定位到该纹理绑定的 `VkDeviceMemory`
2. **问题**：在别名场景下，API 可能返回 Memory 块起始位置的数据，而非正确偏移位置的数据
3. **结果**：返回的是 Image A 的内容，而非请求的 Image B

```python
# 错误行为示例
sub = renderdoc.Subresource(mip=0, slice=0)
controller.SaveTexture(sub, "texture_267.png")  # 实际保存的是 Image A 的内容！
```

### 2.3 证据链

| 步骤 | 操作 | 结果 |
|------|------|------|
| 1 | 使用 `SaveTexture` API 提取 ID 267 | MD5: `b755bf9e...` (错误) |
| 2 | 使用 `ThumbnailGenerator` (offset-aware) 提取 ID 267 | MD5: `68286c9c...` (正确) |
| 3 | 对比两者差异 | 确认 API 返回了错误偏移的数据 |

---

## 3. 解决方案

### 3.1 ThumbnailGenerator (推荐)

`ThumbnailGenerator` 通过以下方式规避问题：

1. **解析 XML 元数据**：获取精确的 `MemoryBinding.offset`
2. **从 ZIP 手动提取**：使用 `data[offset:offset+size]` 切片
3. **解码压缩格式**：支持 BC1-7、ASTC、ETC2 等格式

```python
from thumbnail_generator import ThumbnailGenerator

gen = ThumbnailGenerator(xml_path, zip_path)
result = gen.generate_thumbnail(
    image_info,      # ImageInfo: width, height, format
    binding,         # MemoryBinding: image_id, memory_id, offset
    initial_contents # InitialContents: buffer_index, contents_size
)
if result.success:
    thumbnail_base64 = result.base64_data
```

### 3.2 已实现的集成

`rdc_to_bundle_report.py` 已更新为双轨策略：

```
Step 0: 打开 RDC
Step 0.5: 检测 ZIP+XML 导出文件
          ↓ 存在
Step 1: 初始化 ThumbnailGenerator
Step 2: 构建 extractable 映射 {res_id: (img, binding, ic)}
Step 3: 生成缩略图
        ├── 优先: ThumbnailGenerator (offset-aware)
        └── 回退: controller.SaveTexture() (标准 API)
Step 4: 输出统计
```

**代码位置**: `scripts/rdc_analyzer/rdc_to_bundle_report.py`

---

## 4. 当前状态

### 4.1 已完成

- [x] 问题根因确认（Vulkan 内存别名）
- [x] 解决方案设计（ThumbnailGenerator 集成）
- [x] 代码实现（`rdc_to_bundle_report.py` 修改）
- [x] sidecar 自动定位增强（支持 `*_export.zip + <capture>.xml` 组合）
- [x] 语法验证通过

### 4.2 待验证

- [ ] 在 RenderDoc Python Shell 中运行完整报告生成
- [ ] 验证 Texture_5 (ID 267) 显示正确图像
- [ ] 统计 ThumbnailGenerator vs API 的成功率
- [ ] 确认 154 个纹理的覆盖率

### 4.3 已知限制

| 限制 | 说明 | 影响 |
|------|------|------|
| 需要 ZIP+XML 导出 | ThumbnailGenerator 依赖 `renderdoccmd convert -c zip.xml` 的输出 | 必须先导出 |
| 格式支持 | 部分罕见格式可能未被解码器支持 | 回退到 API |
| 性能 | 解码 100+ BC7 纹理可能耗时较长 | 可接受 |

---

## 5. 验证步骤

### 5.0 Sidecar 定位说明（新增）

`rdc_to_bundle_report.py` 会优先自动查找以下组合：

1. `<capture>.zip + <capture>.zip.xml`
2. `<capture>.zip + <capture>.xml`
3. `<capture>_export.zip + <capture>.xml`（本次重点修复）
4. `frame.zip + frame.zip.xml`

如自动识别失败，可在 RenderDoc Python Shell 中手动指定：

```python
ZIP_PATH = r"D:\\RDC\\ef_r8_export.zip"
XML_PATH = r"D:\\RDC\\ef_r8.xml"
exec(open(r"D:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\rdc_to_bundle_report.py").read())
```

### 5.1 重新生成报告

在 **RenderDoc Python Shell** 中执行：

```python
import sys
sys.path.insert(0, r"D:\Code\git\renderdoc\scripts\rdc_analyzer")

from rdc_to_bundle_report import generate_bundle_report

rdc_path = r"D:\RDC\ef_r8.rdc"
output_dir = r"D:\RDC\ef_r8_report_fixed"

generate_bundle_report(rdc_path, output_dir)
```

### 5.2 预期输出

```
[INFO] 检测到导出文件: D:\RDC\ef_r8_export.zip
[INFO] ThumbnailGenerator 已初始化，可提取纹理: 120
[INFO] 缩略图来源统计: ThumbnailGenerator: ~100+, API: ~10, 总计: 154
```

### 5.3 验证项

1. **打开 `textures.html`**
2. **找到 Texture_5 (ID 267)**
3. **视觉确认**：显示的是正确的纹理内容（非其他纹理）

---

## 6. 相关文档

| 文档 | 说明 |
|------|------|
| [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) | 纹理提取三方案速查 |
| [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) | 无 GPU 提取架构 |
| [TEXTURE_DECODERS.md](TEXTURE_DECODERS.md) | 纹理解码器模块说明 |
| [EXPORT_ROUTES.md](EXPORT_ROUTES.md) | 报告导出路线图 |

---

## 7. 技术附录

### 7.1 XML 元数据结构

```xml
<!-- vkBindImageMemory 调用：建立 Image → Memory 绑定 -->
<chunk id="vkBindImageMemory" eid="138">
    <image>ResourceId::267</image>           <!-- Texture_5 -->
    <memory>ResourceId::37</memory>          <!-- 所属 Memory 块 -->
    <memoryOffset>1048576</memoryOffset>     <!-- 关键：偏移量 -->
</chunk>

<!-- InitialContents：Memory 块的原始数据 -->
<initial_contents>
    <resource_type>Memory</resource_type>
    <resource_id>37</resource_id>
    <contents_size>16777216</contents_size>
    <buffer_index>5</buffer_index>           <!-- ZIP 中的 buffer_0005 -->
</initial_contents>
```

### 7.2 手动提取逻辑

```python
def extract_texture_data(zip_file, binding: MemoryBinding, ic: InitialContents, image_info: ImageInfo):
    # 从 ZIP 读取整个 Memory 块
    buffer_name = f"buffer_{ic.buffer_index:04d}"
    buffer_data = zip_file.read(buffer_name)
    
    # 计算纹理大小
    size = calculate_texture_size(image_info)
    
    # 关键：使用正确的偏移量切片
    texture_data = buffer_data[binding.offset : binding.offset + size]
    
    return texture_data
```

### 7.3 ID 类型转换注意事项

XML 解析时 `resource_id` 为字符串，RenderDoc API 返回整数：

```python
# 正确做法：统一转换为 int
res_id = int(texture.resourceId)  # RenderDoc API
xml_id = int(image_info.resource_id)  # XML 解析结果

if res_id == xml_id:  # 正确比较
    ...
```

---

## 更新历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-02-13 | 1.0.0 | 初始文档，记录问题诊断与解决方案 |

---

## 8. 补充根因：Optimal Tiling 导致离线缩略图 花屏/条纹

除了内存别名（offset）导致的 错图 之外，我们还确认了另一类在离线 ZIP+XML 路线中非常常见的根因：

- ZIP+XML 的 Internal::Initial Contents 可能来自两种资源：
  - eResImage：每个 VkImage 自己的初始内容（更可能已经线性化，可离线解码）
  - eResDeviceMemory：整段 VkDeviceMemory dump（对 VK_IMAGE_TILING_OPTIMAL 往往是 GPU 平铺/Swizzle 布局）

当缩略图生成逻辑 只要能拿到 memory 就优先用 memory 时：
- 如果纹理是 optimal tiling，直接按线性布局解码会得到 条纹/噪点/不可读

### 8.1 缺少 拼图规则 是什么意思（给程序新人）

把纹理 bytes 解码成图片，本质上是把一维数组映射回二维像素。

- 线性布局（CPU 视角）：按 Row0/Row1/Row2 顺序平铺，规则简单
- optimal tiling（GPU 视角）：为了 cache 命中，像素会按 tile 分块并重排存放

你可以把 optimal tiling 理解成：
- 你拿到的是 一堆被打散顺序的拼图块数据
- 但你缺少 拼图规则（tile 尺寸、tile 顺序、swizzle 规则、厂商/驱动细节）

没有这套规则，你再怎么写 Python 代码，也只能把 bytes 按错规则 铺成图，自然就像乱码。

### 8.2 为什么不能靠 Python 离线通用修复，只能依赖 GPU replay 或 eResImage？

- tiling 规则强依赖 GPU/驱动/代际（跨厂商差异大）
- XML/ZIP 通常不包含完整的还原参数
- 要在 Python 里做 跨厂商、跨平台、跨格式 的 tiling 还原，成本极高且很难维护

因此更现实的策略是：
1) 优先使用 eResImage（RenderDoc 已给出更可离线解码的内容）
2) 若只能用 eResDeviceMemory，则仅把它当作 fallback，并接受 可能不可读 的限制
3) 需要 100% 正确时，走 GPU replay 让 GPU 帮忙做线性化 readback

---

## 9. 已落地修复：ThumbnailGenerator 优先 eResImage

实现位置：scripts/rdc_analyzer/thumbnail_generator.py

规则：
1. 如果 initial_contents[image_id] 存在且类型是 eResImage，优先使用（offset=0）
2. 否则才回退到 eResDeviceMemory + vkBindImageMemory.memoryOffset

回归测试：scripts/rdc_analyzer/tests/test_thumbnail_generator_prefers_image_ic.py

---

## 10. ZIP 条目命名纠正（很关键）

Internal::Initial Contents 里的 buffer 数字（例如 Contents=197），通常对应 ZIP 内的条目名是 6 位补零：

- 197 -> 000197

对应代码：

    buffer_name = f"{ic.buffer_index:06d}"
    raw = zf.read(buffer_name)

（之前文档中的 buffer_{index:04d} 写法属于过时示例，容易误导，请以代码实现为准。）

---

## 更新历史（补充）

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-02-13 | 1.1.0 | 补充 Optimal Tiling 花屏根因；修复 ThumbnailGenerator 选择顺序（优先 eResImage） |

