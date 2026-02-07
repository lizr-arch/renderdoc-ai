#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shader 多维度性能分析器 (M4.3)
================================

基于 Mali Offline Compiler (malioc) 的 Shader 性能多维度评估。

核心维度:
- 静态复杂度: Cycles (A/LS/T/V)、寄存器使用
- 动态影响: Draw Call 次数、像素覆盖面积
- 健康评分: 0-100 分，基于加权成本公式
- 规则引擎: 9 条检测规则 → 优化建议

设计文档: docs/M4.3_SHADER_PERF_ANALYSIS_DESIGN.md
官方参考: ARM Mali Best Practices Guide, Vulkan Samples 16-bit Storage

使用方式:
    from rdc_analyzer.analyzers.shader_perf_analyzer import ShaderPerfAnalyzer
    
    analyzer = ShaderPerfAnalyzer()
    result = analyzer.analyze_shader(
        shader_info=shader_data,
        malioc_result=malioc_output,
        frame_context=frame_ctx
    )
    print(result.health_score, result.recommendations)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# 枚举定义
# ============================================================================

class HealthLevel(Enum):
    """健康等级"""
    CRITICAL = "critical"   # 🔴 严重问题
    WARNING = "warning"     # 🟡 警告
    INFO = "info"           # 🟢 正常/提示


class RuleCategory(Enum):
    """规则类别"""
    CYCLES = "cycles"             # 周期相关
    REGISTERS = "registers"       # 寄存器相关
    COVERAGE = "coverage"         # 覆盖率相关
    WEIGHTED = "weighted"         # 加权成本
    FEATURE = "feature"           # 特性相关 (Late Z/S, Uniform)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class CycleMetrics:
    """Mali GPU 周期指标"""
    arithmetic: float = 0.0     # A: 算术运算周期
    load_store: float = 0.0     # LS: 内存访问周期
    texture: float = 0.0        # T: 纹理采样周期
    varying: float = 0.0        # V: 插值器周期
    bound: str = ""             # 瓶颈类型: "A" | "LS" | "T" | "V"
    
    @property
    def total(self) -> float:
        """总周期数 (取最大值，因为流水线并行)"""
        return max(self.arithmetic, self.load_store, self.texture, self.varying)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "arithmetic": self.arithmetic,
            "load_store": self.load_store,
            "texture": self.texture,
            "varying": self.varying,
            "total": self.total,
            "bound": self.bound
        }


@dataclass
class RegisterMetrics:
    """寄存器使用指标"""
    work_registers: int = 0     # 工作寄存器数量
    uniform_registers: int = 0  # Uniform 寄存器数量
    stack_spilling: bool = False  # 是否溢出到栈
    
    # 阈值定义 (来自 ARM 最佳实践)
    THRESHOLD_WARNING = 32      # 32+ 开始影响 Occupancy
    THRESHOLD_CRITICAL = 48     # 48+ 严重影响并行度
    THRESHOLD_MAX = 64          # Mali 最大寄存器数
    
    @property
    def pressure_level(self) -> HealthLevel:
        """寄存器压力等级"""
        if self.stack_spilling or self.work_registers >= self.THRESHOLD_CRITICAL:
            return HealthLevel.CRITICAL
        elif self.work_registers >= self.THRESHOLD_WARNING:
            return HealthLevel.WARNING
        return HealthLevel.INFO
    
    @property
    def occupancy_factor(self) -> float:
        """
        Occupancy 惩罚系数 (用于加权成本计算)
        
        公式: 1.0 + max(0, (registers - 32) / 32) * 0.3
        
        - 32 以下: 1.0 (无惩罚)
        - 48: 1.15 (15% 惩罚)
        - 64: 1.30 (30% 惩罚)
        """
        if self.work_registers <= self.THRESHOLD_WARNING:
            return 1.0
        excess = self.work_registers - self.THRESHOLD_WARNING
        return 1.0 + (excess / 32) * 0.3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_registers": self.work_registers,
            "uniform_registers": self.uniform_registers,
            "stack_spilling": self.stack_spilling,
            "pressure_level": self.pressure_level.value,
            "occupancy_factor": round(self.occupancy_factor, 3)
        }


