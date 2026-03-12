# 🎯 纹理优化建议报告

**文件**: Game_capture.rdc
**生成时间**: 2026-01-18 18:50:28

---

## 📊 总览

| 指标 | 值 |
|------|-----|
| 优化建议总数 | 5 |
| 预计可节省 VRAM | **682.87 MB** |
| 按优先级 | HIGH: 3, MEDIUM: 2 |

## 🟠 高优先级 (强烈建议)

### 1. 压缩 24 个大尺寸未压缩纹理 *(可节省 264.42 MB)*

**类别**: 内存优化

检测到 24 个大于 256x256 的未压缩纹理。使用 BC7/BC3 等压缩格式可显著减少内存占用，同时保持较好的视觉质量。

**操作步骤**:
- [ ] 在纹理导入设置中启用压缩
- [ ] 推荐格式: BC7 (高质量) 或 BC1 (体积优先)
- [ ] 对于法线贴图使用 BC5
- [ ] 重新导入受影响的纹理

<details>
<summary>涉及资源 (24 个)</summary>

- `UI_Water_02 (256×256, R8G8B8A8_UNORM)`
- `UI_Metal_05 (256×256, R8G8B8A8_UNORM)`
- `UI_Water_06 (256×256, R8G8B8A8_UNORM)`
- `UI_Metal_08 (256×256, R8G8B8A8_UNORM)`
- `UI_Door_09 (256×256, R8G8B8A8_UNORM)`
- `UI_Brick_10 (256×256, R8G8B8A8_UNORM)`
- `UI_Cloud_13 (256×256, R8G8B8A8_UNORM)`
- `UI_Enemy_14 (256×256, R8G8B8A8_UNORM)`
- `UI_Debris_15 (256×256, R8G8B8A8_UNORM)`
- `ShadowMap_Fabric_00 (4096×4096, D32_FLOAT)`
- `ShadowMap_Boss_01 (4096×4096, D32_FLOAT)`
- `ShadowMap_Wood_02 (4096×4096, D32_FLOAT)`
- `ShadowMap_Crate_03 (2048×2048, D32_FLOAT)`
- `HDR_Hero_00_Cubemap (256×256, R16G16B16A16_FLOAT)`
- `HDR_Decal_01_Cubemap (256×256, R16G16B16A16_FLOAT)`
- `RT_Rock_00_Color (1920×1080, R11G11B10_FLOAT)`
- `RT_Hero_01_Color (1920×1080, R11G11B10_FLOAT)`
- `RT_Foliage_02_Color (1920×1080, R11G11B10_FLOAT)`
- `RT_FX_03_Color (1280×720, R11G11B10_FLOAT)`
- `RT_Floor_00_Depth (1920×1080, D24_UNORM_S8_UINT)`
- ... 还有 4 个
</details>

---

### 2. 移除 8 组重复纹理 *(可节省 185.87 MB)*

**类别**: 清理冗余

检测到 8 组内容完全相同但 ID 不同的纹理。这通常是资源导入流程重复或资源引用错误导致的。

**操作步骤**:
- [ ] 确认重复纹理是否应该共用同一资源
- [ ] 在资产管理系统中合并重复项
- [ ] 更新所有引用指向唯一资源
- [ ] 删除冗余副本

<details>
<summary>涉及资源 (19 个)</summary>

- `T_Brick_14_N`
- `T_Water_16_D`
- `T_Cloud_05_D`
- `T_Foliage_00_N`
- `T_Chest_09_Albedo`
- `T_Debris_22_D`
- `T_FX_15_Albedo`
- `T_Ground_18_Albedo`
- `T_Rock_02_Mask`
- `RT_Window_141_Color`
- `T_FX_27_N`
- `T_Smoke_08_N`
- `T_Metal_26_N`
- `T_Stone_10_D`
- `T_Barrel_09_Mask`
- `T_FX_21_N`
- `ShadowMap_Wood_02`
- `T_Water_06_Mask`
- `T_Dirt_16_N`
</details>

---

### 3. 清理 19 个未使用纹理 *(可节省 41.06 MB)*

**类别**: 清理冗余

在整个帧中有 19 个纹理从未被任何 Draw Call 或 Dispatch 引用。这些纹理占用 VRAM 但不参与渲染，可能是残留资源或预加载过度。

**操作步骤**:
- [ ] 确认这些纹理是否确实不需要
- [ ] 检查是否为其他帧使用的资源
- [ ] 如确认无用，从资产包中移除
- [ ] 优化资源加载策略，避免预加载不需要的资源

<details>
<summary>涉及资源 (19 个)</summary>

- `T_Smoke_02_D`
- `T_Cloud_05_D`
- `T_Fabric_20_D`
- `T_Prop_25_D`
- `T_Foliage_31_D`
- `T_Stone_34_D`
- `T_Wood_04_Albedo`
- `T_FX_15_Albedo`
- `T_Ground_18_Albedo`
- `T_Dirt_19_Albedo`
- `T_Debris_20_Albedo`
- `T_NPC_07_N`
- `T_Blood_17_N`
- `T_Metal_06_ORM`
- `T_Ground_07_ORM`
- `T_Wall_10_ORM`
- `T_Stone_10_Mask`
- `HDR_Decal_01_Cubemap`
- `HDR_Chest_142_Cubemap`
</details>

---

## 🟡 中优先级 (建议)

### 1. 评估 3 个 4K+ 超大纹理 *(可节省 191.52 MB)*

**类别**: 内存优化

检测到 3 个分辨率达到或超过 4096 的纹理。超大纹理占用大量 VRAM，应评估是否真正需要如此高的分辨率。

**操作步骤**:
- [ ] 评估这些纹理在最终渲染中的实际可见尺寸
- [ ] 对于非主要资产考虑降低分辨率
- [ ] 使用流式加载 (Texture Streaming) 按需加载高分辨率 mip
- [ ] 考虑虚拟纹理技术

<details>
<summary>涉及资源 (3 个)</summary>

- `ShadowMap_Fabric_00 (4096×4096, D32_FLOAT)`
- `ShadowMap_Boss_01 (4096×4096, D32_FLOAT)`
- `ShadowMap_Wood_02 (4096×4096, D32_FLOAT)`
</details>

---

### 2. 规范化 7 个非标准尺寸纹理

**类别**: 性能优化

检测到 7 个纹理使用非 2 的幂次尺寸。非 POT 纹理可能导致某些 GPU 上的兼容性问题，并可能无法有效使用硬件压缩和 Mipmap。

**操作步骤**:
- [ ] 将纹理尺寸调整为最接近的 2 的幂次
- [ ] 使用纹理图集合并小纹理
- [ ] 确保 UI 纹理有正确的导入设置

<details>
<summary>涉及资源 (7 个)</summary>

- `RT_Rock_00_Color (1920×1080)`
- `RT_Hero_01_Color (1920×1080)`
- `RT_Foliage_02_Color (1920×1080)`
- `RT_FX_03_Color (1280×720)`
- `RT_Floor_00_Depth (1920×1080)`
- `RT_Window_01_Depth (1920×1080)`
- `RT_Window_141_Color (1280×720)`
</details>

---

## 💡 最佳实践参考

1. **压缩格式**: 优先使用 BC7 (高质量) 或 BC1 (低质量但体积小)
2. **Mipmap**: 所有运行时纹理都应有 Mipmap (UI除外)
3. **尺寸规范**: 使用 2 的幂次尺寸 (256, 512, 1024...)
4. **避免重复**: 使用纹理图集或共享引用
5. **按需加载**: 大纹理考虑流式加载

---
*报告由 RenderDoc Texture Analyzer 自动生成*