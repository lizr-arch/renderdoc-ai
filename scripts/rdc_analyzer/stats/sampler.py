#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多帧统计采样器
==============

从多个帧样本中聚合统计数据，降低单帧噪声。

用法:
    sampler = MultiFrameSampler()
    sampler.add_sample(frame1_data)
    sampler.add_sample(frame2_data)
    sampler.add_sample(frame3_data)
    
    aggregated = sampler.aggregate()
    print(f"Draw Calls: {aggregated.draw_calls.mean} ± {aggregated.draw_calls.std}")
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import statistics
from pathlib import Path


@dataclass
class MetricStatistics:
    """单个指标的统计数据"""
    
    values: List[float] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        """样本数量"""
        return len(self.values)
    
    @property
    def mean(self) -> float:
        """均值"""
        if not self.values:
            return 0.0
        return statistics.mean(self.values)
    
    @property
    def median(self) -> float:
        """中位数"""
        if not self.values:
            return 0.0
        return statistics.median(self.values)
    
    @property
    def std(self) -> float:
        """标准差"""
        if len(self.values) < 2:
            return 0.0
        return statistics.stdev(self.values)
    
    @property
    def min(self) -> float:
        """最小值"""
        if not self.values:
            return 0.0
        return min(self.values)
    
    @property
    def max(self) -> float:
        """最大值"""
        if not self.values:
            return 0.0
        return max(self.values)
    
    @property
    def p95(self) -> float:
        """95th 百分位数"""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = int(len(sorted_vals) * 0.95)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]
    
    @property
    def p99(self) -> float:
        """99th 百分位数"""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = int(len(sorted_vals) * 0.99)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]
    
    @property
    def cv(self) -> float:
        """变异系数 (Coefficient of Variation)
        
        CV = std / mean，用于衡量数据离散程度。
        CV < 0.1: 低波动 (稳定)
        CV 0.1-0.3: 中等波动
        CV > 0.3: 高波动 (不稳定)
        """
        if self.mean == 0:
            return 0.0
        return self.std / abs(self.mean)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "count": self.count,
            "mean": round(self.mean, 2),
            "median": round(self.median, 2),
            "std": round(self.std, 2),
            "min": round(self.min, 2),
            "max": round(self.max, 2),
            "p95": round(self.p95, 2),
            "p99": round(self.p99, 2),
            "cv": round(self.cv, 4),
        }


@dataclass
class FrameSample:
    """单帧样本数据"""
    
    # 基础指标
    draw_calls: int = 0
    vertices: int = 0
    triangles: int = 0
    
    # 资源指标
    texture_count: int = 0
    texture_memory_bytes: int = 0
    buffer_count: int = 0
    buffer_memory_bytes: int = 0
    shader_count: int = 0
    
    # Pass 指标
    pass_count: int = 0
    
    # 来源信息
    source_file: str = ""
    frame_index: int = 0
    
    # 扩展指标 (可选)
    extra_metrics: Dict[str, float] = field(default_factory=dict)
    
    @classmethod
    def from_json_data(cls, data: Dict[str, Any], source_file: str = "", frame_index: int = 0) -> "FrameSample":
        """从 JSON 数据创建样本
        
        Args:
            data: JSON 数据 (支持 Phase 1/Phase 2 格式)
            source_file: 来源文件名
            frame_index: 帧索引
            
        Returns:
            FrameSample 实例
        """
        # 尝试从 statistics 或 summary 获取数据
        stats = data.get("statistics", {})
        summary = data.get("summary", {})
        
        # 优先使用 statistics，回退到 summary
        draw_calls = (
            stats.get("totalDrawCalls", 0) or 
            summary.get("draw_call_count", 0)
        )
        vertices = (
            stats.get("totalVertices", 0) or 
            summary.get("total_vertices", 0)
        )
        triangles = (
            stats.get("totalTriangles", 0) or 
            summary.get("total_triangles", 0)
        )
        
        # 纹理统计
        textures = data.get("textures", [])
        texture_count = stats.get("textureCount", 0) or len(textures)
        texture_memory = sum(t.get("size_bytes", 0) for t in textures)
        
        # Buffer 统计
        buffers = data.get("buffers", [])
        buffer_count = len(buffers)
        buffer_memory = sum(b.get("size_bytes", b.get("size", 0)) for b in buffers)
        
        # Shader 统计
        shaders = data.get("shaders", [])
        shader_count = stats.get("shaderCount", 0) or len(shaders)
        
        return cls(
            draw_calls=draw_calls,
            vertices=vertices,
            triangles=triangles,
            texture_count=texture_count,
            texture_memory_bytes=texture_memory,
            buffer_count=buffer_count,
            buffer_memory_bytes=buffer_memory,
            shader_count=shader_count,
            source_file=source_file,
            frame_index=frame_index,
        )