@dataclass
class DynamicMetrics:
    """动态帧上下文指标"""
    draw_count: int = 1                 # Shader 在一帧中的调用次数
    viewport_width: int = 1920          # 视口宽度
    viewport_height: int = 1080         # 视口高度
    estimated_coverage: float = 0.5     # 像素覆盖率估算 (0.0 - 1.0)
    pass_name: str = ""                 # Pass 名称 (用于覆盖率启发式)
    
    @property
    def viewport_pixels(self) -> int:
        """视口像素总数"""
        return self.viewport_width * self.viewport_height
    
    @property
    def covered_pixels(self) -> int:
        """预估覆盖像素数"""
        return int(self.viewport_pixels * self.estimated_coverage)
    
    @staticmethod
    def estimate_coverage_from_pass(pass_name: str) -> float:
        """
        基于 Pass 名称启发式估算覆盖率
        
        参考设计文档表 3 的 Pass-Type Heuristic Map
        """
        name_lower = pass_name.lower()
        
        # 全屏效果: 100%
        fullscreen_keywords = [
            "post", "bloom", "blur", "dof", "ao", "ssao", "ssr", 
            "tonemap", "fxaa", "smaa", "taa", "motion", "composite",
            "fullscreen", "screen", "blit", "copy"
        ]
        for kw in fullscreen_keywords:
            if kw in name_lower:
                return 1.0
        
        # 阴影: 50% (通常只渲染部分场景)
        if "shadow" in name_lower:
            return 0.5
        
        # UI: 20%
        if "ui" in name_lower or "hud" in name_lower:
            return 0.2
        
        # 粒子: 10%
        if "particle" in name_lower or "vfx" in name_lower:
            return 0.1
        
        # 默认: 50%
        return 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "draw_count": self.draw_count,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "estimated_coverage": self.estimated_coverage,
            "covered_pixels": self.covered_pixels,
            "pass_name": self.pass_name
        }


@dataclass
class ShaderPerfRule:
    """性能检测规则"""
    rule_id: str                # R1-R9
    name: str                   # 规则名称
    condition: str              # 触发条件描述
    level: HealthLevel          # 级别
    category: RuleCategory      # 类别
    source: str = "malioc"      # 来源: "malioc" | "heuristic" | "arm_best_practice"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "condition": self.condition,
            "level": self.level.value,
            "category": self.category.value,
            "source": self.source
        }


@dataclass 
class ShaderRecommendation:
    """优化建议"""
    rule_id: str                # 触发规则 ID
    title: str                  # 标题
    detail: str                 # 详细说明
    action: str                 # 具体操作建议
    arm_reference: str = ""     # ARM 官方文档链接
    priority: int = 0           # 优先级 (0 最高)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "detail": self.detail,
            "action": self.action,
            "arm_reference": self.arm_reference,
            "priority": self.priority
        }


@dataclass
class ShaderPerfResult:
    """Shader 性能分析结果"""
    shader_name: str = ""
    shader_type: str = ""           # "vertex" | "fragment" | "compute"
    gpu_target: str = "Mali-G78"    # 目标 GPU
    
    # 指标
    cycles: CycleMetrics = field(default_factory=CycleMetrics)
    registers: RegisterMetrics = field(default_factory=RegisterMetrics)
    dynamic: DynamicMetrics = field(default_factory=DynamicMetrics)
    
    # 评分
    health_score: int = 100         # 0-100 分
    health_level: HealthLevel = HealthLevel.INFO
    weighted_cost: float = 0.0      # 加权成本
    
    # 触发的规则和建议
    triggered_rules: List[str] = field(default_factory=list)
    recommendations: List[ShaderRecommendation] = field(default_factory=list)
    
    # 原始数据 (调试用)
    raw_malioc: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "shader_name": self.shader_name,
            "shader_type": self.shader_type,
            "gpu_target": self.gpu_target,
            "cycles": self.cycles.to_dict(),
            "registers": self.registers.to_dict(),
            "dynamic": self.dynamic.to_dict(),
            "health_score": self.health_score,
            "health_level": self.health_level.value,
            "weighted_cost": round(self.weighted_cost, 2),
            "triggered_rules": self.triggered_rules,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


# ============================================================================
# GPU 下拉框选项 (按档位分组)
# ============================================================================

@dataclass
class GPUOption:
    """GPU 选项"""
    name: str               # 显示名称
    malioc_id: str          # malioc --core 参数
    tier: str               # 档位: "flagship" | "premium" | "mainstream" | "entry"
    year: int               # 发布年份
    description: str = ""   # 简短描述


