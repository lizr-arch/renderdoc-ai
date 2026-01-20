#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化建议引擎 - 独立版本
=======================

从 analyzers/optimization_advisor.py 提取的独立版本，
用于 generate_real_report.py 直接调用，避免包导入问题。

功能：
- 根据 Shader 分析结果生成优化建议
- 基于瓶颈类型、寄存器使用、SFU 指令等因素
- 输出优先级排序的建议列表
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ============================================================================
# 枚举定义
# ============================================================================

class OptimizationPriority(Enum):
    """优化优先级"""
    CRITICAL = auto()   # 严重问题，必须优化
    HIGH = auto()       # 高优先级
    MEDIUM = auto()     # 中优先级
    LOW = auto()        # 低优先级，可选优化


class OptimizationCategory(Enum):
    """优化类别"""
    ARITHMETIC = "Arithmetic"
    TEXTURE = "Texture"
    MEMORY = "Memory"
    VARYING = "Varying"
    REGISTER = "Register"
    CONTROL_FLOW = "Control Flow"
    PRECISION = "Precision"
    GENERAL = "General"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class OptimizationSuggestion:
    """单条优化建议"""
    category: OptimizationCategory
    priority: OptimizationPriority
    title: str
    description: str
    expected_impact: str
    code_example: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'category': self.category.value,
            'priority': self.priority.name,
            'title': self.title,
            'description': self.description,
            'expected_impact': self.expected_impact,
            'code_example': self.code_example,
        }


@dataclass
class ShaderAnalysisContext:
    """Shader 分析上下文"""
    name: str
    shader_type: str  # 'vertex' or 'fragment'
    bound: str        # 'Arithmetic', 'Texture', 'Load/Store', 'Varying'
    cycles: Dict[str, float] = field(default_factory=dict)
    registers: Dict[str, int] = field(default_factory=dict)
    category_counts: Dict[str, int] = field(default_factory=dict)
    mali_cycles: Dict[str, float] = field(default_factory=dict)
    
    # 控制流特征
    has_loops: bool = False
    has_branching: bool = False
    has_discard: bool = False
    has_derivatives: bool = False
    loop_depth: int = 0
    branch_depth: int = 0
    
    # 资源使用
    texture_count: int = 0
    sampler_count: int = 0
    cbuffer_count: int = 0
    temp_registers: int = 0
    
    # 使用情况
    usage_count: int = 1


# ============================================================================
# 优化建议引擎
# ============================================================================

