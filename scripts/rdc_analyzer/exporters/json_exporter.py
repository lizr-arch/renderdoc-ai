"""
JSON 导出器
===========

将 Draw Call 分析结果序列化为 JSON 格式
支持完整的调用链、依赖图和问题列表的导出
"""

import json
import gzip
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.pipeline_state import (
    DrawCallDetail,
    PipelineSnapshot,
    ShaderBindings,
    ResourceBinding,
    RenderTargetInfo,
    DepthStencilInfo,
    RasterizerStateInfo,
    SamplerInfo,
)
from ..analysis.call_analyzer import BindingIssue, IssueSeverity, IssueCategory
from ..analysis.resource_tracker import (
    ResourceDependency,
    ResourceLifetime,
    DependencyType,
)


@dataclass
class JSONExportConfig:
    """JSON 导出配置"""
    
    # 输出格式
    indent: int = 2
    ensure_ascii: bool = False
    sort_keys: bool = False
    
    # 压缩选项
    compress: bool = False  # 是否使用 gzip 压缩
    
    # 内容选项
    include_pipeline_state: bool = True  # 包含完整的管线状态
    include_shader_details: bool = True  # 包含着色器详细信息
    include_resource_bindings: bool = True  # 包含资源绑定
    include_dependencies: bool = True  # 包含依赖图
    include_issues: bool = True  # 包含检测到的问题
    include_statistics: bool = True  # 包含统计信息
    
    # 简化选项
    omit_empty_fields: bool = True  # 省略空字段
    omit_default_values: bool = False  # 省略默认值
    
    # 元数据
    include_metadata: bool = True  # 包含导出元数据


class EnhancedJSONEncoder(json.JSONEncoder):
    """增强的 JSON 编码器，支持 dataclass 和 Enum"""
    
    def default(self, obj: Any) -> Any:
        # 处理 Enum
        if isinstance(obj, Enum):
            return obj.value
        
        # 处理 dataclass
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        
        # 处理 Path
        if isinstance(obj, Path):
            return str(obj)
        
        # 处理 datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # 处理 bytes
        if isinstance(obj, bytes):
            return obj.hex()
        
        # 处理 set
        if isinstance(obj, set):
            return list(obj)
        
        return super().default(obj)


@dataclass
class AnalysisMetadata:
    """分析元数据"""
    export_time: str
    analyzer_version: str = "1.0.0"
    source_file: Optional[str] = None
    api_type: Optional[str] = None
    frame_number: Optional[int] = None
    total_events: int = 0
    total_draw_calls: int = 0


@dataclass 
class ExportedIssue:
    """导出的问题格式"""
    event_id: int
    rule_id: str
    severity: str
    category: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportedDependency:
    """导出的依赖格式"""
    source_event: int
    target_event: int
    resource_id: int
    resource_name: str
    dependency_type: str
    access_detail: str


@dataclass
class ExportedLifetime:
    """导出的资源生命周期"""
    resource_id: int
    resource_name: str
    resource_type: str
    first_access_event: int
    last_access_event: int
    read_count: int
    write_count: int
    hazards: List[str]
    is_written_never_read: bool


@dataclass
class ExportedDrawCall:
    """导出的 Draw Call 格式"""
    event_id: int
    name: str
    draw_type: str
    vertex_count: int
    instance_count: int
    index_offset: int
    vertex_offset: int
    
    # 可选的详细信息
    pipeline_state: Optional[Dict[str, Any]] = None
    issues: List[ExportedIssue] = field(default_factory=list)
    resource_reads: List[int] = field(default_factory=list)
    resource_writes: List[int] = field(default_factory=list)


@dataclass
class ExportedStatistics:
    """导出的统计信息"""
    total_draw_calls: int = 0
    total_issues: int = 0
    issues_by_severity: Dict[str, int] = field(default_factory=dict)
    issues_by_category: Dict[str, int] = field(default_factory=dict)
    issues_by_rule: Dict[str, int] = field(default_factory=dict)
    
    total_resources: int = 0
    total_dependencies: int = 0
    dependencies_by_type: Dict[str, int] = field(default_factory=dict)
    
    redundant_bindings: int = 0
    missing_resources: int = 0
    unused_resources: int = 0


@dataclass
class AnalysisExport:
    """完整的分析导出结构"""
    metadata: AnalysisMetadata
    draw_calls: List[ExportedDrawCall]
    issues: List[ExportedIssue]
    dependencies: List[ExportedDependency]
    resource_lifetimes: List[ExportedLifetime]
    statistics: ExportedStatistics