# 按档位分组的 GPU 列表
GPU_OPTIONS_BY_TIER: Dict[str, List[GPUOption]] = {
    "flagship": [
        GPUOption("Immortalis-G720", "Immortalis-G720", "flagship", 2023, "2023 最新旗舰，支持光追"),
        GPUOption("Immortalis-G715", "Immortalis-G715", "flagship", 2022, "Dimensity 9200"),
        GPUOption("Mali-G710", "Mali-G710", "flagship", 2021, "Dimensity 9000"),
        GPUOption("Mali-G78", "Mali-G78", "flagship", 2020, "Exynos 2100/Dimensity 1200"),
        GPUOption("Mali-G77", "Mali-G77", "flagship", 2019, "Exynos 990/Dimensity 1000"),
    ],
    "premium": [
        GPUOption("Mali-G715", "Mali-G715", "premium", 2022, "不含光追的 G715"),
        GPUOption("Mali-G615", "Mali-G615", "premium", 2022, "中高端 2022"),
        GPUOption("Mali-G76", "Mali-G76", "premium", 2018, "Kirin 980/990"),
        GPUOption("Mali-G68", "Mali-G68", "premium", 2021, "中高端 2021"),
    ],
    "mainstream": [
        GPUOption("Mali-G610", "Mali-G610", "mainstream", 2022, "Dimensity 8000 系列"),
        GPUOption("Mali-G510", "Mali-G510", "mainstream", 2021, "中端常用"),
        GPUOption("Mali-G57", "Mali-G57", "mainstream", 2020, "Dimensity 700/800"),
        GPUOption("Mali-G52", "Mali-G52", "mainstream", 2018, "Helio G85/G90"),
    ],
    "entry": [
        GPUOption("Mali-G310", "Mali-G310", "entry", 2021, "入门级 Valhall"),
        GPUOption("Mali-G31", "Mali-G31", "entry", 2018, "入门级/电视盒子"),
    ],
}

# 默认 GPU
DEFAULT_GPU = "Mali-G78"


def get_gpu_options_for_dropdown() -> List[Dict[str, Any]]:
    """
    获取用于 UI 下拉框的 GPU 选项列表
    
    返回格式适合 HTML <select> <optgroup> 渲染
    """
    result = []
    tier_labels = {
        "flagship": "🏆 旗舰级",
        "premium": "⭐ 高端级", 
        "mainstream": "📱 主流级",
        "entry": "💡 入门级"
    }
    
    for tier, gpus in GPU_OPTIONS_BY_TIER.items():
        group = {
            "tier": tier,
            "label": tier_labels.get(tier, tier),
            "options": [
                {
                    "value": gpu.malioc_id,
                    "label": f"{gpu.name} ({gpu.year})",
                    "description": gpu.description,
                    "selected": gpu.malioc_id == DEFAULT_GPU
                }
                for gpu in gpus
            ]
        }
        result.append(group)
    
    return result


# ============================================================================
# 规则引擎
# ============================================================================

# 预定义规则 (来自设计文档)
SHADER_PERF_RULES: Dict[str, ShaderPerfRule] = {
    "R1": ShaderPerfRule(
        "R1", "Stack Spilling", 
        "stack_spilling == true",
        HealthLevel.CRITICAL, RuleCategory.REGISTERS, "malioc"
    ),
    "R2": ShaderPerfRule(
        "R2", "全屏高复杂度",
        "coverage >= 0.8 && cycles >= 30",
        HealthLevel.CRITICAL, RuleCategory.COVERAGE, "heuristic"
    ),
    "R3": ShaderPerfRule(
        "R3", "极端寄存器压力",
        "work_registers >= 56",
        HealthLevel.CRITICAL, RuleCategory.REGISTERS, "malioc"
    ),
    "R4": ShaderPerfRule(
        "R4", "成本过高",
        "weighted_cost > top 10%",
        HealthLevel.CRITICAL, RuleCategory.WEIGHTED, "heuristic"
    ),
    "R5": ShaderPerfRule(
        "R5", "高 Cycles",
        "total_cycles >= 20",
        HealthLevel.WARNING, RuleCategory.CYCLES, "arm_best_practice"
    ),
    "R6": ShaderPerfRule(
        "R6", "寄存器压力",
        "work_registers >= 32",
        HealthLevel.WARNING, RuleCategory.REGISTERS, "arm_best_practice"
    ),
    "R7": ShaderPerfRule(
        "R7", "Late Z/S Test",
        "has_late_zs == true",
        HealthLevel.WARNING, RuleCategory.FEATURE, "malioc"
    ),
    "R8": ShaderPerfRule(
        "R8", "Uniform 计算",
        "has_uniform_computation == true",
        HealthLevel.WARNING, RuleCategory.FEATURE, "malioc"
    ),
    "R9": ShaderPerfRule(
        "R9", "高复杂度低影响",
        "cycles >= 20 && coverage < 0.1",
        HealthLevel.INFO, RuleCategory.COVERAGE, "heuristic"
    ),
}

