#!/usr/bin/env markdown
# RDC Analyzer 架构设计文档

> 版本: 3.0  
> 最后更新: 2025-01  
> 状态: 设计阶段

---

## 1. 概述

### 1.1 项目背景

当前 `scripts/rdc_analyzer.py` 已经发展到 1800+ 行代码，包含解析、分析、检测、报告等多种职责。随着功能增加，单文件架构面临以下问题：

| 问题 | 描述 | 影响 |
|------|------|------|
| **单文件过大** | 所有功能集中在一个文件 | 难以导航、理解、维护 |
| **职责混杂** | 解析/分析/检测/报告耦合 | 修改一处可能影响全局 |
| **规则硬编码** | 检测规则散落在代码各处 | 难以新增/禁用/配置规则 |
| **扩展性差** | 仅支持 D3D11 Chunk 定义 | 无法适配 Vulkan/D3D12 |
| **测试困难** | 缺乏清晰的模块边界 | 无法进行单元测试 |

### 1.2 设计目标

1. **模块化**: 按职责拆分为独立模块，每个文件 100-300 行
2. **可扩展**: 支持添加新的图形 API (Vulkan/D3D12)、新规则、新报告格式
3. **可测试**: 每个模块有清晰接口，可独立测试
4. **可配置**: 规则和阈值可通过配置文件调整
5. **向后兼容**: 保持 CLI 接口不变，迁移对用户透明

### 1.3 技术约束

- Python 3.8+ (使用 dataclass、typing 等特性)
- 可选依赖: `renderdoc` (API 模式)、`lz4` (二进制模式解压)
- 输出格式: JSON、Markdown (未来: HTML)

---

## 2. 包结构设计