class JSONExporter:
    """JSON 导出器"""
    
    def __init__(self, config: Optional[JSONExportConfig] = None):
        self.config = config or JSONExportConfig()
    
    def export(
        self,
        draws: List[DrawCallDetail],
        issues: Optional[List[BindingIssue]] = None,
        dependencies: Optional[List[ResourceDependency]] = None,
        lifetimes: Optional[Dict[int, ResourceLifetime]] = None,
        source_file: Optional[str] = None,
        api_type: Optional[str] = None,
    ) -> str:
        """
        导出分析结果为 JSON 字符串
        
        Args:
            draws: Draw Call 详情列表
            issues: 检测到的问题列表
            dependencies: 资源依赖关系列表
            lifetimes: 资源生命周期字典
            source_file: 源 RDC 文件路径
            api_type: API 类型 (D3D11, Vulkan, etc.)
        
        Returns:
            JSON 格式的字符串
        """
        export_data = self._build_export_structure(
            draws, issues, dependencies, lifetimes, source_file, api_type
        )
        
        return json.dumps(
            asdict(export_data),
            cls=EnhancedJSONEncoder,
            indent=self.config.indent,
            ensure_ascii=self.config.ensure_ascii,
            sort_keys=self.config.sort_keys,
        )
    
    def export_to_file(
        self,
        output_path: Union[str, Path],
        draws: List[DrawCallDetail],
        issues: Optional[List[BindingIssue]] = None,
        dependencies: Optional[List[ResourceDependency]] = None,
        lifetimes: Optional[Dict[int, ResourceLifetime]] = None,
        source_file: Optional[str] = None,
        api_type: Optional[str] = None,
    ) -> Path:
        """
        导出分析结果到文件
        
        Args:
            output_path: 输出文件路径
            draws: Draw Call 详情列表
            issues: 检测到的问题列表
            dependencies: 资源依赖关系列表
            lifetimes: 资源生命周期字典
            source_file: 源 RDC 文件路径
            api_type: API 类型
        
        Returns:
            输出文件的 Path 对象
        """
        output_path = Path(output_path)
        json_content = self.export(
            draws, issues, dependencies, lifetimes, source_file, api_type
        )
        
        if self.config.compress or output_path.suffix == '.gz':
            with gzip.open(output_path, 'wt', encoding='utf-8') as f:
                f.write(json_content)
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
        
        return output_path
    
    def _build_export_structure(
        self,
        draws: List[DrawCallDetail],
        issues: Optional[List[BindingIssue]],
        dependencies: Optional[List[ResourceDependency]],
        lifetimes: Optional[Dict[int, ResourceLifetime]],
        source_file: Optional[str],
        api_type: Optional[str],
    ) -> AnalysisExport:
        """构建导出数据结构"""
        
        # 构建元数据
        metadata = AnalysisMetadata(
            export_time=datetime.now().isoformat(),
            source_file=source_file,
            api_type=api_type,
            total_events=len(draws),
            total_draw_calls=len([d for d in draws if d.draw_type]),
        )
        
        # 转换 Draw Calls
        exported_draws = [self._convert_draw_call(d) for d in draws]
        
        # 转换问题
        exported_issues = []
        if issues and self.config.include_issues:
            exported_issues = [self._convert_issue(i) for i in issues]
        
        # 转换依赖关系
        exported_deps = []
        if dependencies and self.config.include_dependencies:
            exported_deps = [self._convert_dependency(d) for d in dependencies]
        
        # 转换资源生命周期
        exported_lifetimes = []
        if lifetimes and self.config.include_dependencies:
            exported_lifetimes = [
                self._convert_lifetime(lt) for lt in lifetimes.values()
            ]
        
        # 计算统计信息
        statistics = self._compute_statistics(
            draws, exported_issues, exported_deps, lifetimes
        )
        
        return AnalysisExport(
            metadata=metadata,
            draw_calls=exported_draws,
            issues=exported_issues,
            dependencies=exported_deps,
            resource_lifetimes=exported_lifetimes,
            statistics=statistics,
        )
    
    def _convert_draw_call(self, draw: DrawCallDetail) -> ExportedDrawCall:
        """转换 DrawCallDetail 为导出格式"""
        # DrawCallDetail 使用 start_index 和 base_vertex 而不是 index_offset 和 vertex_offset
        exported = ExportedDrawCall(
            event_id=draw.event_id,
            name=draw.name,
            draw_type=draw.draw_type.name if isinstance(draw.draw_type, Enum) else str(draw.draw_type) if draw.draw_type else "",
            vertex_count=draw.vertex_count,
            instance_count=draw.instance_count,
            index_offset=draw.start_index,
            vertex_offset=draw.base_vertex,
        )
        
        # 添加管线状态 - 注意 DrawCallDetail 使用 pipeline 而不是 pipeline_state
        if self.config.include_pipeline_state and draw.pipeline:
            exported.pipeline_state = self._convert_pipeline_state(draw.pipeline)
        
        return exported
    
    def _convert_pipeline_state(self, state: PipelineSnapshot) -> Dict[str, Any]:
        """转换管线状态为字典"""
        result: Dict[str, Any] = {}
        
        # 输入装配 - PipelineSnapshot 的字段是展平的，不是嵌套的
        result['input_assembly'] = {
            'topology': state.primitive_topology.name if isinstance(state.primitive_topology, Enum) else str(state.primitive_topology),
            'vertex_buffers': [
                self._convert_resource_binding(vb) 
                for vb in (state.vertex_buffers or [])
            ],
        }
        if state.index_buffer:
            result['input_assembly']['index_buffer'] = self._convert_resource_binding(state.index_buffer)
        
        # 着色器绑定 - PipelineSnapshot 使用 vertex_shader, pixel_shader 等命名
        if self.config.include_shader_details:
            shader_map = {
                'vs': state.vertex_shader,
                'hs': state.hull_shader,
                'ds': state.domain_shader,
                'gs': state.geometry_shader,
                'ps': state.pixel_shader,
                'cs': state.compute_shader,
            }
            for stage_name, shader in shader_map.items():
                if shader and shader.resource_id:
                    result[f'{stage_name}_bindings'] = self._convert_shader_bindings_obj(shader)
        
        # 光栅化器状态 - 使用 rasterizer_state 字段
        if state.rasterizer_state:
            rs = state.rasterizer_state
            result['rasterizer'] = {
                'fill_mode': rs.fill_mode.name if isinstance(rs.fill_mode, Enum) else str(rs.fill_mode),
                'cull_mode': rs.cull_mode.name if isinstance(rs.cull_mode, Enum) else str(rs.cull_mode),
                'front_ccw': rs.front_ccw,
                'depth_bias': rs.depth_bias,
                'scissor_enabled': rs.scissor_enabled,
            }
            if state.viewports:
                result['rasterizer']['viewports'] = [vp.to_dict() for vp in state.viewports]
            if state.scissor_rects:
                result['rasterizer']['scissor_rects'] = [sr.to_dict() for sr in state.scissor_rects]
        
        # 输出合并器 - render_targets 和 depth_stencil 是顶级字段
        if self.config.include_resource_bindings:
            result['output_merger'] = {
                'render_targets': [
                    self._convert_render_target(rt)
                    for rt in (state.render_targets or [])
                ],
            }
            if state.depth_stencil:
                result['output_merger']['depth_stencil'] = self._convert_depth_stencil(state.depth_stencil)
            if state.blend_states:
                result['output_merger']['blend_states'] = [bs.to_dict() for bs in state.blend_states]
        
        return result
    
    def _convert_shader_bindings_obj(self, shader: ShaderBindings) -> Dict[str, Any]:
        """转换 ShaderBindings 对象为字典"""
        result: Dict[str, Any] = {
            'shader_resource_id': shader.resource_id,
            'shader_name': shader.name or "",
        }
        
        if self.config.include_resource_bindings:
            if shader.constant_buffers:
                result['constant_buffers'] = [
                    self._convert_resource_binding(cb)
                    for cb in shader.constant_buffers
                ]
            if shader.shader_resources:
                result['shader_resources'] = [
                    self._convert_resource_binding(sr)
                    for sr in shader.shader_resources
                ]
            if shader.samplers:
                result['samplers'] = [
                    self._convert_sampler(s)
                    for s in shader.samplers
                ]
            if shader.uavs:
                result['uavs'] = [
                    self._convert_resource_binding(u)
                    for u in shader.uavs
                ]
        
        return result
    
    def _convert_render_target(self, rt: RenderTargetInfo) -> Dict[str, Any]:
        """转换 RenderTargetInfo 为字典"""
        return {
            'slot': rt.slot,
            'resource_id': rt.resource_id,
            'resource_name': rt.resource_name,
            'format': rt.format,
            'width': rt.width,
            'height': rt.height,
            'load_action': rt.load_action,
            'store_action': rt.store_action,
        }
    
    def _convert_depth_stencil(self, ds: DepthStencilInfo) -> Dict[str, Any]:
        """转换 DepthStencilInfo 为字典"""
        return {
            'resource_id': ds.resource_id,
            'resource_name': ds.resource_name,
            'format': ds.format,
            'width': ds.width,
            'height': ds.height,
            'depth_test_enabled': ds.depth_test_enabled,
            'depth_write_enabled': ds.depth_write_enabled,
            'depth_func': ds.depth_func,
            'stencil_enabled': ds.stencil_enabled,
        }
    
    def _convert_sampler(self, sampler: SamplerInfo) -> Dict[str, Any]:
        """转换 SamplerInfo 为字典"""
        return {
            'slot': sampler.slot,
            'resource_id': sampler.resource_id,
            'filter_mode': sampler.filter_mode,
            'address_u': sampler.address_u,
            'address_v': sampler.address_v,
            'address_w': sampler.address_w,
            'max_anisotropy': sampler.max_anisotropy,
        }
    
    def _convert_shader_bindings(self, bindings: ShaderBindings) -> Dict[str, Any]:
        """转换着色器绑定为字典"""
        result: Dict[str, Any] = {
            'shader_resource_id': bindings.shader_resource_id,
            'shader_name': bindings.shader_name or "",
            'entry_point': bindings.entry_point or "",
        }
        
        if self.config.include_resource_bindings:
            if bindings.constant_buffers:
                result['constant_buffers'] = [
                    self._convert_resource_binding(cb)
                    for cb in bindings.constant_buffers
                ]
            if bindings.shader_resources:
                result['shader_resources'] = [
                    self._convert_resource_binding(sr)
                    for sr in bindings.shader_resources
                ]
            if bindings.samplers:
                result['samplers'] = [
                    self._convert_resource_binding(s)
                    for s in bindings.samplers
                ]
            if bindings.uavs:
                result['uavs'] = [
                    self._convert_resource_binding(u)
                    for u in bindings.uavs
                ]
        
        return result
    
    def _convert_resource_binding(self, binding: ResourceBinding) -> Dict[str, Any]:
        """转换资源绑定为字典"""
        result = {
            'slot': binding.slot,
            'resource_id': binding.resource_id,
        }
        
        if binding.resource_name:
            result['resource_name'] = binding.resource_name
        if binding.resource_type:
            result['resource_type'] = binding.resource_type
        if binding.format:
            result['format'] = binding.format
        if binding.width:
            result['width'] = binding.width
        if binding.height:
            result['height'] = binding.height
        if binding.depth:
            result['depth'] = binding.depth
        if binding.array_size:
            result['array_size'] = binding.array_size
        if binding.mip_levels:
            result['mip_levels'] = binding.mip_levels
        if binding.size_bytes:
            result['size_bytes'] = binding.size_bytes
        if binding.stride:
            result['stride'] = binding.stride
        
        return result
    
    def _convert_issue(self, issue: BindingIssue) -> ExportedIssue:
        """转换问题为导出格式"""
        return ExportedIssue(
            event_id=issue.event_id,
            rule_id=issue.rule_id,
            severity=issue.severity.value if isinstance(issue.severity, Enum) else str(issue.severity),
            category=issue.category.value if isinstance(issue.category, Enum) else str(issue.category),
            message=issue.message,
            details=issue.details or {},
        )
    
    def _convert_dependency(self, dep: ResourceDependency) -> ExportedDependency:
        """转换依赖为导出格式"""
        # 构建访问详情字符串
        source_access = dep.source_access.name if isinstance(dep.source_access, Enum) else str(dep.source_access)
        target_access = dep.target_access.name if isinstance(dep.target_access, Enum) else str(dep.target_access)
        access_detail = f"{source_access} -> {target_access}"
        
        return ExportedDependency(
            source_event=dep.source_event_id,
            target_event=dep.target_event_id,
            resource_id=dep.resource_id,
            resource_name=dep.resource_name or f"Resource_{dep.resource_id}",
            dependency_type=dep.dependency_type.value if isinstance(dep.dependency_type, Enum) else str(dep.dependency_type),
            access_detail=access_detail,
        )
    
    def _convert_lifetime(self, lifetime: ResourceLifetime) -> ExportedLifetime:
        """转换资源生命周期为导出格式"""
        # ResourceType 是枚举类型
        resource_type = lifetime.resource_type.name if isinstance(lifetime.resource_type, Enum) else str(lifetime.resource_type) if lifetime.resource_type else "Unknown"
        
        # 计算是否写入但未读取（写入次数 > 0 且读取次数 == 0）
        is_written_never_read = lifetime.write_count > 0 and lifetime.read_count == 0
        
        return ExportedLifetime(
            resource_id=lifetime.resource_id,
            resource_name=lifetime.resource_name or f"Resource_{lifetime.resource_id}",
            resource_type=resource_type,
            first_access_event=lifetime.first_access_event,
            last_access_event=lifetime.last_access_event,
            read_count=lifetime.read_count,
            write_count=lifetime.write_count,
            hazards=[],  # 暂时留空，hazards 需要从外部分析获得
            is_written_never_read=is_written_never_read,
        )
    
    def _compute_statistics(
        self,
        draws: List[DrawCallDetail],
        issues: List[ExportedIssue],
        dependencies: List[ExportedDependency],
        lifetimes: Optional[Dict[int, ResourceLifetime]],
    ) -> ExportedStatistics:
        """计算统计信息"""
        stats = ExportedStatistics(
            total_draw_calls=len(draws),
            total_issues=len(issues),
            total_resources=len(lifetimes) if lifetimes else 0,
            total_dependencies=len(dependencies),
        )
        
        # 按严重程度分组
        for issue in issues:
            severity = issue.severity
            stats.issues_by_severity[severity] = stats.issues_by_severity.get(severity, 0) + 1
        
        # 按类别分组
        for issue in issues:
            category = issue.category
            stats.issues_by_category[category] = stats.issues_by_category.get(category, 0) + 1
        
        # 按规则分组
        for issue in issues:
            rule_id = issue.rule_id
            stats.issues_by_rule[rule_id] = stats.issues_by_rule.get(rule_id, 0) + 1
        
        # 按依赖类型分组
        for dep in dependencies:
            dep_type = dep.dependency_type
            stats.dependencies_by_type[dep_type] = stats.dependencies_by_type.get(dep_type, 0) + 1
        
        # 计算特定问题数量
        stats.redundant_bindings = sum(
            1 for i in issues if 'redundant' in i.rule_id.lower()
        )
        stats.missing_resources = sum(
            1 for i in issues if 'missing' in i.message.lower()
        )
        
        # 未使用的资源（写入但未读取）
        if lifetimes:
            stats.unused_resources = sum(
                1 for lt in lifetimes.values() if lt.write_count > 0 and lt.read_count == 0
            )
        
        return stats