# 规则 → 建议映射
RULE_RECOMMENDATIONS: Dict[str, ShaderRecommendation] = {
    "R1": ShaderRecommendation(
        "R1", "减少寄存器使用",
        "Shader 使用了过多寄存器导致溢出到栈内存，严重影响性能",
        "1. 减少临时变量\n2. 拆分复杂 Shader\n3. 使用 FP16 (mediump) 替代 FP32",
        "https://developer.arm.com/documentation/102643/latest/",
        priority=0
    ),
    "R2": ShaderRecommendation(
        "R2", "优化全屏效果 Shader",
        "全屏 Shader 复杂度过高，每个像素都需要大量计算",
        "1. 将不变计算移到 Vertex Shader\n2. 使用 LUT 替代复杂数学\n3. 考虑降采样处理",
        "https://developer.arm.com/documentation/102073/latest/",
        priority=0
    ),
    "R3": ShaderRecommendation(
        "R3", "大幅降低寄存器使用",
        "寄存器使用量接近硬件上限，GPU 无法有效隐藏延迟",
        "1. 使用 FP16/mediump\n2. 简化算法\n3. 拆分为多 Pass",
        "https://developer.arm.com/documentation/102643/latest/",
        priority=0
    ),
    "R4": ShaderRecommendation(
        "R4", "整体优化 Shader",
        "综合考虑 Cycles、覆盖率、调用次数后，该 Shader 是帧内热点",
        "1. 逐条检查 malioc 输出，优化瓶颈管线\n2. 考虑 LOD/简化版本\n3. 减少调用次数",
        "",
        priority=0
    ),
    "R5": ShaderRecommendation(
        "R5", "降低 Shader 复杂度",
        "Shader 周期数较高，可能影响帧率",
        "1. 检查是否有冗余采样/计算\n2. 预计算常量\n3. 使用更简单的算法",
        "https://developer.arm.com/documentation/102073/latest/",
        priority=1
    ),
    "R6": ShaderRecommendation(
        "R6", "降低寄存器压力",
        "寄存器使用超过 32，开始影响 GPU 线程并行度 (Occupancy)",
        "1. 使用 mediump (FP16) 变量\n2. 减少临时变量作用域\n3. 考虑拆分 Shader",
        "https://developer.arm.com/documentation/102643/latest/",
        priority=1
    ),
    "R7": ShaderRecommendation(
        "R7", "避免 Late Z/S Test",
        "Fragment Shader 修改了深度或使用了 discard，导致无法进行 Early-Z 剔除",
        "1. 避免在 Fragment Shader 中使用 discard\n2. 不要修改 gl_FragDepth\n3. 使用 Alpha Test 替代 Alpha Blend + discard",
        "https://developer.arm.com/documentation/102073/latest/",
        priority=1
    ),
    "R8": ShaderRecommendation(
        "R8", "预计算 Uniform",
        "在 Shader 中对 Uniform 进行了可在 CPU 预计算的操作",
        "1. 将 Uniform 的数学运算移到 CPU\n2. 预计算矩阵、向量变换\n3. 使用专用 Uniform Buffer",
        "https://developer.arm.com/documentation/102073/latest/",
        priority=2
    ),
    "R9": ShaderRecommendation(
        "R9", "考虑简化版本",
        "Shader 复杂度较高，但像素覆盖率很低，可考虑针对此场景简化",
        "1. 创建 LOD 版本\n2. 根据距离选择简化 Shader\n3. 当前可能不需要优化",
        "",
        priority=2
    ),
}


# ============================================================================
# 评分算法
# ============================================================================