```
scripts/
└── rdc_analyzer/                 # Python 包根目录
    ├── __init__.py               # 版本号、公共导出
    ├── __main__.py               # CLI 入口: python -m rdc_analyzer
    ├── analyzer.py               # 主分析器类 (门面模式)
    │
    ├── core/                     # 核心数据结构
    │   ├── __init__.py
    │   ├── types.py              # 资源信息类: TextureInfo, BufferInfo, ShaderInfo, DrawCallInfo
    │   ├── result.py             # 分析结果类: AnalysisResult, FrameSummary, RenderPassInfo
    │   ├── enums.py              # 枚举定义: Severity, Category, Platform
    │   └── context.py            # 分析上下文: AnalysisContext (贯穿分析流程的共享状态)
    │
    ├── parsers/                  # 解析器模块 (策略模式)
    │   ├── __init__.py           # 导出 get_parser() 工厂函数
    │   ├── base.py               # BaseParser 抽象基类
    │   ├── api_parser.py         # RenderDoc Python API 解析器
    │   ├── binary_parser.py      # 二进制直接解析器
    │   └── chunk_defs/           # Chunk ID 定义 (按图形 API 分)
    │       ├── __init__.py
    │       ├── d3d11_chunks.py   # D3D11 Chunk ID 映射
    │       ├── d3d12_chunks.py   # D3D12 Chunk ID 映射 (预留)
    │       └── vulkan_chunks.py  # Vulkan Chunk ID 映射 (预留)
    │
    ├── analyzers/                # 分析器模块 (管道模式)
    │   ├── __init__.py           # 导出所有分析器
    │   ├── base.py               # BaseAnalyzer 抽象基类
    │   ├── frame_analyzer.py     # 帧级摘要分析
    │   ├── resource_analyzer.py  # 资源 (纹理/Buffer/Shader) 分析
    │   ├── pass_analyzer.py      # Pass 结构识别
    │   └── state_analyzer.py     # 状态切换分析
    │
    ├── rules/                    # 规则引擎 (注册器模式)
    │   ├── __init__.py           # 导出 RuleRegistry
    │   ├── base.py               # BaseRule 抽象基类
    │   ├── registry.py           # RuleRegistry 规则注册中心
    │   ├── thresholds.py         # PC/Mobile 阈值配置
    │   │
    │   ├── draw_call/            # Draw Call 规则组
    │   │   ├── __init__.py       # 自动注册本目录所有规则
    │   │   ├── dc_001_high_count.py
    │   │   ├── dc_002_state_switch.py
    │   │   ├── dc_003_unbatched.py
    │   │   ├── dc_004_instancing.py
    │   │   └── dc_005_empty_draw.py
    │   │
    │   ├── texture/              # 纹理规则组
    │   │   ├── __init__.py
    │   │   ├── tex_001_uncompressed.py
    │   │   ├── tex_002_non_pot.py
    │   │   ├── tex_003_no_mipmap.py
    │   │   ├── tex_004_huge.py
    │   │   ├── tex_005_high_memory.py
    │   │   └── tex_006_duplicate.py
    │   │
    │   ├── vertex/               # 顶点规则组
    │   │   ├── __init__.py
    │   │   ├── vert_001_high_count.py
    │   │   ├── vert_002_large_draw.py
    │   │   └── vert_003_lod_issue.py
    │   │
    │   ├── render_target/        # RT 规则组
    │   │   ├── __init__.py
    │   │   ├── rt_001_frequent_switch.py
    │   │   ├── rt_002_unused.py
    │   │   ├── rt_003_oversized.py
    │   │   └── rt_004_multiple_clear.py
    │   │
    │   ├── shader/               # Shader 规则组
    │   │   ├── __init__.py
    │   │   ├── shader_001_frequent_switch.py
    │   │   ├── shader_002_high_sampler.py
    │   │   └── shader_003_large_cb.py
    │   │
    │   ├── buffer/               # Buffer 规则组
    │   │   ├── __init__.py
    │   │   ├── buf_001_high_memory.py
    │   │   └── buf_002_large_dynamic.py
    │   │
    │   ├── state/                # 状态规则组
    │   │   ├── __init__.py
    │   │   ├── state_001_depth_blend.py
    │   │   └── state_002_cull_off.py
    │   │
    │   ├── overdraw/             # Overdraw 规则组
    │   │   ├── __init__.py
    │   │   ├── od_001_transparent_ratio.py
    │   │   └── od_003_fullscreen_pass.py
    │   │
    │   └── mobile/               # 移动端特定规则
    │       ├── __init__.py
    │       ├── mobile_001_tbdr_loadstore.py
    │       ├── mobile_002_float16.py
    │       └── mobile_003_transparent_sort.py
    │
    ├── reporters/                # 报告生成器 (策略模式)
    │   ├── __init__.py           # 导出 get_reporter() 工厂函数
    │   ├── base.py               # BaseReporter 抽象基类
    │   ├── json_reporter.py      # JSON 格式输出
    │   ├── markdown_reporter.py  # Markdown 格式输出
    │   └── html_reporter.py      # HTML 交互式报告 (预留)
    │
    ├── utils/                    # 工具函数
    │   ├── __init__.py
    │   ├── format_utils.py       # 格式分类、压缩检测
    │   ├── memory_utils.py       # 内存估算 (BPP 计算)
    │   └── lz4_utils.py          # LZ4 分块解压
    │
    └── config/                   # 配置管理
        ├── __init__.py
        ├── settings.py           # 全局设置类
        └── logging_config.py     # 日志配置
```

### 2.1 文件数量统计

| 模块 | 文件数 | 说明 |
|------|--------|------|
| 根目录 | 3 | `__init__`, `__main__`, `analyzer` |
| core/ | 5 | 核心数据结构 |
| parsers/ | 6 | 解析器 + Chunk 定义 |
| analyzers/ | 6 | 分析器 |
| rules/ | ~35 | 规则引擎 + 各类规则 |
| reporters/ | 4 | 报告生成器 |
| utils/ | 4 | 工具函数 |
| config/ | 3 | 配置管理 |
| **总计** | **~66** | - |

---

## 3. 核心接口设计

### 3.1 数据流概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         RDCAnalyzer                              │
│  (门面类，协调整个分析流程)                                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 解析 (Parser)                                          │
│  ┌─────────────┐    ┌─────────────┐                             │
│  │ APIParser   │ or │BinaryParser │  → ParsedData               │
│  └─────────────┘    └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 分析 (Analyzers Pipeline)                              │
│  ┌──────────────┐ ┌─────────────────┐ ┌─────────────┐           │
│  │FrameAnalyzer│→│ResourceAnalyzer │→│ PassAnalyzer│→ ...      │
│  └──────────────┘ └─────────────────┘ └─────────────┘           │
│                          ↓                                       │
│                  AnalysisContext (共享状态)                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 规则检测 (Rule Engine)                                 │
│  ┌──────────────┐                                                │
│  │ RuleRegistry │ → 遍历所有适用规则 → List[Issue]               │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: 报告生成 (Reporter)                                    │
│  ┌──────────────┐    ┌────────────────┐                         │
│  │JSONReporter  │ or │MarkdownReporter│  → 输出文件              │
│  └──────────────┘    └────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心类接口

