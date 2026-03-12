# RDC 数据示例：一个游戏场景的完整解析

> **版本**: 1.0 | **更新**: 2025-01-31 | **前置阅读**: [02_RDC_STRUCTURE.md](./02_RDC_STRUCTURE.md)
>
> **阅读时间**: 15 分钟

---

## 一、场景设定

假设我们在玩一个简单的 3D 游戏，当前画面是：

```
┌─────────────────────────────────────────┐
│                天空盒                    │
│         ☁️           ☁️                  │
│                 🌄                       │
│  ┌────────────────────────────────────┐ │
│  │        地形 (草地+山丘)             │ │
│  │                                    │ │
│  │      🧍 玩家角色                    │ │
│  │       ↳ 持枪 🔫                    │ │
│  │                ✨ 粒子特效          │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

这一帧画面包含 **5 个渲染对象**：

| 对象 | 三角形数量 | 纹理 | 说明 |
|------|-----------|------|------|
| 天空盒 | 12 | 1 张 Cubemap (6 面) | 背景天空 |
| 地形 | 50,000 | 2 张 (草地 + 岩石) | 大面积地面 |
| 玩家角色 | 8,000 | 3 张 (皮肤/衣服/头发) | 主角模型 |
| 武器 | 2,000 | 1 张 (金属) | 角色手中的枪 |
| 粒子特效 | 1,000 | 1 张 (火花) | 射击后的效果 |

**合计**：约 61,012 个三角形，8 张纹理

---

## 二、GPU 命令序列（Chunk 列表）

当游戏渲染这一帧时，发送给 GPU 的命令大概是这样的：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 事件ID │ Chunk 类型              │ 参数                                 │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│   1    │ vkCmdBeginRenderPass   │ 开始主渲染通道                        │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│   2    │ vkCmdBindPipeline      │ 选择"天空盒"着色器管线                │
│   3    │ vkCmdBindDescriptorSets│ 绑定天空盒 Cubemap 纹理               │
│   4    │ vkCmdDraw              │ 画 12 个三角形 (36 顶点)             │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│   5    │ vkCmdBindPipeline      │ 选择"地形"着色器管线                  │
│   6    │ vkCmdBindDescriptorSets│ 绑定草地+岩石纹理                     │
│   7    │ vkCmdBindVertexBuffers │ 绑定地形顶点数据                      │
│   8    │ vkCmdBindIndexBuffer   │ 绑定地形索引数据                      │
│   9    │ vkCmdDrawIndexed       │ 画 50,000 个三角形                   │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│  10    │ vkCmdBindPipeline      │ 选择"角色"着色器管线                  │
│  11    │ vkCmdPushConstants     │ 传入角色世界矩阵                      │
│  12    │ vkCmdBindDescriptorSets│ 绑定角色纹理 (皮肤/衣服/头发)         │
│  13    │ vkCmdDrawIndexed       │ 画 8,000 个三角形 (角色)             │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│  14    │ vkCmdPushConstants     │ 传入武器世界矩阵                      │
│  15    │ vkCmdBindDescriptorSets│ 绑定武器纹理                          │
│  16    │ vkCmdDrawIndexed       │ 画 2,000 个三角形 (武器)             │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│  17    │ vkCmdBindPipeline      │ 选择"粒子"着色器管线 (半透明)         │
│  18    │ vkCmdBindDescriptorSets│ 绑定火花纹理                          │
│  19    │ vkCmdDraw              │ 画 1,000 个三角形 (粒子)             │
├────────┼─────────────────────────┼──────────────────────────────────────┤
│  20    │ vkCmdEndRenderPass     │ 结束主渲染通道                        │
└────────┴─────────────────────────┴──────────────────────────────────────┘
```

---

## 三、单个 Chunk 的详细数据

让我们看看 **事件 #9** `vkCmdDrawIndexed`（画地形）的详细参数：

### Chunk 二进制结构

```
┌──────────────────────────────────────────────────────────────────┐
│  Chunk Header                                                    │
│  ├── ChunkID: 0x1234 (vkCmdDrawIndexed)                          │
│  └── Flags: 0x0001                                               │
├──────────────────────────────────────────────────────────────────┤
│  Length: 20 字节                                                 │
├──────────────────────────────────────────────────────────────────┤
│  Data:                                                           │
│  ├── indexCount:    150000  (4字节) ← 150000 ÷ 3 = 50000 三角形  │
│  ├── instanceCount: 1       (4字节) ← 实例数量                   │
│  ├── firstIndex:    0       (4字节) ← 从第 0 个索引开始          │
│  ├── vertexOffset:  0       (4字节) ← 顶点偏移                   │
│  └── firstInstance: 0       (4字节) ← 第一个实例 ID              │
└──────────────────────────────────────────────────────────────────┘
```

### 用十六进制表示

```
地址        00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F
─────────────────────────────────────────────────────────────
00000000    34 12 01 00                                        ← ChunkID + Flags
00000004    14 00 00 00                                        ← Length = 20
00000008    B0 49 02 00                                        ← indexCount = 150000
0000000C    01 00 00 00                                        ← instanceCount = 1
00000010    00 00 00 00                                        ← firstIndex = 0
00000014    00 00 00 00                                        ← vertexOffset = 0
00000018    00 00 00 00                                        ← firstInstance = 0
```

