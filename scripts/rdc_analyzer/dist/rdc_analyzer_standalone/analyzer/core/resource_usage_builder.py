"""
资源使用索引构建器 (M1.2)
========================

遍历帧数据，构建资源反向索引（ResourceUsageIndex）。

功能：
    - 遍历所有 Draw/Dispatch 事件
    - 提取每个事件绑定的纹理、Shader、Buffer、RT
    - 构建 资源ID → 使用记录列表 的反向索引
    - 支持用途推测 (purpose_hint)

数据来源：
    - ParsedData.draws: DrawCallInfo 列表或 Dict 列表
    - ParsedData.textures: 纹理信息（用于交叉引用）
    - ParsedData.shaders: Shader 信息
    - ParsedData.render_passes: Pass 信息（用于 pass_name）

输出：
    - ResourceUsageIndex: 包含 texture_usages, shader_usages, buffer_usages, render_target_usages

使用示例：
    builder = ResourceUsageBuilder()
    index = builder.build(parsed_data)
    print(index.get_statistics())
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
import re

from .types import (
    UsageRecord,
    ResourceUsageIndex,
    ParsedData,
    DrawCallInfo,
    TextureInfo,
)


# ============================================================================
# 用途推测器 (Purpose Hinter)
# ============================================================================

class PurposeHinter:
    """
    纹理用途推测器
    
    基于纹理名称、格式、尺寸等信息推测用途。
    """
    
    # 名称关键词 → 用途映射
    NAME_PATTERNS = {
        # 材质纹理
        r'(albedo|diffuse|base_?color|_d\.|\bd\b)': 'Albedo',
        r'(normal|nrm|_n\.|bump)': 'Normal',
        r'(roughness|rough|_r\.|smoothness)': 'Roughness',
        r'(metallic|metal|_m\.)': 'Metallic',
        r'(ao|occlusion|ambient)': 'AO',
        r'(emissive|emission|glow)': 'Emissive',
        r'(height|displacement|parallax)': 'Height',
        r'(opacity|alpha|mask|_a\.)': 'Opacity',
        
        # 特殊纹理
        r'(shadow|shadowmap|csm|cascaded)': 'Shadow',
        r'(depth|_z\.|zbuffer)': 'Depth',
        r'(noise|random|blue_?noise)': 'Noise',
        r'(lut|lookup|color_?grading)': 'LUT',
        r'(cubemap|envmap|environment|skybox|ibl)': 'Environment',
        r'(lightmap|gi|indirect)': 'Lightmap',
        r'(reflection|ssr|probe)': 'Reflection',
        
        # RT 相关
        r'(gbuffer|g_?buffer)': 'GBuffer',
        r'(scene_?color|hdr_?target|main_?color)': 'SceneColor',
        r'(velocity|motion_?vector)': 'Velocity',
        r'(bloom|glow_?buffer)': 'Bloom',
        r'(post_?process|pp_)': 'PostProcess',
    }
    
    # 格式 → 用途映射
    FORMAT_HINTS = {
        # 压缩格式通常是材质纹理
        'BC1': 'Albedo',
        'BC3': 'Albedo',
        'BC5': 'Normal',
        'BC7': 'Albedo',
        'DXT1': 'Albedo',
        'DXT5': 'Albedo',
        
        # 深度格式
        'D16': 'Depth',
        'D24': 'Depth',
        'D32': 'Depth',
        'D24S8': 'DepthStencil',
        'D32S8': 'DepthStencil',
        
        # HDR 格式通常是 RT
        'R16G16B16A16_FLOAT': 'HDR_RT',
        'R11G11B10_FLOAT': 'HDR_RT',
        'R32G32B32A32_FLOAT': 'HDR_RT',
    }
    
    @classmethod
    def guess_purpose(
        cls,
        name: str = "",
        format_str: str = "",
        width: int = 0,
        height: int = 0,
        is_render_target: bool = False,
        is_depth_stencil: bool = False,
        binding_slot: int = -1
    ) -> str:
        """
        推测纹理用途
        
        优先级：
        1. 特殊标记 (is_render_target, is_depth_stencil)
        2. 名称匹配
        3. 格式匹配
        4. 槽位推测
        
        Returns:
            用途字符串，如 "Albedo", "Normal", "Shadow" 等
        """
        # 1. 特殊标记
        if is_depth_stencil:
            return "DepthStencil"
        if is_render_target:
            return "RenderTarget"
        
        # 2. 名称匹配
        name_lower = name.lower()
        for pattern, purpose in cls.NAME_PATTERNS.items():
            if re.search(pattern, name_lower, re.IGNORECASE):
                return purpose
        
        # 3. 格式匹配
        format_upper = format_str.upper()
        for fmt_key, purpose in cls.FORMAT_HINTS.items():
            if fmt_key in format_upper:
                return purpose
        
        # 4. 槽位推测 (常见约定)
        if binding_slot == 0:
            return "Albedo"  # t0 通常是 Albedo
        elif binding_slot == 1:
            return "Normal"  # t1 通常是 Normal
        elif binding_slot == 2:
            return "Roughness"  # t2 可能是 Roughness/Metallic
        
        return ""  # 无法推测


# ============================================================================
# 资源使用索引构建器
# ============================================================================

@dataclass
class ResourceUsageBuilder:
    """
    资源使用索引构建器 (M1.2)
    
    遍历 ParsedData 构建 ResourceUsageIndex。
    """
    
    # 配置
    enable_purpose_hint: bool = True  # 是否启用用途推测
    
    # 内部缓存
    _texture_info_map: Dict[str, TextureInfo] = field(default_factory=dict)
    _pass_map: Dict[int, str] = field(default_factory=dict)  # event_id -> pass_name
    
    def build(self, data: ParsedData) -> ResourceUsageIndex:
        """
        构建资源使用索引
        
        Args:
            data: ParsedData 对象（来自 XML/API 解析器）
            
        Returns:
            ResourceUsageIndex 实例
        """
        index = ResourceUsageIndex()
        
        # 1. 预处理：构建纹理信息映射
        self._build_texture_info_map(data)
        
        # 2. 预处理：构建 Pass 映射
        self._build_pass_map(data)
        
        # 3. 遍历 Draw 事件
        for draw in data.draws:
            self._process_draw(draw, index, data)
        
        # 4. 遍历 Dispatch 事件
        for dispatch in data.dispatches:
            self._process_dispatch(dispatch, index)
        
        return index
    
    def _build_texture_info_map(self, data: ParsedData) -> None:
        """构建纹理 ID → TextureInfo 映射"""
        self._texture_info_map = {}
        
        for tex in data.textures:
            if isinstance(tex, dict):
                tex_id = str(tex.get('id', '') or tex.get('resource_id', '') or tex.get('resourceId', ''))
                if tex_id:
                    # 创建临时 TextureInfo
                    self._texture_info_map[tex_id] = TextureInfo(
                        resource_id=tex_id,
                        name=tex.get('name', ''),
                        width=tex.get('width', 0),
                        height=tex.get('height', 0),
                        format=tex.get('format', ''),
                        is_render_target=tex.get('is_render_target', False) or tex.get('isRenderTarget', False),
                        is_depth_stencil=tex.get('is_depth_stencil', False) or tex.get('isDepthStencil', False),
                    )
            elif hasattr(tex, 'resource_id'):
                self._texture_info_map[tex.resource_id] = tex
    
    def _build_pass_map(self, data: ParsedData) -> None:
        """构建事件 ID → Pass 名称映射"""
        self._pass_map = {}
        
        for rp in data.render_passes:
            if isinstance(rp, dict):
                start_eid = rp.get('start_event_id', 0) or rp.get('startEventId', 0)
                end_eid = rp.get('end_event_id', 0) or rp.get('endEventId', 0)
                pass_name = rp.get('name', '') or rp.get('marker_name', '')
                
                if start_eid and end_eid:
                    for eid in range(start_eid, end_eid + 1):
                        self._pass_map[eid] = pass_name
    
    def _process_draw(
        self,
        draw: Any,
        index: ResourceUsageIndex,
        data: ParsedData
    ) -> None:
        """处理单个 Draw 事件"""
        # 提取基本信息
        if isinstance(draw, dict):
            event_id = draw.get('eid', 0) or draw.get('event_id', 0) or draw.get('eventId', 0)
            draw_name = draw.get('name', '')
            vs_id = draw.get('vs_id', '') or draw.get('vs', '')
            ps_id = draw.get('ps_id', '') or draw.get('ps', '')
            rt_ids = draw.get('rt_ids', []) or draw.get('outputs', [])
            ds_id = draw.get('ds_id', '') or draw.get('depth', '')
            pipeline = draw.get('pipelineState', {}) or draw.get('pipeline', {})
        elif hasattr(draw, 'event_id'):
            event_id = draw.event_id
            draw_name = draw.name
            vs_id = draw.vs_id
            ps_id = draw.ps_id
            rt_ids = draw.rt_ids
            ds_id = draw.ds_id
            pipeline = {}
        else:
            return
        
        if not event_id:
            return
        
        pass_name = self._pass_map.get(event_id, '')
        
        # 1. 记录 Shader 使用
        if vs_id:
            index.add_shader_usage(str(vs_id), UsageRecord(
                event_id=event_id,
                binding_type="VS",
                purpose_hint="VertexShader",
                pass_name=pass_name,
                draw_name=draw_name
            ))
        
        if ps_id:
            index.add_shader_usage(str(ps_id), UsageRecord(
                event_id=event_id,
                binding_type="PS",
                purpose_hint="PixelShader",
                pass_name=pass_name,
                draw_name=draw_name
            ))
        
        # 2. 记录 RenderTarget 使用
        for slot, rt_id in enumerate(rt_ids or []):
            if rt_id:
                index.add_rt_usage(str(rt_id), UsageRecord(
                    event_id=event_id,
                    binding_type="RTV",
                    slot=slot,
                    purpose_hint="RenderTarget",
                    pass_name=pass_name,
                    draw_name=draw_name
                ))
        
        # 3. 记录 DepthStencil 使用
        if ds_id:
            index.add_rt_usage(str(ds_id), UsageRecord(
                event_id=event_id,
                binding_type="DSV",
                slot=0,
                purpose_hint="DepthStencil",
                pass_name=pass_name,
                draw_name=draw_name
            ))
        
        # 4. 从 pipeline 中提取 SRV 纹理绑定
        self._extract_texture_bindings(event_id, draw_name, pass_name, pipeline, index)
        
        # 5. 从 draw 的 bindings/resourceBindings 提取（备选格式）
        if isinstance(draw, dict):
            bindings = draw.get('bindings', {}) or draw.get('resourceBindings', {})
            self._extract_texture_bindings(event_id, draw_name, pass_name, bindings, index)
    
    def _extract_texture_bindings(
        self,
        event_id: int,
        draw_name: str,
        pass_name: str,
        pipeline: Dict,
        index: ResourceUsageIndex
    ) -> None:
        """从 pipeline/bindings 中提取纹理绑定"""
        if not pipeline:
            return
        
        # 格式 1: shaderResources (新格式)
        shader_resources = pipeline.get('shaderResources', {})
        if shader_resources:
            for stage, resources in shader_resources.items():
                if isinstance(resources, list):
                    for res in resources:
                        if isinstance(res, dict):
                            res_id = str(res.get('resourceId', '') or res.get('resource', ''))
                            slot = res.get('slot', -1)
                            if res_id:
                                purpose = self._guess_texture_purpose(res_id, slot)
                                index.add_texture_usage(res_id, UsageRecord(
                                    event_id=event_id,
                                    binding_type="SRV",
                                    slot=slot,
                                    purpose_hint=purpose,
                                    pass_name=pass_name,
                                    draw_name=draw_name
                                ))
        
        # 格式 2: textures 列表
        textures = pipeline.get('textures', [])
        for tex in textures:
            if isinstance(tex, dict):
                tex_id = str(tex.get('id', '') or tex.get('resourceId', ''))
                slot = tex.get('slot', -1)
                if tex_id:
                    purpose = self._guess_texture_purpose(tex_id, slot)
                    index.add_texture_usage(tex_id, UsageRecord(
                        event_id=event_id,
                        binding_type="SRV",
                        slot=slot,
                        purpose_hint=purpose,
                        pass_name=pass_name,
                        draw_name=draw_name
                    ))
        
        # 格式 3: descriptorSets (Vulkan)
        desc_sets = pipeline.get('descriptorSets', {})
        for set_id, bindings in desc_sets.items():
            if isinstance(bindings, list):
                for binding in bindings:
                    if isinstance(binding, dict):
                        desc_type = binding.get('descriptorType', '')
                        if 'SAMPLED_IMAGE' in desc_type or 'COMBINED_IMAGE' in desc_type:
                            resources = binding.get('resources', [])
                            slot = binding.get('binding', -1)
                            for res in resources:
                                res_id = str(res.get('resourceId', '') or res.get('resource', ''))
                                if res_id:
                                    purpose = self._guess_texture_purpose(res_id, slot)
                                    index.add_texture_usage(res_id, UsageRecord(
                                        event_id=event_id,
                                        binding_type="SRV",
                                        slot=slot,
                                        purpose_hint=purpose,
                                        pass_name=pass_name,
                                        draw_name=draw_name
                                    ))
    
    def _process_dispatch(self, dispatch: Any, index: ResourceUsageIndex) -> None:
        """处理 Dispatch 事件"""
        if isinstance(dispatch, dict):
            event_id = dispatch.get('eid', 0) or dispatch.get('event_id', 0)
            draw_name = dispatch.get('name', 'Dispatch')
            cs_id = dispatch.get('cs_id', '') or dispatch.get('cs', '')
            pipeline = dispatch.get('pipelineState', {})
        else:
            return
        
        if not event_id:
            return
        
        pass_name = self._pass_map.get(event_id, '')
        
        # 记录 Compute Shader 使用
        if cs_id:
            index.add_shader_usage(str(cs_id), UsageRecord(
                event_id=event_id,
                binding_type="CS",
                purpose_hint="ComputeShader",
                pass_name=pass_name,
                draw_name=draw_name
            ))
        
        # 提取 UAV 绑定
        if pipeline:
            uavs = pipeline.get('uavs', []) or pipeline.get('readWriteResources', [])
            for uav in uavs:
                if isinstance(uav, dict):
                    res_id = str(uav.get('resourceId', '') or uav.get('resource', ''))
                    slot = uav.get('slot', -1)
                    if res_id:
                        index.add_texture_usage(res_id, UsageRecord(
                            event_id=event_id,
                            binding_type="UAV",
                            slot=slot,
                            purpose_hint="ComputeOutput",
                            pass_name=pass_name,
                            draw_name=draw_name
                        ))
    
    def _guess_texture_purpose(self, tex_id: str, slot: int = -1) -> str:
        """推测纹理用途"""
        if not self.enable_purpose_hint:
            return ""
        
        tex_info = self._texture_info_map.get(tex_id)
        if tex_info:
            return PurposeHinter.guess_purpose(
                name=tex_info.name,
                format_str=tex_info.format,
                width=tex_info.width,
                height=tex_info.height,
                is_render_target=tex_info.is_render_target,
                is_depth_stencil=tex_info.is_depth_stencil,
                binding_slot=slot
            )
        
        # 无纹理信息，仅基于槽位推测
        return PurposeHinter.guess_purpose(binding_slot=slot)


# ============================================================================
# 便捷函数
# ============================================================================

def build_resource_usage_index(data: ParsedData) -> ResourceUsageIndex:
    """
    构建资源使用索引的便捷函数
    
    Args:
        data: ParsedData 对象
        
    Returns:
        ResourceUsageIndex 实例
    """
    builder = ResourceUsageBuilder()
    return builder.build(data)