#### 3.2.1 BaseParser (解析器基类)

```python
# parsers/base.py
from abc import ABC, abstractmethod
from typing import Optional
from ..core.context import ParsedData

class BaseParser(ABC):
    """解析器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """解析器名称"""
        pass
    
    @abstractmethod
    def supports(self, filepath: str) -> bool:
        """检查是否支持解析该文件"""
        pass
    
    @abstractmethod
    def parse(self, filepath: str) -> ParsedData:
        """
        解析 RDC 文件
        
        Args:
            filepath: RDC 文件路径
            
        Returns:
            ParsedData: 统一的中间数据结构
            
        Raises:
            ParseError: 解析失败
        """
        pass
```

#### 3.2.2 BaseAnalyzer (分析器基类)

```python
# analyzers/base.py
from abc import ABC, abstractmethod
from ..core.context import AnalysisContext

class BaseAnalyzer(ABC):
    """分析器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """分析器名称"""
        pass
    
    @property
    def order(self) -> int:
        """执行顺序 (越小越先执行)"""
        return 100
    
    @abstractmethod
    def analyze(self, context: AnalysisContext) -> None:
        """
        执行分析，结果写入 context
        
        Args:
            context: 分析上下文 (包含 ParsedData 和累积的分析结果)
        """
        pass
```

#### 3.2.3 BaseRule (规则基类)

```python
# rules/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from ..core.types import Issue
from ..core.context import AnalysisContext

@dataclass
class RuleMetadata:
    """规则元数据"""
    id: str                      # "RD_DC_001"
    name: str                    # "HIGH_DRAW_CALL_COUNT"
    description: str             # 规则描述
    severity: str                # "error" | "warning" | "info"
    category: str                # "performance" | "memory" | "correctness"
    platforms: List[str]         # ["pc", "mobile"] 或 ["mobile"]
    enabled: bool = True         # 是否启用
    
class BaseRule(ABC):
    """规则抽象基类"""
    
    @property
    @abstractmethod
    def metadata(self) -> RuleMetadata:
        """规则元数据"""
        pass
    
    @abstractmethod
    def check(self, context: AnalysisContext) -> Optional[Issue]:
        """
        执行规则检查
        
        Args:
            context: 分析上下文
            
        Returns:
            Issue: 如果检测到问题则返回 Issue，否则返回 None
        """
        pass
    
    def get_threshold(self, context: AnalysisContext, key: str):
        """获取阈值 (自动根据平台选择)"""
        return context.thresholds.get(key)
```

#### 3.2.4 RuleRegistry (规则注册中心)

```python
# rules/registry.py
from typing import Dict, List, Type, Optional
from .base import BaseRule

class RuleRegistry:
    """规则注册中心 (单例模式)"""
    
    _instance: Optional['RuleRegistry'] = None
    _rules: Dict[str, BaseRule] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, rule_class: Type[BaseRule]) -> Type[BaseRule]:
        """
        装饰器：注册规则类
        
        用法:
            @RuleRegistry.register
            class DC001HighDrawCallCount(BaseRule):
                ...
        """
        instance = rule_class()
        cls._rules[instance.metadata.id] = instance
        return rule_class
    
    @classmethod
    def get_rules(cls, 
                  platform: str = "pc",
                  category: Optional[str] = None,
                  enabled_only: bool = True) -> List[BaseRule]:
        """获取符合条件的规则列表"""
        rules = []
        for rule in cls._rules.values():
            meta = rule.metadata
            if enabled_only and not meta.enabled:
                continue
            if platform not in meta.platforms:
                continue
            if category and meta.category != category:
                continue
            rules.append(rule)
        return rules
    
    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[BaseRule]:
        """根据 ID 获取规则"""
        return cls._rules.get(rule_id)
    
    @classmethod
    def disable_rule(cls, rule_id: str) -> bool:
        """禁用指定规则"""
        if rule := cls._rules.get(rule_id):
            rule.metadata.enabled = False
            return True
        return False
```