@dataclass
class AggregatedMetrics:
    """聚合后的统计指标"""
    
    # 各指标的统计数据
    draw_calls: MetricStatistics = field(default_factory=MetricStatistics)
    vertices: MetricStatistics = field(default_factory=MetricStatistics)
    triangles: MetricStatistics = field(default_factory=MetricStatistics)
    texture_count: MetricStatistics = field(default_factory=MetricStatistics)
    texture_memory: MetricStatistics = field(default_factory=MetricStatistics)
    buffer_count: MetricStatistics = field(default_factory=MetricStatistics)
    buffer_memory: MetricStatistics = field(default_factory=MetricStatistics)
    shader_count: MetricStatistics = field(default_factory=MetricStatistics)
    
    # 采样元信息
    sample_count: int = 0
    source_files: List[str] = field(default_factory=list)
    
    # 扩展指标
    extra_metrics: Dict[str, MetricStatistics] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 JSON 输出"""
        result = {
            "sample_count": self.sample_count,
            "source_files": self.source_files,
            "metrics": {
                "draw_calls": self.draw_calls.to_dict(),
                "vertices": self.vertices.to_dict(),
                "triangles": self.triangles.to_dict(),
                "texture_count": self.texture_count.to_dict(),
                "texture_memory_bytes": self.texture_memory.to_dict(),
                "buffer_count": self.buffer_count.to_dict(),
                "buffer_memory_bytes": self.buffer_memory.to_dict(),
                "shader_count": self.shader_count.to_dict(),
            }
        }
        
        if self.extra_metrics:
            result["extra_metrics"] = {
                k: v.to_dict() for k, v in self.extra_metrics.items()
            }
        
        return result
    
    def to_compare_data(self) -> Dict[str, Any]:
        """转换为 DiffEngine 可用的格式
        
        使用均值作为代表值，与单帧对比逻辑兼容。
        同时保留统计信息供显著性检测使用。
        """
        return {
            "statistics": {
                "totalDrawCalls": int(self.draw_calls.mean),
                "totalVertices": int(self.vertices.mean),
                "totalTriangles": int(self.triangles.mean),
                "textureCount": int(self.texture_count.mean),
                "shaderCount": int(self.shader_count.mean),
            },
            "summary": {
                "draw_call_count": int(self.draw_calls.mean),
                "total_vertices": int(self.vertices.mean),
                "total_triangles": int(self.triangles.mean),
                "texture_count": int(self.texture_count.mean),
                "shader_count": int(self.shader_count.mean),
            },
            "textures": [],  # 多帧模式下不提供细粒度资源对比
            "shaders": [],
            "buffers": [],
            "draw_calls": [],
            # 附加统计信息供显著性检测
            "_statistics": self.to_dict(),
        }


class MultiFrameSampler:
    """多帧统计采样器
    
    收集多个帧样本，输出统计聚合结果。
    
    用法:
        sampler = MultiFrameSampler()
        
        # 添加样本
        for json_data in json_files:
            sampler.add_sample_from_json(json_data)
        
        # 获取聚合结果
        aggregated = sampler.aggregate()
        print(f"Draw Calls: {aggregated.draw_calls.mean} ± {aggregated.draw_calls.std}")
    """
    
    def __init__(self):
        self._samples: List[FrameSample] = []
    
    @property
    def sample_count(self) -> int:
        """当前样本数量"""
        return len(self._samples)
    
    def add_sample(self, sample: FrameSample) -> None:
        """添加帧样本
        
        Args:
            sample: FrameSample 实例
        """
        self._samples.append(sample)
    
    def add_sample_from_json(
        self, 
        data: Dict[str, Any], 
        source_file: str = "",
        frame_index: Optional[int] = None
    ) -> None:
        """从 JSON 数据添加样本
        
        Args:
            data: JSON 数据
            source_file: 来源文件名
            frame_index: 帧索引 (默认自动递增)
        """
        if frame_index is None:
            frame_index = len(self._samples)
        
        sample = FrameSample.from_json_data(data, source_file, frame_index)
        self.add_sample(sample)
    
    def add_samples_from_directory(
        self,
        directory: str,
        pattern: str = "*.json"
    ) -> int:
        """从目录批量加载样本
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            
        Returns:
            加载的样本数量
        """
        import json
        
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        count = 0
        for json_file in sorted(dir_path.glob(pattern)):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 处理列表格式 (Phase 1)
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                
                self.add_sample_from_json(data, json_file.name)
                count += 1
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[!] 跳过无效文件: {json_file.name} ({e})")
        
        return count
    
    def clear(self) -> None:
        """清空所有样本"""
        self._samples.clear()
    
    def aggregate(self) -> AggregatedMetrics:
        """聚合所有样本，生成统计结果
        
        Returns:
            AggregatedMetrics 实例，包含各指标的统计数据
        """
        if not self._samples:
            return AggregatedMetrics()
        
        # 初始化统计对象
        result = AggregatedMetrics(
            sample_count=len(self._samples),
            source_files=[s.source_file for s in self._samples if s.source_file],
        )
        
        # 收集各指标的值
        for sample in self._samples:
            result.draw_calls.values.append(float(sample.draw_calls))
            result.vertices.values.append(float(sample.vertices))
            result.triangles.values.append(float(sample.triangles))
            result.texture_count.values.append(float(sample.texture_count))
            result.texture_memory.values.append(float(sample.texture_memory_bytes))
            result.buffer_count.values.append(float(sample.buffer_count))
            result.buffer_memory.values.append(float(sample.buffer_memory_bytes))
            result.shader_count.values.append(float(sample.shader_count))
            
            # 扩展指标
            for key, value in sample.extra_metrics.items():
                if key not in result.extra_metrics:
                    result.extra_metrics[key] = MetricStatistics()
                result.extra_metrics[key].values.append(float(value))
        
        return result
    
    def get_stability_report(self) -> Dict[str, Any]:
        """生成数据稳定性报告
        
        评估各指标的波动程度，用于判断采样是否充分。
        
        Returns:
            稳定性报告，包含各指标的 CV 值和稳定性评级
        """
        aggregated = self.aggregate()
        
        def classify_stability(cv: float) -> str:
            if cv < 0.05:
                return "excellent"  # 非常稳定
            elif cv < 0.10:
                return "good"       # 稳定
            elif cv < 0.20:
                return "moderate"   # 中等波动
            else:
                return "unstable"   # 不稳定，建议增加采样
        
        metrics_cv = {
            "draw_calls": aggregated.draw_calls.cv,
            "vertices": aggregated.vertices.cv,
            "triangles": aggregated.triangles.cv,
            "texture_count": aggregated.texture_count.cv,
            "texture_memory": aggregated.texture_memory.cv,
            "buffer_count": aggregated.buffer_count.cv,
            "buffer_memory": aggregated.buffer_memory.cv,
        }
        
        return {
            "sample_count": aggregated.sample_count,
            "metrics": {
                k: {
                    "cv": round(v, 4),
                    "stability": classify_stability(v)
                }
                for k, v in metrics_cv.items()
            },
            "overall_stability": classify_stability(
                sum(metrics_cv.values()) / len(metrics_cv)
            ),
            "recommendation": (
                "sufficient" if aggregated.sample_count >= 3 
                and all(v < 0.2 for v in metrics_cv.values())
                else "need_more_samples"
            ),
        }
