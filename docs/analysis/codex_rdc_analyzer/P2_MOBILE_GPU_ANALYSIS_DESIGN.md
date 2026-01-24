# P2 设计文档：移动 GPU 专项分析扩展

> **创建时间**: 2025-01-21  
> **优先级**: P2 (低优先级)  
> **状态**: 设计阶段  
> **前置依赖**: P0/P1 已完成，Mali 分析器已实现

---

## 0. 概述

本文档规划两个 P2 任务的实现方案：
- **P2-2**: Adreno GPU 专项分析
- **P2-3**: Tile-Based GPU 效率分析

### 目标

| 任务 | 目标 | 预期产出 |
|------|------|----------|
| Adreno 分析器 | 类似 Mali，支持高通 Adreno GPU 的 Shader 性能分析 | `analyzers/adreno_analyzer.py` |
| Tile-Based 分析 | 通用 TBDR 效率问题检测（overdraw、tile memory、render pass 优化） | `analyzers/tile_based_analyzer.py` |

### 优先级评估

| 因素 | 说明 |
|------|------|
| **市场覆盖** | Adreno (高通) + Mali (ARM) 覆盖 ~85% 移动 GPU 市场 |
| **工具依赖** | Adreno 需要 Snapdragon Profiler SDK 或 Adreno GPU Profiler |
| **复杂度** | Tile-Based 分析可基于 RenderDoc 现有数据，无需外部工具 |
| **建议顺序** | P2-3 (Tile-Based) → P2-2 (Adreno) |

---

## 1. P2-3: Tile-Based GPU 效率分析

### 1.1 背景

移动 GPU（Mali、Adreno、PowerVR、Apple GPU）均采用 **Tile-Based Deferred Rendering (TBDR)** 架构，与桌面 GPU 的 **Immediate Mode Rendering (IMR)** 有本质区别。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TBDR vs IMR 架构对比                                  │
└─────────────────────────────────────────────────────────────────────────┘

IMR (桌面 GPU):
  顶点着色 → 光栅化 → 像素着色 → 写入 Framebuffer (VRAM)
  每个三角形立即处理，直接写显存

TBDR (移动 GPU):
  1. Binning Pass: 顶点着色 → 三角形分配到 Tiles (16x16 或 32x32)
  2. Tile Pass: 逐 Tile 从 On-Chip Memory 渲染
  3. Resolve: 最终结果写回 VRAM

关键区别:
  - TBDR 在 On-Chip Memory 完成渲染，减少带宽
  - 但如果 Tile 切换过多或 On-Chip 溢出，性能反而更差
```

### 1.2 可检测的问题

| 问题代码 | 问题 | 检测方法 | 严重性 |
|----------|------|----------|--------|
| `TILE_001` | Overdraw 过高 | 像素着色次数 / 屏幕像素数 > 阈值 | High |
| `TILE_002` | Render Target 过大导致 Tile Memory 溢出 | RT 尺寸 × 格式大小 > Tile Memory 预估 | High |
| `TILE_003` | 不必要的 RT 切换 (Load/Store) | 检测 vkCmdBeginRenderPass 的 loadOp/storeOp | Medium |
| `TILE_004` | 缺少 MSAA Resolve 优化 | MSAA 未使用 Lazy Resolve | Medium |
| `TILE_005` | Transient Attachment 未启用 | Depth/Stencil 未标记 TRANSIENT | Low |
| `TILE_006` | Pass 边界不清晰 | 检测 Debug Markers 缺失 | Info |

### 1.3 数据来源

| 数据 | 来源 | 路线 |
|------|------|------|
| Draw Call 数量 | XML / Python API | A / B |
| 纹理/RT 尺寸和格式 | XML / Python API | A / B |
| Render Pass 信息 | Vulkan/GLES 事件 | B (需 ReplayController) |
| loadOp/storeOp | FrameCapture 结构化数据 | B |
| 像素着色次数 | Shader 分析 / 启发式估算 | 估算 |

### 1.4 实现方案

#### 文件结构

```
scripts/rdc_analyzer/
├── analyzers/
│   ├── tile_based_analyzer.py      # 新增：TBDR 效率分析
│   └── tile_based_rules.py         # 新增：TBDR 规则定义
├── core/
│   └── tile_memory.py              # 新增：Tile Memory 估算模型
```

#### 核心类设计

```python
# analyzers/tile_based_analyzer.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional

class TileBasedGPU(Enum):
    """支持的 TBDR GPU 系列"""
    MALI = "mali"           # ARM Mali
    ADRENO = "adreno"       # Qualcomm Adreno
    POWERVR = "powervr"     # Imagination PowerVR
    APPLE = "apple"         # Apple GPU
    GENERIC = "generic"     # 通用 TBDR

