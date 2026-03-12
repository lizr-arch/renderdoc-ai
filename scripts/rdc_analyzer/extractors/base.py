"""
提取器基类
==========

定义状态提取器的接口和基础设施

提取器负责:
1. 从 RenderDoc 的 ReplayController 读取管线状态
2. 将原生 API 状态映射到统一的数据模型
3. 支持不同图形 API 的特定逻辑
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Generic
import logging

from ..core.pipeline_state import (
    PipelineSnapshot,
    DrawCallDetail,
    CallTraceResult,
    ResourceBinding,
    ShaderBindings,
    RenderTargetInfo,
    DepthStencilInfo,
    DrawType,
    ShaderStage,
    ResourceType,
)


logger = logging.getLogger(__name__)


# =============================================================================
# 异常类型
# =============================================================================

class ExtractorError(Exception):
    """提取器错误基类"""
    pass


class APINotSupportedError(ExtractorError):
    """不支持的图形 API"""
    def __init__(self, api: str):
        self.api = api
        super().__init__(f"Graphics API not supported: {api}")


class ReplayNotAvailableError(ExtractorError):
    """回放控制器不可用"""
    pass


class StateExtractionError(ExtractorError):
    """状态提取失败"""
    def __init__(self, event_id: int, reason: str):
        self.event_id = event_id
        self.reason = reason
        super().__init__(f"Failed to extract state at event {event_id}: {reason}")


# =============================================================================
# 事件类型
# =============================================================================

class EventType(Enum):
    """RenderDoc 事件类型"""
    UNKNOWN = auto()
    
    # 标记/分组
    MARKER_PUSH = auto()      # BeginEvent, PushMarker
    MARKER_POP = auto()       # EndEvent, PopMarker
    
    # 绘制调用
    DRAW = auto()
    DRAW_INDEXED = auto()
    DRAW_INSTANCED = auto()
    DRAW_INDEXED_INSTANCED = auto()
    DRAW_INDIRECT = auto()
    DRAW_INDEXED_INDIRECT = auto()
    DRAW_INDIRECT_COUNT = auto()
    
    # 计算
    DISPATCH = auto()
    DISPATCH_INDIRECT = auto()
    
    # 清除
    CLEAR_RTV = auto()
    CLEAR_DSV = auto()
    CLEAR_UAV = auto()
    
    # 复制/解析
    COPY_BUFFER = auto()
    COPY_TEXTURE = auto()
    COPY_BUFFER_REGION = auto()
    RESOLVE = auto()
    
    # 资源更新
    UPDATE_BUFFER = auto()
    MAP = auto()
    UNMAP = auto()
    
    # 状态设置（通常不单独记录）
    SET_PIPELINE = auto()
    SET_RENDER_TARGETS = auto()
    SET_VIEWPORTS = auto()
    SET_SCISSORS = auto()
    
    # 同步
    BARRIER = auto()
    FENCE = auto()
    
    # 查询
    BEGIN_QUERY = auto()
    END_QUERY = auto()
    RESOLVE_QUERY = auto()
    
    # Present
    PRESENT = auto()


@dataclass
class EventInfo:
    """
    RenderDoc 事件信息
    
    表示调用树中的单个节点
    """
    event_id: int                          # 唯一事件 ID
    name: str                              # API 调用名称
    event_type: EventType = EventType.UNKNOWN
    
    # 层级信息
    parent_id: Optional[int] = None        # 父事件 ID
    children: List['EventInfo'] = field(default_factory=list)
    depth: int = 0                         # 嵌套深度
    
    # 标记信息
    marker_path: str = ""                  # 完整标记路径
    
    # 绘制调用参数（如果适用）
    draw_params: Dict[str, Any] = field(default_factory=dict)
    
    # 时间信息
    gpu_duration_ns: int = 0
    
    def is_draw_call(self) -> bool:
        """是否是绘制调用"""
        return self.event_type in (
            EventType.DRAW, EventType.DRAW_INDEXED,
            EventType.DRAW_INSTANCED, EventType.DRAW_INDEXED_INSTANCED,
            EventType.DRAW_INDIRECT, EventType.DRAW_INDEXED_INDIRECT,
            EventType.DRAW_INDIRECT_COUNT
        )
    
    def is_dispatch(self) -> bool:
        """是否是计算调度"""
        return self.event_type in (EventType.DISPATCH, EventType.DISPATCH_INDIRECT)
    
    def is_marker(self) -> bool:
        """是否是标记事件"""
        return self.event_type in (EventType.MARKER_PUSH, EventType.MARKER_POP)
    
    def is_actionable(self) -> bool:
        """是否是有实际 GPU 工作的事件"""
        return self.is_draw_call() or self.is_dispatch() or self.event_type in (
            EventType.CLEAR_RTV, EventType.CLEAR_DSV, EventType.CLEAR_UAV,
            EventType.COPY_BUFFER, EventType.COPY_TEXTURE, EventType.RESOLVE
        )


# =============================================================================
# 提取器配置
# =============================================================================

@dataclass
class ExtractorConfig:
    """提取器配置"""
    
    # 提取范围
    extract_shaders: bool = True           # 是否提取着色器信息
    extract_textures: bool = True          # 是否提取纹理信息
    extract_buffers: bool = True           # 是否提取缓冲区信息
    extract_samplers: bool = True          # 是否提取采样器信息
    extract_render_targets: bool = True    # 是否提取渲染目标信息
    
    # 过滤选项
    skip_clears: bool = False              # 是否跳过清除操作
    skip_copies: bool = False              # 是否跳过复制操作
    marker_filter: Optional[str] = None    # 只提取匹配的标记路径
    
    # 性能选项
    cache_pipeline_states: bool = True     # 是否缓存管线状态
    batch_size: int = 100                  # 批量处理大小
    
    # 调试选项
    verbose: bool = False                  # 详细日志


# =============================================================================
# 提取器基类
# =============================================================================

class BaseExtractor(ABC):
    """
    状态提取器基类
    
    定义从 RDC 文件提取管线状态的标准接口。
    每个图形 API (D3D11, D3D12, Vulkan, OpenGL) 需要实现自己的提取器。
    
    使用方式:
        extractor = D3D11Extractor(controller, config)
        result = extractor.extract_full_trace()
    """
    
    # 子类需要覆盖
    API_NAME: str = "Unknown"
    SUPPORTED_VERSIONS: List[str] = []
    
    def __init__(self, controller: Any, config: Optional[ExtractorConfig] = None):
        """
        初始化提取器
        
        Args:
            controller: RenderDoc ReplayController 实例
            config: 提取配置
        """
        self.controller = controller
        self.config = config or ExtractorConfig()
        
        # 缓存
        self._pipeline_cache: Dict[int, PipelineSnapshot] = {}
        self._shader_cache: Dict[int, ShaderBindings] = {}
        self._resource_cache: Dict[int, ResourceBinding] = {}
        
        # 事件树
        self._events: List[EventInfo] = []
        self._event_map: Dict[int, EventInfo] = {}
    
    # -------------------------------------------------------------------------
    # 抽象方法 - 子类必须实现
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def get_api_version(self) -> str:
        """
        获取图形 API 版本
        
        Returns:
            版本字符串，如 "11.0", "12.0", "1.3"
        """
        pass
    
    @abstractmethod
    def build_event_tree(self) -> List[EventInfo]:
        """
        构建事件树
        
        遍历 RenderDoc 的事件列表，构建层级结构
        
        Returns:
            根级事件列表
        """
        pass
    
    @abstractmethod
    def extract_pipeline_state(self, event_id: int) -> PipelineSnapshot:
        """
        提取指定事件的管线状态
        
        Args:
            event_id: RenderDoc 事件 ID
            
        Returns:
            完整的管线状态快照
            
        Raises:
            StateExtractionError: 提取失败
        """
        pass
    
    @abstractmethod
    def extract_draw_params(self, event_id: int) -> Dict[str, Any]:
        """
        提取绘制调用参数
        
        Args:
            event_id: RenderDoc 事件 ID
            
        Returns:
            包含 vertex_count, index_count 等参数的字典
        """
        pass
    
    # -------------------------------------------------------------------------
    # 可选覆盖的方法
    # -------------------------------------------------------------------------
    
    def extract_shader_info(self, stage: ShaderStage, resource_id: int) -> Optional[ShaderBindings]:
        """
        提取着色器详细信息
        
        默认实现返回基本信息，子类可覆盖以提供更多细节
        """
        return ShaderBindings(
            stage=stage,
            resource_id=resource_id,
        )
    
    def extract_resource_info(self, resource_id: int) -> Optional[ResourceBinding]:
        """
        提取资源详细信息
        
        默认实现返回基本信息，子类可覆盖
        """
        return ResourceBinding(
            slot=0,
            stage=ShaderStage.VERTEX,
            resource_id=resource_id,
        )
    
    def get_gpu_timing(self, event_id: int) -> int:
        """
        获取 GPU 执行时间（纳秒）
        
        默认返回 0，子类可覆盖以提供实际时间
        """
        return 0
    
    # -------------------------------------------------------------------------
    # 核心提取方法
    # -------------------------------------------------------------------------
    
    def extract_full_trace(self) -> CallTraceResult:
        """
        提取完整的调用追踪
        
        这是主入口方法，遍历所有事件并提取状态
        
        Returns:
            包含所有 Draw Call 信息的 CallTraceResult
        """
        logger.info(f"Starting full trace extraction with {self.API_NAME} extractor")
        
        # 构建事件树
        self._events = self.build_event_tree()
        self._event_map = {e.event_id: e for e in self._flatten_events(self._events)}
        
        # 初始化结果
        result = CallTraceResult(
            api=self.API_NAME,
        )
        
        # 遍历所有可操作事件
        draw_calls: List[DrawCallDetail] = []
        
        for event in self._flatten_events(self._events):
            if not event.is_actionable():
                continue
            
            # 应用过滤器
            if self.config.marker_filter and self.config.marker_filter not in event.marker_path:
                continue
            
            if self.config.skip_clears and event.event_type in (
                EventType.CLEAR_RTV, EventType.CLEAR_DSV, EventType.CLEAR_UAV
            ):
                continue
            
            if self.config.skip_copies and event.event_type in (
                EventType.COPY_BUFFER, EventType.COPY_TEXTURE
            ):
                continue
            
            try:
                # 提取管线状态
                pipeline = self._get_cached_pipeline(event.event_id)
                
                # 提取绘制参数
                params = self.extract_draw_params(event.event_id)
                
                # 创建 DrawCallDetail
                detail = DrawCallDetail(
                    event_id=event.event_id,
                    name=event.name,
                    draw_type=self._map_event_type_to_draw_type(event.event_type),
                    parent_id=event.parent_id,
                    marker_path=event.marker_path,
                    depth=event.depth,
                    vertex_count=params.get('vertex_count', 0),
                    index_count=params.get('index_count', 0),
                    instance_count=params.get('instance_count', 1),
                    base_vertex=params.get('base_vertex', 0),
                    start_index=params.get('start_index', 0),
                    start_instance=params.get('start_instance', 0),
                    thread_group_x=params.get('thread_group_x', 0),
                    thread_group_y=params.get('thread_group_y', 0),
                    thread_group_z=params.get('thread_group_z', 0),
                    pipeline=pipeline,
                    gpu_duration_ns=self.get_gpu_timing(event.event_id),
                )
                
                draw_calls.append(detail)
                
                if self.config.verbose:
                    logger.debug(f"Extracted event {event.event_id}: {event.name}")
                    
            except StateExtractionError as e:
                logger.warning(f"Failed to extract event {event.event_id}: {e}")
                continue
        
        # 填充结果
        result.draw_calls = draw_calls
        result.total_draw_calls = sum(1 for dc in draw_calls if dc.is_draw)
        result.total_dispatches = sum(1 for dc in draw_calls if dc.is_dispatch)
        result.total_clears = sum(1 for dc in draw_calls if dc.is_clear)
        
        # 统计唯一资源
        result.unique_shaders = len(self._shader_cache)
        result.unique_textures = self._count_unique_resources(ResourceType.TEXTURE_2D)
        result.unique_buffers = self._count_unique_resources(ResourceType.BUFFER)
        
        logger.info(
            f"Extraction complete: {result.total_draw_calls} draws, "
            f"{result.total_dispatches} dispatches, {result.total_clears} clears"
        )
        
        return result
    
    def extract_single_event(self, event_id: int) -> DrawCallDetail:
        """
        提取单个事件的详细信息
        
        Args:
            event_id: 事件 ID
            
        Returns:
            DrawCallDetail 对象
        """
        # 确保事件树已构建
        if not self._events:
            self._events = self.build_event_tree()
            self._event_map = {e.event_id: e for e in self._flatten_events(self._events)}
        
        event = self._event_map.get(event_id)
        if not event:
            raise StateExtractionError(event_id, "Event not found")
        
        pipeline = self.extract_pipeline_state(event_id)
        params = self.extract_draw_params(event_id)
        
        return DrawCallDetail(
            event_id=event.event_id,
            name=event.name,
            draw_type=self._map_event_type_to_draw_type(event.event_type),
            marker_path=event.marker_path,
            depth=event.depth,
            vertex_count=params.get('vertex_count', 0),
            index_count=params.get('index_count', 0),
            instance_count=params.get('instance_count', 1),
            pipeline=pipeline,
        )
    
    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------
    
    def _get_cached_pipeline(self, event_id: int) -> PipelineSnapshot:
        """获取缓存的管线状态，或提取新的"""
        if self.config.cache_pipeline_states and event_id in self._pipeline_cache:
            return self._pipeline_cache[event_id]
        
        pipeline = self.extract_pipeline_state(event_id)
        
        if self.config.cache_pipeline_states:
            self._pipeline_cache[event_id] = pipeline
        
        return pipeline
    
    def _flatten_events(self, events: List[EventInfo]) -> List[EventInfo]:
        """将事件树展平为列表"""
        result = []
        for event in events:
            result.append(event)
            result.extend(self._flatten_events(event.children))
        return result
    
    def _map_event_type_to_draw_type(self, event_type: EventType) -> DrawType:
        """将 EventType 映射到 DrawType"""
        mapping = {
            EventType.DRAW: DrawType.DRAW,
            EventType.DRAW_INDEXED: DrawType.DRAW_INDEXED,
            EventType.DRAW_INSTANCED: DrawType.DRAW_INSTANCED,
            EventType.DRAW_INDEXED_INSTANCED: DrawType.DRAW_INDEXED_INSTANCED,
            EventType.DRAW_INDIRECT: DrawType.DRAW_INDIRECT,
            EventType.DRAW_INDEXED_INDIRECT: DrawType.DRAW_INDEXED_INDIRECT,
            EventType.DISPATCH: DrawType.DISPATCH,
            EventType.DISPATCH_INDIRECT: DrawType.DISPATCH_INDIRECT,
            EventType.CLEAR_RTV: DrawType.CLEAR_RTV,
            EventType.CLEAR_DSV: DrawType.CLEAR_DSV,
            EventType.CLEAR_UAV: DrawType.CLEAR_UAV,
            EventType.COPY_BUFFER: DrawType.COPY,
            EventType.COPY_TEXTURE: DrawType.COPY,
            EventType.RESOLVE: DrawType.RESOLVE,
        }
        return mapping.get(event_type, DrawType.OTHER)
    
    def _count_unique_resources(self, resource_type: ResourceType) -> int:
        """统计特定类型的唯一资源数"""
        count = 0
        for res in self._resource_cache.values():
            if res.resource_type == resource_type:
                count += 1
        return count
    
    def clear_cache(self):
        """清除所有缓存"""
        self._pipeline_cache.clear()
        self._shader_cache.clear()
        self._resource_cache.clear()


# =============================================================================
# 提取器注册表
# =============================================================================

class ExtractorRegistry:
    """
    提取器注册表
    
    管理不同图形 API 的提取器实现
    """
    
    _extractors: Dict[str, Type[BaseExtractor]] = {}
    
    @classmethod
    def register(cls, api_name: str) -> Callable[[Type[BaseExtractor]], Type[BaseExtractor]]:
        """
        注册提取器的装饰器
        
        用法:
            @ExtractorRegistry.register("D3D11")
            class D3D11Extractor(BaseExtractor):
                ...
        """
        def decorator(extractor_class: Type[BaseExtractor]) -> Type[BaseExtractor]:
            cls._extractors[api_name.upper()] = extractor_class
            return extractor_class
        return decorator
    
    @classmethod
    def get(cls, api_name: str) -> Optional[Type[BaseExtractor]]:
        """获取指定 API 的提取器类"""
        return cls._extractors.get(api_name.upper())
    
    @classmethod
    def list_supported_apis(cls) -> List[str]:
        """列出所有支持的 API"""
        return list(cls._extractors.keys())
    
    @classmethod
    def create(cls, api_name: str, controller: Any, 
               config: Optional[ExtractorConfig] = None) -> BaseExtractor:
        """
        创建提取器实例
        
        Args:
            api_name: 图形 API 名称
            controller: ReplayController 实例
            config: 提取配置
            
        Returns:
            提取器实例
            
        Raises:
            APINotSupportedError: 不支持的 API
        """
        extractor_class = cls.get(api_name)
        if not extractor_class:
            raise APINotSupportedError(api_name)
        return extractor_class(controller, config)
