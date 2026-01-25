"""
XMLToContextBridge - XML 解析结果到 AnalysisContext 的桥接器
==============================================================

将 parse_rdc_xml.py 的输出 dict 转换为 AnalysisContext 对象，
使 PerformanceAnalyzer 和 OptimizationAdvisor 能够直接使用。

TASK-007 实现
Created: 2026-01-19
"""

from typing import Dict, List, Any, Optional
from dataclasses import asdict

from .types import (
    ParsedData,
    DrawCallInfo,
    TextureInfo,
    BufferInfo,
    ShaderInfo,
    FrameSummary,
    PassInfo,
    PerformanceReport,
)
from .context import AnalysisContext


class XMLToContextBridge:
    """
    将 XML 解析结果转换为 AnalysisContext 的桥接器。
    
    使用方式:
        xml_data = parse_rdc_xml(xml_path)
        context = XMLToContextBridge.convert(xml_data)
        analyzer = PerformanceAnalyzer(context)
        analyzer.analyze()
    """
    
    # Draw Call 类型映射 (XML action type -> normalized type)
    DRAW_CALL_TYPES = {
        'DrawIndexed', 'DrawIndexedInstanced', 'DrawIndexedInstancedIndirect',
        'Draw', 'DrawInstanced', 'DrawInstancedIndirect',
        'vkCmdDraw', 'vkCmdDrawIndexed', 'vkCmdDrawIndirect',
        'vkCmdDrawIndexedIndirect', 'vkCmdDrawIndirectCount',
        'glDrawElements', 'glDrawArrays', 'glDrawElementsInstanced',
    }
    
    DISPATCH_TYPES = {
        'Dispatch', 'DispatchIndirect',
        'vkCmdDispatch', 'vkCmdDispatchIndirect',
        'glDispatchCompute',
    }
    
    @classmethod
    def convert(cls, xml_data: Dict[str, Any], file_path: str = "") -> AnalysisContext:
        """
        将 XML 解析数据转换为 AnalysisContext。
        
        Args:
            xml_data: parse_rdc_xml() 的输出 dict
            file_path: 可选的源文件路径
            
        Returns:
            填充完成的 AnalysisContext 对象
        """
        context = AnalysisContext()
        
        # 1. 基础元数据
        context.api = xml_data.get('apiType', 'Unknown')
        context.file_path = file_path or xml_data.get('file_path', '')
        
        # 2. 转换事件为 DrawCallInfo 列表
        context.draw_calls = cls._convert_events(xml_data.get('events', []))
        
        # 3. 转换纹理
        context.textures = cls._convert_textures(xml_data.get('textures', []))
        
        # 4. 转换缓冲区
        context.buffers = cls._convert_buffers(xml_data.get('buffers', []))
        
        # 5. 转换 Shader (TASK-201)
        context.shaders = cls._convert_shaders(
            xml_data.get('shaders', []),
            context.draw_calls
        )
        
        # 6. 生成帧摘要
        context.frame_summary = cls._convert_statistics(
            xml_data.get('statistics', {}),
            context.draw_calls,
            context.textures,
            context.buffers
        )
        
        # 6. 填充 ParsedData (保留原始数据供回溯)
        context.parsed = cls._create_parsed_data(xml_data, file_path)
        
        # 7. 初始化空的性能报告 (由 PerformanceAnalyzer 填充)
        context.performance_report = PerformanceReport()
        
        return context
    
    @classmethod
    def _convert_events(cls, events: List[Dict]) -> List[DrawCallInfo]:
        """
        将 XML events 转换为 DrawCallInfo 列表。
        
        仅保留 Draw Call 类型的事件，跳过其他 API 调用。
        """
        draw_calls = []
        
        for event in events:
            event_type = event.get('name', '')
            
            # 跳过非 Draw Call
            if not cls._is_draw_call(event_type):
                continue
            
            params_raw = event.get('params', {})
            pipeline = event.get('pipelineState', {})
            
            # 将 params 列表转换为字典（如果需要）
            params = cls._normalize_params(params_raw)
            
            # 提取基础信息
            draw_call = DrawCallInfo(
                event_id=event.get('eventId', 0),
                type=event_type,
            )
            
            # 提取顶点/索引数量（优先从事件顶层字段获取，回退到 params）
            draw_call.index_count = cls._safe_int(
                event.get('indexCount') or params.get('IndexCount') or params.get('indexCount', 0)
            )
            draw_call.vertex_count = cls._safe_int(
                event.get('vertexCount') or params.get('VertexCount') or params.get('vertexCount', 0)
            )
            draw_call.instance_count = cls._safe_int(
                event.get('instanceCount') or params.get('InstanceCount') or params.get('instanceCount', 1)
            ) or 1
            
            # 如果没有 vertex_count，尝试从 index_count 推断
            if draw_call.vertex_count == 0 and draw_call.index_count > 0:
                draw_call.vertex_count = draw_call.index_count
            
            # 提取 Shader ID
            shaders = pipeline.get('shaders', {})
            draw_call.vs_id = cls._extract_shader_id(shaders, 'VS', 'Vertex')
            draw_call.ps_id = cls._extract_shader_id(shaders, 'PS', 'Pixel', 'Fragment')
            
            # 提取 Render Target IDs
            draw_call.rt_ids = cls._extract_render_target_ids(pipeline)
            
            # 提取 Depth Stencil ID
            draw_call.ds_id = cls._extract_depth_stencil_id(pipeline)
            
            # 提取渲染状态
            draw_call.blend_enabled = cls._extract_blend_enabled(pipeline)
            draw_call.depth_write = cls._extract_depth_write(pipeline)
            draw_call.depth_test = cls._extract_depth_test(pipeline)
            draw_call.cull_mode = cls._extract_cull_mode(pipeline)
            draw_call.fill_mode = cls._extract_fill_mode(pipeline)
            
            draw_calls.append(draw_call)
        
        return draw_calls
    
    @classmethod
    def _convert_textures(cls, textures: List[Dict]) -> List[TextureInfo]:
        """
        将 XML textures 转换为 TextureInfo 列表。
        """
        result = []
        
        for tex in textures:
            info = TextureInfo(
                resource_id=str(tex.get('resourceId', '')),
                name=tex.get('name', ''),
                width=cls._safe_int(tex.get('width', 0)),
                height=cls._safe_int(tex.get('height', 0)),
                depth=cls._safe_int(tex.get('depth', 1)),
                array_size=cls._safe_int(tex.get('arraySize', 1)),
                mip_levels=cls._safe_int(tex.get('mipLevels', 1)),
                format=tex.get('format', ''),
                sample_count=cls._safe_int(tex.get('sampleCount', 1)),
            )
            
            # 判断格式类别
            info.format_category = cls._categorize_texture_format(info.format)
            
            # 估算内存大小
            if info.memory_size == 0:
                info.memory_size = cls._estimate_texture_memory(info)
            
            result.append(info)
        
        return result
    
    @classmethod
    def _convert_buffers(cls, buffers: List[Dict]) -> List[BufferInfo]:
        """
        将 XML buffers 转换为 BufferInfo 列表。
        """
        result = []
        
        for buf in buffers:
            info = BufferInfo(
                resource_id=str(buf.get('resourceId', '')),
                name=buf.get('name', ''),
                size=cls._safe_int(buf.get('size', 0)),
                stride=cls._safe_int(buf.get('stride', 0)),
            )
            
            # 从 usage 字段推断属性
            usage = buf.get('usage', [])
            if isinstance(usage, str):
                usage = [usage]
            info.usage = usage
            
            info.is_constant_buffer = 'ConstantBuffer' in usage or 'UniformBuffer' in usage
            info.is_dynamic = 'Dynamic' in usage or buf.get('cpuAccess', '') == 'Write'
            
            result.append(info)
        
        return result
    
    @classmethod
    def _convert_shaders(
        cls,
        shaders: List[Dict],
        draw_calls: List[DrawCallInfo]
    ) -> List[ShaderInfo]:
        """
        将 JSON shaders 转换为 ShaderInfo 列表。
        
        同时计算每个 Shader 的使用次数 (bind_count)。
        
        TASK-201: Shader 数据桥接完善
        """
        result = []
        
        # 统计各 Shader ID 使用次数
        shader_usage: Dict[str, int] = {}
        for dc in draw_calls:
            for shader_id in (dc.vs_id, dc.ps_id):
                if shader_id:
                    shader_usage[shader_id] = shader_usage.get(shader_id, 0) + 1
        
        for shader in shaders:
            # 兼容两种格式：
            # 1. 新格式 (bindings.json): resourceId, type, stats, cycles
            # 2. XML解析格式 (parse_rdc_xml.py): id, stage, type, name
            res_id = str(shader.get('resourceId', '') or shader.get('id', ''))
            shader_type = shader.get('type', '') or shader.get('stage', '')  # VS, PS, CS, PIPELINE etc.
            stats = shader.get('stats', {})
            cycles = shader.get('cycles', {})
            
            # 构建 ShaderInfo (仅填充 Optimizer 需要的字段)
            info = ShaderInfo(
                resource_id=res_id,
                type=shader_type,
                name=shader.get('name', ''),
                hash=shader.get('hash', ''),
                bind_count=shader_usage.get(res_id, 0),
            )
            
            # 添加 Mali Offline Compiler 风格的属性 (供 OptimizationAdvisor 使用)
            # 这些属性在 ShaderInfo 基类中不存在，所以我们使用动态属性
            # 但 OptimizationAdvisor 期望 ShaderAnalysisContext，所以我们创建兼容对象
            info._analysis_context = {
                'name': info.name,
                'shader_type': 'vertex' if shader_type in ('VS', 'Vertex') else (
                    'compute' if shader_type in ('CS', 'Compute') else 'fragment'
                ),
                'bound': shader.get('bound', 'Unknown'),
                'cycles': {
                    'arithmetic': cycles.get('arithmetic', 0),
                    'texture': cycles.get('texture', 0),
                    'load_store': cycles.get('loadStore', 0),
                    'varying': cycles.get('varying', 0),
                    'total': cycles.get('total', 0),
                },
                'registers': {
                    'work': stats.get('tempRegisters', 0),
                },
                'has_loops': stats.get('hasLoops', False),
                'has_branching': stats.get('hasBranching', False),
                'has_discard': stats.get('hasDiscard', False),
                'has_derivatives': stats.get('hasDerivatives', False),
                'loop_depth': stats.get('loopDepth', 0),
                'branch_depth': stats.get('branchDepth', 0),
                'texture_count': stats.get('textureCount', 0),
                'sampler_count': stats.get('samplerCount', 0),
                'cbuffer_count': stats.get('cbufferCount', 0),
                'temp_registers': stats.get('tempRegisters', 0),
                'usage_count': shader_usage.get(res_id, 1),
            }
            
            result.append(info)
        
        return result
    
    @classmethod
    def _convert_statistics(
        cls,
        statistics: Dict[str, Any],
        draw_calls: List[DrawCallInfo],
        textures: List[TextureInfo],
        buffers: List[BufferInfo]
    ) -> FrameSummary:
        """
        生成帧摘要统计。
        
        优先使用 XML statistics，不足时从转换后的数据计算。
        """
        summary = FrameSummary()
        
        # 从 statistics 获取基础数据
        summary.draw_call_count = cls._safe_int(statistics.get('totalDrawCalls', len(draw_calls)))
        summary.dispatch_count = cls._safe_int(statistics.get('dispatchCalls', 0))
        
        # 从 draw_calls 计算顶点和图元
        summary.vertex_count = sum(dc.vertex_count for dc in draw_calls)
        summary.primitive_count = summary.vertex_count // 3  # 假设三角形
        
        # 资源计数
        summary.texture_count = len(textures)
        summary.buffer_count = len(buffers)
        
        # 内存统计
        summary.total_texture_memory = sum(t.memory_size for t in textures)
        summary.total_buffer_memory = sum(b.size for b in buffers)
        
        # 状态变更统计 (需要遍历 draw_calls)
        summary.shader_changes = cls._count_state_changes(draw_calls, 'vs_id', 'ps_id')
        summary.rt_switches = cls._count_state_changes(draw_calls, 'rt_ids')
        summary.blend_state_changes = cls._count_state_changes(draw_calls, 'blend_enabled')
        summary.depth_state_changes = cls._count_state_changes(draw_calls, 'depth_write', 'depth_test')
        
        # 从 statistics 覆盖（如果有更准确的数据）
        if 'shaderChanges' in statistics:
            summary.shader_changes = cls._safe_int(statistics['shaderChanges'])
        if 'renderTargetSwitches' in statistics:
            summary.rt_switches = cls._safe_int(statistics['renderTargetSwitches'])
        
        return summary
    
    @classmethod
    def _create_parsed_data(cls, xml_data: Dict, file_path: str) -> ParsedData:
        """
        创建 ParsedData 对象，保留原始数据用于回溯。
        """
        parsed = ParsedData(
            api=xml_data.get('apiType', ''),
            file_path=file_path,
            total_events=len(xml_data.get('events', [])),
        )
        
        # 保留原始 draws (过滤后)
        parsed.draws = [
            e for e in xml_data.get('events', [])
            if cls._is_draw_call(e.get('name', ''))
        ]
        
        # 保留原始 dispatches
        parsed.dispatches = [
            e for e in xml_data.get('events', [])
            if cls._is_dispatch(e.get('name', ''))
        ]
        
        # 保留纹理和缓冲区原始数据
        parsed.textures = xml_data.get('textures', [])
        parsed.buffers = xml_data.get('buffers', [])
        
        return parsed
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    @classmethod
    def _normalize_params(cls, params_raw: Any) -> Dict[str, Any]:
        """
        将 params 列表转换为字典格式。
        
        XML 解析器可能返回两种格式:
        1. dict 格式: {'IndexCount': 100, ...}
        2. list 格式: [{'name': 'indexCount', 'value': '100'}, ...]
        
        此方法统一转换为 dict 格式。
        """
        if isinstance(params_raw, dict):
            return params_raw
        
        if isinstance(params_raw, list):
            result = {}
            for param in params_raw:
                if isinstance(param, dict) and 'name' in param:
                    name = param['name']
                    value = param.get('value', '')
                    # 尝试转换为数字
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            pass
                    result[name] = value
            return result
        
        return {}
    
    @classmethod
    def _is_draw_call(cls, event_type: str) -> bool:
        """判断事件类型是否为 Draw Call"""
        # 精确匹配
        if event_type in cls.DRAW_CALL_TYPES:
            return True
        # 模糊匹配 (处理带后缀的变体)
        for known in cls.DRAW_CALL_TYPES:
            if event_type.startswith(known):
                return True
        return False
    
    @classmethod
    def _is_dispatch(cls, event_type: str) -> bool:
        """判断事件类型是否为 Dispatch"""
        if event_type in cls.DISPATCH_TYPES:
            return True
        for known in cls.DISPATCH_TYPES:
            if event_type.startswith(known):
                return True
        return False
    
    @classmethod
    def _safe_int(cls, value: Any) -> int:
        """安全转换为整数"""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0
    
    @classmethod
    def _extract_shader_id(cls, shaders: Dict, *keys: str) -> str:
        """从 shaders dict 提取指定类型的 Shader ID"""
        for key in keys:
            if key in shaders:
                shader = shaders[key]
                if isinstance(shader, dict):
                    return str(shader.get('resourceId', ''))
                return str(shader)
        return ""
    
    @classmethod
    def _extract_render_target_ids(cls, pipeline: Dict) -> List[str]:
        """提取 Render Target IDs"""
        rt_ids = []
        
        # D3D11/D3D12 格式
        output = pipeline.get('outputMerger', {})
        render_targets = output.get('renderTargets', [])
        
        for rt in render_targets:
            if isinstance(rt, dict):
                res_id = rt.get('resourceId', '')
                if res_id:
                    rt_ids.append(str(res_id))
            elif rt:
                rt_ids.append(str(rt))
        
        # Vulkan 格式 (framebuffer)
        if not rt_ids:
            fb = pipeline.get('framebuffer', {})
            attachments = fb.get('colorAttachments', [])
            for att in attachments:
                if isinstance(att, dict):
                    res_id = att.get('resourceId', att.get('imageResourceId', ''))
                    if res_id:
                        rt_ids.append(str(res_id))
        
        return rt_ids
    
    @classmethod
    def _extract_depth_stencil_id(cls, pipeline: Dict) -> str:
        """提取 Depth Stencil ID"""
        # D3D11/D3D12
        output = pipeline.get('outputMerger', {})
        ds = output.get('depthStencilView', output.get('depthTarget', {}))
        if isinstance(ds, dict) and ds:  # 非空 dict
            res_id = ds.get('resourceId', '')
            if res_id:
                return str(res_id)
        
        # Vulkan
        fb = pipeline.get('framebuffer', {})
        ds_att = fb.get('depthAttachment', {})
        if isinstance(ds_att, dict) and ds_att:  # 非空 dict
            res_id = ds_att.get('resourceId', ds_att.get('imageResourceId', ''))
            if res_id:
                return str(res_id)
        
        return ""
    
    @classmethod
    def _extract_blend_enabled(cls, pipeline: Dict) -> bool:
        """提取混合是否启用"""
        # D3D11/D3D12
        output = pipeline.get('outputMerger', {})
        blend = output.get('blendState', {})
        if isinstance(blend, dict):
            # 检查任意 RT 的混合状态
            targets = blend.get('renderTargets', blend.get('blends', []))
            for t in targets:
                if isinstance(t, dict) and t.get('blendEnable', False):
                    return True
        
        # Vulkan
        cb = pipeline.get('colorBlend', {})
        attachments = cb.get('attachments', [])
        for att in attachments:
            if isinstance(att, dict) and att.get('blendEnable', False):
                return True
        
        return False
    
    @classmethod
    def _extract_depth_write(cls, pipeline: Dict) -> bool:
        """提取深度写入是否启用"""
        # D3D11/D3D12
        output = pipeline.get('outputMerger', {})
        ds = output.get('depthStencilState', {})
        if isinstance(ds, dict) and ds:  # 非空 dict 才处理
            return ds.get('depthWriteMask', True) not in (False, 0, 'Zero')
        
        # Vulkan
        ds_vk = pipeline.get('depthStencil', {})
        if isinstance(ds_vk, dict) and ds_vk:  # 非空 dict 才处理
            return ds_vk.get('depthWriteEnable', True)
        
        return True  # 默认启用
    
    @classmethod
    def _extract_depth_test(cls, pipeline: Dict) -> bool:
        """提取深度测试是否启用"""
        # D3D11/D3D12
        output = pipeline.get('outputMerger', {})
        ds = output.get('depthStencilState', {})
        if isinstance(ds, dict) and ds:  # 非空 dict 才处理
            return ds.get('depthEnable', True)
        
        # Vulkan
        ds_vk = pipeline.get('depthStencil', {})
        if isinstance(ds_vk, dict) and ds_vk:  # 非空 dict 才处理
            return ds_vk.get('depthTestEnable', True)
        
        return True  # 默认启用
    
    @classmethod
    def _extract_cull_mode(cls, pipeline: Dict) -> str:
        """提取剔除模式"""
        # D3D11/D3D12
        rs = pipeline.get('rasterizerState', pipeline.get('rasterizer', {}))
        if isinstance(rs, dict):
            mode = rs.get('cullMode', 'back')
            if isinstance(mode, str):
                return mode.lower()
        
        return "back"
    
    @classmethod
    def _extract_fill_mode(cls, pipeline: Dict) -> str:
        """提取填充模式"""
        rs = pipeline.get('rasterizerState', pipeline.get('rasterizer', {}))
        if isinstance(rs, dict):
            mode = rs.get('fillMode', 'solid')
            if isinstance(mode, str):
                return mode.lower()
        
        return "solid"
    
    @classmethod
    def _categorize_texture_format(cls, format_str: str) -> str:
        """判断纹理格式类别"""
        fmt = format_str.upper()
        
        # 压缩格式
        compressed_prefixes = ('BC', 'DXT', 'ETC', 'ASTC', 'PVRTC')
        if any(fmt.startswith(p) for p in compressed_prefixes):
            return "compressed"
        
        # 深度格式
        if 'DEPTH' in fmt or 'D24' in fmt or 'D32' in fmt or 'D16' in fmt:
            return "depth"
        
        return "uncompressed"
    
    @classmethod
    def _estimate_texture_memory(cls, tex: TextureInfo) -> int:
        """估算纹理内存大小 (字节)"""
        # 简化估算：width * height * bpp * array * mips
        bpp = 4  # 默认 4 bytes per pixel (RGBA8)
        
        if tex.format_category == "compressed":
            bpp = 1  # 压缩格式约 0.5-1 byte per pixel
        elif 'R32G32B32A32' in tex.format:
            bpp = 16
        elif 'R16G16B16A16' in tex.format:
            bpp = 8
        elif 'R32G32' in tex.format:
            bpp = 8
        elif 'DEPTH' in tex.format.upper():
            bpp = 4
        
        base_size = tex.width * tex.height * tex.depth * bpp
        
        # Mipmap 系数 (约 1.33x)
        if tex.mip_levels > 1:
            base_size = int(base_size * 1.33)
        
        return base_size * tex.array_size
    
    @classmethod
    def _count_state_changes(cls, draw_calls: List[DrawCallInfo], *attrs: str) -> int:
        """统计状态变更次数"""
        if not draw_calls:
            return 0
        
        changes = 0
        prev_values = None
        
        for dc in draw_calls:
            curr_values = tuple(getattr(dc, attr, None) for attr in attrs)
            if prev_values is not None and curr_values != prev_values:
                changes += 1
            prev_values = curr_values
        
        return changes