#### 3.2.5 BaseReporter (报告生成器基类)

```python
# reporters/base.py
from abc import ABC, abstractmethod
from ..core.result import AnalysisResult

class BaseReporter(ABC):
    """报告生成器抽象基类"""
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        """报告格式名称 (如 "json", "markdown")"""
        pass
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """输出文件扩展名 (如 ".json", ".md")"""
        pass
    
    @abstractmethod
    def generate(self, result: AnalysisResult) -> str:
        """
        生成报告内容
        
        Args:
            result: 分析结果
            
        Returns:
            str: 报告内容字符串
        """
        pass
    
    def save(self, result: AnalysisResult, filepath: str) -> None:
        """保存报告到文件"""
        content = self.generate(result)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
```

#### 3.2.6 AnalysisContext (分析上下文)

```python
# core/context.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .types import TextureInfo, BufferInfo, ShaderInfo, DrawCallInfo
from .result import FrameSummary, RenderPassInfo

@dataclass
class ParsedData:
    """解析器输出的原始数据"""
    meta: Dict[str, Any] = field(default_factory=dict)
    
    # API 模式下的 RenderDoc 对象引用
    controller: Any = None  # rd.ReplayController
    actions: List[Any] = field(default_factory=list)  # rd.ActionDescription
    
    # 二进制模式下的 Chunk 数据
    chunks: List[Dict] = field(default_factory=list)
    chunk_stats: Dict[str, int] = field(default_factory=dict)

@dataclass
class AnalysisContext:
    """
    分析上下文 (贯穿整个分析流程的共享状态)
    
    - 由 Parser 创建，包含 ParsedData
    - 由各 Analyzer 填充分析结果
    - 由 Rule 读取数据进行检测
    - 最终转换为 AnalysisResult
    """
    # 原始解析数据
    parsed: ParsedData
    
    # 平台配置
    platform: str = "pc"
    thresholds: Dict[str, Any] = field(default_factory=dict)
    
    # 分析结果 (由各 Analyzer 填充)
    frame_summary: FrameSummary = field(default_factory=FrameSummary)
    textures: List[TextureInfo] = field(default_factory=list)
    buffers: List[BufferInfo] = field(default_factory=list)
    shaders: List[ShaderInfo] = field(default_factory=list)
    draw_calls: List[DrawCallInfo] = field(default_factory=list)
    render_passes: List[RenderPassInfo] = field(default_factory=list)
    
    # 状态跟踪 (供分析器共享)
    _marker_stack: List[str] = field(default_factory=list)
    _rt_usage: Dict[int, int] = field(default_factory=dict)
    _rt_clear_counts: Dict[int, int] = field(default_factory=dict)
    _shader_bind_counts: Dict[str, int] = field(default_factory=dict)
    
    def to_result(self, issues: List['Issue']) -> 'AnalysisResult':
        """转换为最终分析结果"""
        from .result import AnalysisResult
        return AnalysisResult(
            version="3.0",
            meta=self.parsed.meta,
            frame_summary=self.frame_summary,
            textures=self.textures,
            buffers=self.buffers,
            shaders=self.shaders,
            draw_calls=self.draw_calls,
            render_passes=self.render_passes,
            issues=issues,
        )
```

---

## 4. 设计模式应用

### 4.1 策略模式 (Strategy Pattern)

**应用场景**: Parser、Reporter

**优点**: 
- 可在运行时切换解析器/报告生成器
- 易于添加新的解析器 (如 Vulkan) 或报告格式 (如 HTML)

```python
# 工厂函数选择策略
def get_parser() -> BaseParser:
    if HAS_RENDERDOC:
        return APIParser()
    elif HAS_LZ4:
        return BinaryParser()
    else:
        raise RuntimeError("No available parser")

# 使用
parser = get_parser()
data = parser.parse(filepath)
```

### 4.2 注册器模式 (Registry Pattern)

**应用场景**: 规则引擎

**优点**:
- 规则自动注册，无需手动维护列表
- 支持按条件筛选规则 (平台、类别)
- 支持运行时禁用/启用规则

