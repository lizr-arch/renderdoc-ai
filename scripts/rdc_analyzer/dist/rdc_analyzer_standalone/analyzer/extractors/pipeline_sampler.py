"""
PipelineSnapshot 采样器
======================

提供非 Mali 路径的最小管线状态采样功能。

功能:
- 采样 N 个关键 draw/dispatch 调用
- 提取最小 PipelineSnapshot (VS/PS/RT/DS/viewport/scissor/topology)
- 支持采样策略配置

采样策略:
- uniform: 均匀采样
- first_n: 采样前 N 个
- last_n: 采样后 N 个
- diverse: 尝试采样不同着色器组合的 draw call
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

# 核心类型
from ..core.pipeline_state import (
    PipelineSnapshot,
    ResourceBinding,
    ShaderBindings,
    RenderTargetInfo,
    DepthStencilInfo,
    ViewportInfo,
    ScissorRect,
    DrawCallDetail,
    ResourceType,
    ShaderStage,
    PrimitiveTopology,
    DrawType,
)

logger = logging.getLogger(__name__)


class SamplingStrategy(Enum):
    """采样策略"""
    UNIFORM = auto()      # 均匀采样
    FIRST_N = auto()      # 采样前 N 个
    LAST_N = auto()       # 采样后 N 个
    DIVERSE = auto()      # 多样性采样（不同着色器组合）


@dataclass
class SamplingConfig:
    """采样配置"""
    sample_count: int = 20              # 采样数量
    strategy: SamplingStrategy = SamplingStrategy.UNIFORM
    include_dispatches: bool = True      # 是否包含 dispatch 调用
    skip_clears: bool = True            # 是否跳过 clear 操作
    
    # 最小采样内容
    extract_vertex_shader: bool = True
    extract_pixel_shader: bool = True
    extract_compute_shader: bool = True
    extract_render_targets: bool = True
    extract_depth_stencil: bool = True
    extract_viewports: bool = True
    extract_scissors: bool = True
    extract_topology: bool = True


@dataclass
class PipelineSample:
    """单个管线状态采样结果"""
    event_id: int
    name: str
    draw_type: DrawType
    snapshot: PipelineSnapshot
    
    # 着色器 ID (用于多样性采样)
    vertex_shader_id: int = 0
    pixel_shader_id: int = 0
    compute_shader_id: int = 0
    
    # 可选的绘制参数
    vertex_count: int = 0
    index_count: int = 0
    instance_count: int = 1
    
    def shader_signature(self) -> Tuple[int, int, int]:
        """返回着色器签名 (用于去重)"""
        return (self.vertex_shader_id, self.pixel_shader_id, self.compute_shader_id)


@dataclass
class SamplingResult:
    """采样结果"""
    samples: List[PipelineSample] = field(default_factory=list)
    total_candidates: int = 0
    sampled_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    
    # 统计信息
    unique_shaders: int = 0
    unique_render_targets: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_candidates": self.total_candidates,
            "sampled_count": self.sampled_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "unique_shaders": self.unique_shaders,
            "unique_render_targets": self.unique_render_targets,
            "samples": [
                {
                    "event_id": s.event_id,
                    "name": s.name,
                    "draw_type": s.draw_type.name,
                    "vertex_shader_id": s.vertex_shader_id,
                    "pixel_shader_id": s.pixel_shader_id,
                    "pipeline": s.snapshot.to_dict() if s.snapshot else None,
                }
                for s in self.samples
            ]
        }


class PipelineSampler:
    """
    管线状态采样器
    
    提供非 Mali 路径的最小管线状态采样功能。
    当 ReplayController 可用时，可以采样关键 draw/dispatch 调用的管线状态。
    
    使用方式:
        sampler = PipelineSampler(controller, config)
        result = sampler.sample_from_draw_calls(draw_calls)
    """
    
    def __init__(
        self,
        controller: Any,
        config: Optional[SamplingConfig] = None
    ):
        """
        初始化采样器
        
        Args:
            controller: RenderDoc ReplayController 实例
            config: 采样配置
        """
        self.controller = controller
        self.config = config or SamplingConfig()
        
        # 缓存
        self._shader_ids_seen: set = set()
        self._rt_ids_seen: set = set()
    
    def sample_from_events(
        self,
        events: List[Dict[str, Any]]
    ) -> SamplingResult:
        """
        从事件列表中采样管线状态
        
        Args:
            events: 事件列表 (包含 eventId, name, flags 等)
            
        Returns:
            SamplingResult: 采样结果
        """
        try:
            import renderdoc as rd
        except ImportError:
            logger.error("无法导入 renderdoc 模块")
            return SamplingResult(error_count=1)
        
        # 筛选候选事件
        candidates = []
        for event in events:
            flags = event.get('flags', 0)
            
            # 检查是否是 draw call
            is_draw = bool(flags & int(rd.ActionFlags.Drawcall))
            is_dispatch = bool(flags & int(rd.ActionFlags.Dispatch))
            is_clear = bool(flags & int(rd.ActionFlags.Clear))
            
            # 应用过滤
            if is_clear and self.config.skip_clears:
                continue
            
            if is_dispatch and not self.config.include_dispatches:
                continue
            
            if is_draw or (is_dispatch and self.config.include_dispatches):
                candidates.append(event)
        
        result = SamplingResult(total_candidates=len(candidates))
        
        if not candidates:
            logger.warning("没有找到可采样的事件")
            return result
        
        # 选择采样索引
        sample_indices = self._select_sample_indices(
            len(candidates),
            self.config.sample_count,
            self.config.strategy
        )
        
        logger.info(f"采样 {len(sample_indices)}/{len(candidates)} 个事件")
        
        # 执行采样
        for idx in sample_indices:
            event = candidates[idx]
            try:
                sample = self._sample_single_event(event, rd)
                if sample:
                    result.samples.append(sample)
                    result.sampled_count += 1
                    
                    # 更新统计
                    sig = sample.shader_signature()
                    self._shader_ids_seen.add(sig)
                else:
                    result.skipped_count += 1
            except Exception as e:
                logger.debug(f"采样事件 {event.get('eventId')} 失败: {e}")
                result.error_count += 1
        
        # 最终统计
        result.unique_shaders = len(self._shader_ids_seen)
        result.unique_render_targets = len(self._rt_ids_seen)
        
        return result
    
    def sample_diverse(
        self,
        events: List[Dict[str, Any]],
        max_samples: Optional[int] = None
    ) -> SamplingResult:
        """
        多样性采样：尝试采样不同着色器组合的事件
        
        Args:
            events: 事件列表
            max_samples: 最大采样数量
            
        Returns:
            SamplingResult: 采样结果
        """
        original_strategy = self.config.strategy
        original_count = self.config.sample_count
        
        try:
            self.config.strategy = SamplingStrategy.DIVERSE
            if max_samples:
                self.config.sample_count = max_samples
            
            return self.sample_from_events(events)
        finally:
            self.config.strategy = original_strategy
            self.config.sample_count = original_count
    
    def _select_sample_indices(
        self,
        total_count: int,
        sample_count: int,
        strategy: SamplingStrategy
    ) -> List[int]:
        """根据策略选择采样索引"""
        if sample_count >= total_count:
            return list(range(total_count))
        
        if strategy == SamplingStrategy.FIRST_N:
            return list(range(sample_count))
        
        elif strategy == SamplingStrategy.LAST_N:
            return list(range(total_count - sample_count, total_count))
        
        elif strategy == SamplingStrategy.UNIFORM:
            # 均匀分布采样
            step = total_count / sample_count
            return [int(i * step) for i in range(sample_count)]
        
        elif strategy == SamplingStrategy.DIVERSE:
            # 多样性采样：先均匀采样一半，剩下的在采样时动态选择
            # 这里先返回均匀采样，实际多样性逻辑在采样时处理
            half_count = sample_count
            step = total_count / half_count
            return [int(i * step) for i in range(half_count)]
        
        return list(range(min(sample_count, total_count)))
    
    def _sample_single_event(
        self,
        event: Dict[str, Any],
        rd: Any
    ) -> Optional[PipelineSample]:
        """采样单个事件的管线状态"""
        event_id = event.get('eventId', 0)
        name = event.get('name', '')
        flags = event.get('flags', 0)
        
        # 移动到目标事件
        self.controller.SetFrameEvent(event_id, True)
        
        # 获取管线状态
        state = self.controller.GetPipelineState()
        if not state:
            return None
        
        # 确定 draw type
        draw_type = self._determine_draw_type(flags, rd)
        
        # 创建快照
        snapshot = PipelineSnapshot()
        
        # 着色器 ID
        vs_id, ps_id, cs_id = 0, 0, 0
        
        # 提取着色器
        if draw_type == DrawType.DISPATCH:
            # Compute shader
            if self.config.extract_compute_shader:
                try:
                    cs_refl = state.GetShaderReflection(rd.ShaderStage.Compute)
                    if cs_refl:
                        cs_id = int(cs_refl.resourceId)
                        snapshot.compute_shader = ShaderBindings(
                            stage=ShaderStage.COMPUTE,
                            resource_id=cs_id,
                            name=cs_refl.debugName if hasattr(cs_refl, 'debugName') else ""
                        )
                except Exception:
                    pass
        else:
            # Graphics pipeline
            if self.config.extract_vertex_shader:
                try:
                    vs_refl = state.GetShaderReflection(rd.ShaderStage.Vertex)
                    if vs_refl:
                        vs_id = int(vs_refl.resourceId)
                        snapshot.vertex_shader = ShaderBindings(
                            stage=ShaderStage.VERTEX,
                            resource_id=vs_id,
                            name=vs_refl.debugName if hasattr(vs_refl, 'debugName') else ""
                        )
                except Exception:
                    pass
            
            if self.config.extract_pixel_shader:
                try:
                    ps_refl = state.GetShaderReflection(rd.ShaderStage.Pixel)
                    if ps_refl:
                        ps_id = int(ps_refl.resourceId)
                        snapshot.pixel_shader = ShaderBindings(
                            stage=ShaderStage.PIXEL,
                            resource_id=ps_id,
                            name=ps_refl.debugName if hasattr(ps_refl, 'debugName') else ""
                        )
                except Exception:
                    pass
        
        # 提取渲染目标和深度模板
        if self.config.extract_render_targets or self.config.extract_depth_stencil:
            self._extract_output_merger(snapshot, state, rd)
        
        # 提取视口和裁剪
        if self.config.extract_viewports or self.config.extract_scissors:
            self._extract_viewports_scissors(snapshot, state)
        
        # 提取拓扑
        if self.config.extract_topology:
            self._extract_topology(snapshot, state, rd)
        
        # 创建采样结果
        sample = PipelineSample(
            event_id=event_id,
            name=name,
            draw_type=draw_type,
            snapshot=snapshot,
            vertex_shader_id=vs_id,
            pixel_shader_id=ps_id,
            compute_shader_id=cs_id,
            vertex_count=event.get('numIndices', 0) or 0,
            index_count=event.get('numIndices', 0) or 0,
            instance_count=event.get('numInstances', 1) or 1,
        )
        
        return sample
    
    def _determine_draw_type(self, flags: int, rd: Any) -> DrawType:
        """确定绘制类型"""
        if flags & int(rd.ActionFlags.Dispatch):
            return DrawType.DISPATCH
        elif flags & int(rd.ActionFlags.Clear):
            return DrawType.CLEAR_RTV
        elif flags & int(rd.ActionFlags.Indexed):
            if flags & int(rd.ActionFlags.Instanced):
                return DrawType.DRAW_INDEXED_INSTANCED
            return DrawType.DRAW_INDEXED
        elif flags & int(rd.ActionFlags.Instanced):
            return DrawType.DRAW_INSTANCED
        elif flags & int(rd.ActionFlags.Drawcall):
            return DrawType.DRAW
        return DrawType.OTHER
    
    def _extract_output_merger(
        self,
        snapshot: PipelineSnapshot,
        state: Any,
        rd: Any
    ):
        """提取输出合并阶段信息"""
        try:
            # 获取输出目标
            outputs = state.GetOutputTargets()
            
            if self.config.extract_render_targets:
                for i, output in enumerate(outputs):
                    if output.resourceId != rd.ResourceId.Null():
                        # 获取纹理描述
                        try:
                            tex_desc = self.controller.GetTexture(output.resourceId)
                            width = tex_desc.width if tex_desc else 0
                            height = tex_desc.height if tex_desc else 0
                            fmt = str(tex_desc.format.Name()) if tex_desc and hasattr(tex_desc.format, 'Name') else ""
                        except Exception:
                            width, height, fmt = 0, 0, ""
                        
                        rt_id = int(output.resourceId)
                        self._rt_ids_seen.add(rt_id)
                        
                        snapshot.render_targets.append(RenderTargetInfo(
                            slot=i,
                            resource_id=rt_id,
                            width=width,
                            height=height,
                            format=fmt
                        ))
            
            if self.config.extract_depth_stencil:
                depth = state.GetDepthTarget()
                if depth.resourceId != rd.ResourceId.Null():
                    try:
                        tex_desc = self.controller.GetTexture(depth.resourceId)
                        width = tex_desc.width if tex_desc else 0
                        height = tex_desc.height if tex_desc else 0
                        fmt = str(tex_desc.format.Name()) if tex_desc and hasattr(tex_desc.format, 'Name') else ""
                    except Exception:
                        width, height, fmt = 0, 0, ""
                    
                    snapshot.depth_stencil = DepthStencilInfo(
                        resource_id=int(depth.resourceId),
                        width=width,
                        height=height,
                        format=fmt
                    )
        except Exception as e:
            logger.debug(f"提取 output merger 失败: {e}")
    
    def _extract_viewports_scissors(
        self,
        snapshot: PipelineSnapshot,
        state: Any
    ):
        """提取视口和裁剪矩形"""
        try:
            if self.config.extract_viewports:
                viewports = state.GetViewportScissor().viewportScissors
                for vp_sc in viewports:
                    vp = vp_sc.vp
                    if vp.width > 0 and vp.height > 0:
                        snapshot.viewports.append(ViewportInfo(
                            x=vp.x,
                            y=vp.y,
                            width=vp.width,
                            height=vp.height,
                            min_depth=vp.minDepth,
                            max_depth=vp.maxDepth
                        ))
            
            if self.config.extract_scissors:
                viewports = state.GetViewportScissor().viewportScissors
                for vp_sc in viewports:
                    sc = vp_sc.scissor
                    if sc.width > 0 and sc.height > 0:
                        snapshot.scissor_rects.append(ScissorRect(
                            x=sc.x,
                            y=sc.y,
                            width=sc.width,
                            height=sc.height
                        ))
        except Exception as e:
            logger.debug(f"提取 viewport/scissor 失败: {e}")
    
    def _extract_topology(
        self,
        snapshot: PipelineSnapshot,
        state: Any,
        rd: Any
    ):
        """提取图元拓扑"""
        try:
            ia = state.GetIAState()
            if ia:
                topo = ia.topology
                snapshot.primitive_topology = self._map_topology(topo, rd)
        except Exception as e:
            logger.debug(f"提取 topology 失败: {e}")
    
    def _map_topology(self, topology: Any, rd: Any) -> PrimitiveTopology:
        """映射拓扑类型"""
        topo_map = {
            rd.Topology.Unknown: PrimitiveTopology.UNDEFINED,
            rd.Topology.PointList: PrimitiveTopology.POINT_LIST,
            rd.Topology.LineList: PrimitiveTopology.LINE_LIST,
            rd.Topology.LineStrip: PrimitiveTopology.LINE_STRIP,
            rd.Topology.TriangleList: PrimitiveTopology.TRIANGLE_LIST,
            rd.Topology.TriangleStrip: PrimitiveTopology.TRIANGLE_STRIP,
            rd.Topology.LineList_Adj: PrimitiveTopology.LINE_LIST_ADJ,
            rd.Topology.LineStrip_Adj: PrimitiveTopology.LINE_STRIP_ADJ,
            rd.Topology.TriangleList_Adj: PrimitiveTopology.TRIANGLE_LIST_ADJ,
            rd.Topology.TriangleStrip_Adj: PrimitiveTopology.TRIANGLE_STRIP_ADJ,
        }
        return topo_map.get(topology, PrimitiveTopology.TRIANGLE_LIST)


def sample_pipeline_states(
    controller: Any,
    events: List[Dict[str, Any]],
    sample_count: int = 20,
    strategy: SamplingStrategy = SamplingStrategy.UNIFORM,
    config: Optional[SamplingConfig] = None
) -> SamplingResult:
    """
    便捷函数：采样管线状态
    
    Args:
        controller: RenderDoc ReplayController
        events: 事件列表
        sample_count: 采样数量
        strategy: 采样策略
        config: 完整配置 (如提供则覆盖前面的参数)
        
    Returns:
        SamplingResult: 采样结果
        
    Example:
        >>> result = sample_pipeline_states(controller, events, sample_count=30)
        >>> print(f"采样了 {result.sampled_count} 个事件")
        >>> for sample in result.samples:
        ...     print(f"  EID {sample.event_id}: VS={sample.vertex_shader_id}")
    """
    if config is None:
        config = SamplingConfig(
            sample_count=sample_count,
            strategy=strategy
        )
    
    sampler = PipelineSampler(controller, config)
    return sampler.sample_from_events(events)