# 便捷函数
def export_to_json(
    draws: List[DrawCallDetail],
    output_path: Optional[Union[str, Path]] = None,
    **kwargs
) -> Union[str, Path]:
    """
    导出分析结果为 JSON
    
    Args:
        draws: Draw Call 详情列表
        output_path: 可选的输出文件路径
        **kwargs: 传递给 JSONExporter.export() 的参数
    
    Returns:
        如果提供了 output_path，返回文件路径
        否则返回 JSON 字符串
    """
    exporter = JSONExporter()
    
    if output_path:
        return exporter.export_to_file(output_path, draws, **kwargs)
    else:
        return exporter.export(draws, **kwargs)


def export_analysis_results(
    draws: List[DrawCallDetail],
    issues: List[BindingIssue],
    dependencies: List[ResourceDependency],
    lifetimes: Dict[int, ResourceLifetime],
    output_path: Union[str, Path],
    config: Optional[JSONExportConfig] = None,
    source_file: Optional[str] = None,
    api_type: Optional[str] = None,
) -> Path:
    """
    导出完整的分析结果
    
    这是一个高级便捷函数，一次性导出所有分析数据
    
    Args:
        draws: Draw Call 详情列表
        issues: 检测到的问题列表
        dependencies: 资源依赖关系列表
        lifetimes: 资源生命周期字典
        output_path: 输出文件路径
        config: 可选的导出配置
        source_file: 源 RDC 文件路径
        api_type: API 类型
    
    Returns:
        输出文件的 Path 对象
    """
    exporter = JSONExporter(config)
    return exporter.export_to_file(
        output_path,
        draws,
        issues=issues,
        dependencies=dependencies,
        lifetimes=lifetimes,
        source_file=source_file,
        api_type=api_type,
    )
