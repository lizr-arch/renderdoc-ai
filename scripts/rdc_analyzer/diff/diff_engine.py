"""
DiffEngine - RDC 差异对比引擎
============================

核心对比逻辑，输入两个 RDC 解析结果，输出结构化差异报告。

TASK-010 实现
Created: 2026-01-20
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import asdict

from .diff_types import (
    DiffResult,
    SummaryDiff,
    MetricDiff,
    TextureDiff,
    ShaderDiff,
    BufferDiff,
    DrawCallDiff,
    StateDiff,
    DiffStatus,
)


class DiffEngine:
    """
    RDC 差异对比引擎
    
    支持两种输入格式:
    1. 原始 JSON dict (parse_rdc_xml 输出)
    2. AnalysisContext 对象 (XMLToContextBridge 输出)
    
    使用示例:
        engine = DiffEngine()
        result = engine.compare(baseline_data, target_data)
        print(result.to_json())
    """
    
    def __init__(self, ignore_order: bool = False):
        """
        初始化对比引擎
        
        Args:
            ignore_order: 是否忽略 Draw Call 顺序差异
        """
        self.ignore_order = ignore_order
    
    def compare(
        self,
        baseline: Dict[str, Any],
        target: Dict[str, Any],
        baseline_file: str = "",
        target_file: str = ""
    ) -> DiffResult:
        """
        执行差异对比
        
        Args:
            baseline: 基准数据 (parse_rdc_xml 输出)
            target: 目标数据 (parse_rdc_xml 输出)
            baseline_file: 基准文件路径 (可选)
            target_file: 目标文件路径 (可选)
            
        Returns:
            DiffResult: 完整差异报告
        """
        result = DiffResult(
            baseline_file=baseline_file or baseline.get('file_path', 'baseline'),
            target_file=target_file or target.get('file_path', 'target'),
            api_type=baseline.get('apiType', target.get('apiType', 'Unknown')),
        )
        
        # 1. 对比帧摘要统计
        result.summary = self._compare_summary(baseline, target)
        
        # 2. 对比纹理
        result.texture_diffs = self._compare_textures(
            baseline.get('textures', []),
            target.get('textures', [])
        )
        
        # 3. 对比 Shader
        result.shader_diffs = self._compare_shaders(
            baseline.get('shaders', []),
            target.get('shaders', [])
        )
        
        # 4. 对比 Buffer
        result.buffer_diffs = self._compare_buffers(
            baseline.get('buffers', []),
            target.get('buffers', [])
        )
        
        # 5. 对比 Draw Call
        result.draw_call_diffs = self._compare_draw_calls(
            baseline.get('events', []),
            target.get('events', [])
        )
        
        # 6. 对比渲染状态 (从 events 的 pipelineState 提取)
        result.state_diffs = self._compare_states(
            baseline.get('events', []),
            target.get('events', [])
        )
        
        return result
    
    def _compare_summary(
        self,
        baseline: Dict[str, Any],
        target: Dict[str, Any]
    ) -> SummaryDiff:
        """对比帧级统计摘要"""
        summary = SummaryDiff()
        
        # 从 statistics 或 events 计算
        b_stats = baseline.get('statistics', {})
        t_stats = target.get('statistics', {})
        b_events = baseline.get('events', [])
        t_events = target.get('events', [])
        
        # Draw Call 数量
        b_draws = b_stats.get('totalDrawCalls', self._count_draws(b_events))
        t_draws = t_stats.get('totalDrawCalls', self._count_draws(t_events))
        summary.draw_calls = MetricDiff("draw_calls", b_draws, t_draws)
        
        # Dispatch 数量
        b_dispatches = b_stats.get('dispatchCalls', self._count_dispatches(b_events))
        t_dispatches = t_stats.get('dispatchCalls', self._count_dispatches(t_events))
        summary.dispatches = MetricDiff("dispatches", b_dispatches, t_dispatches)
        
        # 三角形数量
        b_triangles = b_stats.get('totalTriangles', self._count_triangles(b_events))
        t_triangles = t_stats.get('totalTriangles', self._count_triangles(t_events))
        summary.triangles = MetricDiff("triangles", b_triangles, t_triangles)
        
        # 顶点数量
        b_vertices = b_stats.get('totalVertices', self._count_vertices(b_events))
        t_vertices = t_stats.get('totalVertices', self._count_vertices(t_events))
        summary.vertices = MetricDiff("vertices", b_vertices, t_vertices)
        
        # 纹理数量和内存
        b_textures = baseline.get('textures', [])
        t_textures = target.get('textures', [])
        summary.texture_count = MetricDiff("texture_count", len(b_textures), len(t_textures))
        summary.texture_memory = MetricDiff(
            "texture_memory",
            self._sum_texture_memory(b_textures),
            self._sum_texture_memory(t_textures)
        )
        
        # Buffer 数量和内存
        b_buffers = baseline.get('buffers', [])
        t_buffers = target.get('buffers', [])
        summary.buffer_count = MetricDiff("buffer_count", len(b_buffers), len(t_buffers))
        summary.buffer_memory = MetricDiff(
            "buffer_memory",
            self._sum_buffer_memory(b_buffers),
            self._sum_buffer_memory(t_buffers)
        )
        
        # Shader 数量
        b_shaders = baseline.get('shaders', [])
        t_shaders = target.get('shaders', [])
        summary.shader_count = MetricDiff("shader_count", len(b_shaders), len(t_shaders))
        
        # 状态变更统计
        summary.shader_changes = MetricDiff(
            "shader_changes",
            b_stats.get('shaderChanges', 0),
            t_stats.get('shaderChanges', 0)
        )
        summary.rt_switches = MetricDiff(
            "rt_switches",
            b_stats.get('renderTargetSwitches', 0),
            t_stats.get('renderTargetSwitches', 0)
        )
        
        return summary
    
    def _compare_textures(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[TextureDiff]:
        """对比纹理列表"""
        diffs = []
        
        # 建立索引 (resourceId -> texture)
        b_map = {str(t.get('resourceId', '')): t for t in baseline}
        t_map = {str(t.get('resourceId', '')): t for t in target}
        
        b_ids = set(b_map.keys())
        t_ids = set(t_map.keys())
        
        # 新增的纹理
        for rid in (t_ids - b_ids):
            tex = t_map[rid]
            diff = TextureDiff(
                resource_id=rid,
                name=tex.get('name', ''),
                status=DiffStatus.ADDED,
                width=tex.get('width', 0),
                height=tex.get('height', 0),
                format=tex.get('format', ''),
                memory_size=self._get_texture_memory(tex),
            )
            diffs.append(diff)
        
        # 删除的纹理
        for rid in (b_ids - t_ids):
            tex = b_map[rid]
            diff = TextureDiff(
                resource_id=rid,
                name=tex.get('name', ''),
                status=DiffStatus.REMOVED,
                width=tex.get('width', 0),
                height=tex.get('height', 0),
                format=tex.get('format', ''),
                memory_size=self._get_texture_memory(tex),
            )
            diffs.append(diff)
        
        # 修改的纹理 (同 ID 但属性变化)
        for rid in (b_ids & t_ids):
            b_tex = b_map[rid]
            t_tex = t_map[rid]
            
            changes = {}
            for field in ['width', 'height', 'format', 'mipLevels', 'arraySize']:
                b_val = b_tex.get(field)
                t_val = t_tex.get(field)
                if b_val != t_val:
                    changes[field] = (b_val, t_val)
            
            if changes:
                diff = TextureDiff(
                    resource_id=rid,
                    name=t_tex.get('name', ''),
                    status=DiffStatus.MODIFIED,
                    width=t_tex.get('width', 0),
                    height=t_tex.get('height', 0),
                    format=t_tex.get('format', ''),
                    memory_size=self._get_texture_memory(t_tex),
                    changes=changes,
                )
                diffs.append(diff)
        
        return diffs
    
    def _compare_shaders(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[ShaderDiff]:
        """对比 Shader 列表"""
        diffs = []
        
        # 建立索引 (resourceId -> shader)
        b_map = {str(s.get('resourceId', '')): s for s in baseline}
        t_map = {str(s.get('resourceId', '')): s for s in target}
        
        b_ids = set(b_map.keys())
        t_ids = set(t_map.keys())
        
        # 新增
        for rid in (t_ids - b_ids):
            shader = t_map[rid]
            diff = ShaderDiff(
                resource_id=rid,
                name=shader.get('name', ''),
                status=DiffStatus.ADDED,
                shader_type=shader.get('type', ''),
                hash=shader.get('hash', ''),
            )
            diffs.append(diff)
        
        # 删除
        for rid in (b_ids - t_ids):
            shader = b_map[rid]
            diff = ShaderDiff(
                resource_id=rid,
                name=shader.get('name', ''),
                status=DiffStatus.REMOVED,
                shader_type=shader.get('type', ''),
                hash=shader.get('hash', ''),
            )
            diffs.append(diff)
        
        # 修改 (hash 变化表示内容变化)
        for rid in (b_ids & t_ids):
            b_shader = b_map[rid]
            t_shader = t_map[rid]
            
            b_hash = b_shader.get('hash', '')
            t_hash = t_shader.get('hash', '')
            
            if b_hash and t_hash and b_hash != t_hash:
                diff = ShaderDiff(
                    resource_id=rid,
                    name=t_shader.get('name', ''),
                    status=DiffStatus.MODIFIED,
                    shader_type=t_shader.get('type', ''),
                    hash=t_hash,
                    changes={'hash': (b_hash, t_hash)},
                )
                diffs.append(diff)
        
        return diffs
    
    def _compare_buffers(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[BufferDiff]:
        """对比 Buffer 列表"""
        diffs = []
        
        b_map = {str(b.get('resourceId', '')): b for b in baseline}
        t_map = {str(b.get('resourceId', '')): b for b in target}
        
        b_ids = set(b_map.keys())
        t_ids = set(t_map.keys())
        
        # 新增
        for rid in (t_ids - b_ids):
            buf = t_map[rid]
            diff = BufferDiff(
                resource_id=rid,
                name=buf.get('name', ''),
                status=DiffStatus.ADDED,
                size=buf.get('size', 0),
                usage=str(buf.get('usage', '')),
            )
            diffs.append(diff)
        
        # 删除
        for rid in (b_ids - t_ids):
            buf = b_map[rid]
            diff = BufferDiff(
                resource_id=rid,
                name=buf.get('name', ''),
                status=DiffStatus.REMOVED,
                size=buf.get('size', 0),
                usage=str(buf.get('usage', '')),
            )
            diffs.append(diff)
        
        # 修改
        for rid in (b_ids & t_ids):
            b_buf = b_map[rid]
            t_buf = t_map[rid]
            
            changes = {}
            if b_buf.get('size') != t_buf.get('size'):
                changes['size'] = (b_buf.get('size'), t_buf.get('size'))
            
            if changes:
                diff = BufferDiff(
                    resource_id=rid,
                    name=t_buf.get('name', ''),
                    status=DiffStatus.MODIFIED,
                    size=t_buf.get('size', 0),
                    usage=str(t_buf.get('usage', '')),
                    changes=changes,
                )
                diffs.append(diff)
        
        return diffs
    
    def _compare_draw_calls(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[DrawCallDiff]:
        """
        对比 Draw Call 列表
        
        策略:
        1. 如果 ignore_order=False，按 event_id 顺序对比
        2. 如果 ignore_order=True，按 Draw Call 特征匹配
        """
        diffs = []
        
        # 过滤出 Draw Call
        b_draws = [e for e in baseline if self._is_draw_call(e)]
        t_draws = [e for e in target if self._is_draw_call(e)]
        
        if self.ignore_order:
            # 按特征匹配 (shader + RT + vertex_count)
            diffs = self._compare_draws_by_signature(b_draws, t_draws)
        else:
            # 按顺序对比
            diffs = self._compare_draws_by_order(b_draws, t_draws)
        
        return diffs
    
    def _compare_draws_by_order(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[DrawCallDiff]:
        """按顺序对比 Draw Call"""
        diffs = []
        
        max_len = max(len(baseline), len(target))
        
        for i in range(max_len):
            b_draw = baseline[i] if i < len(baseline) else None
            t_draw = target[i] if i < len(target) else None
            
            if b_draw is None:
                # 新增
                diff = DrawCallDiff(
                    event_id=t_draw.get('eventId', 0),
                    status=DiffStatus.ADDED,
                    draw_type=t_draw.get('name', ''),
                    index_count=t_draw.get('indexCount', 0),
                    vertex_count=t_draw.get('vertexCount', 0),
                )
                diffs.append(diff)
            elif t_draw is None:
                # 删除
                diff = DrawCallDiff(
                    event_id=b_draw.get('eventId', 0),
                    status=DiffStatus.REMOVED,
                    draw_type=b_draw.get('name', ''),
                    index_count=b_draw.get('indexCount', 0),
                    vertex_count=b_draw.get('vertexCount', 0),
                )
                diffs.append(diff)
            else:
                # 对比变化
                changes = self._diff_draw_call(b_draw, t_draw)
                if changes:
                    diff = DrawCallDiff(
                        event_id=t_draw.get('eventId', 0),
                        status=DiffStatus.MODIFIED,
                        matched_event_id=b_draw.get('eventId', 0),
                        draw_type=t_draw.get('name', ''),
                        index_count=t_draw.get('indexCount', 0),
                        vertex_count=t_draw.get('vertexCount', 0),
                        changes=changes,
                    )
                    diffs.append(diff)
        
        return diffs
    
    def _compare_draws_by_signature(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[DrawCallDiff]:
        """按特征签名匹配 Draw Call"""
        diffs = []
        
        # 生成签名 -> draw 映射
        def get_signature(draw: Dict) -> str:
            ps = draw.get('pipelineState', {})
            shaders = ps.get('shaders', {})
            vs = shaders.get('VS', shaders.get('Vertex', {}))
            ps_shader = shaders.get('PS', shaders.get('Pixel', shaders.get('Fragment', {})))
            
            vs_id = vs.get('resourceId', '') if isinstance(vs, dict) else str(vs)
            ps_id = ps_shader.get('resourceId', '') if isinstance(ps_shader, dict) else str(ps_shader)
            
            return f"{vs_id}|{ps_id}|{draw.get('indexCount', 0)}"
        
        b_by_sig: Dict[str, List[Dict]] = {}
        for d in baseline:
            sig = get_signature(d)
            b_by_sig.setdefault(sig, []).append(d)
        
        t_by_sig: Dict[str, List[Dict]] = {}
        for d in target:
            sig = get_signature(d)
            t_by_sig.setdefault(sig, []).append(d)
        
        matched_b_ids: Set[int] = set()
        matched_t_ids: Set[int] = set()
        
        # 匹配相同签名的 Draw
        for sig, t_list in t_by_sig.items():
            b_list = b_by_sig.get(sig, [])
            
            for i, t_draw in enumerate(t_list):
                if i < len(b_list):
                    # 匹配成功
                    b_draw = b_list[i]
                    matched_b_ids.add(b_draw.get('eventId', 0))
                    matched_t_ids.add(t_draw.get('eventId', 0))
                    
                    changes = self._diff_draw_call(b_draw, t_draw)
                    if changes:
                        diff = DrawCallDiff(
                            event_id=t_draw.get('eventId', 0),
                            status=DiffStatus.MODIFIED,
                            matched_event_id=b_draw.get('eventId', 0),
                            changes=changes,
                        )
                        diffs.append(diff)
                else:
                    # Target 新增
                    diff = DrawCallDiff(
                        event_id=t_draw.get('eventId', 0),
                        status=DiffStatus.ADDED,
                        draw_type=t_draw.get('name', ''),
                    )
                    diffs.append(diff)
        
        # Baseline 中未匹配的视为删除
        for b_draw in baseline:
            if b_draw.get('eventId', 0) not in matched_b_ids:
                diff = DrawCallDiff(
                    event_id=b_draw.get('eventId', 0),
                    status=DiffStatus.REMOVED,
                    draw_type=b_draw.get('name', ''),
                )
                diffs.append(diff)
        
        return diffs
    
    def _diff_draw_call(
        self,
        baseline: Dict,
        target: Dict
    ) -> Dict[str, Tuple[Any, Any]]:
        """对比单个 Draw Call 的详细差异"""
        changes = {}
        
        # 基础字段
        fields = ['name', 'indexCount', 'vertexCount', 'instanceCount']
        for f in fields:
            b_val = baseline.get(f)
            t_val = target.get(f)
            if b_val != t_val:
                changes[f] = (b_val, t_val)
        
        # Pipeline State 对比
        b_ps = baseline.get('pipelineState', {})
        t_ps = target.get('pipelineState', {})
        
        # Shader 对比
        b_shaders = b_ps.get('shaders', {})
        t_shaders = t_ps.get('shaders', {})
        for stage in ['VS', 'PS', 'GS', 'HS', 'DS', 'CS', 'Vertex', 'Pixel', 'Fragment']:
            b_shader = b_shaders.get(stage, {})
            t_shader = t_shaders.get(stage, {})
            b_id = b_shader.get('resourceId', '') if isinstance(b_shader, dict) else str(b_shader)
            t_id = t_shader.get('resourceId', '') if isinstance(t_shader, dict) else str(t_shader)
            if b_id != t_id and (b_id or t_id):
                changes[f'shader_{stage}'] = (b_id, t_id)
        
        # Blend State
        b_blend = self._extract_blend_enabled(b_ps)
        t_blend = self._extract_blend_enabled(t_ps)
        if b_blend != t_blend:
            changes['blend_enabled'] = (b_blend, t_blend)
        
        # Depth State
        b_depth = self._extract_depth_test(b_ps)
        t_depth = self._extract_depth_test(t_ps)
        if b_depth != t_depth:
            changes['depth_test'] = (b_depth, t_depth)
        
        return changes
    
    def _compare_states(
        self,
        baseline: List[Dict],
        target: List[Dict]
    ) -> List[StateDiff]:
        """对比渲染状态设置"""
        # 简化实现：仅在 Draw Call 数量相等时进行逐一对比
        diffs = []
        
        b_draws = [e for e in baseline if self._is_draw_call(e)]
        t_draws = [e for e in target if self._is_draw_call(e)]
        
        for i, (b, t) in enumerate(zip(b_draws, t_draws)):
            b_ps = b.get('pipelineState', {})
            t_ps = t.get('pipelineState', {})
            
            # Viewport 差异
            b_vp = b_ps.get('viewport') or {}
            t_vp = t_ps.get('viewport') or {}
            vp_changes = {}
            for f in ['width', 'height', 'x', 'y']:
                if b_vp.get(f) != t_vp.get(f):
                    vp_changes[f] = (b_vp.get(f), t_vp.get(f))
            if vp_changes:
                diffs.append(StateDiff(
                    state_type='viewport',
                    event_id=t.get('eventId', i),
                    changes=vp_changes,
                ))
            
            # Blend State 差异
            b_blend = b_ps.get('blendState', b_ps.get('outputMerger', {}).get('blendState', {}))
            t_blend = t_ps.get('blendState', t_ps.get('outputMerger', {}).get('blendState', {}))
            if b_blend != t_blend:
                diffs.append(StateDiff(
                    state_type='blend',
                    event_id=t.get('eventId', i),
                    changes={'blendState': (str(b_blend)[:100], str(t_blend)[:100])},
                ))
        
        return diffs
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _is_draw_call(self, event: Dict) -> bool:
        """判断是否为 Draw Call"""
        name = event.get('name', '')
        draw_keywords = ['Draw', 'vkCmdDraw', 'glDraw']
        return any(kw in name for kw in draw_keywords)
    
    def _is_dispatch(self, event: Dict) -> bool:
        """判断是否为 Dispatch"""
        name = event.get('name', '')
        return 'Dispatch' in name or 'vkCmdDispatch' in name
    
    def _count_draws(self, events: List[Dict]) -> int:
        """统计 Draw Call 数量"""
        return sum(1 for e in events if self._is_draw_call(e))
    
    def _count_dispatches(self, events: List[Dict]) -> int:
        """统计 Dispatch 数量"""
        return sum(1 for e in events if self._is_dispatch(e))
    
    def _count_triangles(self, events: List[Dict]) -> int:
        """统计总三角形数"""
        total = 0
        for e in events:
            if self._is_draw_call(e):
                idx = e.get('indexCount', 0)
                vtx = e.get('vertexCount', 0)
                count = idx if idx > 0 else vtx
                instances = e.get('instanceCount', 1) or 1
                total += (count // 3) * instances
        return total
    
    def _count_vertices(self, events: List[Dict]) -> int:
        """统计总顶点数"""
        total = 0
        for e in events:
            if self._is_draw_call(e):
                idx = e.get('indexCount', 0)
                vtx = e.get('vertexCount', 0)
                count = idx if idx > 0 else vtx
                instances = e.get('instanceCount', 1) or 1
                total += count * instances
        return total
    
    def _sum_texture_memory(self, textures: List[Dict]) -> int:
        """计算纹理总内存"""
        return sum(self._get_texture_memory(t) for t in textures)
    
    def _get_texture_memory(self, tex: Dict) -> int:
        """获取单个纹理内存"""
        # 优先使用已计算的 memorySize
        if tex.get('memorySize'):
            return tex['memorySize']
        
        # 估算
        w = tex.get('width', 0)
        h = tex.get('height', 0)
        d = tex.get('depth', 1)
        mips = tex.get('mipLevels', 1)
        arrays = tex.get('arraySize', 1)
        
        bpp = 4  # 默认 RGBA8
        fmt = tex.get('format', '').upper()
        if 'BC' in fmt or 'DXT' in fmt:
            bpp = 1
        elif 'R32G32B32A32' in fmt:
            bpp = 16
        elif 'R16G16B16A16' in fmt:
            bpp = 8
        
        base = w * h * d * bpp
        if mips > 1:
            base = int(base * 1.33)
        
        return base * arrays
    
    def _sum_buffer_memory(self, buffers: List[Dict]) -> int:
        """计算 Buffer 总内存"""
        return sum(b.get('size', 0) for b in buffers)
    
    def _extract_blend_enabled(self, pipeline: Dict) -> bool:
        """从 pipeline state 提取混合状态"""
        output = pipeline.get('outputMerger', {})
        blend = output.get('blendState', {})
        if isinstance(blend, dict):
            targets = blend.get('renderTargets', blend.get('blends', []))
            for t in targets:
                if isinstance(t, dict) and t.get('blendEnable', False):
                    return True
        
        # Vulkan
        cb = pipeline.get('colorBlend', {})
        for att in cb.get('attachments', []):
            if isinstance(att, dict) and att.get('blendEnable', False):
                return True
        
        return False
    
    def _extract_depth_test(self, pipeline: Dict) -> bool:
        """从 pipeline state 提取深度测试状态"""
        output = pipeline.get('outputMerger', {})
        ds = output.get('depthStencilState', {})
        if isinstance(ds, dict) and ds:
            return ds.get('depthEnable', True)
        
        ds_vk = pipeline.get('depthStencil', {})
        if isinstance(ds_vk, dict) and ds_vk:
            return ds_vk.get('depthTestEnable', True)
        
        return True
