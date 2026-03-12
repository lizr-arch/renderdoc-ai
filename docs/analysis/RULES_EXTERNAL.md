# 外部工具依赖规则

> **版本**: 1.0 | **更新日期**: 2025-01-16
>
> **说明**: 本文档列出无法仅通过 RenderDoc 实现，需要外部工具或数据源的优化规则。

---

## 一、规则分类总览

| 类别 | 所需工具 | 规则数量 |
|------|----------|----------|
| GPU 硬件计数器 | NVIDIA Nsight / AMD RGP / Intel GPA | 8 |
| Shader 源码分析 | DXBC/SPIRV 反编译器 / Mali Offline Compiler | 10 |
| CPU 侧性能 | PIX / Superluminal / Tracy | 6 |
| 移动端 TBDR | Mali Offline Compiler / PowerVR Tools / Snapdragon Profiler | 5 |
| 引擎/运行时数据 | Unity Profiler / UE Insights / 自研引擎 Profiler | 7 |
| 资产管线 | 美术工具 / 资产管理系统 | 4 |

---

## 二、GPU 硬件计数器规则

### 所需工具
- **NVIDIA**: Nsight Graphics, Nsight Systems
- **AMD**: Radeon GPU Profiler (RGP), Radeon GPU Analyzer (RGA)
- **Intel**: Graphics Performance Analyzers (GPA)

| 规则ID | 规则名称 | 检测逻辑 | 工具 | 优先级 |
|--------|----------|----------|------|--------|
| `EXT_GPU_001` | SM 利用率低 | GPU SM 单元利用率 <50% | Nsight | 🔴 高 |
| `EXT_GPU_002` | TEX 单元瓶颈 | 纹理采样单元利用率 >90% | Nsight/RGP | 🔴 高 |
| `EXT_GPU_003` | L2 缓存命中率低 | L2 Cache Hit Rate <70% | Nsight/RGP | 🟠 中 |
| `EXT_GPU_004` | VRAM 带宽饱和 | Memory Bandwidth >80% | Nsight/RGP | 🔴 高 |
| `EXT_GPU_005` | Warp 占用率低 | Occupancy <50% | Nsight | 🟠 中 |
| `EXT_GPU_006` | ROP 瓶颈 | Render Output 单元 >90% | Nsight/RGP | 🟠 中 |
| `EXT_GPU_007` | ZROP 瓶颈 | 深度测试单元 >90% | Nsight | 🟠 中 |
| `EXT_GPU_008` | Wave 执行时间不均 | Shader Wave 执行时间方差大 | RGP | 🟡 低 |

**NVIDIA Nsight 示例输出**:
```
GPU Throughput:
  SM Active: 45.2%
  TEX Throughput: 87.3%  ← 可能是瓶颈
  L2 Hit Rate: 62.1%     ← 偏低
  DRAM Throughput: 71.4%
```

---

## 三、Shader 源码分析规则

### 所需工具
- **通用**: SPIRV-Cross, dxc (DirectX Shader Compiler)
- **ARM**: Mali Offline Compiler (malioc)
- **Qualcomm**: Adreno GPU Profiler
- **静态分析**: Shader Playground (web)

| 规则ID | 规则名称 | 检测逻辑 | 工具 | 优先级 |
|--------|----------|----------|------|--------|
| `EXT_SHADER_001` | 使用 discard | 片元着色器包含 discard 语句 | 反编译器 | 🔴 高 |
| `EXT_SHADER_002` | 动态分支过深 | if/else 嵌套 >2 层 | 反编译器 | 🟠 中 |
| `EXT_SHADER_003` | 未使用 MAD 优化 | a*b+c 未合并为 mad 指令 | malioc | 🟠 中 |
| `EXT_SHADER_004` | 高精度滥用 | 非必要使用 highp/float | 反编译器 | 🟠 中 |
| `EXT_SHADER_005` | SFU 指令过多 | sin/cos/pow 使用 >5 次 | malioc | 🟠 中 |
| `EXT_SHADER_006` | 寄存器溢出 | Stack spilling = true | malioc | 🔴 高 |
| `EXT_SHADER_007` | 复杂数学函数 | 使用 atan2/asin 等 | 反编译器 | 🟡 低 |
| `EXT_SHADER_008` | 纹理依赖读取 | tex2D 坐标依赖另一个 tex2D | 反编译器 | 🟠 中 |
| `EXT_SHADER_009` | 循环展开失败 | 动态循环边界 | malioc | 🟠 中 |
| `EXT_SHADER_010` | 16-bit 利用率低 | 16-bit arithmetic <30% | malioc | 🟡 低 |

