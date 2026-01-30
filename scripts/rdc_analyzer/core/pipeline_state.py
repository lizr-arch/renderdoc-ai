"""
管线状态数据模型
================

定义 API 调用级分析所需的数据结构，包括：
- 资源绑定信息
- 着色器信息  
- 管线状态快照
- Draw Call 完整信息
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


# =============================================================================
# 枚举类型
# =============================================================================

class ShaderStage(Enum):
    """着色器阶段"""
    VERTEX = "VS"
    HULL = "HS"
    DOMAIN = "DS"
    GEOMETRY = "GS"
    PIXEL = "PS"
    COMPUTE = "CS"
    
    # Vulkan/Modern API 额外阶段
    TASK = "TS"
    MESH = "MS"
    RAYGENERATION = "RGS"
    INTERSECTION = "IS"
    ANYHIT = "AHS"
    CLOSESTHIT = "CHS"
    MISS = "MISS"
    CALLABLE = "CALL"


class ResourceType(Enum):
    """资源类型"""
    UNKNOWN = auto()
    BUFFER = auto()
    TEXTURE_1D = auto()
    TEXTURE_2D = auto()
    TEXTURE_3D = auto()
    TEXTURE_CUBE = auto()
    TEXTURE_1D_ARRAY = auto()
    TEXTURE_2D_ARRAY = auto()
    TEXTURE_CUBE_ARRAY = auto()
    SAMPLER = auto()
    RENDER_TARGET = auto()
    DEPTH_STENCIL = auto()
    UAV = auto()  # Unordered Access View


class PrimitiveTopology(Enum):
    """图元拓扑"""
    UNDEFINED = auto()
    POINT_LIST = auto()
    LINE_LIST = auto()
    LINE_STRIP = auto()
    TRIANGLE_LIST = auto()
    TRIANGLE_STRIP = auto()
    LINE_LIST_ADJ = auto()
    LINE_STRIP_ADJ = auto()
    TRIANGLE_LIST_ADJ = auto()
    TRIANGLE_STRIP_ADJ = auto()
    PATCH_LIST = auto()


class DrawType(Enum):
    """绘制调用类型"""
    DRAW = auto()
    DRAW_INDEXED = auto()
    DRAW_INSTANCED = auto()
    DRAW_INDEXED_INSTANCED = auto()
    DRAW_INDIRECT = auto()
    DRAW_INDEXED_INDIRECT = auto()
    DISPATCH = auto()
    DISPATCH_INDIRECT = auto()
    CLEAR_RTV = auto()
    CLEAR_DSV = auto()
    CLEAR_UAV = auto()
    COPY = auto()
    RESOLVE = auto()
    OTHER = auto()


class AccessType(Enum):
    """资源访问类型"""
    READ = auto()
    WRITE = auto()
    READ_WRITE = auto()


class CullMode(Enum):
    """剔除模式"""
    NONE = auto()
    FRONT = auto()
    BACK = auto()


class FillMode(Enum):
    """填充模式"""
    SOLID = auto()
    WIREFRAME = auto()


# =============================================================================
# 基础数据结构
# =============================================================================

@dataclass
class ResourceBinding:
    """
    资源绑定信息
    
    表示绑定到管线某个槽位的资源
    """
    slot: int                              # 绑定槽位 (0-127)
    stage: ShaderStage                     # 着色器阶段
    resource_id: int                       # RenderDoc 资源 ID
    resource_name: str = ""                # 用户定义名称
    resource_type: ResourceType = ResourceType.UNKNOWN
    
    # 格式信息
    format: str = ""                       # "R8G8B8A8_UNORM", "BC3_UNORM" 等
    
    # 尺寸信息
    width: int = 0
    height: int = 0
    depth: int = 1                         # 3D纹理深度或数组大小
    mip_levels: int = 1
    array_size: int = 1
    
    # 内存信息
    size_bytes: int = 0
    
    # 缓冲区特定
    stride: int = 0                        # 顶点/结构体步长
    offset: int = 0                        # 绑定偏移
    
    def __post_init__(self):
        """确保 stage 是枚举类型"""
        if isinstance(self.stage, str):
            self.stage = ShaderStage(self.stage)
        if isinstance(self.resource_type, str):
            self.resource_type = ResourceType[self.resource_type]
    
    @property
    def dimensions(self) -> Tuple[int, ...]:
        """返回尺寸元组"""
        if self.resource_type in (ResourceType.TEXTURE_3D,):
            return (self.width, self.height, self.depth)
        elif self.resource_type in (ResourceType.TEXTURE_1D, ResourceType.TEXTURE_1D_ARRAY):
            return (self.width,)
        else:
            return (self.width, self.height)
    
    @property
    def dimension_str(self) -> str:
        """返回可读的尺寸字符串"""
        if self.resource_type == ResourceType.BUFFER:
            return f"{self.size_bytes} bytes"
        dims = self.dimensions
        return "x".join(str(d) for d in dims)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "slot": self.slot,
            "stage": self.stage.value if isinstance(self.stage, ShaderStage) else self.stage,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type.name if isinstance(self.resource_type, ResourceType) else self.resource_type,
            "format": self.format,
            "dimensions": self.dimension_str,
            "size_bytes": self.size_bytes,
        }


@dataclass
class SamplerInfo:
    """采样器信息"""
    slot: int
    stage: ShaderStage
    resource_id: int
    
    # 采样器状态
    filter_mode: str = ""                  # "Point", "Linear", "Anisotropic"
    address_u: str = ""                    # "Wrap", "Clamp", "Mirror", "Border"
    address_v: str = ""
    address_w: str = ""
    max_anisotropy: int = 1
    mip_lod_bias: float = 0.0
    min_lod: float = 0.0
    max_lod: float = 0.0
    border_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    comparison_func: str = ""              # "Never", "Less", "Equal", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "slot": self.slot,
            "stage": self.stage.value if isinstance(self.stage, ShaderStage) else self.stage,
            "filter": self.filter_mode,
            "address": f"{self.address_u}/{self.address_v}/{self.address_w}",
            "max_anisotropy": self.max_anisotropy,
        }


@dataclass
class ShaderBindings:
    """
    着色器绑定信息
    
    包含着色器及其绑定的所有资源
    """
    stage: ShaderStage
    resource_id: int                       # 着色器资源 ID
    name: str = ""                         # 入口点名称
    file_path: str = ""                    # 源文件路径（如果有）
    bytecode_hash: str = ""                # 用于识别相同着色器
    
    # 绑定的资源
    constant_buffers: List[ResourceBinding] = field(default_factory=list)
    shader_resources: List[ResourceBinding] = field(default_factory=list)  # SRV
    samplers: List[SamplerInfo] = field(default_factory=list)
    uavs: List[ResourceBinding] = field(default_factory=list)
    
    # 反射信息（可选）
    input_signature: List[Dict[str, Any]] = field(default_factory=list)
    output_signature: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_all_resources(self) -> List[ResourceBinding]:
        """获取所有绑定的资源"""
        resources = []
        resources.extend(self.constant_buffers)
        resources.extend(self.shader_resources)
        resources.extend(self.uavs)
        return resources
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stage": self.stage.value if isinstance(self.stage, ShaderStage) else self.stage,
            "resource_id": self.resource_id,
            "name": self.name,
            "constant_buffers": [cb.to_dict() for cb in self.constant_buffers],
            "shader_resources": [sr.to_dict() for sr in self.shader_resources],
            "samplers": [s.to_dict() for s in self.samplers],
            "uavs": [u.to_dict() for u in self.uavs],
        }


@dataclass
class RenderTargetInfo:
    """渲染目标信息"""
    slot: int                              # RTV slot (0-7)
    resource_id: int
    resource_name: str = ""
    format: str = ""
    width: int = 0
    height: int = 0
    
    # 加载/存储操作（移动端重要）
    load_action: str = "Load"              # "Load", "Clear", "DontCare"
    store_action: str = "Store"            # "Store", "DontCare", "Resolve"
    clear_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "slot": self.slot,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "format": self.format,
            "dimensions": f"{self.width}x{self.height}",
            "load_action": self.load_action,
            "store_action": self.store_action,
        }


@dataclass
class DepthStencilInfo:
    """深度模板缓冲信息"""
    resource_id: int
    resource_name: str = ""
    format: str = ""
    width: int = 0
    height: int = 0
    
    # 深度状态
    depth_test_enabled: bool = True
    depth_write_enabled: bool = True
    depth_func: str = "Less"               # "Never", "Less", "Equal", etc.
    
    # 模板状态
    stencil_enabled: bool = False
    stencil_read_mask: int = 0xFF
    stencil_write_mask: int = 0xFF
    
    # 加载/存储
    depth_load_action: str = "Load"
    depth_store_action: str = "Store"
    stencil_load_action: str = "Load"
    stencil_store_action: str = "Store"
    clear_depth: float = 1.0
    clear_stencil: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "format": self.format,
            "dimensions": f"{self.width}x{self.height}",
            "depth_test": self.depth_test_enabled,
            "depth_write": self.depth_write_enabled,
            "depth_func": self.depth_func,
            "stencil_enabled": self.stencil_enabled,
        }


@dataclass
class ViewportInfo:
    """视口信息"""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    min_depth: float = 0.0
    max_depth: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class ScissorRect:
    """裁剪矩形"""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass  
class BlendStateInfo:
    """混合状态信息"""
    enabled: bool = False
    src_blend: str = "One"
    dst_blend: str = "Zero"
    blend_op: str = "Add"
    src_blend_alpha: str = "One"
    dst_blend_alpha: str = "Zero"
    blend_op_alpha: str = "Add"
    write_mask: int = 0xF                  # RGBA 写入掩码
    
    def to_dict(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "src": self.src_blend,
            "dst": self.dst_blend,
            "op": self.blend_op,
        }


@dataclass
class RasterizerStateInfo:
    """光栅化状态信息"""
    fill_mode: FillMode = FillMode.SOLID
    cull_mode: CullMode = CullMode.BACK
    front_ccw: bool = False                # 逆时针为正面
    depth_bias: int = 0
    depth_bias_clamp: float = 0.0
    slope_scaled_depth_bias: float = 0.0
    depth_clip_enabled: bool = True
    scissor_enabled: bool = False
    multisample_enabled: bool = False
    antialiased_line_enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_mode": self.fill_mode.name,
            "cull_mode": self.cull_mode.name,
            "depth_bias": self.depth_bias,
            "scissor_enabled": self.scissor_enabled,
        }


# =============================================================================
# 管线状态快照
# =============================================================================

@dataclass
class PipelineSnapshot:
    """
    管线状态快照
    
    表示某个绘制调用时刻的完整管线状态
    """
    # 输入装配阶段 (IA)
    vertex_buffers: List[ResourceBinding] = field(default_factory=list)
    index_buffer: Optional[ResourceBinding] = None
    primitive_topology: PrimitiveTopology = PrimitiveTopology.TRIANGLE_LIST
    input_layout_id: int = 0
    
    # 着色器阶段
    vertex_shader: Optional[ShaderBindings] = None
    hull_shader: Optional[ShaderBindings] = None
    domain_shader: Optional[ShaderBindings] = None
    geometry_shader: Optional[ShaderBindings] = None
    pixel_shader: Optional[ShaderBindings] = None
    compute_shader: Optional[ShaderBindings] = None
    
    # 流输出 (SO)
    stream_output_buffers: List[ResourceBinding] = field(default_factory=list)
    
    # 光栅化阶段 (RS)
    viewports: List[ViewportInfo] = field(default_factory=list)
    scissor_rects: List[ScissorRect] = field(default_factory=list)
    rasterizer_state: RasterizerStateInfo = field(default_factory=RasterizerStateInfo)
    
    # 输出合并阶段 (OM)
    render_targets: List[RenderTargetInfo] = field(default_factory=list)
    depth_stencil: Optional[DepthStencilInfo] = None
    blend_states: List[BlendStateInfo] = field(default_factory=list)
    sample_mask: int = 0xFFFFFFFF
    
    def get_all_inputs(self) -> List[ResourceBinding]:
        """
        获取所有输入资源（扁平化）
        
        Returns:
            所有作为输入绑定的资源列表
        """
        inputs = []
        
        # 顶点/索引缓冲
        inputs.extend(self.vertex_buffers)
        if self.index_buffer:
            inputs.append(self.index_buffer)
        
        # 着色器资源
        for shader in [self.vertex_shader, self.hull_shader, self.domain_shader,
                       self.geometry_shader, self.pixel_shader, self.compute_shader]:
            if shader:
                inputs.extend(shader.get_all_resources())
        
        return inputs
    
    def get_all_outputs(self) -> List[ResourceBinding]:
        """
        获取所有输出资源（扁平化）
        
        Returns:
            所有作为输出绑定的资源列表
        """
        outputs = []
        
        # 渲染目标
        for rt in self.render_targets:
            outputs.append(ResourceBinding(
                slot=rt.slot,
                stage=ShaderStage.PIXEL,
                resource_id=rt.resource_id,
                resource_name=rt.resource_name,
                resource_type=ResourceType.RENDER_TARGET,
                format=rt.format,
                width=rt.width,
                height=rt.height,
            ))
        
        # 深度模板
        if self.depth_stencil:
            ds = self.depth_stencil
            outputs.append(ResourceBinding(
                slot=0,
                stage=ShaderStage.PIXEL,
                resource_id=ds.resource_id,
                resource_name=ds.resource_name,
                resource_type=ResourceType.DEPTH_STENCIL,
                format=ds.format,
                width=ds.width,
                height=ds.height,
            ))
        
        # UAV
        for shader in [self.pixel_shader, self.compute_shader]:
            if shader:
                outputs.extend(shader.uavs)
        
        # 流输出
        outputs.extend(self.stream_output_buffers)
        
        return outputs
    
    def get_active_shaders(self) -> List[ShaderBindings]:
        """获取激活的着色器列表"""
        shaders = []
        for shader in [self.vertex_shader, self.hull_shader, self.domain_shader,
                       self.geometry_shader, self.pixel_shader, self.compute_shader]:
            if shader and shader.resource_id > 0:
                shaders.append(shader)
        return shaders
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "input_assembly": {
                "vertex_buffers": [vb.to_dict() for vb in self.vertex_buffers],
                "index_buffer": self.index_buffer.to_dict() if self.index_buffer else None,
                "topology": self.primitive_topology.name,
            },
            "shaders": {
                "vertex": self.vertex_shader.to_dict() if self.vertex_shader else None,
                "hull": self.hull_shader.to_dict() if self.hull_shader else None,
                "domain": self.domain_shader.to_dict() if self.domain_shader else None,
                "geometry": self.geometry_shader.to_dict() if self.geometry_shader else None,
                "pixel": self.pixel_shader.to_dict() if self.pixel_shader else None,
                "compute": self.compute_shader.to_dict() if self.compute_shader else None,
            },
            "rasterizer": self.rasterizer_state.to_dict(),
            "output_merger": {
                "render_targets": [rt.to_dict() for rt in self.render_targets],
                "depth_stencil": self.depth_stencil.to_dict() if self.depth_stencil else None,
                "blend_states": [bs.to_dict() for bs in self.blend_states],
            },
            "viewports": [vp.to_dict() for vp in self.viewports],
        }


# =============================================================================
# Draw Call 详细信息
# =============================================================================

@dataclass
class DrawCallDetail:
    """
    Draw Call 详细信息
    
    包含单个绘制调用的所有相关数据（用于 API 调用级分析）
    与 types.py 中的 DrawCallInfo 不同，这个类包含完整的管线状态快照
    """
    # 基本信息
    event_id: int                          # RenderDoc 事件 ID
    name: str                              # "DrawIndexed", "Dispatch" 等
    draw_type: DrawType = DrawType.OTHER
    
    # 层级信息
    parent_id: Optional[int] = None        # 父事件 (Pass/Marker)
    marker_path: str = ""                  # 完整标记路径 "Shadow/MainLight/Cascade0"
    depth: int = 0                         # 嵌套深度
    
    # 绘制参数
    vertex_count: int = 0
    index_count: int = 0
    instance_count: int = 1
    base_vertex: int = 0
    start_index: int = 0
    start_instance: int = 0
    
    # Dispatch 参数
    thread_group_x: int = 0
    thread_group_y: int = 0
    thread_group_z: int = 0
    
    # 管线状态
    pipeline: PipelineSnapshot = field(default_factory=PipelineSnapshot)
    
    # 时间信息（如果可用）
    gpu_duration_ns: int = 0               # GPU 执行时间（纳秒）
    
    # 标志
    has_side_effects: bool = False         # 是否有副作用（写入 UAV 等）
    is_indirect: bool = False              # 是否是间接调用
    
    @property
    def is_draw(self) -> bool:
        """是否是绘制调用"""
        return self.draw_type in (
            DrawType.DRAW, DrawType.DRAW_INDEXED,
            DrawType.DRAW_INSTANCED, DrawType.DRAW_INDEXED_INSTANCED,
            DrawType.DRAW_INDIRECT, DrawType.DRAW_INDEXED_INDIRECT
        )
    
    @property
    def is_dispatch(self) -> bool:
        """是否是计算着色器调度"""
        return self.draw_type in (DrawType.DISPATCH, DrawType.DISPATCH_INDIRECT)
    
    @property
    def is_clear(self) -> bool:
        """是否是清除操作"""
        return self.draw_type in (DrawType.CLEAR_RTV, DrawType.CLEAR_DSV, DrawType.CLEAR_UAV)
    
    @property
    def primitive_count(self) -> int:
        """估算的图元数量"""
        count = self.index_count if self.index_count > 0 else self.vertex_count
        topology = self.pipeline.primitive_topology
        
        if topology == PrimitiveTopology.TRIANGLE_LIST:
            return count // 3
        elif topology == PrimitiveTopology.TRIANGLE_STRIP:
            return max(0, count - 2)
        elif topology == PrimitiveTopology.LINE_LIST:
            return count // 2
        elif topology == PrimitiveTopology.LINE_STRIP:
            return max(0, count - 1)
        elif topology == PrimitiveTopology.POINT_LIST:
            return count
        else:
            return count // 3  # 默认按三角形算
    
    @property
    def total_primitives(self) -> int:
        """包含实例的总图元数"""
        return self.primitive_count * self.instance_count
    
    def get_all_inputs(self) -> List[ResourceBinding]:
        """获取所有输入资源"""
        return self.pipeline.get_all_inputs()
    
    def get_all_outputs(self) -> List[ResourceBinding]:
        """获取所有输出资源"""
        return self.pipeline.get_all_outputs()
    
    def estimate_bandwidth(self) -> Tuple[int, int]:
        """
        估算带宽使用
        
        Returns:
            (read_bytes, write_bytes) 元组
        """
        read_bytes = 0
        write_bytes = 0
        
        # 输入带宽（简化估算）
        for inp in self.get_all_inputs():
            if inp.resource_type == ResourceType.BUFFER:
                # 顶点/索引缓冲按使用量算
                if inp.stride > 0:
                    count = self.vertex_count * self.instance_count
                    read_bytes += count * inp.stride
                else:
                    read_bytes += inp.size_bytes
            else:
                # 纹理按采样估算（简化：假设读取一次）
                read_bytes += inp.size_bytes // max(1, inp.mip_levels)
        
        # 输出带宽
        for out in self.get_all_outputs():
            if out.resource_type in (ResourceType.RENDER_TARGET, ResourceType.DEPTH_STENCIL):
                # 按像素数估算
                pixel_count = out.width * out.height
                bytes_per_pixel = self._format_bytes(out.format)
                write_bytes += pixel_count * bytes_per_pixel
            else:
                write_bytes += out.size_bytes
        
        return (read_bytes, write_bytes)
    
    def _format_bytes(self, format_str: str) -> int:
        """估算格式的每像素字节数"""
        format_upper = format_str.upper()
        
        if "R32G32B32A32" in format_upper:
            return 16
        elif "R16G16B16A16" in format_upper or "R32G32" in format_upper:
            return 8
        elif "R8G8B8A8" in format_upper or "R32" in format_upper or "R16G16" in format_upper:
            return 4
        elif "R16" in format_upper or "R8G8" in format_upper:
            return 2
        elif "R8" in format_upper:
            return 1
        elif "BC1" in format_upper or "BC4" in format_upper:
            return 0.5  # 压缩格式
        elif "BC" in format_upper:
            return 1  # BC2/3/5/6/7
        elif "D24" in format_upper or "D32" in format_upper:
            return 4
        elif "D16" in format_upper:
            return 2
        else:
            return 4  # 默认
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        read_bw, write_bw = self.estimate_bandwidth()
        
        return {
            "event_id": self.event_id,
            "name": self.name,
            "type": self.draw_type.name,
            "marker_path": self.marker_path,
            "depth": self.depth,
            "draw_params": {
                "vertex_count": self.vertex_count,
                "index_count": self.index_count,
                "instance_count": self.instance_count,
                "primitive_count": self.total_primitives,
            },
            "dispatch_params": {
                "x": self.thread_group_x,
                "y": self.thread_group_y,
                "z": self.thread_group_z,
            } if self.is_dispatch else None,
            "pipeline": self.pipeline.to_dict(),
            "bandwidth": {
                "read_bytes": read_bw,
                "write_bytes": write_bw,
            },
            "gpu_duration_ns": self.gpu_duration_ns,
        }


# =============================================================================
# 调用追踪结果
# =============================================================================

@dataclass
class CallTraceResult:
    """
    调用追踪分析结果
    
    包含整帧的所有 Draw Call 信息
    """
    # 元数据
    file_path: str = ""
    api: str = ""                          # "D3D11", "D3D12", "Vulkan", "OpenGL"
    analysis_time: datetime = field(default_factory=datetime.now)
    
    # Draw Call 列表
    draw_calls: List[DrawCallDetail] = field(default_factory=list)
    
    # 统计信息
    total_draw_calls: int = 0
    total_dispatches: int = 0
    total_clears: int = 0
    
    # 资源使用统计
    unique_textures: int = 0
    unique_buffers: int = 0
    unique_shaders: int = 0
    
    def get_draws_by_marker(self, marker: str) -> List[DrawCallDetail]:
        """按标记路径过滤 Draw Call"""
        return [dc for dc in self.draw_calls if marker in dc.marker_path]
    
    def get_draws_by_type(self, draw_type: DrawType) -> List[DrawCallDetail]:
        """按类型过滤 Draw Call"""
        return [dc for dc in self.draw_calls if dc.draw_type == draw_type]
    
    def get_resource_usage(self, resource_id: int) -> List[Tuple[int, AccessType]]:
        """
        获取资源的使用情况
        
        Returns:
            [(event_id, access_type), ...] 列表
        """
        usage = []
        for dc in self.draw_calls:
            # 检查输入
            for inp in dc.get_all_inputs():
                if inp.resource_id == resource_id:
                    usage.append((dc.event_id, AccessType.READ))
                    break
            
            # 检查输出
            for out in dc.get_all_outputs():
                if out.resource_id == resource_id:
                    usage.append((dc.event_id, AccessType.WRITE))
                    break
        
        return usage
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（完整导出）"""
        return {
            "metadata": {
                "file_path": self.file_path,
                "api": self.api,
                "analysis_time": self.analysis_time.isoformat(),
            },
            "statistics": {
                "total_draw_calls": self.total_draw_calls,
                "total_dispatches": self.total_dispatches,
                "total_clears": self.total_clears,
                "unique_textures": self.unique_textures,
                "unique_buffers": self.unique_buffers,
                "unique_shaders": self.unique_shaders,
            },
            "draw_calls": [dc.to_dict() for dc in self.draw_calls],
        }