class OptimizationAdvisor:
    """
    优化建议引擎
    
    分析 Shader 性能数据并生成针对性的优化建议。
    """
    
    # 阈值定义
    THRESHOLDS = {
        'high_sfu_ratio': 0.3,      # SFU 指令占比超过 30% 视为高
        'high_texture_cycles': 20,   # 纹理周期超过 20 视为高
        'high_register_count': 32,   # 工作寄存器超过 32 视为高
        'high_varying_cycles': 10,   # Varying 周期超过 10 视为高
        'many_textures': 4,          # 超过 4 个纹理采样视为多
        'deep_loops': 2,             # 循环嵌套超过 2 层视为深
        'high_usage': 50,            # 被超过 50 个 Draw Call 使用视为热点
    }
    
    def analyze(self, context: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """
        分析 Shader 并生成优化建议
        
        Args:
            context: Shader 分析上下文
            
        Returns:
            List[OptimizationSuggestion]: 优化建议列表，按优先级排序
        """
        suggestions = []
        
        # 1. 基于瓶颈类型的建议
        suggestions.extend(self._analyze_bottleneck(context))
        
        # 2. 寄存器压力分析
        suggestions.extend(self._analyze_registers(context))
        
        # 3. SFU 使用分析
        suggestions.extend(self._analyze_sfu_usage(context))
        
        # 4. 纹理使用分析
        suggestions.extend(self._analyze_texture_usage(context))
        
        # 5. 控制流分析
        suggestions.extend(self._analyze_control_flow(context))
        
        # 6. Varying 分析（仅 Fragment Shader）
        if context.shader_type == 'fragment':
            suggestions.extend(self._analyze_varying(context))
        
        # 7. 热点 Shader 特殊建议
        suggestions.extend(self._analyze_hotspot(context))
        
        # 按优先级排序
        priority_order = {
            OptimizationPriority.CRITICAL: 0,
            OptimizationPriority.HIGH: 1,
            OptimizationPriority.MEDIUM: 2,
            OptimizationPriority.LOW: 3,
        }
        suggestions.sort(key=lambda s: priority_order[s.priority])
        
        return suggestions
    
    def _analyze_bottleneck(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """基于瓶颈类型生成建议"""
        suggestions = []
        bound = ctx.bound.lower()
        
        if 'arith' in bound:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.ARITHMETIC,
                priority=OptimizationPriority.HIGH,
                title="Arithmetic Bound - 减少计算量",
                description=(
                    "该 Shader 受算术单元限制。考虑以下优化:\n"
                    "• 使用 mediump 精度替代 highp（适用于颜色、UV 等）\n"
                    "• 预计算常量表达式，移到 CPU 或 Uniform\n"
                    "• 使用查找表 (LUT) 替代复杂数学函数\n"
                    "• 简化向量运算，避免不必要的 normalize()"
                ),
                expected_impact="可减少 10-30% 的 Arithmetic 周期"
            ))
            
        elif 'tex' in bound:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.TEXTURE,
                priority=OptimizationPriority.HIGH,
                title="Texture Bound - 优化纹理采样",
                description=(
                    "该 Shader 受纹理采样限制。考虑以下优化:\n"
                    "• 减少纹理采样次数，合并通道\n"
                    "• 使用较小的纹理或 Mipmap\n"
                    "• 考虑使用纹理数组替代多个单独纹理\n"
                    "• 避免依赖纹理采样（采样结果用于计算 UV）"
                ),
                expected_impact="可减少 20-40% 的 Texture 周期"
            ))
            
        elif 'load' in bound or 'store' in bound:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.MEMORY,
                priority=OptimizationPriority.HIGH,
                title="Load/Store Bound - 优化内存访问",
                description=(
                    "该 Shader 受内存访问限制。考虑以下优化:\n"
                    "• 减少 Uniform Buffer 访问次数\n"
                    "• 合并多个小的 Uniform 到 vec4\n"
                    "• 使用 UBO 替代多个独立 Uniform\n"
                    "• 确保内存访问对齐"
                ),
                expected_impact="可减少 15-25% 的 Load/Store 周期"
            ))
            
        elif 'vary' in bound:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.VARYING,
                priority=OptimizationPriority.HIGH,
                title="Varying Bound - 优化顶点到片元数据传递",
                description=(
                    "该 Shader 受 Varying 传递限制。考虑以下优化:\n"
                    "• 减少 Varying 数量，合并到 vec4\n"
                    "• 使用 flat 限定符避免插值\n"
                    "• 在 Fragment Shader 中重新计算简单值\n"
                    "• 使用打包格式传递多个值"
                ),
                expected_impact="可减少 20-30% 的 Varying 周期"
            ))
        
        return suggestions
    
    def _analyze_registers(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """寄存器使用分析"""
        suggestions = []
        
        work_regs = ctx.registers.get('work', 0)
        stack_spill = ctx.registers.get('stack_spilling', 0)
        
        if stack_spill and stack_spill > 0:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.REGISTER,
                priority=OptimizationPriority.CRITICAL,
                title="寄存器溢出 - 严重性能问题",
                description=(
                    f"检测到 {stack_spill} 字节的栈溢出。这会导致严重的性能下降。\n"
                    "• 减少同时使用的临时变量\n"
                    "• 分解复杂表达式为多个步骤\n"
                    "• 使用 mediump 减少寄存器占用\n"
                    "• 考虑将 Shader 拆分为多个 Pass"
                ),
                expected_impact="消除溢出可提升 50%+ 性能"
            ))
        
        if work_regs > self.THRESHOLDS['high_register_count']:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.REGISTER,
                priority=OptimizationPriority.MEDIUM,
                title=f"寄存器使用较高 ({work_regs} 个)",
                description=(
                    "高寄存器使用会降低 Warp 占用率。\n"
                    "• 减少临时变量的生存期\n"
                    "• 重用临时变量\n"
                    "• 使用 mediump 精度"
                ),
                expected_impact="可提升 GPU 占用率 10-20%"
            ))
        
        return suggestions
    
    def _analyze_sfu_usage(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """SFU（特殊函数单元）使用分析"""
        suggestions = []
        
        total_insts = sum(ctx.category_counts.values()) or 1
        sfu_count = ctx.category_counts.get('sfu', 0)
        sfu_ratio = sfu_count / total_insts
        
        if sfu_ratio > self.THRESHOLDS['high_sfu_ratio']:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.ARITHMETIC,
                priority=OptimizationPriority.HIGH,
                title=f"SFU 使用率高 ({sfu_ratio:.0%})",
                description=(
                    "大量使用 SFU 指令（sin/cos/sqrt/rsqrt/log/exp）。\n"
                    "• 使用查找表 (LUT) + 线性插值替代 sin/cos\n"
                    "• 使用 inversesqrt(x) * x 替代 sqrt(x)\n"
                    "• 预计算 log/exp 到 Uniform\n"
                    "• 使用多项式近似替代精确计算"
                ),
                expected_impact="可减少 30-50% 的 SFU 周期",
                code_example=(
                    "// 使用 LUT 替代 sin/cos\n"
                    "float fastSin(float x) {\n"
                    "    return texture(sinLUT, vec2(x / 6.28, 0.5)).r;\n"
                    "}\n\n"
                    "// 使用 rsqrt 替代 sqrt\n"
                    "float fastLen = x * inversesqrt(dot(x, x));"
                )
            ))
        
        return suggestions
    
    def _analyze_texture_usage(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """纹理使用分析"""
        suggestions = []
        
        tex_count = ctx.texture_count
        tex_cycles = ctx.cycles.get('texture', 0)
        
        if tex_count > self.THRESHOLDS['many_textures']:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.TEXTURE,
                priority=OptimizationPriority.MEDIUM,
                title=f"纹理采样数量较多 ({tex_count} 个)",
                description=(
                    "多次纹理采样会增加延迟和带宽消耗。\n"
                    "• 合并多个纹理到纹理数组\n"
                    "• 将多个通道数据打包到单个纹理\n"
                    "• 使用 Atlas 减少纹理切换\n"
                    "• 考虑是否所有采样都必要"
                ),
                expected_impact="可减少 10-20% 的纹理开销"
            ))
        
        if tex_cycles > self.THRESHOLDS['high_texture_cycles']:
            tex_inst_count = ctx.category_counts.get('texture', 0)
            if tex_inst_count > 0:
                suggestions.append(OptimizationSuggestion(
                    category=OptimizationCategory.TEXTURE,
                    priority=OptimizationPriority.MEDIUM,
                    title="考虑纹理预取和缓存优化",
                    description=(
                        "纹理周期较高，可能存在缓存未命中。\n"
                        "• 确保连续像素采样连续的纹理坐标\n"
                        "• 使用合适的 Mipmap 级别\n"
                        "• 避免依赖纹理采样模式"
                    ),
                    expected_impact="可提升纹理缓存命中率"
                ))
        
        return suggestions
    
    def _analyze_control_flow(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """控制流分析"""
        suggestions = []
        
        if ctx.has_discard and ctx.shader_type == 'fragment':
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.CONTROL_FLOW,
                priority=OptimizationPriority.MEDIUM,
                title="使用 discard 可能影响性能",
                description=(
                    "discard 会禁用 Early-Z 优化，影响深度测试效率。\n"
                    "• 尽早执行 discard 检查\n"
                    "• 考虑使用 Alpha Test 替代\n"
                    "• 将需要 discard 的对象单独渲染"
                ),
                expected_impact="可改善深度测试效率"
            ))
        
        if ctx.loop_depth > self.THRESHOLDS['deep_loops']:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.CONTROL_FLOW,
                priority=OptimizationPriority.HIGH,
                title=f"嵌套循环较深 (深度 {ctx.loop_depth})",
                description=(
                    "深层嵌套循环会导致线程发散和性能下降。\n"
                    "• 尽可能展开循环\n"
                    "• 减少循环迭代次数\n"
                    "• 将循环移到 Compute Shader 预处理"
                ),
                expected_impact="可减少 20-40% 的循环开销"
            ))
        
        if ctx.has_branching and ctx.branch_depth > 1:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.CONTROL_FLOW,
                priority=OptimizationPriority.LOW,
                title="存在分支，可能导致线程发散",
                description=(
                    "GPU 上分支会导致部分线程空转。\n"
                    "• 使用 mix()/step() 替代简单 if\n"
                    "• 确保分支条件在 Warp 内一致\n"
                    "• 将不同路径的对象分批渲染"
                ),
                expected_impact="可减少线程发散开销",
                code_example=(
                    "// 避免分支\n"
                    "// 替代: if (x > 0.5) y = a; else y = b;\n"
                    "y = mix(b, a, step(0.5, x));"
                )
            ))
        
        return suggestions
    
    def _analyze_varying(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """Varying 使用分析（仅 Fragment Shader）"""
        suggestions = []
        
        varying_cycles = ctx.cycles.get('varying', 0)
        
        if varying_cycles > self.THRESHOLDS['high_varying_cycles']:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.VARYING,
                priority=OptimizationPriority.MEDIUM,
                title=f"Varying 周期较高 ({varying_cycles:.1f})",
                description=(
                    "大量 Varying 数据传递会消耗带宽。\n"
                    "• 减少 Varying 数量，合并到 vec4\n"
                    "• 使用 flat 避免不必要的插值\n"
                    "• 在 Fragment Shader 中重新计算简单值\n"
                    "• 使用打包格式 (如 2x16 bit)"
                ),
                expected_impact="可减少 15-25% 的 Varying 开销"
            ))
        
        return suggestions
    
    def _analyze_hotspot(self, ctx: ShaderAnalysisContext) -> List[OptimizationSuggestion]:
        """热点 Shader 分析"""
        suggestions = []
        
        if ctx.usage_count > self.THRESHOLDS['high_usage']:
            suggestions.append(OptimizationSuggestion(
                category=OptimizationCategory.GENERAL,
                priority=OptimizationPriority.HIGH,
                title=f"热点 Shader - 被 {ctx.usage_count} 个 Draw Call 使用",
                description=(
                    "该 Shader 使用频率非常高，任何优化都会产生显著效果。\n"
                    "• 优先优化此 Shader\n"
                    "• 考虑是否可以合批减少 Draw Call\n"
                    "• 确保使用最优的渲染路径"
                ),
                expected_impact="优化此 Shader 将产生最大性能收益"
            ))
        
        return suggestions