```python
# 规则定义 (自动注册)
@RuleRegistry.register
class DC001HighDrawCallCount(BaseRule):
    @property
    def metadata(self) -> RuleMetadata:
        return RuleMetadata(
            id="RD_DC_001",
            name="HIGH_DRAW_CALL_COUNT",
            description="Draw Call 数量过高",
            severity="warning",
            category="performance",
            platforms=["pc", "mobile"],
        )
    
    def check(self, context: AnalysisContext) -> Optional[Issue]:
        threshold = self.get_threshold(context, 'draw_call_warning')
        actual = context.frame_summary.total_draw_calls
        
        if actual > threshold:
            return Issue(
                severity=self.metadata.severity,
                category=self.metadata.category,
                code=self.metadata.id,
                message=f"Draw Call 数量 ({actual}) 超过阈值 ({threshold})",
                threshold=threshold,
                actual=actual,
                suggestion="使用 GPU Instancing、合批或 LOD 优化",
            )
        return None
```

### 4.3 管道模式 (Pipeline Pattern)

**应用场景**: 分析器链

**优点**:
- 分析步骤可组合、可重排
- 每个分析器职责单一
- 便于添加新的分析维度

```python
class RDCAnalyzer:
    def __init__(self, platform: str = "pc"):
        self.platform = platform
        self.analyzers = [
            FrameAnalyzer(),      # order=10
            ResourceAnalyzer(),   # order=20
            PassAnalyzer(),       # order=30
            StateAnalyzer(),      # order=40
        ]
        # 按 order 排序
        self.analyzers.sort(key=lambda a: a.order)
    
    def analyze(self, filepath: str) -> AnalysisResult:
        # 解析
        parser = get_parser()
        parsed = parser.parse(filepath)
        
        # 创建上下文
        context = AnalysisContext(
            parsed=parsed,
            platform=self.platform,
            thresholds=get_thresholds(self.platform),
        )
        
        # 分析管道
        for analyzer in self.analyzers:
            analyzer.analyze(context)
        
        # 规则检测
        rules = RuleRegistry.get_rules(platform=self.platform)
        issues = []
        for rule in rules:
            if issue := rule.check(context):
                issues.append(issue)
        
        # 返回结果
        return context.to_result(issues)
```

### 4.4 门面模式 (Facade Pattern)

**应用场景**: RDCAnalyzer 主类

**优点**:
- 对外提供简洁的 API
- 隐藏内部复杂性

```python
# 用户只需要这一个入口
from rdc_analyzer import RDCAnalyzer

analyzer = RDCAnalyzer(platform="pc")
result = analyzer.analyze("capture.rdc")
analyzer.save_report(result, "report.json", format="json")
```

---

## 5. 阈值配置设计

### 5.1 阈值结构

```python
# rules/thresholds.py
from typing import Dict, Any

THRESHOLDS_PC: Dict[str, Any] = {
    # Draw Call
    'draw_call_warning': 2000,
    'draw_call_error': 5000,
    'small_draw_vertices': 100,
    'small_draw_ratio_warning': 0.20,
    'state_switch_ratio_warning': 0.80,
    'instancing_candidate_threshold': 10,
    
    # 纹理
    'texture_uncompressed_size': 1024,
    'texture_huge_size': 4096,
    'texture_memory_warning_mb': 2048,
    'texture_no_mipmap_size': 512,
    
    # ... 更多阈值
}

THRESHOLDS_MOBILE: Dict[str, Any] = {
    # 移动端更严格的阈值
    'draw_call_warning': 200,
    'draw_call_error': 500,
    'texture_uncompressed_size': 512,
    'texture_huge_size': 2048,
    # ...
}

def get_thresholds(platform: str) -> Dict[str, Any]:
    """获取指定平台的阈值配置"""
    if platform == "mobile":
        return THRESHOLDS_MOBILE.copy()
    return THRESHOLDS_PC.copy()
```

### 5.2 自定义阈值 (未来)

```python
# 支持从配置文件加载自定义阈值
analyzer = RDCAnalyzer(
    platform="pc",
    config_file="custom_thresholds.yaml"  # 未来支持
)
```

---

## 6. 迁移计划

### 6.1 分阶段实施

