# Mali Shader 分析器使用说明

> **版本**: v1.0.0 | **最后更新**: 2025-01

## 概述

此工具可以分析 RenderDoc 捕获文件 (`.rdc`) 中的 Shader，使用 Mali Offline Compiler (`malioc`) 估算在 Mali GPU 上的性能表现。

### 主要功能

- 🎯 **瓶颈识别** - 自动识别 Arithmetic / Texture / Load-Store / Varying 瓶颈
- 📊 **完整指标** - 显示 FMA/CVT/SFU 分解、寄存器使用、线程占用率
- 🔍 **交互式报告** - 可折叠列表、筛选、排序
- 📱 **多 GPU 支持** - 默认 Mali-G78 (Valhall)，可修改

## 系统要求

| 组件 | 路径 |
|------|------|
| **RenderDoc** | `C:\Program Files\RenderDoc` |
| **Arm Performance Studio** | `D:\Program Files\Arm\Arm Performance Studio 2025.3` |
| **Python 3.x** | 系统 PATH 中 |

## 快速开始

### 方法 1: 独立运行（生成示例报告）

```bash
# 在 PowerShell 或 CMD 中运行
py -3 d:\Code\git\renderdoc\scripts\rdc_analyzer\generate_sample_report.py
```

**输出**:
- 控制台显示分析摘要
- HTML 报告: `scripts/rdc_analyzer/output/mali_shader_report.html`

### 方法 2: 在 RenderDoc Python Shell 中运行

1. **打开 RenderDoc** (`qrenderdoc.exe`)
2. **打开 RDC 文件**: File → Open Capture
3. **打开 Python Shell**: Window → Python Shell
4. **运行脚本**:
   ```python
   exec(open(r'd:\Code\git\renderdoc\scripts\rdc_analyzer\renderdoc_mali_shell.py').read())
   ```

## 报告解读

### 顶部汇总

| 指标 | 说明 |
|------|------|
| **Total Analyzed** | 成功分析的 Shader 数量 |
| **Vertex Shaders** | VS 数量 |
| **Fragment Shaders** | PS/FS 数量 |
| **Total Arith Cycles** | 所有 Shader 的算术周期总和 |
| **Total Texture Cycles** | 所有 Shader 的纹理周期总和 |

### 瓶颈分布

显示各瓶颈类型的 Shader 数量：
- 🔴 **Arithmetic** - 计算瓶颈
- 🔵 **Texture** - 纹理采样瓶颈
- 🟢 **Load/Store** - 内存访问瓶颈
- 🟣 **Varying** - 插值瓶颈

### Shader 列表

点击任意行展开详情：

| 区块 | 内容 |
|------|------|
| **Performance Cycles** | 各 Pipeline 的周期数（Arith/FMA/CVT/SFU/L-S/Tex/Vary） |
| **Shader Properties** | Work Registers / Uniform Registers / Thread Occupancy / FP16% |

### 筛选与排序

| 功能 | 说明 |
|------|------|
| **Type Filter** | 只显示 Vertex / Fragment |
| **Bound Filter** | 只显示特定瓶颈类型 |
| **Sort** | 按名称 / Cycle 数排序 |
| **Expand All** | 展开所有详情 |
| **Collapse All** | 收起所有详情 |

## 性能指标详解

### Pipeline 单元

| Pipeline | 说明 | 优化方向 |
|----------|------|----------|
| **arith_total** | 算术总周期 | - |
| **arith_fma** | FMA (乘加融合) | 减少复杂数学 |
| **arith_cvt** | 类型转换 | 统一精度 |
| **arith_sfu** | 特殊函数 (sin/cos/sqrt) | 用查找表替代 |
| **load_store** | 内存读写 | 减少 buffer 访问 |
| **texture** | 纹理采样 | 降低采样次数/尺寸 |
| **varying** | 顶点→片段插值 | 减少传递数据 |

### Shader 属性

| 属性 | 说明 | 优化建议 |
|------|------|----------|
| **Work Registers** | 读写寄存器数 | 越低越好 (影响 Occupancy) |
| **Uniform Registers** | 只读寄存器数 | 线程间共享 |
| **Thread Occupancy** | 并发线程百分比 | >75% 良好，<50% 需优化 |
| **16-bit Arithmetic** | FP16 使用率 | 越高越好 (2x 吞吐) |
| **Stack Spilling** | 寄存器溢出到内存 | 必须避免！ |

## 优化建议

### 按瓶颈类型

| 瓶颈 | 建议 |
|------|------|
| **Arithmetic** | 使用 `mediump`/`lowp`；简化数学公式；预计算常量 |
| **Texture** | 减少采样次数；使用更小 mipmap；合并纹理 |
| **Load/Store** | 优化数据布局；减少 buffer 读写；使用 UBO |
| **Varying** | 减少 VS→PS 传递的变量；打包数据 |

### 通用建议

1. **优先优化周期数最高的 Shader**
2. **关注 Work Registers > 32 的 Shader**（影响 Occupancy）
3. **避免 Stack Spilling**（性能杀手）
4. **提升 FP16 使用率**（移动端收益显著）

## 常见问题

### Q: malioc 找不到？

检查路径：
```cmd
"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe" --version
```

如需修改路径，编辑 `generate_sample_report.py` 中的 `MALIOC` 变量。

### Q: DXBC Shader 分析准确吗？

当前版本对 DX Shader 使用"复杂度等价"的 GLSL Stub 进行估算。结果用于识别瓶颈类型，非精确周期数。

Vulkan (SPIR-V) Shader 可直接被 malioc 分析，结果更准确。

### Q: 如何更换目标 GPU？

编辑 `generate_sample_report.py` 中的 `TARGET_GPU` 变量：

```python
TARGET_GPU = "Mali-G78"  # 可改为 Mali-G715, Mali-G610 等
```

运行 `malioc --list` 查看支持的 GPU 列表。

### Q: 报告打不开？

确保输出目录存在：
```bash
mkdir d:\Code\git\renderdoc\scripts\rdc_analyzer\output
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `generate_sample_report.py` | 主入口，生成 HTML 报告 |
| `renderdoc_mali_shell.py` | RenderDoc Python Shell 版本 |
| `analyzers/mali_analyzer.py` | Mali 分析器核心 |
| `converters/shader_converter.py` | DXBC → GLSL 转换器 |
| `output/mali_shader_report.html` | 生成的报告 |
| `docs/MALI_INTEGRATION_SUMMARY.md` | 项目总结文档 |

## 更新日志

### v1.0.0 (2025-01)
- 初始版本
- 支持 malioc JSON v2 完整解析
- 交互式可折叠报告
- 筛选/排序功能