# ============================================================================
# 报告生成辅助函数
# ============================================================================

def generate_optimization_report(
    analysis_results: List[Dict],
    include_code_examples: bool = True
) -> Dict:
    """
    为一组分析结果生成优化报告
    
    Args:
        analysis_results: Shader 分析结果列表
        include_code_examples: 是否包含代码示例
        
    Returns:
        Dict: 包含所有建议的报告
    """
    advisor = OptimizationAdvisor()
    report = {
        'summary': {
            'total_shaders': len(analysis_results),
            'total_suggestions': 0,
            'critical_issues': 0,
            'high_priority': 0,
        },
        'by_shader': [],
        'top_suggestions': [],
    }
    
    all_suggestions = []
    
    for result in analysis_results:
        if not result.get('success', True):
            continue
        
        # 构建上下文
        ctx = ShaderAnalysisContext(
            name=result.get('name', 'Unknown'),
            shader_type=result.get('type', 'fragment'),
            bound=result.get('bound', 'Unknown'),
            cycles=result.get('cycles', {}),
            registers=result.get('registers', {}),
            category_counts=result.get('category_counts', {}),
            mali_cycles=result.get('mali_cycles', {}),
            has_loops=result.get('has_loops', False),
            has_branching=result.get('has_branching', False),
            has_discard=result.get('has_discard', False),
            has_derivatives=result.get('has_derivatives', False),
            loop_depth=result.get('loop_depth', 0),
            branch_depth=result.get('branch_depth', 0),
            texture_count=result.get('texture_count', 0),
            sampler_count=result.get('sampler_count', 0),
            cbuffer_count=result.get('cbuffer_count', 0),
            temp_registers=result.get('temp_registers', 0),
            usage_count=result.get('usage_count', 1),
        )
        
        suggestions = advisor.analyze(ctx)
        
        shader_report = {
            'name': ctx.name,
            'type': ctx.shader_type,
            'bound': ctx.bound,
            'usage_count': ctx.usage_count,
            'suggestions': [s.to_dict() for s in suggestions],
        }
        
        if not include_code_examples:
            for s in shader_report['suggestions']:
                s.pop('code_example', None)
        
        report['by_shader'].append(shader_report)
        
        # 统计
        for s in suggestions:
            all_suggestions.append((ctx.name, s))
            if s.priority == OptimizationPriority.CRITICAL:
                report['summary']['critical_issues'] += 1
            elif s.priority == OptimizationPriority.HIGH:
                report['summary']['high_priority'] += 1
    
    report['summary']['total_suggestions'] = len(all_suggestions)
    
    # 选出 Top 建议
    priority_order = {
        OptimizationPriority.CRITICAL: 0,
        OptimizationPriority.HIGH: 1,
        OptimizationPriority.MEDIUM: 2,
        OptimizationPriority.LOW: 3,
    }
    all_suggestions.sort(key=lambda x: priority_order[x[1].priority])
    
    for shader_name, suggestion in all_suggestions[:10]:
        report['top_suggestions'].append({
            'shader': shader_name,
            **suggestion.to_dict()
        })
    
    return report