**Mali Offline Compiler 示例输出**:
```
$ malioc shader.frag -c Mali-G78

Work registers: 32
Uniform registers: 8
Stack spilling: true  ← 严重问题！

Total Instruction Cycles:
  FMA: 12.5
  CVT: 2.3
  SFU: 8.7  ← SFU 占比高
  TEX: 15.2
```

---

## 四、CPU 侧性能规则

### 所需工具
- **Windows**: PIX, Superluminal, Very Sleepy
- **跨平台**: Tracy Profiler, Optick
- **引擎内置**: Unity Profiler, UE Insights

| 规则ID | 规则名称 | 检测逻辑 | 工具 | 优先级 |
|--------|----------|----------|------|--------|
| `EXT_CPU_001` | Draw Call 提交耗时长 | 单帧 D3D API 调用 >5ms | PIX | 🔴 高 |
| `EXT_CPU_002` | 资源上传阻塞 | Map/Unmap 导致 GPU Stall | PIX | 🔴 高 |
| `EXT_CPU_003` | 驱动开销大 | 驱动层耗时 >2ms/帧 | Superluminal | 🟠 中 |
| `EXT_CPU_004` | Cache Miss 严重 | L1/L2 Miss Rate 高 | VTune/perf | 🟠 中 |
| `EXT_CPU_005` | 锁竞争 | 多线程锁等待时间长 | Tracy | 🟠 中 |
| `EXT_CPU_006` | 频繁内存分配 | 每帧 malloc/new >50 次 | Tracy | 🟡 低 |

---

## 五、移动端 TBDR 规则

### 所需工具
- **ARM Mali**: Mali Offline Compiler, Streamline
- **PowerVR**: PVRTune, PVRShaderEditor
- **Qualcomm Adreno**: Snapdragon Profiler

| 规则ID | 规则名称 | 检测逻辑 | 工具 | 优先级 |
|--------|----------|----------|------|--------|
| `EXT_TBDR_001` | Alpha Test 破坏 HSR | 使用 Alpha Test 导致 Hidden Surface Removal 失效 | malioc | 🔴 高 |
| `EXT_TBDR_002` | Tile 频繁刷新 | RT 切换导致 Tile Memory Flush | Streamline | 🔴 高 |
| `EXT_TBDR_003` | FBO 不兼容 | 修改 FBO Attachment 导致重建 | PVRTune | 🟠 中 |
| `EXT_TBDR_004` | MSAA + 透明混合 | Tile Memory 压力大 | Snapdragon | 🟠 中 |
| `EXT_TBDR_005` | 过大 Tile 尺寸 | 渲染目标超出最优 Tile 尺寸 | 硬件文档 | 🟡 低 |

**TBDR 架构说明**:
```
┌─────────────────────────────────────────────┐
│ PowerVR / Mali / Adreno TBDR 架构           │
├─────────────────────────────────────────────┤
│ 1. Geometry → Tile Binning                  │
│ 2. Tile-by-Tile Rendering (On-Chip Memory)  │
│ 3. Final Resolve to DRAM                    │
├─────────────────────────────────────────────┤
│ ⚠️ Alpha Test/Discard 破坏 HSR              │
│ ⚠️ RT 切换导致 Tile Flush = 性能损失        │
└─────────────────────────────────────────────┘
```

---

## 六、引擎/运行时数据规则

### 所需工具
- **Unity**: Profiler, Frame Debugger, Memory Profiler
- **Unreal**: Insights, Stat Commands, GPU Visualizer
- **自研引擎**: 内置 Profiler

| 规则ID | 规则名称 | 检测逻辑 | 工具 | 优先级 |
|--------|----------|----------|------|--------|
| `EXT_ENGINE_001` | 合批失败原因 | 检查 SRP Batcher 兼容性 | Unity Frame Debugger | 🟠 中 |
| `EXT_ENGINE_002` | GC Spike | 单帧 GC 分配 >1KB | Unity Profiler | 🔴 高 |
| `EXT_ENGINE_003` | LOD 切换距离不合理 | LOD 级别与距离不匹配 | 引擎编辑器 | 🟠 中 |
| `EXT_ENGINE_004` | Culling 效率低 | 可见物体/总物体 比例低 | 引擎 Stats | 🟠 中 |
| `EXT_ENGINE_005` | Skinning 开销 | 蒙皮网格计算耗时 | 引擎 Profiler | 🟠 中 |
| `EXT_ENGINE_006` | 粒子 Overdraw | 粒子系统导致严重 Overdraw | 引擎 Stats | 🟠 中 |
| `EXT_ENGINE_007` | Shadow Cascade 配置 | CSM 级联配置不合理 | 引擎设置 | 🟡 低 |