| 阶段 | 任务 | 依赖 | 预计文件数 |
|------|------|------|-----------|
| **Stage 0** | 撰写本设计文档 | - | 1 |
| **Stage 1** | 创建包目录结构 | Stage 0 | 10 (`__init__.py` 等) |
| **Stage 2** | 迁移核心数据类型 | Stage 1 | 4 (core/) |
| **Stage 3** | 拆分解析器 | Stage 2 | 6 (parsers/) |
| **Stage 4** | 拆分分析器 | Stage 3 | 5 (analyzers/) |
| **Stage 5** | 规则引擎 + 规则迁移 | Stage 4 | ~35 (rules/) |
| **Stage 6** | 拆分报告生成器 | Stage 4 | 4 (reporters/) |
| **Stage 7** | CLI 入口 + 集成测试 | Stage 6 | 2 |
| **Stage 8** | 废弃旧 rdc_analyzer.py | Stage 7 | 0 (删除) |

### 6.2 兼容性保证

- **CLI 接口不变**: `python -m rdc_analyzer capture.rdc` 等命令保持兼容
- **输出格式不变**: JSON/Markdown 报告格式保持一致
- **旧脚本保留**: 在 Stage 8 之前，`rdc_analyzer.py` 作为 fallback 保留

### 6.3 测试策略

每个阶段完成后进行集成测试：

```bash
# 使用测试 RDC 文件验证
py -3 -m rdc_analyzer "Resource/Game_x64h_2026.01.07_05.35.50_frame3996.rdc" --platform pc
```

对比新旧输出，确保：
- Draw Call 数量一致
- 资源统计一致
- 检测到的问题一致

---

## 7. 规则文件命名规范

### 7.1 文件命名

```
{category}_{rule_number}_{short_name}.py
```

示例：
- `dc_001_high_count.py` - Draw Call 数量过高
- `tex_003_no_mipmap.py` - 纹理缺少 Mipmap
- `mobile_001_tbdr_loadstore.py` - TBDR Load/Store 检查

### 7.2 规则 ID 格式

```
RD_{CATEGORY}_{NUMBER}
```

| 类别 | 前缀 | 示例 |
|------|------|------|
| Draw Call | DC | RD_DC_001 |
| 纹理 | TEX | RD_TEX_003 |
| 顶点 | VERT | RD_VERT_001 |
| RT | RT | RD_RT_002 |
| Shader | SHADER | RD_SHADER_001 |
| Buffer | BUF | RD_BUF_001 |
| 状态 | STATE | RD_STATE_001 |
| Overdraw | OD | RD_OD_001 |
| 移动端 | MOBILE | RD_MOBILE_001 |

---

## 8. 附录

### 8.1 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 规则定义 | `docs/analysis/RULES_RENDERDOC.md` | 35 条可实现规则 |
| 输出规格 | `docs/analysis/RDC_ANALYSIS_SPEC.md` | JSON/Markdown 格式定义 |
| 外部规则 | `docs/analysis/RULES_EXTERNAL.md` | 需外部工具的规则 |
| RDC 解析 | `docs/analysis/RDC_PARSING_INDEX.md` | 二进制格式说明 |

### 8.2 依赖关系

```
rdc_analyzer (包)
├── 必需: Python 3.8+
├── 可选: renderdoc (API 模式)
├── 可选: lz4 (二进制模式解压)
└── 可选: pyyaml (配置文件, 未来)
```

### 8.3 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2025-01 | 初始单文件实现 |
| 2.0 | 2025-01 | 添加二进制解析、完整规则 |
| 3.0 | 2025-01 | 模块化重构 (本文档) |

---

## 9. 决策记录

### 9.1 为什么选择 Python 包结构而不是多个独立脚本？

**决策**: 使用标准 Python 包结构 (`rdc_analyzer/`)

**理由**:
1. 支持 `python -m rdc_analyzer` 调用方式
2. 模块间可以使用相对导入
3. 便于未来发布到 PyPI
4. 符合 Python 最佳实践

### 9.2 为什么规则使用装饰器自动注册？

**决策**: 使用 `@RuleRegistry.register` 装饰器

**理由**:
1. 添加新规则时无需修改注册表
2. 规则定义和注册在同一处，减少遗漏
3. 支持按需加载规则模块

### 9.3 为什么分析器使用管道模式？

**决策**: 分析器按 `order` 属性排序后顺序执行

**理由**:
1. 某些分析器依赖前置分析的结果 (如 StateAnalyzer 需要 DrawCall 列表)
2. 便于插入新的分析步骤
3. 职责清晰，易于单独测试

---

*文档结束*