def generate_optimization_from_context(context: Any) -> Dict:
    """
    从 AnalysisContext 生成优化报告
    
    这是专为 generate_real_report.py 设计的入口函数，
    接收 AnalysisContext 并转换为优化建议。
    
    Args:
        context: AnalysisContext 对象（来自 bridge.py）
        
    Returns:
        Dict: 优化报告，格式与 generate_optimization_report 相同
    """
    # 如果没有 shaders 属性，返回空报告
    if not hasattr(context, 'shaders') or not context.shaders:
        return {
            'summary': {
                'total_shaders': 0,
                'total_suggestions': 0,
                'critical_issues': 0,
                'high_priority': 0,
            },
            'by_shader': [],
            'top_suggestions': [],
        }
    
    # 转换 shaders 为 analysis_results 格式
    analysis_results = []
    for shader in context.shaders:
        result = {
            'name': getattr(shader, 'name', 'Unknown'),
            'type': getattr(shader, 'shader_type', 'fragment'),
            'bound': getattr(shader, 'bound', 'Unknown'),
            'cycles': getattr(shader, 'cycles', {}),
            'registers': getattr(shader, 'registers', {}),
            'category_counts': getattr(shader, 'category_counts', {}),
            'mali_cycles': getattr(shader, 'mali_cycles', {}),
            'has_loops': getattr(shader, 'has_loops', False),
            'has_branching': getattr(shader, 'has_branching', False),
            'has_discard': getattr(shader, 'has_discard', False),
            'has_derivatives': getattr(shader, 'has_derivatives', False),
            'loop_depth': getattr(shader, 'loop_depth', 0),
            'branch_depth': getattr(shader, 'branch_depth', 0),
            'texture_count': getattr(shader, 'texture_count', 0),
            'sampler_count': getattr(shader, 'sampler_count', 0),
            'cbuffer_count': getattr(shader, 'cbuffer_count', 0),
            'temp_registers': getattr(shader, 'temp_registers', 0),
            'usage_count': getattr(shader, 'usage_count', 1),
            'success': True,
        }
        analysis_results.append(result)
    
    return generate_optimization_report(analysis_results, include_code_examples=True)