# 阈值定义 (来自设计文档)
CYCLES_THRESHOLD_OK = 8         # <= 8 cycles: 优秀
CYCLES_THRESHOLD_WARN = 14      # <= 14 cycles: 良好
CYCLES_THRESHOLD_HIGH = 20      # <= 20 cycles: 警告
# > 20 cycles: 危险


def calculate_cycles_score(total_cycles: float) -> int:
    """
    基于 Cycles 计算评分 (0-100)
    
    参考: ARM Best Practice - Fragment Shader Complexity Guide
    """
    if total_cycles <= CYCLES_THRESHOLD_OK:
        return 100
    elif total_cycles <= CYCLES_THRESHOLD_WARN:
        # 8-14 之间线性下降: 100 → 80
        ratio = (total_cycles - CYCLES_THRESHOLD_OK) / (CYCLES_THRESHOLD_WARN - CYCLES_THRESHOLD_OK)
        return int(100 - ratio * 20)
    elif total_cycles <= CYCLES_THRESHOLD_HIGH:
        # 14-20 之间线性下降: 80 → 60
        ratio = (total_cycles - CYCLES_THRESHOLD_WARN) / (CYCLES_THRESHOLD_HIGH - CYCLES_THRESHOLD_WARN)
        return int(80 - ratio * 20)
    else:
        # > 20 之后快速下降: 60 → 0
        excess = total_cycles - CYCLES_THRESHOLD_HIGH
        return max(0, int(60 - excess * 3))


def calculate_register_score(work_registers: int, stack_spilling: bool) -> int:
    """
    基于寄存器使用计算评分 (0-100)
    
    参考: ARM Best Practice - Register Pressure
    """
    if stack_spilling:
        return 20  # 溢出直接严重扣分
    
    if work_registers <= 16:
        return 100
    elif work_registers <= 32:
        # 16-32 之间轻微下降
        ratio = (work_registers - 16) / 16
        return int(100 - ratio * 15)
    elif work_registers <= 48:
        # 32-48 之间明显下降
        ratio = (work_registers - 32) / 16
        return int(85 - ratio * 30)
    else:
        # 48+ 严重下降
        excess = work_registers - 48
        return max(10, int(55 - excess * 3))


def calculate_weighted_cost(
    cycles: float,
    viewport_pixels: int,
    coverage: float,
    draw_count: int,
    register_penalty: float
) -> float:
    """
    计算加权成本
    
    公式: pixel_work = cycles × viewport_pixels × coverage × draw_count
          weighted_cost = pixel_work × register_penalty
    
    单位: Mega-Cycle-Pixels (MCP)
    """
    pixel_work = cycles * viewport_pixels * coverage * draw_count
    weighted_cost = pixel_work * register_penalty
    # 归一化到 Mega 单位
    return weighted_cost / 1_000_000


def calculate_health_score(
    cycles_score: int,
    register_score: int,
    triggered_critical: int,
    triggered_warning: int
) -> Tuple[int, HealthLevel]:
    """
    计算综合健康评分
    
    公式: base = (cycles_score × 0.4 + register_score × 0.3 + 30)
          final = base - critical × 15 - warning × 5
    
    Returns:
        (score, level)
    """
    # 基础分: 40% Cycles + 30% Registers + 30% 基础
    base_score = cycles_score * 0.4 + register_score * 0.3 + 30
    
    # 规则扣分
    penalty = triggered_critical * 15 + triggered_warning * 5
    
    final_score = max(0, min(100, int(base_score - penalty)))
    
    # 确定等级
    if final_score < 40 or triggered_critical > 0:
        level = HealthLevel.CRITICAL
    elif final_score < 70 or triggered_warning > 0:
        level = HealthLevel.WARNING
    else:
        level = HealthLevel.INFO
    
    return final_score, level


# ============================================================================
# 分析器主类
# ============================================================================

