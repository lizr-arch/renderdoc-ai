# 为什么 Vulkan 的 XML+ZIP 缩略图不可读（新手版）

**目标读者**：刚接触 RenderDoc / 图形调试的程序新人  
**结论一句话**：Vulkan 的 XML+ZIP 导出只给了“显存里的原料数据”，没有“拼图规则”，所以解码出来就是噪点。

---

## 1. 用最通俗的比喻

把纹理想象成一张大图：

- **可直接查看的图**：像素是“一行一行排好”的。
- **Vulkan 的 OPTIMAL TILING**：为了 GPU 速度，把图切成很多块，乱序放进显存。

**XML+ZIP 只导出了这些“乱序显存块”**，没有告诉你怎么拼回去。  
所以你拿它去当正常图片解码，结果一定是噪点。

---

## 2. 关键事实（来自源码与实测）

### ✅ 实测样本
`D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.zip.xml`

### ✅ Vulkan Capture
检测 API 类型为 **Vulkan**。

### ✅ 全部为 OPTIMAL TILING
所有 `vkCreateImage` 的 tiling 均为 `VK_IMAGE_TILING_OPTIMAL`。

**含义：显存布局是 GPU 专用的非线性布局。**

### ✅ XML 里没有 per-image 的 rowPitch / 子资源布局
XML 里唯一的 “RowPitch” 是设备属性 `optimalBufferCopyRowPitchAlignment`，  
并不是每个纹理各自的行对齐信息。

**含义：CPU 无法知道怎么把显存里的块拼成一张正常图。**

### ✅ 当前解码器假设输入是“紧凑线性数据”
解码接口只接受 `(data, width, height, format)`，  
默认认为 `data` 是“一行一行排好的像素”。

**但 Vulkan 的 XML+ZIP 给的不是这种数据。**

---

## 3. 为什么这一定会失败？

因为 Vulkan 的显存布局是 **GPU 优化格式**：

- 对 GPU 来说：快
- 对 CPU 来说：不可直接阅读

XML+ZIP 缺少 “拼图规则”，解码器只会把“乱序块”当作“整齐像素行”。
所以结果必然是噪点。

---

## 4. 那正确的方式是什么？

要得到**可读缩略图**，必须走 **Replay / SaveTexture**：

- `renderdoccmd export` 会回放 GPU 并生成标准图片
- 这一步会把 GPU 的非线性布局转换为线性像素

所以：

✅ **Vulkan → 必须用 renderdoccmd export**  
❌ **Vulkan XML+ZIP → 无法直接生成可读图**

---

## 5. D3D11 的情况不同

D3D11 XML 通常包含 rowPitch（行对齐信息），
因此**通过正确处理 rowPitch，可以得到可读图**。

更直白的说，D3D11 的纹理初始数据通常来自 CPU 上传：

- 数据是**线性排列**的（只是每行可能有 padding）。
- XML 能告诉你**每行真实占用多少字节（rowPitch）**。
- 所以你可以用 Python 做一件很简单的事：
  - 每行只取 `真实像素宽度` 对应的字节
  - 把 padding 丢掉
  - 行与行拼起来，就能得到正确图像

对比 Vulkan：

- Vulkan 的 OPTIMAL TILING 是**显卡私有布局**，不是“线性 + padding”。
- XML+ZIP **不提供** per-image 的 rowPitch / subresource layout。
- 你不知道 tile 怎么排、怎么拼，Python 也无从下手。

结论：
- **D3D11：XML+ZIP 有修复价值**
- **Vulkan：XML+ZIP 基本无解（结构性缺失）**

---

## 6. 示意图（概念）

**D3D11（线性 + padding，可修）**

```
显存/文件里的数据:
[Row0 像素][padding][Row1 像素][padding][Row2 像素][padding]...

Python 的修复做法:
Row0 取前 width*bpp 字节
Row1 取前 width*bpp 字节
Row2 取前 width*bpp 字节
拼起来 -> 得到正常图像
```

**Vulkan OPTIMAL TILING（GPU 私有布局，不可修）**

```
图像应有的顺序 (2x2 tiles):
T1 T2
T3 T4

显存里实际顺序 (厂商私有):
T3 T1 T4 T2 ...

XML+ZIP 没告诉我们：
T1/T2/T3/T4 的真实映射关系
=> CPU 无法还原
```

**更直观的 4x4 ASCII 示意（同一块图，顺序被打乱）**

```
理想顺序（线性）:
[A][A][B][B]
[A][A][B][B]
[C][C][D][D]
[C][C][D][D]

显存顺序（OPTIMAL，示意）:
[C][C][A][A]
[C][C][A][A]
[D][D][B][B]
[D][D][B][B]

缺少“拼图规则” = 不知道 A/B/C/D 的真实位置
```

---

## 7. 流程图（文本版）

```
RDC (Vulkan)
   |
   | renderdoccmd convert -c zip.xml
   v
XML+ZIP (raw GPU memory)
   |
   | CPU 解码 (假设线性)
   v
噪点 / 不可读  <--- 缺少拼图规则 (tiling / swizzle / layout)
   |
   | 需要 GPU replay
   v
renderdoccmd export (SaveTexture)
   |
   v
可读缩略图
```

---

## 8. 来源与证据

- RenderDoc CLI Export 输出含 `textures.json`：`renderdoccmd/renderdoccmd.cpp:656`  
- 解码器接口假设线性数据：`scripts/rdc_analyzer/decoders/texture_decoder.py:269`
- Vulkan XML 采样结果（tiling=OPTIMAL）：`scripts/_tmp_inspect_zipxml.py`

> 注：MCP 文档检索未发现官方说明（search_docs=0），结论来自本地源码 + 实测数据。
