"""
性能热点分析器 (Performance Hotspot Analyzer)
==============================================

基于 Draw Call 复杂度估算，识别性能瓶颈。

复杂度评分模型:
    Score = Primitives × Instances × RTCount × ShaderWeight × StateWeight

其中:
    - Primitives = vertex_count / 3 (或 index_count / 3)
    - Instances = instance_count
    - RTCount = len(rt_ids) (MRT 倍率)
    - ShaderWeight = 基于 Shader 指令数估算 (默认 1.0)
    - StateWeight = 考虑混合/深度测试等开销 (1.0 ~ 1.5)

Author: RDC Analyzer Team
Date: 2025-01
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum


class HotspotLevel(Enum):
    """热点级别"""
    CRITICAL = "critical"  # Top 5% - 严重瓶颈
    HIGH = "high"          # Top 10% - 高负载
    MEDIUM = "medium"      # Top 25% - 中等负载
    LOW = "low"            # 其他 - 正常


@dataclass
class DrawComplexityScore:
    """Draw Call 复杂度评分"""
    event_id: int
    name: str = ""
    
    # 原始数据
    primitive_count: int = 0      # 三角形数量
    vertex_count: int = 0         # 顶点数
    instance_count: int = 1       # 实例数
    rt_count: int = 1             # 渲染目标数量
    
    # 权重因子
    shader_weight: float = 1.0    # Shader 复杂度权重 (0.5 ~ 3.0)
    state_weight: float = 1.0     # 状态复杂度权重 (1.0 ~ 1.5)
    
    # 计算结果
    base_score: float = 0.0       # 基础分 = primitives × instances
    weighted_score: float = 0.0   # 加权分 = base × rt × shader × state
    
    # 分类
    hotspot_level: HotspotLevel = HotspotLevel.LOW
    percentile: float = 0.0       # 百分位 (0-100, 100 = 最重)
    
    # 关联数据
    pass_index: int = 0
    vs_id: str = ""
    ps_id: str = ""
    
    def calculate(self) -> float:
        """计算复杂度分数"""
        # 基础分: 几何复杂度
        if self.primitive_count > 0:
            geo_score = self.primitive_count
        else:
            geo_score = max(self.vertex_count // 3, 1)
        
        self.base_score = geo_score * self.instance_count
        
        # 加权分: 考虑渲染状态
        self.weighted_score = (
            self.base_score 
            * max(self.rt_count, 1)
            * self.shader_weight
            * self.state_weight
        )
        
        return self.weighted_score


@dataclass 
class PassHotspot:
    """Pass 级别热点聚合"""
    pass_index: int
    pass_name: str = ""
    
    # 聚合统计
    draw_count: int = 0
    total_score: float = 0.0
    avg_score: float = 0.0
    max_score: float = 0.0
    
    # 热点 Draw Calls
    top_draws: List[DrawComplexityScore] = field(default_factory=list)
    
    # 分类
    hotspot_level: HotspotLevel = HotspotLevel.LOW
    percentile: float = 0.0


@dataclass
class HotspotReport:
    """热点分析报告"""
    # 全局统计
    total_draws: int = 0
    total_score: float = 0.0
    avg_score: float = 0.0
    
    # 阈值
    critical_threshold: float = 0.0   # Top 5%
    high_threshold: float = 0.0       # Top 10%
    medium_threshold: float = 0.0     # Top 25%
    
    # 热点列表 (按 score 降序)
    hotspots: List[DrawComplexityScore] = field(default_factory=list)
    
    # Pass 级别聚合
    pass_hotspots: List[PassHotspot] = field(default_factory=list)
    
    # 优化建议
    suggestions: List[Dict[str, Any]] = field(default_factory=list)


class HotspotAnalyzer:
    """
    性能热点分析器
    
    使用方法:
        analyzer = HotspotAnalyzer()
        for draw in draw_calls:
            analyzer.add_draw(draw)
        report = analyzer.analyze()
    """
    
    # Shader 类型权重 (基于典型复杂度)
    SHADER_WEIGHTS = {
        "simple": 0.5,        # 简单着色器 (纯色、无光照)
        "standard": 1.0,      # 标准着色器 (基础光照)
        "pbr": 1.5,           # PBR 着色器
        "complex": 2.0,       # 复杂着色器 (多光源、SSS)
        "compute_heavy": 2.5, # 计算密集型
        "unknown": 1.0,       # 默认
    }
    
    # 状态权重因子
    STATE_WEIGHTS = {
        "blend_enabled": 0.1,   # Alpha 混合增加开销
        "depth_write": 0.0,     # 深度写入 (正常)
        "no_depth_test": 0.05,  # 无深度测试 (可能是 UI/后处理)
        "wireframe": -0.2,      # 线框模式 (更轻)
    }
    
    def __init__(self, shader_db: Optional[Dict[str, Dict]] = None):
        """
        初始化分析器
        
        Args:
            shader_db: Shader 数据库 {shader_id: {instruction_count, type, ...}}
        """
        self.shader_db = shader_db or {}
        self.scores: List[DrawComplexityScore] = []
        self._pass_draws: Dict[int, List[DrawComplexityScore]] = {}
    
    def add_draw(self, draw: Any) -> DrawComplexityScore:
        """
        添加 Draw Call 并计算复杂度
        
        Args:
            draw: DrawCallInfo 或包含 draw 信息的 dict
        
        Returns:
            计算后的 DrawComplexityScore
        """
        # 提取字段 (支持 dataclass 和 dict)
        if hasattr(draw, 'event_id'):
            event_id = draw.event_id
            name = getattr(draw, 'name', '')
            vertex_count = getattr(draw, 'vertex_count', 0)
            index_count = getattr(draw, 'index_count', 0)
            instance_count = getattr(draw, 'instance_count', 1) or 1
            rt_ids = getattr(draw, 'rt_ids', [])
            vs_id = getattr(draw, 'vs_id', '')
            ps_id = getattr(draw, 'ps_id', '')
            pass_index = getattr(draw, 'pass_index', 0)
            blend_enabled = getattr(draw, 'blend_enabled', False)
            depth_test = getattr(draw, 'depth_test', True)
            fill_mode = getattr(draw, 'fill_mode', 'solid')
        else:
            # Dict 格式
            event_id = draw.get('eid', draw.get('event_id', 0))
            name = draw.get('name', '')
            vertex_count = draw.get('vertex_count', draw.get('numVerts', 0))
            index_count = draw.get('index_count', draw.get('numIndices', 0))
            instance_count = draw.get('instance_count', draw.get('numInstances', 1)) or 1
            rt_ids = draw.get('rt_ids', draw.get('outputs', []))
            vs_id = draw.get('vs_id', draw.get('vs', ''))
            ps_id = draw.get('ps_id', draw.get('ps', ''))
            pass_index = draw.get('pass_index', 0)
            blend_enabled = draw.get('blend_enabled', False)
            depth_test = draw.get('depth_test', True)
            fill_mode = draw.get('fill_mode', 'solid')
        
        # 计算三角形数
        if index_count > 0:
            primitive_count = index_count // 3
        elif vertex_count > 0:
            primitive_count = vertex_count // 3
        else:
            primitive_count = 0
        
        # 计算 Shader 权重
        shader_weight = self._estimate_shader_weight(vs_id, ps_id)
        
        # 计算状态权重
        state_weight = 1.0
        if blend_enabled:
            state_weight += self.STATE_WEIGHTS["blend_enabled"]
        if not depth_test:
            state_weight += self.STATE_WEIGHTS["no_depth_test"]
        if fill_mode == "wireframe":
            state_weight += self.STATE_WEIGHTS["wireframe"]
        
        # 创建评分对象
        score = DrawComplexityScore(
            event_id=event_id,
            name=name,
            primitive_count=primitive_count,
            vertex_count=vertex_count,
            instance_count=instance_count,
            rt_count=len(rt_ids) if rt_ids else 1,
            shader_weight=shader_weight,
            state_weight=max(state_weight, 0.5),
            pass_index=pass_index,
            vs_id=vs_id,
            ps_id=ps_id,
        )
        
        # 计算分数
        score.calculate()
        
        # 记录
        self.scores.append(score)
        
        # 按 Pass 分组
        if pass_index not in self._pass_draws:
            self._pass_draws[pass_index] = []
        self._pass_draws[pass_index].append(score)
        
        return score
    
    def _estimate_shader_weight(self, vs_id: str, ps_id: str) -> float:
        """
        估算 Shader 复杂度权重
        
        基于:
        1. Shader 数据库中的指令数
        2. Shader 名称启发式推断
        """
        weight = 1.0
        
        # 查询 Shader 数据库
        for shader_id in [vs_id, ps_id]:
            if shader_id and shader_id in self.shader_db:
                shader_info = self.shader_db[shader_id]
                instr_count = shader_info.get('instruction_count', 0)
                if instr_count > 0:
                    # 基于指令数估算 (100 指令 = 1.0, 500 指令 = 2.0)
                    weight = max(weight, 0.5 + (instr_count / 200))
        
        # 名称启发式
        name_lower = (vs_id + ps_id).lower()
        if 'pbr' in name_lower or 'physical' in name_lower:
            weight = max(weight, self.SHADER_WEIGHTS["pbr"])
        elif 'shadow' in name_lower or 'depth' in name_lower:
            weight = max(weight, self.SHADER_WEIGHTS["simple"])
        elif 'post' in name_lower or 'blur' in name_lower:
            weight = max(weight, self.SHADER_WEIGHTS["compute_heavy"])
        
        return min(weight, 3.0)  # 上限
    
    def analyze(self, top_n: int = 20) -> HotspotReport:
        """
        执行分析，生成热点报告
        
        Args:
            top_n: 返回的热点数量
        
        Returns:
            HotspotReport
        """
        if not self.scores:
            return HotspotReport()
        
        # 按分数排序
        sorted_scores = sorted(self.scores, key=lambda x: x.weighted_score, reverse=True)
        
        # 计算统计量
        total_score = sum(s.weighted_score for s in sorted_scores)
        avg_score = total_score / len(sorted_scores)
        
        # 计算百分位阈值
        n = len(sorted_scores)
        critical_idx = max(0, int(n * 0.05) - 1)
        high_idx = max(0, int(n * 0.10) - 1)
        medium_idx = max(0, int(n * 0.25) - 1)
        
        critical_threshold = sorted_scores[critical_idx].weighted_score if n > 0 else 0
        high_threshold = sorted_scores[high_idx].weighted_score if n > 0 else 0
        medium_threshold = sorted_scores[medium_idx].weighted_score if n > 0 else 0
        
        # 分配热点级别
        for i, score in enumerate(sorted_scores):
            percentile = 100 * (1 - i / n) if n > 0 else 0
            score.percentile = percentile
            
            if score.weighted_score >= critical_threshold and i < max(1, int(n * 0.05)):
                score.hotspot_level = HotspotLevel.CRITICAL
            elif score.weighted_score >= high_threshold and i < max(1, int(n * 0.10)):
                score.hotspot_level = HotspotLevel.HIGH
            elif score.weighted_score >= medium_threshold and i < max(1, int(n * 0.25)):
                score.hotspot_level = HotspotLevel.MEDIUM
            else:
                score.hotspot_level = HotspotLevel.LOW
        
        # Pass 级别聚合
        pass_hotspots = self._aggregate_passes()
        
        # 生成建议
        suggestions = self._generate_suggestions(sorted_scores[:top_n])
        
        return HotspotReport(
            total_draws=len(sorted_scores),
            total_score=total_score,
            avg_score=avg_score,
            critical_threshold=critical_threshold,
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            hotspots=sorted_scores[:top_n],
            pass_hotspots=pass_hotspots,
            suggestions=suggestions,
        )
    
    def _aggregate_passes(self) -> List[PassHotspot]:
        """聚合 Pass 级别热点"""
        pass_hotspots = []
        
        for pass_idx, draws in sorted(self._pass_draws.items()):
            if not draws:
                continue
            
            total = sum(d.weighted_score for d in draws)
            max_score = max(d.weighted_score for d in draws)
            avg = total / len(draws)
            
            # Top 3 draws in this pass
            top_draws = sorted(draws, key=lambda x: x.weighted_score, reverse=True)[:3]
            
            ph = PassHotspot(
                pass_index=pass_idx,
                draw_count=len(draws),
                total_score=total,
                avg_score=avg,
                max_score=max_score,
                top_draws=top_draws,
            )
            pass_hotspots.append(ph)
        
        # 按总分排序
        pass_hotspots.sort(key=lambda x: x.total_score, reverse=True)
        
        # 分配级别
        if pass_hotspots:
            n = len(pass_hotspots)
            for i, ph in enumerate(pass_hotspots):
                ph.percentile = 100 * (1 - i / n)
                if i < max(1, int(n * 0.1)):
                    ph.hotspot_level = HotspotLevel.CRITICAL
                elif i < max(1, int(n * 0.25)):
                    ph.hotspot_level = HotspotLevel.HIGH
                elif i < max(1, int(n * 0.5)):
                    ph.hotspot_level = HotspotLevel.MEDIUM
        
        return pass_hotspots
    
    def _generate_suggestions(self, hotspots: List[DrawComplexityScore]) -> List[Dict[str, Any]]:
        """为热点生成优化建议"""
        suggestions = []
        
        for hs in hotspots:
            if hs.hotspot_level == HotspotLevel.LOW:
                continue
            
            sugg = {
                "event_id": hs.event_id,
                "name": hs.name,
                "level": hs.hotspot_level.value,
                "score": hs.weighted_score,
                "reasons": [],
                "recommendations": [],
            }
            
            # 分析原因
            if hs.primitive_count > 100000:
                sugg["reasons"].append(f"高多边形数: {hs.primitive_count:,} triangles")
                sugg["recommendations"].append("考虑使用 LOD (Level of Detail)")
                sugg["recommendations"].append("检查是否可以剔除不可见几何体")
            
            if hs.instance_count > 100:
                sugg["reasons"].append(f"大量实例: {hs.instance_count:,} instances")
                sugg["recommendations"].append("验证实例数是否必要")
                sugg["recommendations"].append("考虑合并静态实例")
            
            if hs.rt_count > 4:
                sugg["reasons"].append(f"多渲染目标 (MRT): {hs.rt_count} RTs")
                sugg["recommendations"].append("检查是否可以减少 G-Buffer 输出")
            
            if hs.shader_weight > 1.5:
                sugg["reasons"].append("复杂着色器")
                sugg["recommendations"].append("考虑简化 Shader 逻辑")
                sugg["recommendations"].append("检查是否有冗余纹理采样")
            
            if not sugg["reasons"]:
                sugg["reasons"].append("综合复杂度较高")
                sugg["recommendations"].append("分析具体渲染内容")
            
            suggestions.append(sugg)
        
        return suggestions
    
    def get_score_distribution(self, bins: int = 10) -> List[Tuple[float, float, int]]:
        """
        获取分数分布直方图数据
        
        Returns:
            List of (min, max, count) tuples
        """
        if not self.scores:
            return []
        
        scores = [s.weighted_score for s in self.scores]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [(min_score, max_score, len(scores))]
        
        bin_width = (max_score - min_score) / bins
        distribution = []
        
        for i in range(bins):
            bin_min = min_score + i * bin_width
            bin_max = bin_min + bin_width
            count = sum(1 for s in scores if bin_min <= s < bin_max or (i == bins - 1 and s == max_score))
            distribution.append((bin_min, bin_max, count))
        
        return distribution


def analyze_hotspots(draw_calls: List[Any], 
                     shader_db: Optional[Dict] = None,
                     top_n: int = 20) -> HotspotReport:
    """
    便捷函数: 分析 Draw Calls 的性能热点
    
    Args:
        draw_calls: DrawCallInfo 列表或 dict 列表
        shader_db: 可选的 Shader 数据库
        top_n: 返回热点数量
    
    Returns:
        HotspotReport
    """
    analyzer = HotspotAnalyzer(shader_db=shader_db)
    for draw in draw_calls:
        analyzer.add_draw(draw)
    return analyzer.analyze(top_n=top_n)