class ShaderPerfAnalyzer:
    """
    Shader 性能分析器
    
    整合 malioc 输出和帧上下文，进行多维度评估。
    """
    
    def __init__(self, gpu_target: str = DEFAULT_GPU):
        """
        初始化
        
        Args:
            gpu_target: 目标 GPU 名称 (用于 malioc --core)
        """
        self.gpu_target = gpu_target
    
    def analyze_from_malioc_result(
        self,
        shader_name: str,
        shader_type: str,
        malioc_data: Dict[str, Any],
        dynamic_ctx: Optional[DynamicMetrics] = None
    ) -> ShaderPerfResult:
        """
        从 malioc JSON 输出分析 Shader
        
        Args:
            shader_name: Shader 名称
            shader_type: "vertex" | "fragment" | "compute"
            malioc_data: malioc --format json 的输出
            dynamic_ctx: 动态帧上下文 (可选)
            
        Returns:
            ShaderPerfResult: 分析结果
        """
        result = ShaderPerfResult(
            shader_name=shader_name,
            shader_type=shader_type,
            gpu_target=self.gpu_target,
            raw_malioc=malioc_data
        )
        
        # 1. 提取 Cycles
        result.cycles = self._extract_cycles(malioc_data)
        
        # 2. 提取 Registers
        result.registers = self._extract_registers(malioc_data)
        
        # 3. 应用动态上下文
        if dynamic_ctx:
            result.dynamic = dynamic_ctx
        
        # 4. 计算加权成本
        result.weighted_cost = calculate_weighted_cost(
            cycles=result.cycles.total,
            viewport_pixels=result.dynamic.viewport_pixels,
            coverage=result.dynamic.estimated_coverage,
            draw_count=result.dynamic.draw_count,
            register_penalty=result.registers.occupancy_factor
        )
        
        # 5. 运行规则引擎
        self._run_rules(result)
        
        # 6. 计算健康评分
        cycles_score = calculate_cycles_score(result.cycles.total)
        register_score = calculate_register_score(
            result.registers.work_registers,
            result.registers.stack_spilling
        )
        
        critical_count = sum(1 for r in result.triggered_rules 
                           if SHADER_PERF_RULES.get(r, ShaderPerfRule("", "", "", HealthLevel.INFO, RuleCategory.CYCLES)).level == HealthLevel.CRITICAL)
        warning_count = sum(1 for r in result.triggered_rules
                          if SHADER_PERF_RULES.get(r, ShaderPerfRule("", "", "", HealthLevel.INFO, RuleCategory.CYCLES)).level == HealthLevel.WARNING)
        
        result.health_score, result.health_level = calculate_health_score(
            cycles_score, register_score, critical_count, warning_count
        )
        
        # 7. 生成建议
        self._generate_recommendations(result)
        
        return result
    
    def _extract_cycles(self, data: Dict[str, Any]) -> CycleMetrics:
        """从 malioc JSON 提取周期数据"""
        cycles = CycleMetrics()
        
        # malioc v8.x JSON schema v2 结构
        # { "shaders": [{ "variants": [{ "performance": { ... } }] }] }
        try:
            shaders = data.get("shaders", [])
            if not shaders:
                return cycles
            
            variants = shaders[0].get("variants", [])
            if not variants:
                return cycles
            
            perf = variants[0].get("performance", {})
            pipelines = perf.get("pipelines", {})
            
            # 提取各管线周期
            cycles.arithmetic = float(pipelines.get("arithmetic", {}).get("bound_pipelines", [{}])[0].get("cycle_count", 0) if pipelines.get("arithmetic", {}).get("bound_pipelines") else pipelines.get("arithmetic", {}).get("cycle_count", 0))
            cycles.load_store = float(pipelines.get("load_store", {}).get("cycle_count", 0))
            cycles.texture = float(pipelines.get("texture", {}).get("cycle_count", 0))
            cycles.varying = float(pipelines.get("varying", {}).get("cycle_count", 0))
            
            # 简化提取 - 尝试直接取 cycle_count
            if cycles.arithmetic == 0:
                cycles.arithmetic = float(pipelines.get("arithmetic", {}).get("cycle_count", 0))
            
            # 瓶颈类型
            max_cycles = max(cycles.arithmetic, cycles.load_store, cycles.texture, cycles.varying)
            if max_cycles > 0:
                if cycles.arithmetic == max_cycles:
                    cycles.bound = "A"
                elif cycles.load_store == max_cycles:
                    cycles.bound = "LS"
                elif cycles.texture == max_cycles:
                    cycles.bound = "T"
                else:
                    cycles.bound = "V"
            
        except (KeyError, IndexError, TypeError):
            pass
        
        return cycles
    
    def _extract_registers(self, data: Dict[str, Any]) -> RegisterMetrics:
        """从 malioc JSON 提取寄存器数据"""
        regs = RegisterMetrics()
        
        try:
            shaders = data.get("shaders", [])
            if not shaders:
                return regs
            
            variants = shaders[0].get("variants", [])
            if not variants:
                return regs
            
            props = variants[0].get("properties", {})
            
            regs.work_registers = int(props.get("work_registers", {}).get("used", 0))
            regs.uniform_registers = int(props.get("uniform_registers", {}).get("used", 0))
            regs.stack_spilling = bool(props.get("has_stack_spilling", False))
            
        except (KeyError, IndexError, TypeError):
            pass
        
        return regs
    
    def _run_rules(self, result: ShaderPerfResult) -> None:
        """运行规则引擎"""
        triggered = []
        
        # R1: Stack Spilling
        if result.registers.stack_spilling:
            triggered.append("R1")
        
        # R2: 全屏高复杂度
        if result.dynamic.estimated_coverage >= 0.8 and result.cycles.total >= 30:
            triggered.append("R2")
        
        # R3: 极端寄存器压力
        if result.registers.work_registers >= 56:
            triggered.append("R3")
        
        # R5: 高 Cycles
        if result.cycles.total >= 20:
            triggered.append("R5")
        
        # R6: 寄存器压力
        if result.registers.work_registers >= 32 and "R3" not in triggered:
            triggered.append("R6")
        
        # R9: 高复杂度低影响
        if result.cycles.total >= 20 and result.dynamic.estimated_coverage < 0.1:
            triggered.append("R9")
        
        # 注意: R4 (成本过高) 需要在批量分析后确定 Top 10%
        # 注意: R7 (Late Z/S) 和 R8 (Uniform 计算) 需要 malioc 详细输出
        
        result.triggered_rules = triggered
    
    def _generate_recommendations(self, result: ShaderPerfResult) -> None:
        """生成优化建议"""
        recommendations = []
        
        for rule_id in result.triggered_rules:
            if rule_id in RULE_RECOMMENDATIONS:
                recommendations.append(RULE_RECOMMENDATIONS[rule_id])
        
        # 按优先级排序
        recommendations.sort(key=lambda r: r.priority)
        
        result.recommendations = recommendations