---

## 四、RDC 转换为 XML 后的样子

当我们用 `renderdoccmd convert -c xml` 把 RDC 转成 XML 后：

```xml
<?xml version="1.0" encoding="utf-8"?>
<rdc version="1.2">
  <chunks>
    <!-- 事件 1: 开始渲染 -->
    <chunk id="1" name="vkCmdBeginRenderPass">
      <renderPass handle="0x12345678"/>
      <framebuffer width="1920" height="1080"/>
      <clearColor r="0.2" g="0.3" b="0.5" a="1.0"/>
    </chunk>
    
    <!-- 事件 2-4: 天空盒 -->
    <chunk id="2" name="vkCmdBindPipeline">
      <pipeline handle="0xAAAA0001" name="Skybox_Pipeline"/>
    </chunk>
    <chunk id="3" name="vkCmdBindDescriptorSets">
      <set index="0">
        <binding slot="0" type="CombinedImageSampler">
          <texture handle="0xBBBB0001" name="sky_cubemap"/>
        </binding>
      </set>
    </chunk>
    <chunk id="4" name="vkCmdDraw">
      <vertexCount>36</vertexCount>
      <instanceCount>1</instanceCount>
      <!-- 36 ÷ 3 = 12 个三角形 -->
    </chunk>
    
    <!-- 事件 5-9: 地形 -->
    <chunk id="5" name="vkCmdBindPipeline">
      <pipeline handle="0xAAAA0002" name="Terrain_Pipeline"/>
    </chunk>
    <chunk id="6" name="vkCmdBindDescriptorSets">
      <set index="0">
        <binding slot="0" type="CombinedImageSampler">
          <texture handle="0xBBBB0002" name="grass_albedo" 
                   width="2048" height="2048" format="BC7"/>
        </binding>
        <binding slot="1" type="CombinedImageSampler">
          <texture handle="0xBBBB0003" name="rock_albedo"
                   width="2048" height="2048" format="BC7"/>
        </binding>
      </set>
    </chunk>
    <chunk id="9" name="vkCmdDrawIndexed">
      <indexCount>150000</indexCount>
      <instanceCount>1</instanceCount>
      <firstIndex>0</firstIndex>
      <!-- 150000 ÷ 3 = 50000 个三角形 -->
    </chunk>
    
    <!-- 事件 10-13: 角色 -->
    <chunk id="10" name="vkCmdBindPipeline">
      <pipeline handle="0xAAAA0003" name="Character_PBR_Pipeline"/>
    </chunk>
    <chunk id="11" name="vkCmdPushConstants">
      <data name="ModelMatrix">
        <m00>1.0</m00><m01>0.0</m01><m02>0.0</m02><m03>0.0</m03>
        <m10>0.0</m10><m11>1.0</m11><m12>0.0</m12><m13>0.0</m13>
        <m20>0.0</m20><m21>0.0</m21><m22>1.0</m22><m23>0.0</m23>
        <m30>10.5</m30><m31>0.0</m31><m32>-5.2</m32><m33>1.0</m33>
        <!-- 角色位置: X=10.5, Y=0, Z=-5.2 -->
      </data>
    </chunk>
    <chunk id="12" name="vkCmdBindDescriptorSets">
      <set index="0">
        <binding slot="0">
          <texture handle="0xBBBB0004" name="character_skin"/>
        </binding>
        <binding slot="1">
          <texture handle="0xBBBB0005" name="character_clothes"/>
        </binding>
        <binding slot="2">
          <texture handle="0xBBBB0006" name="character_hair"/>
        </binding>
      </set>
    </chunk>
    <chunk id="13" name="vkCmdDrawIndexed">
      <indexCount>24000</indexCount>
      <!-- 24000 ÷ 3 = 8000 个三角形 -->
    </chunk>
    
    <!-- ... 更多事件 ... -->
    
  </chunks>
</rdc>
```

---

## 五、分析后的 JSON 报告

如果我们用 Python 脚本分析这个 RDC，最终输出的报告可能是这样的：

