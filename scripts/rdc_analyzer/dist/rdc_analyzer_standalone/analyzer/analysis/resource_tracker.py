"""
资源生命周期追踪器
==================

追踪每个 GPU 资源的读写访问，构建 Draw Call 之间的依赖关系图。

核心功能：
1. 记录资源的每次读写访问
2. 检测读后写 (RAW)、写后读 (WAR)、写后写 (WAW) 依赖
3. 识别未使用的资源写入
4. 生成资源流动可视化数据
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum, auto
from collections import defaultdict

from ..core.pipeline_state import (
    DrawCallDetail,
    PipelineSnapshot,
    ResourceBinding,
    ShaderBindings,
    RenderTargetInfo,
    DepthStencilInfo,
    ResourceType,
    ShaderStage,
    DrawType,
    AccessType,
)


class DependencyType(Enum):
    """资源依赖类型"""
    RAW = auto()  # Read-After-Write: 真依赖，读取之前写入的数据
    WAR = auto()  # Write-After-Read: 反依赖，写入之前读取的资源
    WAW = auto()  # Write-After-Write: 输出依赖，连续写入同一资源


@dataclass
class ResourceAccess:
    """
    资源访问记录
    
    表示某个事件对某个资源的一次访问
    """
    event_id: int
    resource_id: int
    resource_name: str
    access_type: AccessType
    
    # 访问上下文
    stage: Optional[ShaderStage] = None  # 哪个着色器阶段
    slot: int = 0                         # 绑定槽位
    binding_type: str = ""                # "VB", "IB", "CB", "SRV", "UAV", "RT", "DS"
    
    # 资源信息
    resource_type: ResourceType = ResourceType.UNKNOWN
    format: str = ""
    dimensions: str = ""
    
    def __hash__(self):
        return hash((self.event_id, self.resource_id, self.access_type))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'access_type': self.access_type.name,
            'stage': self.stage.value if self.stage else None,
            'slot': self.slot,
            'binding_type': self.binding_type,
        }


@dataclass
class ResourceDependency:
    """
    资源依赖关系
    
    表示两个事件之间因同一资源产生的依赖
    """
    source_event_id: int      # 先发生的事件
    target_event_id: int      # 后发生的事件
    resource_id: int
    resource_name: str
    dependency_type: DependencyType
    
    # 详细信息
    source_access: AccessType  # 源事件的访问类型
    target_access: AccessType  # 目标事件的访问类型
    
    def __hash__(self):
        return hash((self.source_event_id, self.target_event_id, 
                     self.resource_id, self.dependency_type))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_event': self.source_event_id,
            'target_event': self.target_event_id,
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'type': self.dependency_type.name,
        }


@dataclass
class ResourceLifetime:
    """
    资源生命周期信息
    
    追踪单个资源从创建到销毁的完整历史
    """
    resource_id: int
    resource_name: str = ""
    resource_type: ResourceType = ResourceType.UNKNOWN
    format: str = ""
    
    # 尺寸
    width: int = 0
    height: int = 0
    depth: int = 1
    size_bytes: int = 0
    
    # 访问历史
    accesses: List[ResourceAccess] = field(default_factory=list)
    
    # 统计
    read_count: int = 0
    write_count: int = 0
    first_access_event: int = 0
    last_access_event: int = 0
    
    @property
    def is_read_only(self) -> bool:
        """是否只读"""
        return self.write_count == 0 and self.read_count > 0
    
    @property
    def is_write_only(self) -> bool:
        """是否只写（可能未使用）"""
        return self.read_count == 0 and self.write_count > 0
    
    @property
    def access_count(self) -> int:
        """总访问次数"""
        return len(self.accesses)
    
    def add_access(self, access: ResourceAccess) -> None:
        """添加访问记录"""
        self.accesses.append(access)
        
        if access.access_type == AccessType.READ:
            self.read_count += 1
        elif access.access_type == AccessType.WRITE:
            self.write_count += 1
        else:  # READ_WRITE
            self.read_count += 1
            self.write_count += 1
        
        if self.first_access_event == 0:
            self.first_access_event = access.event_id
        self.last_access_event = access.event_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'type': self.resource_type.name,
            'format': self.format,
            'dimensions': f"{self.width}x{self.height}" if self.height > 0 else str(self.width),
            'read_count': self.read_count,
            'write_count': self.write_count,
            'first_event': self.first_access_event,
            'last_event': self.last_access_event,
        }


@dataclass
class ResourceTrackerConfig:
    """追踪器配置"""
    track_vertex_buffers: bool = True
    track_index_buffers: bool = True
    track_constant_buffers: bool = True
    track_textures: bool = True
    track_uavs: bool = True
    track_render_targets: bool = True
    track_depth_stencil: bool = True
    
    # 检测选项
    detect_unused_writes: bool = True   # 检测写后未读
    detect_waw_hazards: bool = True     # 检测连续写入


class ResourceTracker:
    """
    资源生命周期追踪器
    
    分析 DrawCallDetail 流，构建资源依赖图。
    
    使用方法：
        tracker = ResourceTracker()
        for draw in draw_calls:
            tracker.process(draw)
        
        # 获取依赖图
        dependencies = tracker.get_dependencies()
        
        # 获取资源生命周期
        lifetimes = tracker.get_resource_lifetimes()
    """
    
    def __init__(self, config: Optional[ResourceTrackerConfig] = None):
        """初始化追踪器"""
        self.config = config or ResourceTrackerConfig()
        
        # 资源生命周期
        self._resources: Dict[int, ResourceLifetime] = {}
        
        # 最后写入记录: resource_id -> (event_id, AccessType)
        self._last_write: Dict[int, Tuple[int, AccessType]] = {}
        
        # 最后读取记录: resource_id -> event_id
        self._last_read: Dict[int, int] = {}
        
        # 依赖关系
        self._dependencies: List[ResourceDependency] = []
        
        # 统计
        self._processed_count: int = 0
    
    def process(self, draw: DrawCallDetail) -> List[ResourceDependency]:
        """
        处理单个 Draw Call
        
        Args:
            draw: 绘制调用详情
            
        Returns:
            本次发现的新依赖关系
        """
        new_deps: List[ResourceDependency] = []
        
        # 收集本次调用的所有资源访问
        reads, writes = self._collect_accesses(draw)
        
        # 处理读取
        for access in reads:
            self._ensure_resource(access)
            self._resources[access.resource_id].add_access(access)
            
            # 检测 RAW 依赖
            if access.resource_id in self._last_write:
                src_event, src_access = self._last_write[access.resource_id]
                if src_event != draw.event_id:  # 不是同一事件
                    dep = ResourceDependency(
                        source_event_id=src_event,
                        target_event_id=draw.event_id,
                        resource_id=access.resource_id,
                        resource_name=access.resource_name,
                        dependency_type=DependencyType.RAW,
                        source_access=src_access,
                        target_access=AccessType.READ,
                    )
                    new_deps.append(dep)
            
            self._last_read[access.resource_id] = draw.event_id
        
        # 处理写入
        for access in writes:
            self._ensure_resource(access)
            self._resources[access.resource_id].add_access(access)
            
            # 检测 WAR 依赖
            if access.resource_id in self._last_read:
                src_event = self._last_read[access.resource_id]
                if src_event != draw.event_id:
                    dep = ResourceDependency(
                        source_event_id=src_event,
                        target_event_id=draw.event_id,
                        resource_id=access.resource_id,
                        resource_name=access.resource_name,
                        dependency_type=DependencyType.WAR,
                        source_access=AccessType.READ,
                        target_access=AccessType.WRITE,
                    )
                    new_deps.append(dep)
            
            # 检测 WAW 依赖
            if self.config.detect_waw_hazards and access.resource_id in self._last_write:
                src_event, src_access = self._last_write[access.resource_id]
                if src_event != draw.event_id:
                    # 检查中间是否有读取
                    last_read = self._last_read.get(access.resource_id, 0)
                    if last_read < src_event:
                        # 写后写，中间无读取
                        dep = ResourceDependency(
                            source_event_id=src_event,
                            target_event_id=draw.event_id,
                            resource_id=access.resource_id,
                            resource_name=access.resource_name,
                            dependency_type=DependencyType.WAW,
                            source_access=src_access,
                            target_access=AccessType.WRITE,
                        )
                        new_deps.append(dep)
            
            self._last_write[access.resource_id] = (draw.event_id, access.access_type)
        
        self._dependencies.extend(new_deps)
        self._processed_count += 1
        
        return new_deps
    
    def _collect_accesses(self, draw: DrawCallDetail) -> Tuple[List[ResourceAccess], List[ResourceAccess]]:
        """
        收集绘制调用的所有资源访问
        
        Returns:
            (reads, writes) 元组
        """
        reads: List[ResourceAccess] = []
        writes: List[ResourceAccess] = []
        
        pipeline = draw.pipeline
        
        # 顶点缓冲区 (读)
        if self.config.track_vertex_buffers:
            for vb in pipeline.vertex_buffers:
                if vb.resource_id > 0:
                    reads.append(ResourceAccess(
                        event_id=draw.event_id,
                        resource_id=vb.resource_id,
                        resource_name=vb.resource_name,
                        access_type=AccessType.READ,
                        stage=ShaderStage.VERTEX,
                        slot=vb.slot,
                        binding_type="VB",
                        resource_type=ResourceType.BUFFER,
                    ))
        
        # 索引缓冲区 (读)
        if self.config.track_index_buffers and pipeline.index_buffer:
            ib = pipeline.index_buffer
            if ib.resource_id > 0:
                reads.append(ResourceAccess(
                    event_id=draw.event_id,
                    resource_id=ib.resource_id,
                    resource_name=ib.resource_name,
                    access_type=AccessType.READ,
                    stage=ShaderStage.VERTEX,
                    slot=0,
                    binding_type="IB",
                    resource_type=ResourceType.BUFFER,
                ))
        
        # 着色器资源
        for shader in [pipeline.vertex_shader, pipeline.hull_shader, pipeline.domain_shader,
                       pipeline.geometry_shader, pipeline.pixel_shader, pipeline.compute_shader]:
            if shader:
                shader_reads, shader_writes = self._collect_shader_accesses(draw.event_id, shader)
                reads.extend(shader_reads)
                writes.extend(shader_writes)
        
        # 渲染目标 (写)
        if self.config.track_render_targets:
            for rt in pipeline.render_targets:
                if rt.resource_id > 0:
                    writes.append(ResourceAccess(
                        event_id=draw.event_id,
                        resource_id=rt.resource_id,
                        resource_name=rt.resource_name,
                        access_type=AccessType.WRITE,
                        stage=ShaderStage.PIXEL,
                        slot=rt.slot,
                        binding_type="RT",
                        resource_type=ResourceType.RENDER_TARGET,
                        format=rt.format,
                        dimensions=f"{rt.width}x{rt.height}",
                    ))
        
        # 深度模板缓冲区 (读写)
        if self.config.track_depth_stencil and pipeline.depth_stencil:
            ds = pipeline.depth_stencil
            if ds.resource_id > 0:
                # 深度测试是读取，深度写入是写入
                access_type = AccessType.READ_WRITE if ds.depth_write_enabled else AccessType.READ
                if ds.depth_write_enabled:
                    writes.append(ResourceAccess(
                        event_id=draw.event_id,
                        resource_id=ds.resource_id,
                        resource_name=ds.resource_name,
                        access_type=AccessType.WRITE,
                        stage=ShaderStage.PIXEL,
                        slot=0,
                        binding_type="DS",
                        resource_type=ResourceType.DEPTH_STENCIL,
                        format=ds.format,
                    ))
                if ds.depth_test_enabled:
                    reads.append(ResourceAccess(
                        event_id=draw.event_id,
                        resource_id=ds.resource_id,
                        resource_name=ds.resource_name,
                        access_type=AccessType.READ,
                        stage=ShaderStage.PIXEL,
                        slot=0,
                        binding_type="DS",
                        resource_type=ResourceType.DEPTH_STENCIL,
                        format=ds.format,
                    ))
        
        return reads, writes
    
    def _collect_shader_accesses(
        self, 
        event_id: int, 
        shader: ShaderBindings
    ) -> Tuple[List[ResourceAccess], List[ResourceAccess]]:
        """收集着色器阶段的资源访问"""
        reads: List[ResourceAccess] = []
        writes: List[ResourceAccess] = []
        
        # 常量缓冲区 (读)
        if self.config.track_constant_buffers:
            for cb in shader.constant_buffers:
                if cb.resource_id > 0:
                    reads.append(ResourceAccess(
                        event_id=event_id,
                        resource_id=cb.resource_id,
                        resource_name=cb.resource_name,
                        access_type=AccessType.READ,
                        stage=shader.stage,
                        slot=cb.slot,
                        binding_type="CB",
                        resource_type=ResourceType.BUFFER,
                    ))
        
        # SRV (读)
        if self.config.track_textures:
            for srv in shader.shader_resources:
                if srv.resource_id > 0:
                    reads.append(ResourceAccess(
                        event_id=event_id,
                        resource_id=srv.resource_id,
                        resource_name=srv.resource_name,
                        access_type=AccessType.READ,
                        stage=shader.stage,
                        slot=srv.slot,
                        binding_type="SRV",
                        resource_type=srv.resource_type,
                        format=srv.format,
                    ))
        
        # UAV (读写)
        if self.config.track_uavs:
            for uav in shader.uavs:
                if uav.resource_id > 0:
                    writes.append(ResourceAccess(
                        event_id=event_id,
                        resource_id=uav.resource_id,
                        resource_name=uav.resource_name,
                        access_type=AccessType.READ_WRITE,
                        stage=shader.stage,
                        slot=uav.slot,
                        binding_type="UAV",
                        resource_type=uav.resource_type,
                        format=uav.format,
                    ))
        
        return reads, writes
    
    def _ensure_resource(self, access: ResourceAccess) -> None:
        """确保资源存在于追踪器中"""
        if access.resource_id not in self._resources:
            self._resources[access.resource_id] = ResourceLifetime(
                resource_id=access.resource_id,
                resource_name=access.resource_name,
                resource_type=access.resource_type,
                format=access.format,
            )
    
    def get_dependencies(self) -> List[ResourceDependency]:
        """获取所有依赖关系"""
        return self._dependencies.copy()
    
    def get_resource_lifetimes(self) -> Dict[int, ResourceLifetime]:
        """获取所有资源生命周期"""
        return self._resources.copy()
    
    def get_unused_writes(self) -> List[Tuple[int, ResourceLifetime]]:
        """
        获取写后未读的资源
        
        Returns:
            (last_write_event_id, resource) 列表
        """
        unused = []
        for res_id, resource in self._resources.items():
            if resource.is_write_only:
                # 找到最后一次写入事件
                last_write_event = 0
                for access in resource.accesses:
                    if access.access_type in (AccessType.WRITE, AccessType.READ_WRITE):
                        last_write_event = max(last_write_event, access.event_id)
                unused.append((last_write_event, resource))
        return unused
    
    def get_waw_hazards(self) -> List[ResourceDependency]:
        """获取所有 WAW 冲突"""
        return [d for d in self._dependencies if d.dependency_type == DependencyType.WAW]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        raw_count = sum(1 for d in self._dependencies if d.dependency_type == DependencyType.RAW)
        war_count = sum(1 for d in self._dependencies if d.dependency_type == DependencyType.WAR)
        waw_count = sum(1 for d in self._dependencies if d.dependency_type == DependencyType.WAW)
        
        return {
            'processed_events': self._processed_count,
            'tracked_resources': len(self._resources),
            'total_dependencies': len(self._dependencies),
            'raw_dependencies': raw_count,
            'war_dependencies': war_count,
            'waw_dependencies': waw_count,
            'unused_writes': len(self.get_unused_writes()),
        }
    
    def reset(self) -> None:
        """重置追踪器状态"""
        self._resources.clear()
        self._last_write.clear()
        self._last_read.clear()
        self._dependencies.clear()
        self._processed_count = 0
    
    def build_dependency_graph(self) -> Dict[str, Any]:
        """
        构建用于可视化的依赖图数据
        
        Returns:
            包含 nodes 和 edges 的字典（适用于 D3.js 等可视化库）
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        
        # 收集所有涉及的事件
        event_ids: Set[int] = set()
        for dep in self._dependencies:
            event_ids.add(dep.source_event_id)
            event_ids.add(dep.target_event_id)
        
        # 创建节点
        for event_id in sorted(event_ids):
            nodes.append({
                'id': f"e{event_id}",
                'event_id': event_id,
                'label': f"Event {event_id}",
            })
        
        # 创建边
        for i, dep in enumerate(self._dependencies):
            edges.append({
                'id': f"d{i}",
                'source': f"e{dep.source_event_id}",
                'target': f"e{dep.target_event_id}",
                'resource_id': dep.resource_id,
                'resource_name': dep.resource_name,
                'type': dep.dependency_type.name,
            })
        
        return {
            'nodes': nodes,
            'edges': edges,
        }


# ============ 便捷函数 ============

def track_resources(
    draws: List[DrawCallDetail],
    config: Optional[ResourceTrackerConfig] = None
) -> Tuple[List[ResourceDependency], Dict[int, ResourceLifetime], Dict[str, Any]]:
    """
    追踪一系列 Draw Call 的资源使用
    
    Args:
        draws: DrawCallDetail 列表
        config: 追踪器配置
        
    Returns:
        (依赖列表, 资源生命周期字典, 统计信息)
    """
    tracker = ResourceTracker(config)
    
    for draw in draws:
        tracker.process(draw)
    
    return (
        tracker.get_dependencies(),
        tracker.get_resource_lifetimes(),
        tracker.get_statistics(),
    )