# ============================================================================
# 批量分析辅助函数
# ============================================================================

def analyze_shader_batch(
    shaders: List[Dict[str, Any]],
    gpu_target: str = DEFAULT_GPU
) -> List[ShaderPerfResult]:
    """
    批量分析 Shader
    
    Args:
        shaders: Shader 列表，每项包含 name, type, malioc_data, dynamic_ctx
        gpu_target: 目标 GPU
        
    Returns:
        分析结果列表
    """
    analyzer = ShaderPerfAnalyzer(gpu_target)
    results = []
    
    for shader in shaders:
        result = analyzer.analyze_from_malioc_result(
            shader_name=shader.get("name", "unknown"),
            shader_type=shader.get("type", "fragment"),
            malioc_data=shader.get("malioc_data", {}),
            dynamic_ctx=shader.get("dynamic_ctx")
        )
        results.append(result)
    
    # 后处理: 计算 Top 10% 并触发 R4
    if results:
        costs = [r.weighted_cost for r in results]
        costs.sort(reverse=True)
        top_10_threshold = costs[max(0, len(costs) // 10)]
        
        for result in results:
            if result.weighted_cost >= top_10_threshold and "R4" not in result.triggered_rules:
                result.triggered_rules.append("R4")
                if "R4" in RULE_RECOMMENDATIONS:
                    result.recommendations.insert(0, RULE_RECOMMENDATIONS["R4"])
    
    return results


def get_health_color(level: HealthLevel) -> str:
    """获取健康等级对应的 CSS 颜色"""
    colors = {
        HealthLevel.CRITICAL: "#ef4444",   # red-500
        HealthLevel.WARNING: "#f59e0b",    # amber-500
        HealthLevel.INFO: "#10b981",       # green-500
    }
    return colors.get(level, "#6b7280")


def get_health_emoji(level: HealthLevel) -> str:
    """获取健康等级对应的 Emoji"""
    emojis = {
        HealthLevel.CRITICAL: "🔴",
        HealthLevel.WARNING: "🟡",
        HealthLevel.INFO: "🟢",
    }
    return emojis.get(level, "⚪")
