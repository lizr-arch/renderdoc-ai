"""
D3D11 管线状态提取器
====================

从 D3D11 RDC 文件中提取完整的管线状态信息

功能:
1. 提取输入装配阶段（顶点缓冲、索引缓冲、输入布局）
2. 提取所有着色器阶段及其资源绑定
3. 提取光栅化状态、混合状态、深度模板状态
4. 提取渲染目标和视口信息
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
    RENDERDOC_AVAILABLE = True
except ImportError:
    rd = None  # type: ignore
    RENDERDOC_AVAILABLE = False

from .base import (
    BaseExtractor,
    ExtractorRegistry,
    ExtractorConfig,
    EventInfo,
    EventType,
    StateExtractionError,
)
from .event_parser import EventParser
from .replay_wrapper import ReplayWrapper, CaptureInfo

from ..core.pipeline_state import (
    PipelineSnapshot,
    DrawCallDetail,
    ResourceBinding,
    ShaderBindings,
    SamplerInfo,
    RenderTargetInfo,
    DepthStencilInfo,
    ViewportInfo,
    ScissorRect,
    BlendStateInfo,
    RasterizerStateInfo,
    ResourceType,
    ShaderStage,
    PrimitiveTopology,
    CullMode,
    FillMode,
)


logger = logging.getLogger(__name__)


# =============================================================================
# D3D11 格式映射
# =============================================================================

def map_d3d11_primitive_topology(topology: Any) -> PrimitiveTopology:
    """映射 D3D11 图元拓扑到通用枚举"""
    if not RENDERDOC_AVAILABLE:
        return PrimitiveTopology.TRIANGLE_LIST
    
    # RenderDoc 的 Topology 枚举
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
        rd.Topology.PatchList_1CPs: PrimitiveTopology.PATCH_LIST,
    }
    
    return topo_map.get(topology, PrimitiveTopology.TRIANGLE_LIST)


def map_d3d11_format(fmt: Any) -> str:
    """映射 D3D11 格式到字符串"""
    if not RENDERDOC_AVAILABLE or fmt is None:
        return ""
    
    # 尝试获取格式名称
    try:
        return str(fmt).replace("ResourceFormat.", "")
    except Exception:
        return str(fmt)


def get_format_bytes_per_pixel(fmt_str: str) -> int:
    """估算格式的每像素字节数"""
    fmt = fmt_str.upper()
    
    if "R32G32B32A32" in fmt:
        return 16
    elif "R16G16B16A16" in fmt or "R32G32" in fmt:
        return 8
    elif "R8G8B8A8" in fmt or "R32" in fmt or "R16G16" in fmt or "R10G10B10A2" in fmt:
        return 4
    elif "R16" in fmt or "R8G8" in fmt:
        return 2
    elif "R8" in fmt:
        return 1
    elif "BC1" in fmt or "BC4" in fmt:
        return 0  # 块压缩，需要特殊处理
    elif "BC" in fmt:
        return 1
    elif "D24" in fmt or "D32" in fmt:
        return 4
    elif "D16" in fmt:
        return 2
    else:
        return 4


# =============================================================================
# D3D11 提取器
# =============================================================================

@ExtractorRegistry.register("D3D11")
class D3D11Extractor(BaseExtractor):
    """
    D3D11 管线状态提取器
    
    从 D3D11 RDC 文件中提取完整的管线状态
    """
    
    API_NAME = "D3D11"
    SUPPORTED_VERSIONS = ["11.0", "11.1"]
    
    def __init__(self, replay: ReplayWrapper, config: Optional[ExtractorConfig] = None):
        """
        初始化 D3D11 提取器
        
        Args:
            replay: ReplayWrapper 实例（已打开）
            config: 提取配置
        """
        # 使用 replay.controller 作为底层控制器
        super().__init__(replay.controller, config)
        
        self.replay = replay
        self._parser = EventParser("D3D11")
    
    def get_api_version(self) -> str:
        """获取 D3D11 版本"""
        return "11.0"
    
    def build_event_tree(self) -> List[EventInfo]:
        """构建事件树"""
        return self._parser.parse_from_controller(self.controller)
    
    def extract_pipeline_state(self, event_id: int) -> PipelineSnapshot:
        """
        提取指定事件的完整管线状态
        
        Args:
            event_id: 事件 ID
            
        Returns:
            PipelineSnapshot 对象
        """
        # 移动到目标事件
        self.replay.move_to_event(event_id)
        
        # 获取 D3D11 管线状态
        d3d11_state = self.replay.get_d3d11_state()
        
        if not d3d11_state:
            raise StateExtractionError(event_id, "Failed to get D3D11 pipeline state")
        
        # 构建快照
        snapshot = PipelineSnapshot()
        
        # 提取各个阶段的状态
        try:
            snapshot.vertex_buffers = self._extract_vertex_buffers(d3d11_state)
            snapshot.index_buffer = self._extract_index_buffer(d3d11_state)
            snapshot.primitive_topology = self._extract_topology(d3d11_state)
            
            # 着色器阶段
            snapshot.vertex_shader = self._extract_shader_stage(d3d11_state, ShaderStage.VERTEX)
            snapshot.hull_shader = self._extract_shader_stage(d3d11_state, ShaderStage.HULL)
            snapshot.domain_shader = self._extract_shader_stage(d3d11_state, ShaderStage.DOMAIN)
            snapshot.geometry_shader = self._extract_shader_stage(d3d11_state, ShaderStage.GEOMETRY)
            snapshot.pixel_shader = self._extract_shader_stage(d3d11_state, ShaderStage.PIXEL)
            snapshot.compute_shader = self._extract_shader_stage(d3d11_state, ShaderStage.COMPUTE)
            
            # 光栅化阶段
            snapshot.viewports = self._extract_viewports(d3d11_state)
            snapshot.scissor_rects = self._extract_scissors(d3d11_state)
            snapshot.rasterizer_state = self._extract_rasterizer_state(d3d11_state)
            
            # 输出合并阶段
            snapshot.render_targets = self._extract_render_targets(d3d11_state)
            snapshot.depth_stencil = self._extract_depth_stencil(d3d11_state)
            snapshot.blend_states = self._extract_blend_states(d3d11_state)
            
        except Exception as e:
            logger.error(f"Error extracting pipeline state at event {event_id}: {e}")
            raise StateExtractionError(event_id, str(e))
        
        return snapshot
    
    def extract_draw_params(self, event_id: int) -> Dict[str, Any]:
        """
        提取绘制调用参数
        
        Args:
            event_id: 事件 ID
            
        Returns:
            绘制参数字典
        """
        # 查找事件
        event = self._event_map.get(event_id)
        if event and event.draw_params:
            return event.draw_params
        
        # 如果没有缓存的参数，尝试从动作中获取
        for action in self.replay.iter_actions():
            if action.eventId == event_id:
                return self._parser._extract_draw_params(action)
        
        return {}
    
    # -------------------------------------------------------------------------
    # 输入装配阶段提取
    # -------------------------------------------------------------------------
    
    def _extract_vertex_buffers(self, state: Any) -> List[ResourceBinding]:
        """提取顶点缓冲区绑定"""
        vertex_buffers = []
        
        ia = state.inputAssembly
        vbs = ia.vertexBuffers
        
        for i, vb in enumerate(vbs):
            if vb.resourceId == rd.ResourceId.Null():
                continue
            
            # 获取缓冲区信息
            buf_desc = self.replay.get_buffer_description(int(vb.resourceId))
            
            binding = ResourceBinding(
                slot=i,
                stage=ShaderStage.VERTEX,
                resource_id=int(vb.resourceId),
                resource_name=self.replay.get_resource_name(int(vb.resourceId)),
                resource_type=ResourceType.BUFFER,
                stride=vb.byteStride,
                offset=vb.byteOffset,
                size_bytes=buf_desc.length if buf_desc else 0,
            )
            vertex_buffers.append(binding)
        
        return vertex_buffers
    
    def _extract_index_buffer(self, state: Any) -> Optional[ResourceBinding]:
        """提取索引缓冲区绑定"""
        ia = state.inputAssembly
        ib = ia.indexBuffer
        
        if ib.resourceId == rd.ResourceId.Null():
            return None
        
        buf_desc = self.replay.get_buffer_description(int(ib.resourceId))
        
        # 确定索引格式
        fmt_str = ""
        if ib.byteStride == 2:
            fmt_str = "R16_UINT"
        elif ib.byteStride == 4:
            fmt_str = "R32_UINT"
        
        return ResourceBinding(
            slot=0,
            stage=ShaderStage.VERTEX,
            resource_id=int(ib.resourceId),
            resource_name=self.replay.get_resource_name(int(ib.resourceId)),
            resource_type=ResourceType.BUFFER,
            format=fmt_str,
            stride=ib.byteStride,
            offset=ib.byteOffset,
            size_bytes=buf_desc.length if buf_desc else 0,
        )
    
    def _extract_topology(self, state: Any) -> PrimitiveTopology:
        """提取图元拓扑"""
        ia = state.inputAssembly
        return map_d3d11_primitive_topology(ia.topology)
    
    # -------------------------------------------------------------------------
    # 着色器阶段提取
    # -------------------------------------------------------------------------
    
    def _extract_shader_stage(self, state: Any, stage: ShaderStage) -> Optional[ShaderBindings]:
        """
        提取着色器阶段的完整绑定
        
        Args:
            state: D3D11 管线状态
            stage: 着色器阶段
            
        Returns:
            ShaderBindings 或 None（如果该阶段未绑定）
        """
        # 根据阶段获取对应的状态
        stage_state = self._get_stage_state(state, stage)
        if not stage_state:
            return None
        
        # 获取着色器资源 ID
        shader_id = int(stage_state.shader)
        if shader_id == 0:
            return None
        
        # 创建着色器绑定信息
        shader_info = ShaderBindings(
            stage=stage,
            resource_id=shader_id,
            name=self.replay.get_resource_name(shader_id),
        )
        
        # 提取常量缓冲区
        if self.config.extract_buffers:
            shader_info.constant_buffers = self._extract_cbuffers(stage_state, stage)
        
        # 提取着色器资源视图 (SRV)
        if self.config.extract_textures:
            shader_info.shader_resources = self._extract_srvs(stage_state, stage)
        
        # 提取采样器
        if self.config.extract_samplers:
            shader_info.samplers = self._extract_samplers(stage_state, stage)
        
        # 提取 UAV（仅 PS 和 CS）
        if stage in (ShaderStage.PIXEL, ShaderStage.COMPUTE):
            shader_info.uavs = self._extract_uavs(state, stage)
        
        return shader_info
    
    def _get_stage_state(self, state: Any, stage: ShaderStage) -> Optional[Any]:
        """获取指定着色器阶段的状态"""
        stage_map = {
            ShaderStage.VERTEX: state.vertexShader,
            ShaderStage.HULL: state.hullShader,
            ShaderStage.DOMAIN: state.domainShader,
            ShaderStage.GEOMETRY: state.geometryShader,
            ShaderStage.PIXEL: state.pixelShader,
            ShaderStage.COMPUTE: state.computeShader,
        }
        return stage_map.get(stage)
    
    def _extract_cbuffers(self, stage_state: Any, stage: ShaderStage) -> List[ResourceBinding]:
        """提取常量缓冲区绑定"""
        cbuffers = []
        
        for i, cb in enumerate(stage_state.constantBuffers):
            if cb.resourceId == rd.ResourceId.Null():
                continue
            
            buf_desc = self.replay.get_buffer_description(int(cb.resourceId))
            
            binding = ResourceBinding(
                slot=i,
                stage=stage,
                resource_id=int(cb.resourceId),
                resource_name=self.replay.get_resource_name(int(cb.resourceId)),
                resource_type=ResourceType.BUFFER,
                offset=cb.byteOffset,
                size_bytes=cb.byteSize if cb.byteSize > 0 else (buf_desc.length if buf_desc else 0),
            )
            cbuffers.append(binding)
        
        return cbuffers
    
    def _extract_srvs(self, stage_state: Any, stage: ShaderStage) -> List[ResourceBinding]:
        """提取着色器资源视图"""
        srvs = []
        
        for i, srv in enumerate(stage_state.srvs):
            if srv.resourceId == rd.ResourceId.Null():
                continue
            
            # 确定资源类型
            res_type = ResourceType.UNKNOWN
            width, height, depth = 0, 0, 1
            mips = 1
            fmt_str = ""
            size_bytes = 0
            
            # 尝试获取纹理描述
            tex_desc = self.replay.get_texture_description(int(srv.resourceId))
            if tex_desc:
                width = tex_desc.width
                height = tex_desc.height
                depth = tex_desc.depth
                mips = tex_desc.mips
                fmt_str = map_d3d11_format(tex_desc.format)
                
                # 确定纹理类型
                if tex_desc.type == rd.TextureType.Texture1D:
                    res_type = ResourceType.TEXTURE_1D
                elif tex_desc.type == rd.TextureType.Texture2D:
                    res_type = ResourceType.TEXTURE_2D
                elif tex_desc.type == rd.TextureType.Texture3D:
                    res_type = ResourceType.TEXTURE_3D
                elif tex_desc.type == rd.TextureType.TextureCube:
                    res_type = ResourceType.TEXTURE_CUBE
                
                # 估算大小
                bpp = get_format_bytes_per_pixel(fmt_str)
                if bpp > 0:
                    size_bytes = width * height * depth * bpp
            else:
                # 可能是缓冲区
                buf_desc = self.replay.get_buffer_description(int(srv.resourceId))
                if buf_desc:
                    res_type = ResourceType.BUFFER
                    size_bytes = buf_desc.length
            
            binding = ResourceBinding(
                slot=i,
                stage=stage,
                resource_id=int(srv.resourceId),
                resource_name=self.replay.get_resource_name(int(srv.resourceId)),
                resource_type=res_type,
                format=fmt_str,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mips,
                size_bytes=size_bytes,
            )
            srvs.append(binding)
        
        return srvs
    
    def _extract_samplers(self, stage_state: Any, stage: ShaderStage) -> List[SamplerInfo]:
        """提取采样器状态"""
        samplers = []
        
        for i, sam in enumerate(stage_state.samplers):
            if sam.resourceId == rd.ResourceId.Null():
                continue
            
            # 映射过滤模式
            filter_mode = self._map_filter_mode(sam)
            
            # 映射寻址模式
            addr_u = self._map_address_mode(sam.addressU)
            addr_v = self._map_address_mode(sam.addressV)
            addr_w = self._map_address_mode(sam.addressW)
            
            sampler = SamplerInfo(
                slot=i,
                stage=stage,
                resource_id=int(sam.resourceId),
                filter_mode=filter_mode,
                address_u=addr_u,
                address_v=addr_v,
                address_w=addr_w,
                max_anisotropy=sam.maxAnisotropy if hasattr(sam, 'maxAnisotropy') else 1,
                mip_lod_bias=sam.mipLODBias if hasattr(sam, 'mipLODBias') else 0.0,
                min_lod=sam.minLOD if hasattr(sam, 'minLOD') else 0.0,
                max_lod=sam.maxLOD if hasattr(sam, 'maxLOD') else 1000.0,
            )
            samplers.append(sampler)
        
        return samplers
    
    def _extract_uavs(self, state: Any, stage: ShaderStage) -> List[ResourceBinding]:
        """提取 UAV 绑定"""
        uavs = []
        
        if stage == ShaderStage.COMPUTE:
            uav_list = state.computeShader.uavs
        elif stage == ShaderStage.PIXEL:
            uav_list = state.outputMerger.uavs
        else:
            return uavs
        
        for i, uav in enumerate(uav_list):
            if uav.resourceId == rd.ResourceId.Null():
                continue
            
            res_type = ResourceType.UAV
            width, height, size_bytes = 0, 0, 0
            fmt_str = ""
            
            # 尝试获取资源信息
            tex_desc = self.replay.get_texture_description(int(uav.resourceId))
            if tex_desc:
                width = tex_desc.width
                height = tex_desc.height
                fmt_str = map_d3d11_format(tex_desc.format)
            else:
                buf_desc = self.replay.get_buffer_description(int(uav.resourceId))
                if buf_desc:
                    size_bytes = buf_desc.length
            
            binding = ResourceBinding(
                slot=i,
                stage=stage,
                resource_id=int(uav.resourceId),
                resource_name=self.replay.get_resource_name(int(uav.resourceId)),
                resource_type=res_type,
                format=fmt_str,
                width=width,
                height=height,
                size_bytes=size_bytes,
            )
            uavs.append(binding)
        
        return uavs
    
    def _map_filter_mode(self, sampler: Any) -> str:
        """映射采样器过滤模式"""
        if not hasattr(sampler, 'filter'):
            return "Point"
        
        filter_val = str(sampler.filter)
        
        if "Anisotropic" in filter_val:
            return "Anisotropic"
        elif "Linear" in filter_val:
            return "Linear"
        else:
            return "Point"
    
    def _map_address_mode(self, mode: Any) -> str:
        """映射寻址模式"""
        mode_str = str(mode)
        
        if "Wrap" in mode_str:
            return "Wrap"
        elif "Mirror" in mode_str:
            return "Mirror"
        elif "Clamp" in mode_str:
            return "Clamp"
        elif "Border" in mode_str:
            return "Border"
        else:
            return "Wrap"
    
    # -------------------------------------------------------------------------
    # 光栅化阶段提取
    # -------------------------------------------------------------------------
    
    def _extract_viewports(self, state: Any) -> List[ViewportInfo]:
        """提取视口"""
        viewports = []
        
        rs = state.rasterizer
        for vp in rs.viewports:
            if vp.width == 0 and vp.height == 0:
                continue
            
            viewport = ViewportInfo(
                x=vp.x,
                y=vp.y,
                width=vp.width,
                height=vp.height,
                min_depth=vp.minDepth,
                max_depth=vp.maxDepth,
            )
            viewports.append(viewport)
        
        return viewports
    
    def _extract_scissors(self, state: Any) -> List[ScissorRect]:
        """提取裁剪矩形"""
        scissors = []
        
        rs = state.rasterizer
        for sc in rs.scissors:
            if sc.right == 0 and sc.bottom == 0:
                continue
            
            scissor = ScissorRect(
                x=sc.left,
                y=sc.top,
                width=sc.right - sc.left,
                height=sc.bottom - sc.top,
            )
            scissors.append(scissor)
        
        return scissors
    
    def _extract_rasterizer_state(self, state: Any) -> RasterizerStateInfo:
        """提取光栅化状态"""
        rs = state.rasterizer.state
        
        # 映射填充模式
        fill_mode = FillMode.SOLID
        if hasattr(rs, 'fillMode'):
            fill_str = str(rs.fillMode)
            if "Wireframe" in fill_str:
                fill_mode = FillMode.WIREFRAME
        
        # 映射剔除模式
        cull_mode = CullMode.BACK
        if hasattr(rs, 'cullMode'):
            cull_str = str(rs.cullMode)
            if "None" in cull_str:
                cull_mode = CullMode.NONE
            elif "Front" in cull_str:
                cull_mode = CullMode.FRONT
        
        return RasterizerStateInfo(
            fill_mode=fill_mode,
            cull_mode=cull_mode,
            front_ccw=rs.frontCCW if hasattr(rs, 'frontCCW') else False,
            depth_bias=rs.depthBias if hasattr(rs, 'depthBias') else 0,
            depth_bias_clamp=rs.depthBiasClamp if hasattr(rs, 'depthBiasClamp') else 0.0,
            slope_scaled_depth_bias=rs.slopeScaledDepthBias if hasattr(rs, 'slopeScaledDepthBias') else 0.0,
            depth_clip_enabled=rs.depthClip if hasattr(rs, 'depthClip') else True,
            scissor_enabled=rs.scissorEnable if hasattr(rs, 'scissorEnable') else False,
            multisample_enabled=rs.multisampleEnable if hasattr(rs, 'multisampleEnable') else False,
        )
    
    # -------------------------------------------------------------------------
    # 输出合并阶段提取
    # -------------------------------------------------------------------------
    
    def _extract_render_targets(self, state: Any) -> List[RenderTargetInfo]:
        """提取渲染目标"""
        render_targets = []
        
        om = state.outputMerger
        for i, rtv in enumerate(om.renderTargets):
            if rtv.resourceId == rd.ResourceId.Null():
                continue
            
            width, height = 0, 0
            fmt_str = ""
            
            tex_desc = self.replay.get_texture_description(int(rtv.resourceId))
            if tex_desc:
                width = tex_desc.width
                height = tex_desc.height
                fmt_str = map_d3d11_format(tex_desc.format)
            
            rt = RenderTargetInfo(
                slot=i,
                resource_id=int(rtv.resourceId),
                resource_name=self.replay.get_resource_name(int(rtv.resourceId)),
                format=fmt_str,
                width=width,
                height=height,
            )
            render_targets.append(rt)
        
        return render_targets
    
    def _extract_depth_stencil(self, state: Any) -> Optional[DepthStencilInfo]:
        """提取深度模板缓冲"""
        om = state.outputMerger
        dsv = om.depthTarget
        
        if dsv.resourceId == rd.ResourceId.Null():
            return None
        
        width, height = 0, 0
        fmt_str = ""
        
        tex_desc = self.replay.get_texture_description(int(dsv.resourceId))
        if tex_desc:
            width = tex_desc.width
            height = tex_desc.height
            fmt_str = map_d3d11_format(tex_desc.format)
        
        # 获取深度模板状态
        ds_state = om.depthStencilState
        
        return DepthStencilInfo(
            resource_id=int(dsv.resourceId),
            resource_name=self.replay.get_resource_name(int(dsv.resourceId)),
            format=fmt_str,
            width=width,
            height=height,
            depth_test_enabled=ds_state.depthEnable if hasattr(ds_state, 'depthEnable') else True,
            depth_write_enabled=ds_state.depthWrites if hasattr(ds_state, 'depthWrites') else True,
            depth_func=self._map_compare_func(ds_state.depthFunction) if hasattr(ds_state, 'depthFunction') else "Less",
            stencil_enabled=ds_state.stencilEnable if hasattr(ds_state, 'stencilEnable') else False,
        )
    
    def _extract_blend_states(self, state: Any) -> List[BlendStateInfo]:
        """提取混合状态"""
        blend_states = []
        
        om = state.outputMerger
        bs = om.blendState
        
        for i, rt_blend in enumerate(bs.blends):
            blend = BlendStateInfo(
                enabled=rt_blend.enabled if hasattr(rt_blend, 'enabled') else False,
                src_blend=self._map_blend_factor(rt_blend.colorBlend.source) if hasattr(rt_blend, 'colorBlend') else "One",
                dst_blend=self._map_blend_factor(rt_blend.colorBlend.destination) if hasattr(rt_blend, 'colorBlend') else "Zero",
                blend_op=self._map_blend_op(rt_blend.colorBlend.operation) if hasattr(rt_blend, 'colorBlend') else "Add",
                src_blend_alpha=self._map_blend_factor(rt_blend.alphaBlend.source) if hasattr(rt_blend, 'alphaBlend') else "One",
                dst_blend_alpha=self._map_blend_factor(rt_blend.alphaBlend.destination) if hasattr(rt_blend, 'alphaBlend') else "Zero",
                blend_op_alpha=self._map_blend_op(rt_blend.alphaBlend.operation) if hasattr(rt_blend, 'alphaBlend') else "Add",
                write_mask=rt_blend.writeMask if hasattr(rt_blend, 'writeMask') else 0xF,
            )
            blend_states.append(blend)
        
        return blend_states
    
    def _map_compare_func(self, func: Any) -> str:
        """映射比较函数"""
        func_str = str(func)
        
        if "Never" in func_str:
            return "Never"
        elif "Less" in func_str and "Equal" not in func_str:
            return "Less"
        elif "Equal" in func_str and "Less" not in func_str and "Greater" not in func_str:
            return "Equal"
        elif "LessEqual" in func_str:
            return "LessEqual"
        elif "Greater" in func_str and "Equal" not in func_str:
            return "Greater"
        elif "NotEqual" in func_str:
            return "NotEqual"
        elif "GreaterEqual" in func_str:
            return "GreaterEqual"
        elif "Always" in func_str:
            return "Always"
        else:
            return "Less"
    
    def _map_blend_factor(self, factor: Any) -> str:
        """映射混合因子"""
        factor_str = str(factor)
        
        if "Zero" in factor_str:
            return "Zero"
        elif "One" in factor_str and "Minus" not in factor_str:
            return "One"
        elif "SrcColor" in factor_str:
            return "SrcColor"
        elif "InvSrcColor" in factor_str:
            return "InvSrcColor"
        elif "SrcAlpha" in factor_str:
            return "SrcAlpha"
        elif "InvSrcAlpha" in factor_str:
            return "InvSrcAlpha"
        elif "DestAlpha" in factor_str:
            return "DestAlpha"
        elif "InvDestAlpha" in factor_str:
            return "InvDestAlpha"
        elif "DestColor" in factor_str:
            return "DestColor"
        elif "InvDestColor" in factor_str:
            return "InvDestColor"
        else:
            return "One"
    
    def _map_blend_op(self, op: Any) -> str:
        """映射混合操作"""
        op_str = str(op)
        
        if "Add" in op_str:
            return "Add"
        elif "Subtract" in op_str and "Rev" not in op_str:
            return "Subtract"
        elif "RevSubtract" in op_str:
            return "RevSubtract"
        elif "Min" in op_str:
            return "Min"
        elif "Max" in op_str:
            return "Max"
        else:
            return "Add"