@dataclass
class TileMemoryConfig:
    """Tile Memory 配置"""
    tile_size: int = 16           # Tile 尺寸 (16x16 或 32x32)
    on_chip_memory_kb: int = 128  # On-Chip Memory 大小
    max_rt_size_for_tile: int = 4096  # 单 Tile 支持的最大 RT 总大小 (bytes)

    @classmethod
    def for_gpu(cls, gpu: TileBasedGPU) -> 'TileMemoryConfig':
        """根据 GPU 类型返回配置"""
        configs = {
            TileBasedGPU.MALI: cls(tile_size=16, on_chip_memory_kb=256),
            TileBasedGPU.ADRENO: cls(tile_size=16, on_chip_memory_kb=1024),  # GMEM
            TileBasedGPU.POWERVR: cls(tile_size=32, on_chip_memory_kb=512),
            TileBasedGPU.APPLE: cls(tile_size=32, on_chip_memory_kb=512),
            TileBasedGPU.GENERIC: cls(tile_size=16, on_chip_memory_kb=128),
        }
        return configs.get(gpu, configs[TileBasedGPU.GENERIC])

@dataclass
class RenderPassInfo:
    """Render Pass 信息"""
    pass_index: int
    name: str
    color_attachments: List[Dict]   # [{resourceId, format, loadOp, storeOp}, ...]
    depth_attachment: Optional[Dict]
    
    # 统计
    draw_call_count: int = 0
    triangle_count: int = 0
    estimated_overdraw: float = 1.0
    
    # 问题标记
    has_unnecessary_load: bool = False
    has_unnecessary_store: bool = False
    has_tile_memory_overflow: bool = False

class TileBasedAnalyzer:
    """Tile-Based GPU 效率分析器"""
    
    def __init__(self, gpu: TileBasedGPU = TileBasedGPU.GENERIC):
        self.gpu = gpu
        self.config = TileMemoryConfig.for_gpu(gpu)
        self.issues = []
    
    def analyze(self, capture_data) -> List[CanonicalIssue]:
        """分析捕获数据，返回问题列表"""
        self.issues = []
        
        # 1. 分析 Overdraw
        self._analyze_overdraw(capture_data)
        
        # 2. 分析 Tile Memory
        self._analyze_tile_memory(capture_data)
        
        # 3. 分析 Load/Store 操作
        self._analyze_load_store(capture_data)
        
        # 4. 分析 MSAA
        self._analyze_msaa(capture_data)
        
        # 5. 分析 Transient Attachments
        self._analyze_transient(capture_data)
        
        return self.issues
    
    def _analyze_overdraw(self, capture_data):
        """分析 Overdraw"""
        # 估算方法：
        # overdraw = total_fragments / screen_pixels
        # 阈值：移动端建议 < 2.5
        pass
    
    def _analyze_tile_memory(self, capture_data):
        """分析 Tile Memory 使用"""
        # 估算单 Tile 所需内存：
        # tile_bytes = sum(attachment_width * attachment_height * bpp) / num_tiles
        # 如果 tile_bytes > on_chip_memory → 溢出警告
        pass
    
    def _analyze_load_store(self, capture_data):
        """分析 Load/Store 操作"""
        # 检查 loadOp 是否为 LOAD（应为 CLEAR 或 DONT_CARE）
        # 检查 storeOp 是否为 STORE（中间 Pass 应为 DONT_CARE）
        pass
    
    def _analyze_msaa(self, capture_data):
        """分析 MSAA 使用"""
        # 检查是否使用了 Lazy Resolve
        pass
    
    def _analyze_transient(self, capture_data):
        """分析 Transient Attachments"""
        # 检查 Depth/Stencil 是否标记为 TRANSIENT_ATTACHMENT
        pass
```

### 1.5 规则定义

```python
# analyzers/tile_based_rules.py