```json
{
  "summary": {
    "captureFile": "game_frame_001.rdc",
    "captureTime": "2025-01-31 14:30:00",
    "graphicsAPI": "Vulkan",
    "resolution": {
      "width": 1920,
      "height": 1080
    }
  },
  
  "statistics": {
    "totalDrawCalls": 5,
    "totalTriangles": 61012,
    "totalVertices": 183036,
    "renderPassCount": 1
  },
  
  "drawCalls": [
    {
      "eventId": 4,
      "name": "Draw Skybox",
      "pipeline": "Skybox_Pipeline",
      "triangles": 12,
      "textures": ["sky_cubemap"]
    },
    {
      "eventId": 9,
      "name": "Draw Terrain",
      "pipeline": "Terrain_Pipeline",
      "triangles": 50000,
      "textures": ["grass_albedo", "rock_albedo"]
    },
    {
      "eventId": 13,
      "name": "Draw Character",
      "pipeline": "Character_PBR_Pipeline",
      "triangles": 8000,
      "textures": ["character_skin", "character_clothes", "character_hair"]
    },
    {
      "eventId": 16,
      "name": "Draw Weapon",
      "pipeline": "Character_PBR_Pipeline",
      "triangles": 2000,
      "textures": ["weapon_metal"]
    },
    {
      "eventId": 19,
      "name": "Draw Particles",
      "pipeline": "Particle_Additive_Pipeline",
      "triangles": 1000,
      "textures": ["spark_texture"]
    }
  ],
  
  "textures": [
    {
      "id": "0xBBBB0001",
      "name": "sky_cubemap",
      "type": "TextureCube",
      "width": 1024,
      "height": 1024,
      "format": "R8G8B8A8_SRGB",
      "memoryMB": 4.0
    },
    {
      "id": "0xBBBB0002",
      "name": "grass_albedo",
      "type": "Texture2D",
      "width": 2048,
      "height": 2048,
      "format": "BC7_SRGB",
      "memoryMB": 5.33
    },
    {
      "id": "0xBBBB0003",
      "name": "rock_albedo",
      "type": "Texture2D",
      "width": 2048,
      "height": 2048,
      "format": "BC7_SRGB",
      "memoryMB": 5.33
    }
  ],
  
  "performanceHints": [
    {
      "type": "warning",
      "message": "地形 Draw Call 绘制了 50000 个三角形，考虑使用 LOD 优化",
      "eventId": 9
    },
    {
      "type": "info",
      "message": "粒子使用了单独的 Render Pass，符合透明物体渲染最佳实践",
      "eventId": 19
    }
  ]
}
```

---

## 六、从二进制到 JSON 的流程图

```
┌─────────────────┐
│  game.rdc       │  (二进制文件，几十 MB)
│  - 压缩的       │
│  - 不可读      │
└────────┬────────┘
         │
         │ 步骤 1: renderdoccmd convert -c xml
         ▼
┌─────────────────┐
│  game.xml       │  (XML 文件，可能几百 MB)
│  - 可读         │
│  - 但太冗长     │
└────────┬────────┘
         │
         │ 步骤 2: Python 脚本解析
         ▼
┌─────────────────┐
│  analysis.json  │  (结构化数据)
│  - 统计信息     │
│  - 性能建议     │
│  - 资源列表     │
└────────┬────────┘
         │
         │ 步骤 3: 生成 HTML 报告
         ▼
┌─────────────────┐
│  report.html    │  (可视化报告)
│  - 图表         │
│  - 交互式       │
│  - 可分享       │
└─────────────────┘
```

---

## 七、实际操作命令

### 7.1 转换 RDC 为 XML

```powershell
# Windows PowerShell
renderdoccmd convert -c xml -o game.xml game.rdc

# 输出大小对比：
# game.rdc:   45 MB (压缩后)
# game.xml:  320 MB (解压 + 文本化)
```

### 7.2 快速统计三角形数量

```python
import xml.etree.ElementTree as ET

tree = ET.parse("game.xml")
root = tree.getroot()

total_triangles = 0
for chunk in root.findall(".//chunk"):
    name = chunk.get("name", "")
    if name in ["vkCmdDraw", "vkCmdDrawIndexed"]:
        # 获取顶点/索引数量
        index_count = chunk.findtext("indexCount")
        vertex_count = chunk.findtext("vertexCount")
        
        count = int(index_count or vertex_count or 0)
        triangles = count // 3
        total_triangles += triangles
        print(f"Event {chunk.get('id')}: {triangles} triangles")

print(f"\nTotal: {total_triangles} triangles")
```

输出：
```
Event 4: 12 triangles
Event 9: 50000 triangles
Event 13: 8000 triangles
Event 16: 2000 triangles
Event 19: 1000 triangles

Total: 61012 triangles
```

---

## 八、总结

| 阶段 | 数据形态 | 可读性 | 用途 |
|------|----------|--------|------|
| RDC 文件 | 压缩二进制 | ❌ 不可读 | 存储/传输 |
| Chunks 解压后 | 二进制流 | ⚠️ 需专业知识 | 底层调试 |
| XML 文件 | 文本标记 | ✅ 可读 | 详细分析 |
| JSON 报告 | 结构化数据 | ✅✅ 易理解 | 自动化/汇报 |
| HTML 报告 | 可视化 | ✅✅✅ 最友好 | 分享/展示 |

---

## 附录：资源 ID 对照表（本例）

| Handle | 名称 | 类型 |
|--------|------|------|
| 0xAAAA0001 | Skybox_Pipeline | Pipeline |
| 0xAAAA0002 | Terrain_Pipeline | Pipeline |
| 0xAAAA0003 | Character_PBR_Pipeline | Pipeline |
| 0xBBBB0001 | sky_cubemap | TextureCube |
| 0xBBBB0002 | grass_albedo | Texture2D |
| 0xBBBB0003 | rock_albedo | Texture2D |
| 0xBBBB0004 | character_skin | Texture2D |
| 0xBBBB0005 | character_clothes | Texture2D |
| 0xBBBB0006 | character_hair | Texture2D |