---

## 七、资产管线规则

### 所需工具
- **纹理**: TexturePacker, 美术 DCC 工具
- **模型**: Maya/Max, FBX 导出设置
- **资产管理**: 版本控制系统, 资产数据库

| 规则ID | 规则名称 | 检测逻辑 | 工具 | 优先级 |
|--------|----------|----------|------|--------|
| `EXT_ASSET_001` | 纹理未合并 Atlas | 小纹理 >20 张未合并 | TexturePacker | 🟠 中 |
| `EXT_ASSET_002` | 模型未优化 | 顶点数可减少 >30% | Simplygon/Maya | 🟠 中 |
| `EXT_ASSET_003` | 材质变体过多 | 相似材质 >10 个 | 资产审计 | 🟡 低 |
| `EXT_ASSET_004` | 缺少压缩格式 | 平台未配置 ASTC/ETC2 | 导入设置 | 🔴 高 |

---

## 八、工具获取与学习资源

### 8.1 免费工具

| 工具 | 平台 | 下载链接 |
|------|------|----------|
| NVIDIA Nsight Graphics | Windows/Linux | https://developer.nvidia.com/nsight-graphics |
| AMD RGP | Windows/Linux | https://gpuopen.com/rgp/ |
| PIX for Windows | Windows | https://devblogs.microsoft.com/pix/ |
| Mali Offline Compiler | Windows/Linux/Mac | https://developer.arm.com/tools-and-software |
| Tracy Profiler | 跨平台 | https://github.com/wolfpld/tracy |
| SPIRV-Cross | 跨平台 | https://github.com/KhronosGroup/SPIRV-Cross |

### 8.2 学习资源

- **NVIDIA GPU Performance**:  https://developer.nvidia.com/blog/tag/performance/
- **AMD GPUOpen**: https://gpuopen.com/learn/
- **ARM Mali Best Practices**: https://developer.arm.com/documentation/102643/
- **PowerVR Performance**: https://docs.imgtec.com/

---

## 九、与 RenderDoc 规则的配合使用

### 9.1 推荐工作流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. RenderDoc 初筛 (RULES_RENDERDOC.md)                      │
│    → 快速识别 Draw Call / 纹理 / 状态 问题                   │
├─────────────────────────────────────────────────────────────┤
│ 2. 针对性深入 (RULES_EXTERNAL.md)                           │
│    → 发现瓶颈后使用专业工具分析                             │
│    → GPU 瓶颈 → Nsight/RGP                                  │
│    → Shader 问题 → Mali Offline Compiler                    │
│    → CPU 问题 → PIX/Tracy                                   │
├─────────────────────────────────────────────────────────────┤
│ 3. 引擎层验证 (Engine Profiler)                             │
│    → 确认修复效果                                           │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 规则对应表

| RenderDoc 规则 | 深入分析工具 | 外部规则 |
|----------------|--------------|----------|
| `RD_DC_001` (DC 过多) | PIX | `EXT_CPU_001` |
| `RD_TEX_001` (未压缩) | Mali OC | `EXT_SHADER_004` |
| `RD_OD_001` (透明物体) | RGP | `EXT_GPU_006` |
| `RD_SHADER_002` (采样器多) | Nsight | `EXT_GPU_002` |

---

## 十、总结

| 分类 | RenderDoc 可检测 | 需外部工具 |
|------|------------------|------------|
| Draw Call / 批处理 | ✅ 数量、状态切换 | CPU 提交耗时 |
| 纹理资源 | ✅ 格式、尺寸、Mip | 压缩质量评估 |
| Shader | ✅ 绑定资源 | 源码分析、指令统计 |
| GPU 性能 | ❌ | 硬件计数器 |
| CPU 性能 | ❌ | Profiler |
| 移动端 TBDR | ❌ | 专用工具 |

**建议**: 先用 RenderDoc 完成 80% 的问题发现，再用专业工具进行 20% 的深度分析。