TILE_BASED_RULES = {
    'TILE_001': {
        'code': 'TILE_001',
        'name': 'High Overdraw',
        'category': 'tile_efficiency',
        'severity': 'high',
        'threshold': {'overdraw_ratio': 2.5},
        'description': 'Overdraw 比率过高 (>{threshold} 倍)，导致像素着色浪费',
        'suggestion': {
            'title': '减少 Overdraw',
            'steps': [
                '启用 Early-Z 剔除',
                '从前往后排序不透明物体',
                '使用遮挡剔除 (Occlusion Culling)',
                '减少透明物体重叠',
            ],
            'verification_plan': {
                'metrics': ['overdraw_ratio', 'fragment_shader_invocations'],
                'expected_direction': 'decrease',
                'how_to_capture': '优化后抓帧，对比 Overdraw 比率',
            }
        }
    },
    
    'TILE_002': {
        'code': 'TILE_002',
        'name': 'Tile Memory Overflow',
        'category': 'tile_efficiency',
        'severity': 'high',
        'description': 'Render Target 过大导致 Tile Memory 溢出，触发 GMEM Fallback',
        'suggestion': {
            'title': '优化 Tile Memory 使用',
            'steps': [
                '减少 Render Target 数量或尺寸',
                '使用压缩格式 (R11G11B10F 替代 RGBA16F)',
                '拆分为多个 Render Pass',
            ],
            'verification_plan': {
                'metrics': ['tile_memory_usage', 'gmem_load_bandwidth'],
                'expected_direction': 'decrease',
                'how_to_capture': '使用 Snapdragon Profiler 验证 GMEM 使用',
            }
        }
    },
    
    'TILE_003': {
        'code': 'TILE_003',
        'name': 'Unnecessary RT Load/Store',
        'category': 'tile_efficiency',
        'severity': 'medium',
        'description': '检测到不必要的 Render Target Load/Store 操作',
        'suggestion': {
            'title': '优化 Load/Store 操作',
            'steps': [
                '使用 CLEAR 替代 LOAD（如果不需要保留内容）',
                '使用 DONT_CARE 替代 STORE（如果后续不使用）',
                'Vulkan: 检查 VkAttachmentDescription 的 loadOp/storeOp',
            ],
            'engine_howto': {
                'unity': 'RenderTexture.discardContents = true',
                'unreal': 'ERenderTargetActions::DontLoad',
            },
            'verification_plan': {
                'metrics': ['memory_bandwidth'],
                'expected_direction': 'decrease',
                'how_to_capture': '优化后抓帧，检查 loadOp/storeOp',
            }
        }
    },
}
```

### 1.6 集成到主管线

```python
# main.py 中添加 Tile-Based 分析

class AnalysisPipeline:
    def analyze(self):
        # ... 现有分析 ...
        
        # Tile-Based 分析 (可选)
        if self.options.enable_tile_analysis:
            from analyzers.tile_based_analyzer import TileBasedAnalyzer, TileBasedGPU
            
            gpu = TileBasedGPU(self.options.tile_gpu or 'generic')
            tile_analyzer = TileBasedAnalyzer(gpu)
            tile_issues = tile_analyzer.analyze(self._capture_data)
            self._issues.extend(tile_issues)
```

### 1.7 CLI 参数

```bash
# 启用 Tile-Based 分析
py -3 -m rdc_analyzer analyze capture.rdc -o output/ \
    --enable-tile-analysis \
    --tile-gpu mali

# 可选 GPU 类型: mali, adreno, powervr, apple, generic
```

---

## 2. P2-2: Adreno GPU 专项分析

### 2.1 背景

Qualcomm Adreno 是移动 GPU 市场占有率最高的系列（~45%），与 Mali 形成双寡头格局。

### 2.2 工具依赖

| 工具 | 用途 | 获取方式 |
|------|------|----------|
| **Snapdragon Profiler** | GPU 性能分析、Shader 分析 | [下载](https://developer.qualcomm.com/software/snapdragon-profiler) |
| **Adreno GPU Profiler** | 旧版工具（已被 Snapdragon Profiler 替代） | 不再维护 |
| **Offline Shader Compiler** | Shader 离线编译分析 | Snapdragon SDK 包含 |

### 2.3 实现方案（概要）

由于 Adreno 没有类似 `malioc` 的独立离线编译器，实现方式有两种：

**方案 A：调用 Snapdragon Profiler CLI**

```python
# 如果 Snapdragon Profiler 支持 CLI 模式
class AdrenoProfiler:
    def analyze_shader(self, shader_source: str, gpu: str) -> AdrenoAnalysisResult:
        # 1. 保存 Shader 到临时文件
        # 2. 调用 Snapdragon Profiler CLI
        # 3. 解析输出 JSON/XML
        pass
```

**方案 B：基于启发式规则（无需外部工具）**

```python
# 基于 Adreno 架构特点的启发式规则
class AdrenoHeuristicAnalyzer:
    """基于启发式的 Adreno 分析"""
    
    # Adreno 特有问题
    ADRENO_RULES = {
        'ADRENO_001': 'GMEM 带宽瓶颈检测',
        'ADRENO_002': '纹理解压缩开销检测',
        'ADRENO_003': 'Shader ALU 利用率估算',
    }
    
    def analyze(self, capture_data) -> List[CanonicalIssue]:
        # 基于以下数据进行启发式分析：
        # - Draw Call 数量和复杂度
        # - 纹理格式和尺寸
        # - Render Target 配置
        # - Shader 复杂度估算
        pass
```

### 2.4 Adreno GPU 型号

与 Mali 类似，需要维护 Adreno GPU 列表：

```python
# Adreno 主要型号
ADRENO_GPU_LIST = [
    # Adreno 7xx (Snapdragon 8 Gen 3)
    AdrenoGPUInfo("Adreno 750", architecture="A7xx", tier="flagship", year=2023),
    AdrenoGPUInfo("Adreno 740", architecture="A7xx", tier="flagship", year=2022),
    AdrenoGPUInfo("Adreno 730", architecture="A7xx", tier="flagship", year=2021),
    
    # Adreno 6xx (Snapdragon 8xx/7xx)
    AdrenoGPUInfo("Adreno 660", architecture="A6xx", tier="flagship", year=2020),
    AdrenoGPUInfo("Adreno 650", architecture="A6xx", tier="flagship", year=2019),
    AdrenoGPUInfo("Adreno 640", architecture="A6xx", tier="premium", year=2019),
    AdrenoGPUInfo("Adreno 630", architecture="A6xx", tier="flagship", year=2018),
    AdrenoGPUInfo("Adreno 620", architecture="A6xx", tier="mainstream", year=2020),
    AdrenoGPUInfo("Adreno 619", architecture="A6xx", tier="mainstream", year=2020),
    AdrenoGPUInfo("Adreno 618", architecture="A6xx", tier="entry", year=2020),
    AdrenoGPUInfo("Adreno 616", architecture="A6xx", tier="entry", year=2019),
    AdrenoGPUInfo("Adreno 612", architecture="A6xx", tier="entry", year=2019),
    AdrenoGPUInfo("Adreno 610", architecture="A6xx", tier="entry", year=2019),
    
    # Adreno 5xx (旧款，仍有大量设备)
    AdrenoGPUInfo("Adreno 540", architecture="A5xx", tier="flagship", year=2017),
    AdrenoGPUInfo("Adreno 530", architecture="A5xx", tier="flagship", year=2015),
    AdrenoGPUInfo("Adreno 512", architecture="A5xx", tier="mainstream", year=2017),
    AdrenoGPUInfo("Adreno 509", architecture="A5xx", tier="entry", year=2017),
    AdrenoGPUInfo("Adreno 506", architecture="A5xx", tier="entry", year=2016),
    AdrenoGPUInfo("Adreno 505", architecture="A5xx", tier="entry", year=2016),
]
```

### 2.5 建议实现顺序

1. **Phase 1**: 实现启发式分析器（无需外部工具）
2. **Phase 2**: 如果有 Snapdragon Profiler CLI，添加真实分析
3. **Phase 3**: 添加 GPU 型号选择和针对性规则

---

## 3. 实现优先级

| 顺序 | 任务 | 工作量估算 | 理由 |
|------|------|------------|------|
| 1 | **P2-3 Tile-Based 分析** | 2-3 天 | 无需外部工具，可基于现有数据 |
| 2 | **P2-2 Adreno 启发式** | 1-2 天 | 作为 Tile-Based 的补充 |
| 3 | **P2-2 Adreno Profiler 集成** | 3-5 天 | 需要研究 Snapdragon Profiler API |

---

## 4. 测试计划

### 4.1 单元测试

```python
# tests/test_tile_based_analyzer.py

class TestTileBasedAnalyzer:
    def test_overdraw_detection(self):
        """测试 Overdraw 检测"""
        pass
    
    def test_tile_memory_overflow(self):
        """测试 Tile Memory 溢出检测"""
        pass
    
    def test_load_store_optimization(self):
        """测试 Load/Store 优化检测"""
        pass
```

### 4.2 集成测试

使用真实 RDC 样本验证：
- Mali GPU 捕获 → Tile-Based 分析
- Adreno GPU 捕获 → Tile-Based + Adreno 分析

---

## 5. 文档更新清单

实现完成后需要更新的文档：

- [ ] `scripts/rdc_analyzer/README.md` — 添加 Tile-Based 分析说明
- [ ] `scripts/rdc_analyzer/RULES.md` — 添加新规则代码
- [ ] `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md` — 更新文件结构
- [ ] `scripts/rdc_analyzer/docs/ARCHITECTURE_V1.md` — 添加分析器架构图

---

## 6. 决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| Tile-Based 优先于 Adreno | A: 先 Adreno, B: 先 Tile-Based | B | Tile-Based 通用性更强，Mali/Adreno 都受益 |
| Adreno 初期方案 | A: Profiler 集成, B: 启发式 | B | 减少外部依赖，快速交付价值 |
| GPU 配置管理 | A: 硬编码, B: JSON 配置文件 | A | 初期硬编码，后期可提取为配置 |

---

## 7. 参考资料

- [ARM Mali GPU Best Practices](https://developer.arm.com/documentation/102643/latest/)
- [Qualcomm Adreno GPU Best Practices](https://developer.qualcomm.com/sites/default/files/docs/adreno-gpu/developer-guide/)
- [TBDR 架构深入理解](https://developer.imaginationtech.com/presentations/tile-based-deferred-rendering/)
- [Vulkan Render Pass Best Practices](https://arm-software.github.io/vulkan_best_practice_for_mobile_developers/)
