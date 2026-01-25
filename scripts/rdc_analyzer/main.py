#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Analyzer - 端到端分析管线
============================

统一入口，一键分析 RDC 文件并生成完整的 HTML 报告。

使用方式:
    # 在 RenderDoc Python Shell 中
    from rdc_analyzer.main import analyze
    analyze("capture.rdc", output_dir="./output")
    
    # 命令行 (需在 RenderDoc 环境中)
    py -3 -m rdc_analyzer analyze capture.rdc -o ./output
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .rules import RuleRunner, register_all_rules

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AnalysisOptions:
    """
    分析选项配置
    
    控制分析行为、资源采样和输出格式。
    """
    
    # === 输出配置 ===
    output_formats: List[str] = field(default_factory=lambda: ['html'])
    """输出格式列表: 'html', 'json'"""
    
    output_dir: str = "./output"
    """输出目录"""
    
    # === 资源采样 ===
    sample_textures: bool = True
    """是否采样纹理数据（生成缩略图）"""
    
    sample_buffers: bool = True
    """是否采样 Buffer 数据（Constant Buffer 等）"""
    
    max_texture_size: int = 256
    """纹理缩略图最大尺寸（像素）"""
    
    max_buffer_sample_size: int = 4096
    """Buffer 采样最大字节数"""
    
    # === 事件范围 ===
    event_range: Optional[Tuple[int, int]] = None
    """事件 ID 范围 (start, end)，None 表示全部"""
    
    # === 规则配置 ===
    enabled_rules: Optional[List[str]] = None
    """启用的规则 ID 列表，None 表示全部"""
    
    disabled_rules: Optional[List[str]] = None
    """禁用的规则 ID 列表"""
    
    platform: str = "pc"
    """目标平台: 'pc' 或 'mobile'"""
    
    # === 性能分析 ===
    enable_performance_analysis: bool = True
    """是否启用性能分析（PERF001-PERF007 规则）"""
    
    performance_thresholds: Optional[Dict[str, Any]] = None
    """性能规则阈值覆盖（可选）"""
    
    # === Mali GPU 分析 ===
    enable_mali_analysis: bool = False
    """是否启用 Mali GPU 性能分析"""
    
    # === Pipeline State 采样 ===
    enable_pipeline_sampling: bool = True
    """是否启用 Pipeline State 采样（用于规则检查）"""
    
    pipeline_sample_count: int = 30
    """每帧采样的 draw call 数量"""
    
    pipeline_sample_strategy: str = "uniform"
    """采样策略: 'uniform', 'diverse', 'first_n', 'last_n'"""
    
    mali_gpu: str = "Mali-G78"
    """目标 Mali GPU 型号（默认: Mali-G78，市场占有率最高）"""
    
    malioc_path: Optional[str] = None
    """malioc 可执行文件路径（None 则自动查找）"""

    # === Tile-Based GPU 分析 ===
    enable_tile_analysis: bool = False
    """是否启用 Tile-Based 分析"""
    
    tile_gpu: str = "Generic-Tile"
    """目标 Tile GPU 型号（用于 Tile memory 模型）"""
    
    # === Adreno GPU 分析 ===
    enable_adreno_analysis: bool = False
    """是否启用 Adreno 分析"""
    
    adreno_mode: str = "heuristic"
    """Adreno 分析模式: 'heuristic', 'profiler', 'auto'"""
    
    adreno_profiler_path: Optional[str] = None
    """Snapdragon Profiler CLI 路径（可选）"""
    
    
    # === 日志配置 ===
    log_level: str = 'INFO'
    """日志级别: 'DEBUG', 'INFO', 'WARNING', 'ERROR'"""
    
    verbose: bool = False
    """详细输出模式"""


@dataclass
class AnalysisProgress:
    """分析进度信息"""
    stage: str
    current: int
    total: int
    message: str
    
    @property
    def percent(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0


@dataclass
class AnalysisSummary:
    """分析结果摘要"""
    
    # 基本信息
    rdc_path: str
    api: str
    timestamp: str
    duration_seconds: float
    
    # 帧统计
    total_events: int
    draw_call_count: int
    total_vertices: int
    total_triangles: int
    
    # 资源统计
    texture_count: int
    buffer_count: int
    shader_count: int
    
    # 问题统计
    error_count: int
    warning_count: int
    info_count: int
    
    # 输出文件
    output_files: List[str] = field(default_factory=list)


ProgressCallback = Callable[[AnalysisProgress], None]


class AnalysisPipeline:
    """
    端到端分析管线
    
    协调完整的分析流程：
    1. 打开 RDC 文件
    2. 解析事件列表
    3. 提取管线状态
    4. 运行规则分析
    5. 采样资源数据
    6. 生成报告
    """
    
    # 分析阶段定义
    STAGES = [
        ('open', '打开捕获文件', 5),
        ('parse', '解析事件列表', 15),
        ('extract', '提取管线状态', 30),
        ('analyze', '运行规则分析', 20),
        ('sample', '采样资源数据', 20),
        ('export', '生成报告', 10),
    ]
    
    def __init__(
        self,
        rdc_path: str,
        options: Optional[AnalysisOptions] = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """
        初始化分析管线
        
        Args:
            rdc_path: RDC 文件路径
            options: 分析选项，None 使用默认值
            progress_callback: 进度回调函数
        """
        self.rdc_path = rdc_path
        self.options = options or AnalysisOptions()
        self.progress_callback = progress_callback
        
        # 运行时状态
        self._controller = None
        self._capture = None
        self._events = []
        self._draw_calls = []
        self._resources = {}
        self._resource_samples = {}
        self._issues = []
        self._api = "Unknown"
        self._performance_report = None  # 性能分析报告
        self._mali_report = None  # Mali GPU 分析报告
        
        # Pipeline state 采样跟踪
        self._pipeline_state_samples = 0  # 已采样的 draw call 数量
        self._resource_lifecycle_tracked = False  # 是否跟踪了资源生命周期
        self._pipeline_sampling_result = None  # PipelineSampler 结果
        self._resource_lifetimes = {}  # ResourceTracker 结果
        
        # 配置日志级别
        log_level = getattr(logging, self.options.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
    
    def run(self) -> AnalysisSummary:
        """
        执行完整分析
        
        Returns:
            AnalysisSummary: 分析结果摘要
            
        Raises:
            FileNotFoundError: RDC 文件不存在
            RuntimeError: 分析过程中出错
        """
        start_time = datetime.now()
        
        # 验证输入
        if not os.path.exists(self.rdc_path):
            raise FileNotFoundError(f"RDC 文件不存在: {self.rdc_path}")
        
        logger.info(f"开始分析: {self.rdc_path}")
        logger.info(f"输出目录: {self.options.output_dir}")
        
        try:
            # 创建输出目录
            output_dir = Path(self.options.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 执行各阶段
            self._report_progress('open', 0, 1, '正在打开捕获文件...')
            self._open_capture()
            
            self._report_progress('parse', 0, 1, '正在解析事件列表...')
            self._parse_events()
            
            self._report_progress('extract', 0, len(self._events), '正在提取管线状态...')
            self._extract_states()
            
            self._report_progress('analyze', 0, 1, '正在运行规则分析...')
            self._analyze_rules()
            
            if self.options.sample_textures or self.options.sample_buffers:
                self._report_progress('sample', 0, 1, '正在采样资源数据...')
                self._sample_resources()
            
            self._report_progress('export', 0, 1, '正在生成报告...')
            output_files = self._export_reports(output_dir)
            
            # 清理
            self._cleanup()
            
            # 计算时长
            duration = (datetime.now() - start_time).total_seconds()
            
            # 生成摘要
            summary = self._create_summary(duration, output_files)
            
            logger.info(f"分析完成，耗时 {duration:.2f} 秒")
            logger.info(f"生成文件: {output_files}")
            
            return summary
            
        except Exception as e:
            self._cleanup()
            logger.error(f"分析失败: {e}")
            raise
    
    def _report_progress(self, stage: str, current: int, total: int, message: str):
        """报告进度"""
        if self.progress_callback:
            progress = AnalysisProgress(
                stage=stage,
                current=current,
                total=total,
                message=message
            )
            self.progress_callback(progress)
        
        if self.options.verbose:
            logger.debug(f"[{stage}] {message} ({current}/{total})")
    
    def _open_capture(self):
        """打开 RDC 捕获文件"""
        try:
            import renderdoc as rd
        except ImportError:
            raise RuntimeError(
                "无法导入 renderdoc 模块。\n"
                "请在 RenderDoc 的 Python Shell 中运行此脚本，\n"
                "或确保 renderdoc 模块已正确安装。"
            )
        
        # 打开捕获文件
        cap = rd.OpenCaptureFile()
        result = cap.OpenFile(self.rdc_path, '', None)
        
        if result != rd.ResultCode.Succeeded:
            raise RuntimeError(f"无法打开 RDC 文件: {result}")
        
        # 获取 API 类型
        self._api = cap.DriverName()
        logger.info(f"检测到 API: {self._api}")
        
        # 创建回放控制器
        status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
        
        if status != rd.ResultCode.Succeeded:
            cap.Shutdown()
            raise RuntimeError(f"无法创建回放控制器: {status}")
        
        self._capture = cap
        self._controller = controller
        
        self._report_progress('open', 1, 1, f'已打开: {self._api}')
    
    def _parse_events(self):
        """解析事件列表"""
        if not self._controller:
            raise RuntimeError("控制器未初始化")
        
        # 获取所有 Action
        actions = self._controller.GetRootActions()
        
        def flatten_actions(action_list, depth=0):
            """递归展平 Action 树"""
            result = []
            for action in action_list:
                result.append({
                    'eventId': action.eventId,
                    'name': action.GetName(self._controller.GetStructuredFile()),
                    'flags': int(action.flags),
                    'depth': depth,
                    'numIndices': action.numIndices,
                    'numVerts': getattr(action, 'numVertices', 0),
                    'numInstances': action.numInstances,
                })
                
                # 处理子节点
                if len(action.children) > 0:
                    result.extend(flatten_actions(action.children, depth + 1))
            
            return result
        
        self._events = flatten_actions(actions)
        
        # 过滤事件范围
        if self.options.event_range:
            start, end = self.options.event_range
            self._events = [e for e in self._events 
                          if start <= e['eventId'] <= end]
        
        # 识别 Draw Call
        import renderdoc as rd
        self._draw_calls = [
            e for e in self._events 
            if e['flags'] & int(rd.ActionFlags.Drawcall)
        ]
        
        logger.info(f"解析到 {len(self._events)} 个事件，{len(self._draw_calls)} 个 Draw Call")
        self._report_progress('parse', 1, 1, 
                             f'找到 {len(self._draw_calls)} 个 Draw Call')
    
    def _extract_states(self):
        """提取管线状态"""
        if not self._controller:
            raise RuntimeError("控制器未初始化")
        
        import renderdoc as rd
        
        # 提取资源信息
        textures = self._controller.GetTextures()
        buffers = self._controller.GetBuffers()
        
        self._resources = {
            'textures': {},
            'buffers': {}
        }
        
        for tex in textures:
            self._resources['textures'][int(tex.resourceId)] = {
                'id': int(tex.resourceId),
                'name': tex.name if hasattr(tex, 'name') else f"Texture_{tex.resourceId}",
                'width': tex.width,
                'height': tex.height,
                'depth': tex.depth,
                'format': str(tex.format.Name()) if hasattr(tex.format, 'Name') else str(tex.format),
                'mips': tex.mips,
                'arraysize': tex.arraysize,
                'type': 'TEXTURE'
            }
        
        for buf in buffers:
            self._resources['buffers'][int(buf.resourceId)] = {
                'id': int(buf.resourceId),
                'name': buf.name if hasattr(buf, 'name') else f"Buffer_{buf.resourceId}",
                'length': buf.length,
                'type': 'BUFFER'
            }
        
        logger.info(f"提取到 {len(textures)} 个纹理，{len(buffers)} 个 Buffer")
        
        # === Pipeline State 采样 ===
        if self.options.enable_pipeline_sampling and self._draw_calls:
            try:
                self._sample_pipeline_states()
            except Exception as e:
                logger.warning(f"Pipeline State 采样失败: {e}")
        
        self._report_progress('extract', 1, 1, 
                             f'{len(textures)} 纹理, {len(buffers)} Buffer')
    
    def _sample_pipeline_states(self):
        """
        采样 Pipeline State（非 Mali 分析路径）
        
        使用 PipelineSampler 对 draw call 进行抽样，获取关键管线状态：
        - VS/PS Shader
        - Render Target
        - Depth/Stencil
        - Viewport/Scissor
        - Primitive Topology
        """
        try:
            from .extractors.pipeline_sampler import (
                sample_pipeline_states,
                SamplingStrategy,
            )
        except ImportError as e:
            logger.warning(f"无法导入 PipelineSampler: {e}")
            return
        
        # 映射策略名称到枚举
        strategy_map = {
            'uniform': SamplingStrategy.UNIFORM,
            'diverse': SamplingStrategy.DIVERSE,
            'first_n': SamplingStrategy.FIRST_N,
            'last_n': SamplingStrategy.LAST_N,
        }
        strategy = strategy_map.get(
            self.options.pipeline_sample_strategy.lower(),
            SamplingStrategy.UNIFORM
        )
        
        logger.info(
            f"开始 Pipeline State 采样: "
            f"策略={self.options.pipeline_sample_strategy}, "
            f"数量={self.options.pipeline_sample_count}"
        )
        
        try:
            result = sample_pipeline_states(
                controller=self._controller,
                events=self._draw_calls,
                sample_count=self.options.pipeline_sample_count,
                strategy=strategy,
            )
            
            self._pipeline_sampling_result = result
            self._pipeline_state_samples = result.sampled_count
            
            logger.info(
                f"Pipeline State 采样完成: "
                f"{result.sampled_count}/{result.total_candidates} 个事件, "
                f"{result.unique_shaders} 个唯一 Shader 组合"
            )

            # 基于采样结果追踪资源生命周期
            self._track_resource_lifetimes_from_samples()
            
        except Exception as e:
            logger.warning(f"Pipeline State 采样失败: {e}")
            self._pipeline_sampling_result = None

    def _track_resource_lifetimes_from_samples(self):
        """基于 PipelineSampler 的样本追踪资源生命周期"""
        if not self._pipeline_sampling_result or not self._pipeline_sampling_result.samples:
            return

        try:
            from .analysis.resource_tracker import ResourceTracker
            from .core.pipeline_state import DrawCallDetail

            tracker = ResourceTracker()
            for sample in self._pipeline_sampling_result.samples:
                draw = DrawCallDetail(
                    event_id=sample.event_id,
                    name=sample.name,
                    draw_type=sample.draw_type,
                    vertex_count=sample.vertex_count,
                    index_count=sample.index_count,
                    instance_count=sample.instance_count,
                    pipeline=sample.snapshot,
                )
                tracker.process(draw)

            lifetimes = tracker.get_resource_lifetimes()
            if lifetimes:
                self._resource_lifetimes = lifetimes
                self._resource_lifecycle_tracked = True
        except Exception as e:
            logger.warning(f"资源生命周期追踪失败: {e}")

    def _build_rule_context(self):
        """为 RuleRunner 构建最小可用的 AnalysisContext"""
        from .config import get_thresholds
        from .core.context import AnalysisContext
        from .core.types import ParsedData, FrameSummary, DrawCallInfo, TextureInfo, BufferInfo

        draws = []
        draw_calls = []
        total_vertices = 0
        total_triangles = 0

        for dc in self._draw_calls:
            num_indices = dc.get('numIndices', 0) or 0
            num_instances = dc.get('numInstances', 1) or 1
            num_vertices = dc.get('numVerts', 0) or dc.get('numVertices', 0) or 0
            if num_vertices == 0 and num_indices:
                num_vertices = num_indices

            draws.append({
                'event_id': dc.get('eventId', 0),
                'vertex_count': num_vertices,
                'index_count': num_indices,
                'instance_count': num_instances,
                'state': dc.get('state', {}),
                'is_ui': dc.get('is_ui', False),
                'is_postprocess': dc.get('is_postprocess', False),
            })

            total_vertices += num_vertices * num_instances
            total_triangles += (num_vertices // 3) * num_instances

            draw_calls.append(DrawCallInfo(
                event_id=dc.get('eventId', 0),
                name=dc.get('name', ''),
                type=dc.get('name', ''),
                index_count=num_indices,
                vertex_count=num_vertices,
                instance_count=num_instances,
            ))

        parsed = ParsedData(
            api=self._api,
            file_path=self.rdc_path,
            draws=draws,
            resources=self._resources,
        )

        textures = []
        for tex_id, tex_info in self._resources.get('textures', {}).items():
            textures.append(TextureInfo(
                resource_id=str(tex_info.get('id', tex_id)),
                name=tex_info.get('name', ''),
                width=tex_info.get('width', 0),
                height=tex_info.get('height', 0),
                depth=tex_info.get('depth', 1),
                mip_levels=tex_info.get('mips', tex_info.get('mipLevels', 1)),
                array_size=tex_info.get('arraysize', tex_info.get('arraySize', 1)),
                format=tex_info.get('format', ''),
            ))

        buffers = []
        for buf_id, buf_info in self._resources.get('buffers', {}).items():
            buffers.append(BufferInfo(
                resource_id=str(buf_info.get('id', buf_id)),
                name=buf_info.get('name', ''),
                size=buf_info.get('length', buf_info.get('size', 0)),
            ))

        frame_summary = FrameSummary(
            draw_call_count=len(self._draw_calls),
            vertex_count=total_vertices,
            primitive_count=total_triangles,
            texture_count=len(textures),
            buffer_count=len(buffers),
        )

        context = AnalysisContext(
            parsed=parsed,
            platform=self.options.platform,
            thresholds=get_thresholds(self.options.platform),
        )
        context.frame_summary = frame_summary
        context.textures = textures
        context.buffers = buffers
        context.draw_calls = draw_calls

        return context
    
    def _analyze_rules(self):
        """运行规则分析"""
        self._issues = []
        self._performance_report = None
        
        # === 规则引擎 (RuleRunner) ===
        try:
            register_all_rules()

            context = self._build_rule_context()
            if self.options.enable_tile_analysis:
                try:
                    from .analyzers.tile_based_analyzer import TileBasedAnalyzer
                    context.tile_gpu = self.options.tile_gpu
                    TileBasedAnalyzer(context).analyze()
                except Exception as e:
                    logger.warning(f"Tile-Based 分析失败: {e}")
            if self.options.enable_adreno_analysis:
                try:
                    from .analyzers.adreno_analyzer import AdrenoAnalyzer
                    context.adreno_mode = self.options.adreno_mode
                    context.adreno_profiler_path = self.options.adreno_profiler_path
                    self._issues.extend(AdrenoAnalyzer(context).analyze())
                except Exception as e:
                    logger.warning(f"Adreno 分析失败: {e}")
            runner = RuleRunner(context)

            if self.options.enabled_rules:
                runner.enable_only(self.options.enabled_rules)
            if self.options.disabled_rules:
                for rule_id in self.options.disabled_rules:
                    runner.disable_rule(rule_id)

            self._issues.extend(runner.run())
        except Exception as e:
            logger.warning(f"RuleRunner 执行失败: {e}")
        
        total_vertices = sum(dc.get('numIndices', 0) or 0 for dc in self._draw_calls)
        if total_vertices > 5000000:
            self._issues.append({
                'code': 'BIND002',
                'severity': 'warning',
                'message': f'总顶点数过多: {total_vertices:,} (建议 < 5M)',
                'eventId': None
            })
        
        # === 性能分析 (PERF001-PERF007) ===
        if self.options.enable_performance_analysis:
            try:
                self._run_performance_analysis()
            except Exception as e:
                logger.warning(f"性能分析失败: {e}")
        
        logger.info(f"规则分析完成，发现 {len(self._issues)} 个问题")
        
        if self._performance_report:
            perf_score = self._performance_report.get('overall_score', 0)
            perf_issues = len(self._performance_report.get('issues', []))
            logger.info(f"性能分析: 评分 {perf_score}, 发现 {perf_issues} 个问题")
        
        # === Mali GPU 分析 ===
        if self.options.enable_mali_analysis:
            try:
                self._run_mali_analysis()
            except Exception as e:
                logger.warning(f"Mali GPU 分析失败: {e}")
        
        if self._mali_report:
            mali_shaders = self._mali_report.get('total_shaders', 0)
            mali_success = self._mali_report.get('success_count', 0)
            logger.info(f"Mali 分析: {mali_success}/{mali_shaders} Shader 成功分析")
        
        self._report_progress('analyze', 1, 1, f'发现 {len(self._issues)} 个问题')
    
    def _run_performance_analysis(self):
        """运行性能分析器 (PERF001-PERF007)
        
        使用简化的独立分析逻辑，不依赖完整的分析框架。
        """
        from .core.types import PerformanceReport, PerformanceIssue
        from .analyzers.performance_analyzer import (
            is_compressed_format, is_power_of_two, PERFORMANCE_RULES
        )
        
        # 初始化报告
        report = PerformanceReport()
        
        # 收集基础统计
        total_verts = 0
        total_tris = 0
        total_instances = 0
        small_batch_count = 0
        small_batch_threshold = 100  # 小于 100 顶点视为小批次
        
        for dc in self._draw_calls:
            vc = dc.get('numIndices', 0) or 0
            inst = dc.get('numInstances', 1) or 1
            
            total_verts += vc * inst
            total_tris += (vc // 3) * inst
            total_instances += inst
            
            if vc < small_batch_threshold and vc > 0:
                small_batch_count += 1
        
        report.total_draw_calls = len(self._draw_calls)
        report.total_vertices = total_verts
        report.total_triangles = total_tris
        report.total_instances = total_instances
        
        # 纹理统计
        textures = self._resources.get('textures', {})
        report.unique_textures = len(textures)
        
        total_texture_mem = 0
        uncompressed_count = 0
        large_texture_count = 0
        large_threshold = 2048  # PC 平台
        if self.options.platform == 'mobile':
            large_threshold = 1024
        
        for tex_id, tex_info in textures.items():
            w = tex_info.get('width', 0)
            h = tex_info.get('height', 0)
            fmt = tex_info.get('format', 'Unknown')
            mips = tex_info.get('mips', 1)
            
            # 估算内存（简化）
            bpp = 4  # 默认 4 字节/像素
            if is_compressed_format(fmt):
                bpp = 0.5  # 压缩格式约 0.5-1 字节/像素
            else:
                uncompressed_count += 1
                
            mem = w * h * bpp
            for m in range(1, mips):
                mem += (w >> m) * (h >> m) * bpp
            total_texture_mem += mem
            
            # 检查大纹理
            if w > large_threshold or h > large_threshold:
                large_texture_count += 1
                report.issues.append(PerformanceIssue(
                    rule_id='PERF004',
                    severity='warning',
                    category='texture',
                    title='大纹理',
                    message=f'纹理 {tex_info.get("name", tex_id)} ({w}x{h}) 尺寸超过阈值 {large_threshold}',
                    resource_id=str(tex_id),
                    impact_score=5 + min((w * h) // (large_threshold * large_threshold), 10)
                ))
        
        report.total_texture_memory_mb = total_texture_mem / (1024 * 1024)
        
        # PERF003: 小批次检查
        if small_batch_count > len(self._draw_calls) * 0.3:  # 超过 30% 是小批次
            report.issues.append(PerformanceIssue(
                rule_id='PERF003',
                severity='warning',
                category='batch',
                title='小批次绘制',
                message=f'小批次绘制过多: {small_batch_count}/{len(self._draw_calls)} ({small_batch_count*100//max(1,len(self._draw_calls))}%)',
                impact_score=min(small_batch_count // 10, 15),
                actual_value=small_batch_count,
                threshold_value=small_batch_threshold
            ))
        
        # PERF005: 未压缩纹理
        if uncompressed_count > 0 and len(textures) > 0:
            ratio = uncompressed_count / len(textures)
            if ratio > 0.5:  # 超过 50% 未压缩
                report.issues.append(PerformanceIssue(
                    rule_id='PERF005',
                    severity='warning',
                    category='texture',
                    title='未压缩纹理',
                    message=f'未压缩纹理过多: {uncompressed_count}/{len(textures)} ({int(ratio*100)}%)',
                    impact_score=int(ratio * 10),
                    actual_value=uncompressed_count,
                    threshold_value=len(textures)
                ))
        
        # 计算总分
        base_score = 100
        for issue in report.issues:
            base_score -= issue.impact_score
        report.overall_score = max(0, min(100, base_score))
        
        # 生成建议
        if small_batch_count > 50:
            report.recommendations.append({
                'text': f'合并小批次绘制调用 (当前 {small_batch_count} 个)',
                'priority': 'high'
            })
        
        if uncompressed_count > 5:
            report.recommendations.append({
                'text': f'使用 BC/DXT/ASTC 压缩纹理 (当前 {uncompressed_count} 个未压缩)',
                'priority': 'medium'
            })
        
        if large_texture_count > 0:
            report.recommendations.append({
                'text': f'考虑降低大纹理分辨率 (当前 {large_texture_count} 个超过 {large_threshold})',
                'priority': 'medium'
            })
        
        # 转换为字典格式
        self._performance_report = {
            'overall_score': report.overall_score,
            'issues': [
                {
                    'rule_id': i.rule_id,
                    'message': i.message,
                    'event_id': i.event_id,
                    'impact_score': i.impact_score,
                    'category': i.category,
                    'title': i.title,
                    'severity': i.severity
                }
                for i in report.issues
            ],
            'metrics': {
                'total_draw_calls': report.total_draw_calls,
                'total_vertices': report.total_vertices,
                'total_triangles': report.total_triangles,
                'total_textures': report.unique_textures,
                'texture_memory_mb': round(report.total_texture_memory_mb, 2),
                'small_batch_count': small_batch_count
            },
            'recommendations': [
                r if isinstance(r, dict) else {'text': r, 'priority': 'medium'}
                for r in report.recommendations
            ]
        }
        
        # 将性能问题添加到主问题列表
        for issue in report.issues:
            severity = 'warning'
            if issue.impact_score >= 10:
                severity = 'error'
            elif issue.impact_score < 5:
                severity = 'info'
            
            self._issues.append({
                'code': issue.rule_id,
                'severity': severity,
                'message': issue.message,
                'eventId': issue.event_id
            })
    
    def _run_mali_analysis(self):
        """运行 Mali GPU 分析
        
        使用 Mali Offline Compiler (malioc) 分析 Shader 性能。
        需要在系统上安装 malioc 工具。
        
        分析流程:
        1. 获取反汇编目标列表（选择 GLSL 或 SPIR-V）
        2. 遍历 Draw Call，提取 VS/PS Shader
        3. 检测 Shader 格式，如需则转换为 GLSL
        4. 使用 malioc 分析每个 Shader
        5. 汇总结果并生成报告
        """
        import renderdoc as rd
        from .analyzers.mali_analyzer import MaliCompiler, MaliBatchAnalysisResult
        from .converters.shader_converter import ShaderConverter, ShaderStage, ShaderFormat
        
        # 初始化 Mali 编译器
        compiler = MaliCompiler(malioc_path=self.options.malioc_path)
        
        if not compiler.is_available:
            logger.warning("malioc 不可用，跳过 Mali 分析")
            self._mali_report = {
                'status': 'unavailable',
                'error': 'malioc 未安装或未找到。请从 ARM Developer 网站下载 Mali Offline Compiler。',
                'download_url': 'https://developer.arm.com/Tools%20and%20Software/Mali%20Offline%20Compiler'
            }
            return
        
        logger.info(f"开始 Mali GPU 分析 (目标: {self.options.mali_gpu})")
        
        # 初始化 Shader 转换器
        shader_converter = ShaderConverter()
        if shader_converter.has_external_tools:
            logger.info("Shader 转换器: 外部工具可用 (spirv-cross/DXC)")
        else:
            logger.info("Shader 转换器: 使用内置转换")
        
        # 获取可用的反汇编格式
        disasm_targets = self._controller.GetDisassemblyTargets(True)
        logger.debug(f"可用反汇编格式: {list(disasm_targets)}")
        
        # 选择最佳格式 (优先 GLSL，其次 SPIR-V，最后 HLSL/其他)
        target = None
        target_priority = 0  # 0=未选择, 3=GLSL, 2=SPIRV, 1=其他
        
        for t in disasm_targets:
            t_lower = t.lower()
            if 'glsl' in t_lower and target_priority < 3:
                target = t
                target_priority = 3
            elif ('spirv' in t_lower or 'spir-v' in t_lower) and target_priority < 2:
                target = t
                target_priority = 2
            elif target_priority < 1:
                target = t
                target_priority = 1
        
        if not target:
            logger.warning("无法找到合适的 Shader 反汇编格式")
            self._mali_report = {
                'status': 'error',
                'error': '无法获取 Shader 源码格式'
            }
            return
        
        logger.info(f"使用反汇编格式: {target}")
        
        # 收集所有唯一的 Shader
        shaders_to_analyze = []  # [(source, type, name), ...]
        analyzed_shaders = set()  # 用于去重
        conversion_stats = {'total': 0, 'converted': 0, 'failed': 0, 'native_glsl': 0}
        
        for dc in self._draw_calls[:100]:  # 限制分析前 100 个 Draw Call
            event_id = dc['eventId']
            
            # 移动到该事件
            self._controller.SetFrameEvent(event_id, True)
            state = self._controller.GetPipelineState()
            pipe = state.GetGraphicsPipelineObject()
            
            # 更新 pipeline state 采样计数
            self._pipeline_state_samples += 1
            
            # 分析 Vertex Shader
            try:
                vs_refl = state.GetShaderReflection(rd.ShaderStage.Vertex)
                if vs_refl and vs_refl.resourceId not in analyzed_shaders:
                    vs_source = self._controller.DisassembleShader(pipe, vs_refl, target)
                    if vs_source and len(vs_source) > 50:
                        shader_name = f"VS_EID{event_id}"
                        
                        # 检测格式并转换
                        detected_format = shader_converter.detect_format(vs_source)
                        conversion_stats['total'] += 1
                        
                        if detected_format == ShaderFormat.GLSL:
                            # 已经是 GLSL，直接使用
                            conversion_stats['native_glsl'] += 1
                            shaders_to_analyze.append((vs_source, 'vertex', shader_name))
                        else:
                            # 需要转换
                            result = shader_converter.convert_to_glsl(vs_source, ShaderStage.VERTEX)
                            if result.success:
                                conversion_stats['converted'] += 1
                                shaders_to_analyze.append((result.glsl_source, 'vertex', shader_name))
                                if result.warnings:
                                    logger.debug(f"{shader_name} 转换警告: {result.warnings}")
                            else:
                                conversion_stats['failed'] += 1
                                logger.debug(f"{shader_name} 转换失败: {result.error_message}")
                        
                        analyzed_shaders.add(vs_refl.resourceId)
            except Exception as e:
                logger.debug(f"提取 VS 失败 (EID {event_id}): {e}")
            
            # 分析 Pixel/Fragment Shader
            try:
                ps_refl = state.GetShaderReflection(rd.ShaderStage.Pixel)
                if ps_refl and ps_refl.resourceId not in analyzed_shaders:
                    ps_source = self._controller.DisassembleShader(pipe, ps_refl, target)
                    if ps_source and len(ps_source) > 50:
                        shader_name = f"PS_EID{event_id}"
                        
                        # 检测格式并转换
                        detected_format = shader_converter.detect_format(ps_source)
                        conversion_stats['total'] += 1
                        
                        if detected_format == ShaderFormat.GLSL:
                            conversion_stats['native_glsl'] += 1
                            shaders_to_analyze.append((ps_source, 'fragment', shader_name))
                        else:
                            result = shader_converter.convert_to_glsl(ps_source, ShaderStage.FRAGMENT)
                            if result.success:
                                conversion_stats['converted'] += 1
                                shaders_to_analyze.append((result.glsl_source, 'fragment', shader_name))
                                if result.warnings:
                                    logger.debug(f"{shader_name} 转换警告: {result.warnings}")
                            else:
                                conversion_stats['failed'] += 1
                                logger.debug(f"{shader_name} 转换失败: {result.error_message}")
                        
                        analyzed_shaders.add(ps_refl.resourceId)
            except Exception as e:
                logger.debug(f"提取 PS 失败 (EID {event_id}): {e}")
        
        # 记录转换统计
        logger.info(f"Shader 格式统计: 原生GLSL={conversion_stats['native_glsl']}, "
                   f"已转换={conversion_stats['converted']}, 转换失败={conversion_stats['failed']}")
        
        logger.info(f"收集到 {len(shaders_to_analyze)} 个可分析 Shader")
        
        if not shaders_to_analyze:
            self._mali_report = {
                'status': 'empty',
                'message': '未找到可分析的 Shader',
                'conversion_stats': conversion_stats
            }
            return
        
        # 批量分析
        batch_result = compiler.analyze_batch(
            shaders_to_analyze,
            gpu=self.options.mali_gpu
        )
        
        # 转换为报告格式
        self._mali_report = self._convert_mali_result_to_report(batch_result)
        
        # 添加转换统计到报告
        self._mali_report['conversion_stats'] = conversion_stats
        
        logger.info(f"Mali 分析完成: {batch_result.success_count}/{batch_result.total_shaders} 成功")
    
    def _convert_mali_result_to_report(self, batch_result) -> Dict[str, Any]:
        """将 MaliBatchAnalysisResult 转换为报告字典格式
        
        转换后的格式与 _generate_mali_html 期望的数据结构匹配。
        """
        # 计算汇总统计
        total_arithmetic = 0.0
        total_texture = 0.0
        total_ls = 0.0
        total_varying = 0.0
        max_registers = 0
        
        shaders_data = []
        
        for result in batch_result.results:
            if not result.success:
                shaders_data.append({
                    'name': result.shader_name,
                    'type': result.shader_type,
                    'status': 'error',
                    'error': result.error_message
                })
                continue
            
            # 累加周期
            total_arithmetic += result.cycles.arithmetic
            total_texture += result.cycles.texture
            total_ls += result.cycles.load_store
            total_varying += result.cycles.varying
            
            # 最大寄存器
            if result.registers.work_registers > max_registers:
                max_registers = result.registers.work_registers
            
            # Shader 数据
            shaders_data.append({
                'name': result.shader_name,
                'type': result.shader_type,
                'status': 'success',
                'cycles': {
                    'arithmetic': result.cycles.arithmetic,
                    'load_store': result.cycles.load_store,
                    'texture': result.cycles.texture,
                    'varying': result.cycles.varying,
                    'total': result.cycles.total,
                    'bound': result.cycles.bound,
                },
                'registers': {
                    'work': result.registers.work_registers,
                    'uniform': result.registers.uniform_registers,
                    'stack_spilling': result.registers.stack_spilling,
                },
                'recommendations': result.recommendations
            })
        
        # 构建最终报告
        return {
            'status': 'success',
            'gpu_name': batch_result.gpu_name,
            'total_shaders': batch_result.total_shaders,
            'success_count': batch_result.success_count,
            'failed_count': batch_result.failed_count,
            'shaders': shaders_data,
            'summary': {
                'total_arithmetic_cycles': round(total_arithmetic, 2),
                'total_texture_cycles': round(total_texture, 2),
                'total_ls_cycles': round(total_ls, 2),
                'total_varying_cycles': round(total_varying, 2),
                'max_work_registers': max_registers,
                'arithmetic_bound_count': len(batch_result.arithmetic_bound_shaders),
                'texture_bound_count': len(batch_result.texture_bound_shaders),
                'high_register_pressure_count': len(batch_result.shaders_with_high_register_pressure),
                'stack_spilling_count': len(batch_result.shaders_with_stack_spilling),
            },
            'problem_shaders': {
                'arithmetic_bound': batch_result.arithmetic_bound_shaders,
                'texture_bound': batch_result.texture_bound_shaders,
                'high_register_pressure': batch_result.shaders_with_high_register_pressure,
                'stack_spilling': batch_result.shaders_with_stack_spilling,
            }
        }
    
    def _sample_resources(self):
        """采样资源数据"""
        if not self._controller:
            return
        
        import renderdoc as rd
        
        self._resource_samples = {}
        
        # 采样纹理缩略图
        if self.options.sample_textures:
            textures = self._resources.get('textures', {})
            for tex_id, tex_info in list(textures.items())[:50]:  # 限制数量
                try:
                    # 尝试获取缩略图
                    # 这里需要实际的 API 调用
                    self._resource_samples[tex_id] = {
                        'type': 'TEXTURE',
                        'info': tex_info,
                        'thumbnail': None,  # 后续实现
                        'format_info': {
                            'width': tex_info.get('width', 0),
                            'height': tex_info.get('height', 0),
                            'format': tex_info.get('format', 'Unknown')
                        }
                    }
                except Exception as e:
                    logger.debug(f"采样纹理 {tex_id} 失败: {e}")
        
        # 采样 Buffer
        if self.options.sample_buffers:
            buffers = self._resources.get('buffers', {})
            for buf_id, buf_info in list(buffers.items())[:100]:  # 限制数量
                try:
                    # 获取 Buffer 数据
                    data = self._controller.GetBufferData(
                        rd.ResourceId.MakeResourceId(buf_id),
                        0,
                        min(buf_info.get('length', 0), self.options.max_buffer_sample_size)
                    )
                    
                    if data:
                        import base64
                        raw_bytes = bytes(data)
                        self._resource_samples[buf_id] = {
                            'type': 'BUFFER',
                            'info': buf_info,
                            'data': base64.b64encode(raw_bytes).decode('utf-8'),
                            'size': len(raw_bytes)
                        }
                except Exception as e:
                    logger.debug(f"采样 Buffer {buf_id} 失败: {e}")
        
        logger.info(f"采样了 {len(self._resource_samples)} 个资源")
        self._report_progress('sample', 1, 1, 
                             f'采样 {len(self._resource_samples)} 个资源')
    
    def _export_reports(self, output_dir: Path) -> List[str]:
        """生成报告"""
        output_files = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(self.rdc_path).stem
        
        # 计算统计指标
        total_vertices = sum(dc.get('numIndices', 0) or 0 for dc in self._draw_calls)
        total_instances = sum(dc.get('numInstances', 1) or 1 for dc in self._draw_calls)
        
        # 计算资源内存
        texture_memory_bytes = sum(
            tex.get('width', 0) * tex.get('height', 0) * tex.get('depth', 1) * 4  # 估算
            for tex in self._resources.get('textures', {}).values()
        )
        buffer_memory_bytes = sum(
            buf.get('length', 0)
            for buf in self._resources.get('buffers', {}).values()
        )
        
        # 构建 coverage/data_quality 信息
        coverage = self._build_coverage_report()
        
        # 构建 suggestions 列表
        suggestions = self._build_suggestions()
        
        # 构建 preflight 建议 (DoD 7.7)
        preflight = self._build_preflight(coverage)
        
        # 将 issues 转换为 CanonicalIssue 格式 (DoD 7.4)
        canonical_issues = self._canonicalize_issues()

        # === Canonical Compare Schema 关键字段 ===
        textures_list = []
        for tex_id, tex_info in self._resources.get('textures', {}).items():
            width = tex_info.get('width', 0)
            height = tex_info.get('height', 0)
            depth = tex_info.get('depth', 1)
            mip_levels = tex_info.get('mips', tex_info.get('mipLevels', 1))
            array_size = tex_info.get('arraysize', tex_info.get('arraySize', 1))
            fmt = str(tex_info.get('format', '')).upper()

            # 估算纹理内存（与 DiffEngine 对齐）
            bpp = 4
            if 'BC' in fmt or 'DXT' in fmt:
                bpp = 1
            elif 'R32G32B32A32' in fmt:
                bpp = 16
            elif 'R16G16B16A16' in fmt:
                bpp = 8
            base = width * height * depth * bpp
            if mip_levels and mip_levels > 1:
                base = int(base * 1.33)
            memory_size = base * (array_size or 1)

            textures_list.append({
                "resourceId": str(tex_info.get('id', tex_id)),
                "name": tex_info.get('name', f"Texture_{tex_id}"),
                "width": width,
                "height": height,
                "depth": depth,
                "format": tex_info.get('format', ''),
                "mipLevels": mip_levels or 1,
                "arraySize": array_size or 1,
                "memorySize": memory_size,
            })

        buffers_list = []
        for buf_id, buf_info in self._resources.get('buffers', {}).items():
            buffers_list.append({
                "resourceId": str(buf_info.get('id', buf_id)),
                "name": buf_info.get('name', f"Buffer_{buf_id}"),
                "size": buf_info.get('length', buf_info.get('size', 0)),
                "usage": buf_info.get('usage', ''),
            })

        shaders_list = []
        if self._mali_report and self._mali_report.get('shaders'):
            for shader in self._mali_report.get('shaders', []):
                name = shader.get('name', '')
                shader_type = shader.get('type', '')
                resource_id = shader.get('resourceId') or shader.get('hash') or name
                shaders_list.append({
                    "resourceId": str(resource_id),
                    "name": name,
                    "type": shader_type,
                })

        draw_calls_list = []
        for dc in self._draw_calls:
            draw_calls_list.append({
                "eventId": dc.get('eventId', 0),
                "name": dc.get('name', ''),
                "indexCount": dc.get('numIndices', dc.get('indexCount', 0)) or 0,
                "vertexCount": dc.get('numVerts', dc.get('vertexCount', 0)) or 0,
                "instanceCount": dc.get('numInstances', dc.get('instanceCount', 1)) or 1,
                "flags": dc.get('flags', 0),
            })
        
        total_triangles = sum(
            ((dc.get('numIndices', 0) or dc.get('numVerts', 0)) // 3) *
            (dc.get('numInstances', 1) or 1)
            for dc in self._draw_calls
        )
        pipeline_count = self._pipeline_sampling_result.sampled_count if self._pipeline_sampling_result else 0
        shader_count = len(shaders_list)
        if shader_count == 0 and self._pipeline_sampling_result:
            shader_count = self._pipeline_sampling_result.unique_shaders

        # 准备分析数据 - Canonical Schema v1.0
        analysis_data = {
            'schema_version': '1.0',
            'meta': {
                'rdc_path': self.rdc_path,
                'api': self._api,
                'platform': self.options.platform,
                'timestamp': datetime.now().isoformat(),
                'analyzer_version': '2.0.0',
                'renderdoc_version': self._get_renderdoc_version()
            },
            'summary': {
                'total_events': len(self._events),
                'draw_call_count': len(self._draw_calls),
                'dispatch_count': sum(1 for e in self._events if 'Dispatch' in str(e.get('name', ''))),
                'total_vertices': total_vertices,
                'total_triangles': total_triangles,
                'total_instances': total_instances,
                'texture_count': len(textures_list),
                'buffer_count': len(buffers_list),
                'shader_count': shader_count,
                'texture_memory_mb': round(texture_memory_bytes / (1024 * 1024), 2),
                'buffer_memory_mb': round(buffer_memory_bytes / (1024 * 1024), 2),
                'issue_count': len(self._issues),
                'suggestion_count': len(suggestions),
                'pipeline_count': pipeline_count,
                'driver': 'Unknown',
                'gpu_core': (self._mali_report.get('gpu_name') if self._mali_report else self.options.mali_gpu),
            },
            'statistics': {
                'totalDrawCalls': len(draw_calls_list),
                'totalVertices': total_vertices,
                'totalTriangles': total_triangles,
                'dispatchCalls': sum(1 for e in self._events if 'Dispatch' in str(e.get('name', ''))),
                'textureCount': len(textures_list),
                'shaderCount': shader_count,
                'bufferCount': len(buffers_list),
                'shaderChanges': 0,
                'renderTargetSwitches': 0,
            },
            'coverage': coverage,
            'events': self._events[:1000],  # 限制大小
            'draw_calls': draw_calls_list,
            'textures': textures_list,
            'shaders': shaders_list,
            'buffers': buffers_list,
            'resources': self._resources,
            'resource_samples': self._resource_samples,
            'pipeline_samples': (
                self._pipeline_sampling_result.to_dict() 
                if self._pipeline_sampling_result else None
            ),
            'issues': canonical_issues,
            'suggestions': suggestions,
            'preflight': preflight
        }
        
        # 导出 JSON
        if 'json' in self.options.output_formats:
            json_path = output_dir / f"{base_name}_{timestamp}.json"
            import json
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False, default=str)
            output_files.append(str(json_path))
            logger.info(f"已生成 JSON: {json_path}")
        
        # 导出 HTML
        if 'html' in self.options.output_formats:
            html_path = output_dir / f"{base_name}_{timestamp}.html"
            self._export_html(analysis_data, html_path)
            output_files.append(str(html_path))
            logger.info(f"已生成 HTML: {html_path}")
        
        self._report_progress('export', 1, 1, f'生成 {len(output_files)} 个文件')
        return output_files
    
    def _export_html(self, analysis_data: Dict[str, Any], output_path: Path):
        """导出 HTML 报告"""
        from .exporters.html_exporter import HTMLExporter, HTMLExportConfig
        from .core.pipeline_state import DrawCallDetail, DrawType, PipelineSnapshot
        from .analysis.resource_tracker import ResourceLifetime, ResourceType
        from .analysis.call_analyzer import BindingIssue, IssueSeverity, IssueCategory
        
        # 创建配置
        config = HTMLExportConfig(
            title=f"RDC Analysis - {Path(self.rdc_path).stem}",
            theme='dark'
        )
        
        # 使用现有导出器
        exporter = HTMLExporter(config)
        
        # 转换数据格式以匹配导出器期望
        # 使用真正的 DrawCallDetail dataclass，而非 type() 创建伪对象
        draw_call_details = []
        for dc in self._draw_calls:
            # 确定 DrawType
            if dc.get('numIndices', 0) > 0:
                draw_type = DrawType.DRAW_INDEXED
            elif dc.get('numInstances', 0) > 1:
                draw_type = DrawType.DRAW_INSTANCED
            elif 'Dispatch' in dc.get('name', ''):
                draw_type = DrawType.DISPATCH
            elif 'Clear' in dc.get('name', ''):
                draw_type = DrawType.CLEAR_RTV
            else:
                draw_type = DrawType.DRAW
            
            # 使用真正的 DrawCallDetail，缺失字段使用 dataclass 默认值
            detail = DrawCallDetail(
                event_id=dc['eventId'],
                name=dc['name'],
                draw_type=draw_type,
                vertex_count=dc.get('numIndices', 0) or dc.get('numVerts', 0) or 0,
                index_count=dc.get('numIndices', 0) or 0,
                instance_count=dc.get('numInstances', 1) or 1,
                # 其他字段使用 dataclass 默认值（0, None, "" 等）
                # 不再伪造 render_targets, vs_shader, ps_shader 等
            )
            draw_call_details.append(detail)
        
        # 资源生命周期 - 优先使用 ResourceTracker 结果
        resource_lifetimes_dict = {}
        if self._resource_lifetimes:
            resource_lifetimes_dict = dict(self._resource_lifetimes)
        
        # 对未追踪到的资源补充估算占位（保持报告完整性）
        for tex_id, tex_info in self._resources.get('textures', {}).items():
            if tex_id in resource_lifetimes_dict:
                continue
            lifetime = ResourceLifetime(
                resource_id=tex_id,
                resource_name=tex_info.get('name', f'Texture_{tex_id}'),
                resource_type=ResourceType.TEXTURE_2D,
                format=tex_info.get('format', ''),
                width=tex_info.get('width', 0),
                height=tex_info.get('height', 0),
                depth=tex_info.get('depth', 1),
            )
            lifetime.first_access_event = -1  # 估算
            lifetime.last_access_event = -1
            lifetime.read_count = -1
            lifetime._data_status = 'estimated'
            resource_lifetimes_dict[tex_id] = lifetime
        
        for buf_id, buf_info in self._resources.get('buffers', {}).items():
            if buf_id in resource_lifetimes_dict:
                continue
            lifetime = ResourceLifetime(
                resource_id=buf_id,
                resource_name=buf_info.get('name', f'Buffer_{buf_id}'),
                resource_type=ResourceType.BUFFER,
                size_bytes=buf_info.get('length', 0),
            )
            lifetime.first_access_event = -1
            lifetime.last_access_event = -1
            lifetime.read_count = -1
            lifetime._data_status = 'estimated'
            resource_lifetimes_dict[buf_id] = lifetime
        
        # 问题列表 - 使用真正的 BindingIssue 类
        issues = []
        for issue in self._issues:
            try:
                severity_str = issue.get('severity', 'warning').upper()
                severity = IssueSeverity[severity_str] if severity_str in IssueSeverity.__members__ else IssueSeverity.WARNING
            except (KeyError, AttributeError):
                severity = IssueSeverity.WARNING
            
            # 从 issue code 推断 category
            code = issue.get('code', 'UNKNOWN')
            if 'PERF' in code or 'OPTIM' in code:
                category = IssueCategory.PERFORMANCE
            elif 'BIND' in code or 'RES' in code:
                category = IssueCategory.CORRECTNESS
            else:
                category = IssueCategory.BEST_PRACTICE
            
            binding_issue = BindingIssue(
                rule_id=code,
                severity=severity,
                category=category,
                event_id=issue.get('eventId', 0),
                message=issue.get('message', ''),
                suggestion=issue.get('suggestion', '')
            )
            issues.append(binding_issue)
        
        # 导出（包含性能报告和 Mali 报告）
        html_content = exporter.export(
            draws=draw_call_details,
            issues=issues,
            lifetimes=resource_lifetimes_dict,  # 传递资源生命周期数据
            performance_report=self._performance_report,
            mali_report=self._mali_report
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _cleanup(self):
        """清理资源"""
        if self._controller:
            try:
                self._controller.Shutdown()
            except:
                pass
            self._controller = None
        
        if self._capture:
            try:
                self._capture.Shutdown()
            except:
                pass
            self._capture = None
    
    def _get_renderdoc_version(self) -> str:
        """获取 RenderDoc 版本号"""
        try:
            import renderdoc as rd
            if hasattr(rd, 'GetVersionString'):
                return rd.GetVersionString()
            elif hasattr(rd, 'RENDERDOC_VERSION'):
                return str(rd.RENDERDOC_VERSION)
            return 'unknown'
        except Exception:
            return 'unknown'
    
    def _build_coverage_report(self) -> Dict[str, Any]:
        """构建数据覆盖率/质量报告
        
        检测各数据源的实际可用性，区分:
        - present: 有真实数据
        - partial: 部分有真实数据
        - estimated: 使用估算值
        - missing: 完全缺失
        
        Returns:
            Dict 包含各数据面的覆盖状态
        """
        coverage = {
            'overall': 'medium',  # 默认中等可信度
            'details': {},
            'missing_items': [],
            'confidence_reasons': [],
            'sampling_stats': {}  # 采样统计
        }
        
        # === 1. 检查事件数据 ===
        if self._events:
            coverage['details']['events'] = 'present'
        else:
            coverage['details']['events'] = 'missing'
            coverage['missing_items'].append('事件列表为空')
        
        # === 2. 检查 Draw Call 数据 ===
        if self._draw_calls:
            coverage['details']['draw_calls'] = 'present'
        else:
            coverage['details']['draw_calls'] = 'missing'
            coverage['missing_items'].append('未检测到 Draw Call')
        
        # === 3. 检查资源数据 ===
        has_textures = bool(self._resources.get('textures'))
        has_buffers = bool(self._resources.get('buffers'))
        
        if has_textures and has_buffers:
            coverage['details']['resources'] = 'present'
        elif has_textures or has_buffers:
            coverage['details']['resources'] = 'partial'
            coverage['missing_items'].append('资源数据不完整')
        else:
            coverage['details']['resources'] = 'missing'
            coverage['missing_items'].append('无资源数据')
        
        # === 4. 检查 Marker 数据 ===
        has_markers = any(
            e.get('depth', 0) > 0 or 
            any(keyword in str(e.get('name', '')) for keyword in ['Begin', 'End', 'Push', 'Pop'])
            for e in self._events
        )
        coverage['details']['markers'] = 'present' if has_markers else 'missing'
        if not has_markers:
            coverage['missing_items'].append('未检测到 Render Markers（建议开启 Marker/Annotation）')
        
        # === 5. 检查 Pipeline State ===
        # Pipeline State 采样覆盖率判断
        total_draws = len(self._draw_calls)
        sampled_draws = self._pipeline_state_samples
        
        if sampled_draws > 0 and total_draws > 0:
            sample_ratio = sampled_draws / total_draws
            coverage['sampling_stats']['pipeline_state'] = {
                'sampled': sampled_draws,
                'total': total_draws,
                'ratio': round(sample_ratio, 3)
            }
            
            if sample_ratio >= 0.9:
                coverage['details']['pipeline_state'] = 'present'
                coverage['confidence_reasons'].append(
                    f'Pipeline State 覆盖率: {sample_ratio*100:.1f}% ({sampled_draws}/{total_draws})'
                )
            elif sample_ratio >= 0.3:
                coverage['details']['pipeline_state'] = 'partial'
                coverage['confidence_reasons'].append(
                    f'Pipeline State 部分采样: {sample_ratio*100:.1f}% ({sampled_draws}/{total_draws})'
                )
            else:
                coverage['details']['pipeline_state'] = 'estimated'
                coverage['confidence_reasons'].append(
                    f'Pipeline State 采样不足: {sample_ratio*100:.1f}% ({sampled_draws}/{total_draws})'
                )
        else:
            coverage['details']['pipeline_state'] = 'estimated'
            coverage['confidence_reasons'].append('Pipeline State 使用估算值（未进行真实回放）')
        
        # === 6. 检查资源生命周期 ===
        if self._resource_lifecycle_tracked:
            # 根据采样覆盖率标记 present/partial
            if total_draws > 0 and sampled_draws > 0:
                sample_ratio = sampled_draws / total_draws
                if sample_ratio >= 0.9:
                    coverage['details']['resource_lifecycle'] = 'present'
                else:
                    coverage['details']['resource_lifecycle'] = 'partial'
                    coverage['confidence_reasons'].append(
                        f'资源生命周期采样不足: {sample_ratio*100:.1f}% ({sampled_draws}/{total_draws})'
                    )
            else:
                coverage['details']['resource_lifecycle'] = 'present'
        else:
            # 如果有资源采样数据，视为部分可用
            if self._resource_samples:
                coverage['details']['resource_lifecycle'] = 'partial'
                coverage['confidence_reasons'].append(
                    f'资源生命周期：基于 {len(self._resource_samples)} 个采样推断'
                )
            else:
                coverage['details']['resource_lifecycle'] = 'estimated'
                coverage['confidence_reasons'].append('资源生命周期使用估算值')
        
        # === 7. 检查 Shader 分析数据 ===
        if self._mali_report and self._mali_report.get('status') == 'success':
            success_count = self._mali_report.get('success_count', 0)
            total_shaders = self._mali_report.get('total_shaders', 0)
            if success_count > 0:
                coverage['details']['shader_analysis'] = 'present'
                coverage['sampling_stats']['shader_analysis'] = {
                    'analyzed': success_count,
                    'total': total_shaders
                }
            else:
                coverage['details']['shader_analysis'] = 'missing'
        else:
            coverage['details']['shader_analysis'] = 'missing'
        
        # === 8. 检查性能分析数据 ===
        if self._performance_report and self._performance_report.get('overall_score') is not None:
            coverage['details']['performance_metrics'] = 'present'
        else:
            coverage['details']['performance_metrics'] = 'missing'
        
        # === 计算整体可信度 ===
        present_count = sum(1 for v in coverage['details'].values() if v == 'present')
        partial_count = sum(1 for v in coverage['details'].values() if v == 'partial')
        estimated_count = sum(1 for v in coverage['details'].values() if v == 'estimated')
        total_count = len(coverage['details'])
        
        # 加权计算 (present=1.0, partial=0.5, estimated=0.2)
        effective_present = present_count + partial_count * 0.5 + estimated_count * 0.2
        coverage_ratio = effective_present / total_count if total_count > 0 else 0
        
        if coverage_ratio >= 0.8:
            coverage['overall'] = 'high'
        elif coverage_ratio >= 0.5:
            coverage['overall'] = 'medium'
        else:
            coverage['overall'] = 'low'
        
        return coverage
    
    def _build_preflight(self, coverage: Dict[str, Any]) -> Dict[str, Any]:
        """构建 Preflight 检查结果 (DoD 7.7)
        
        当关键数据缺失时，提示用户如何改进抓帧配置。
        
        Args:
            coverage: 覆盖率报告
            
        Returns:
            Dict 包含 preflight 检查结果
        """
        preflight = {
            'status': 'ok',  # ok | warning | error
            'missing_data': [],
            'capture_recommendations': [],
            'degraded_conclusions': []
        }
        
        details = coverage.get('details', {})
        missing = coverage.get('missing_items', [])
        
        # 检查 Marker 数据
        if details.get('markers') == 'missing':
            preflight['status'] = 'warning'
            preflight['missing_data'].append({
                'item': 'Debug Markers',
                'impact': '无法识别渲染 Pass 边界，难以分析渲染管线结构',
                'severity': 'medium'
            })
            preflight['capture_recommendations'].append({
                'action': '启用 Debug Markers',
                'unity': '确保 FrameDebugger 打开时抓帧，或使用 BeginSample/EndSample',
                'unreal': '确保 RenderDoc 插件已启用，UE 会自动添加 Markers',
                'custom': '使用 ID3D11UserDefinedAnnotation::BeginEvent (D3D11) 或 vkCmdDebugMarkerBegin (Vulkan)',
                'docs_link': 'https://renderdoc.org/docs/how/how_annotate_capture.html'
            })
            preflight['degraded_conclusions'].append('Pass 结构分析将使用启发式推断，准确性降低')
        
        # 检查 Pipeline State
        if details.get('pipeline_state') in ['missing', 'estimated']:
            preflight['status'] = 'warning'
            preflight['missing_data'].append({
                'item': 'Pipeline State',
                'impact': '无法分析 Shader/Blend/Depth 状态变化',
                'severity': 'high'
            })
            preflight['degraded_conclusions'].append('状态变更统计将使用估算值')
        
        # 检查资源生命周期
        if details.get('resource_lifecycle') in ['missing', 'estimated']:
            preflight['missing_data'].append({
                'item': 'Resource Lifecycle',
                'impact': '无法追踪资源创建/销毁时机',
                'severity': 'low'
            })
        
        # 检查 Shader 分析
        if details.get('shader_analysis') == 'missing':
            preflight['missing_data'].append({
                'item': 'Shader Analysis',
                'impact': '无法进行 Shader 复杂度分析',
                'severity': 'medium'
            })
            preflight['capture_recommendations'].append({
                'action': '确保 Shader 包含调试信息',
                'unity': '在 Player Settings > Other Settings 中禁用 Shader Stripping',
                'unreal': '在 Project Settings > Rendering 中启用 Keep Shader Debug Info',
                'custom': '编译 Shader 时使用 /Zi (HLSL) 或 -g (GLSL)'
            })
        
        # 如果有多个问题，升级状态
        if len(preflight['missing_data']) >= 3:
            preflight['status'] = 'error'
        
        return preflight
    
    def _canonicalize_issues(self) -> List[Dict[str, Any]]:
        """将所有 issues 转换为 CanonicalIssue 格式 (DoD 7.4)
        
        确保每个 issue 都有 event_ids 和 resource_ids 用于 Evidence Chain。
        
        Returns:
            List of issue dicts in canonical format
        """
        from .core.types import CanonicalIssue
        
        canonical_list = []
        
        for issue in self._issues:
            if isinstance(issue, dict):
                # 已经是 dict 格式，转换为 CanonicalIssue
                event_ids = []
                resource_ids = []
                
                # 提取 event_id (兼容 event_id 和 eventId 两种命名)
                if 'event_id' in issue and issue['event_id'] is not None:
                    event_ids.append(issue['event_id'])
                elif 'eventId' in issue and issue['eventId'] is not None:
                    # 兼容驼峰命名 (从 _analyze_rules 等处产生)
                    event_ids.append(issue['eventId'])
                if 'event_ids' in issue:
                    event_ids.extend(issue['event_ids'])
                if 'eventIds' in issue:
                    # 兼容驼峰命名
                    event_ids.extend(issue['eventIds'])
                if 'related_events' in issue:
                    event_ids.extend(issue['related_events'])
                
                # 提取 resource_id
                if 'resource_id' in issue and issue['resource_id']:
                    resource_ids.append(str(issue['resource_id']))
                if 'resource_ids' in issue:
                    resource_ids.extend([str(r) for r in issue['resource_ids']])
                
                # 构建 evidence
                evidence = {}
                for key in ['threshold', 'actual', 'impact_score', 'pass_index', 'location_path']:
                    if key in issue and issue[key] is not None:
                        evidence[key] = issue[key]
                
                canonical = CanonicalIssue(
                    code=issue.get('code', 'UNKNOWN'),
                    severity=issue.get('severity', 'info'),
                    category=issue.get('category', 'general'),
                    message=issue.get('message', ''),
                    event_ids=list(set(event_ids)),  # 去重
                    resource_ids=list(set(resource_ids)),  # 去重
                    evidence=evidence,
                    suggestion=issue.get('suggestion')
                )
                canonical_list.append(canonical.to_dict())
            
            elif hasattr(issue, 'to_canonical'):
                # 有 to_canonical 方法的对象
                canonical_list.append(issue.to_canonical().to_dict())
            
            elif hasattr(issue, 'to_dict'):
                # 有 to_dict 方法的对象
                canonical_list.append(issue.to_dict())
            
            else:
                # 其他情况，尝试转为 dict
                canonical_list.append({
                    'code': getattr(issue, 'code', 'UNKNOWN'),
                    'severity': getattr(issue, 'severity', 'info'),
                    'category': getattr(issue, 'category', 'general'),
                    'message': str(issue)
                })
        
        return canonical_list
    
    def _build_suggestions(self) -> List[Dict[str, Any]]:
        """构建建议列表
        
        基于发现的 issues 和性能分析结果生成可执行建议。
        每条建议包含: steps, expected_impact, risk, verification_plan
        
        Returns:
            List of suggestion dicts
        """
        suggestions = []
        
        # 从性能报告提取建议
        if self._performance_report:
            for rec in self._performance_report.get('recommendations', []):
                text = rec.get('text', rec) if isinstance(rec, dict) else str(rec)
                priority = rec.get('priority', 'medium') if isinstance(rec, dict) else 'medium'
                
                suggestion = self._create_suggestion_from_recommendation(text, priority)
                if suggestion:
                    suggestions.append(suggestion)
        
        # 从 issues 生成建议
        for issue in self._issues:
            if isinstance(issue, dict):
                code = issue.get('code', '')
            else:
                code = getattr(issue, 'code', '')
            
            # 根据不同类型的 issue 生成建议
            if code in ('BIND001', 'RD_DC_001'):  # Draw Call 过多
                suggestions.append({
                    'id': f'SUG_{code}',
                    'title': '减少 Draw Call 数量',
                    'priority': 'high',
                    'confidence': 'high',
                    'related_issue': code,
                    'steps': [
                        '使用 Static/Dynamic Batching 合并相同材质的物体',
                        '使用 GPU Instancing 批量绘制相同 Mesh',
                        '合并小型 Mesh 为单个大 Mesh（Mesh Combine）',
                        '检查是否有不必要的渲染 Pass'
                    ],
                    'expected_impact': {
                        'metric': 'draw_call_count',
                        'direction': 'decrease',
                        'estimate': '可减少 30-70% Draw Call'
                    },
                    'risk': '合并可能影响裁剪效率，需要平衡',
                    'engine_howto': {
                        'unity': '开启 Player Settings > Static Batching; 使用 DrawMeshInstanced()',
                        'unreal': '使用 Instanced Static Mesh Component; 开启 Merge Actors',
                        'custom': '实现 Instance Buffer，批量提交相同 Mesh'
                    },
                    'verification_plan': {
                        'metrics': ['draw_call_count', 'batch_count'],
                        'expected_direction': 'decrease',
                        'how_to_capture': '抓取优化后的帧，对比 Draw Call 数量'
                    }
                })
            
            elif code in ('BIND002', 'RD_DC_005'):  # 顶点数过多
                suggestions.append({
                    'id': f'SUG_{code}',
                    'title': '优化顶点数量',
                    'priority': 'high',
                    'confidence': 'high',
                    'related_issue': code,
                    'steps': [
                        '使用 LOD（Level of Detail）系统',
                        '简化远处物体的 Mesh',
                        '检查是否有被遮挡但仍在渲染的物体',
                        '使用 Occlusion Culling 剔除不可见物体'
                    ],
                    'expected_impact': {
                        'metric': 'total_vertices',
                        'direction': 'decrease',
                        'estimate': '可减少 20-50% 顶点'
                    },
                    'risk': '过度简化可能影响画质',
                    'engine_howto': {
                        'unity': '使用 LOD Group 组件; 开启 Occlusion Culling',
                        'unreal': '配置 LOD Settings; 使用 HLOD',
                        'custom': '实现视距 LOD 切换逻辑'
                    },
                    'verification_plan': {
                        'metrics': ['total_vertices', 'total_triangles'],
                        'expected_direction': 'decrease',
                        'how_to_capture': '对比优化前后的顶点/三角形数量'
                    }
                })
            
            elif code == 'PERF005':  # 未压缩纹理
                suggestions.append({
                    'id': f'SUG_{code}',
                    'title': '压缩纹理以减少内存和带宽',
                    'priority': 'medium',
                    'confidence': 'high',
                    'related_issue': code,
                    'steps': [
                        '将 RGBA32 纹理转换为 BC/DXT 格式（PC）',
                        '将纹理转换为 ASTC 格式（Mobile）',
                        '对法线贴图使用专用压缩格式（BC5/ASTC）',
                        '检查是否需要 Alpha 通道'
                    ],
                    'expected_impact': {
                        'metric': 'texture_memory_mb',
                        'direction': 'decrease',
                        'estimate': '可减少 60-75% 纹理内存'
                    },
                    'risk': '压缩可能导致轻微画质损失，尤其是渐变区域',
                    'engine_howto': {
                        'unity': '在 Texture Import Settings 中选择 Compression 格式',
                        'unreal': '在 Texture Editor 中设置 Compression Settings',
                        'custom': '使用 texconv/compressonator 工具压缩'
                    },
                    'verification_plan': {
                        'metrics': ['texture_memory_mb'],
                        'expected_direction': 'decrease',
                        'how_to_capture': '对比压缩前后的纹理内存占用'
                    }
                })
            
            elif code == 'PERF004':  # 大纹理
                suggestions.append({
                    'id': f'SUG_{code}',
                    'title': '降低大尺寸纹理分辨率',
                    'priority': 'medium',
                    'confidence': 'medium',
                    'related_issue': code,
                    'steps': [
                        '评估纹理实际显示尺寸（屏幕像素）',
                        '根据使用场景降低纹理分辨率',
                        '使用 Mipmap 避免远距离采样大纹理',
                        '考虑使用 Virtual Texturing（如适用）'
                    ],
                    'expected_impact': {
                        'metric': 'texture_memory_mb',
                        'direction': 'decrease',
                        'estimate': '每降一级约减少 75% 内存'
                    },
                    'risk': '近距离观察可能模糊',
                    'engine_howto': {
                        'unity': '在 Texture Import 中设置 Max Size; 开启 Generate Mip Maps',
                        'unreal': '设置 Maximum Texture Size; 使用 Texture Streaming',
                        'custom': '预处理时生成低分辨率版本'
                    },
                    'verification_plan': {
                        'metrics': ['texture_memory_mb', 'texture_count'],
                        'expected_direction': 'decrease',
                        'how_to_capture': '对比优化前后的纹理内存占用'
                    }
                })
        
        return suggestions
    
    def _create_suggestion_from_recommendation(self, text: str, priority: str) -> Optional[Dict[str, Any]]:
        """从简单建议文本创建结构化建议"""
        # 解析建议类型
        text_lower = text.lower()
        
        if '批次' in text or 'batch' in text_lower:
            return {
                'id': 'SUG_BATCH',
                'title': '优化批次绘制',
                'priority': priority,
                'confidence': 'medium',
                'steps': [text],
                'expected_impact': {
                    'metric': 'draw_call_count',
                    'direction': 'decrease',
                    'estimate': '视具体情况而定'
                },
                'risk': '需要评估合并后的裁剪效率',
                'verification_plan': {
                    'metrics': ['draw_call_count'],
                    'expected_direction': 'decrease',
                    'how_to_capture': '对比优化前后 Draw Call 数量'
                }
            }
        
        elif '压缩' in text or 'compress' in text_lower:
            return {
                'id': 'SUG_COMPRESS',
                'title': '压缩纹理',
                'priority': priority,
                'confidence': 'medium',
                'steps': [text],
                'expected_impact': {
                    'metric': 'texture_memory_mb',
                    'direction': 'decrease',
                    'estimate': '视具体情况而定'
                },
                'risk': '可能轻微影响画质',
                'verification_plan': {
                    'metrics': ['texture_memory_mb'],
                    'expected_direction': 'decrease',
                    'how_to_capture': '对比优化前后纹理内存'
                }
            }
        
        elif '分辨率' in text or 'resolution' in text_lower or '纹理' in text:
            return {
                'id': 'SUG_TEXTURE',
                'title': '优化纹理',
                'priority': priority,
                'confidence': 'medium',
                'steps': [text],
                'expected_impact': {
                    'metric': 'texture_memory_mb',
                    'direction': 'decrease',
                    'estimate': '视具体情况而定'
                },
                'risk': '可能影响画质',
                'verification_plan': {
                    'metrics': ['texture_memory_mb'],
                    'expected_direction': 'decrease',
                    'how_to_capture': '对比优化前后纹理内存'
                }
            }
        
        # 通用建议
        return {
            'id': 'SUG_GENERAL',
            'title': '性能优化建议',
            'priority': priority,
            'confidence': 'low',
            'steps': [text],
            'expected_impact': {
                'metric': 'performance',
                'direction': 'improve',
                'estimate': '视具体情况而定'
            },
            'risk': '需要具体评估',
            'verification_plan': {
                'metrics': ['frame_time'],
                'expected_direction': 'decrease',
                'how_to_capture': '对比优化前后帧时间'
            }
        }
    
    def _create_summary(self, duration: float, output_files: List[str]) -> AnalysisSummary:
        """创建分析摘要"""
        total_vertices = sum(dc.get('numIndices', 0) or 0 for dc in self._draw_calls)
        
        error_count = len([i for i in self._issues if i['severity'] == 'error'])
        warning_count = len([i for i in self._issues if i['severity'] == 'warning'])
        info_count = len([i for i in self._issues if i['severity'] == 'info'])
        
        return AnalysisSummary(
            rdc_path=self.rdc_path,
            api=self._api,
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration,
            total_events=len(self._events),
            draw_call_count=len(self._draw_calls),
            total_vertices=total_vertices,
            total_triangles=total_vertices // 3,
            texture_count=len(self._resources.get('textures', {})),
            buffer_count=len(self._resources.get('buffers', {})),
            shader_count=0,  # 后续实现
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            output_files=output_files
        )


def analyze(
    rdc_path: str,
    output_dir: str = "./output",
    **kwargs
) -> AnalysisSummary:
    """
    便捷分析函数
    
    Args:
        rdc_path: RDC 文件路径
        output_dir: 输出目录
        **kwargs: 传递给 AnalysisOptions 的其他参数，包括:
            - enable_mali_analysis (bool): 启用 Mali GPU 分析
            - mali_gpu (str): 目标 Mali GPU 型号 (默认: "Mali-G78")
            - malioc_path (str): malioc 可执行文件路径
            - enable_tile_analysis (bool): 启用 Tile-Based 分析
            - tile_gpu (str): 目标 Tile GPU 型号 (默认: "Generic-Tile")
            - enable_adreno_analysis (bool): 启用 Adreno 分析
            - adreno_mode (str): Adreno 分析模式 ("heuristic" | "profiler" | "auto")
            - adreno_profiler_path (str): Snapdragon Profiler CLI 路径
            - enable_performance_analysis (bool): 启用性能分析
            - platform (str): 目标平台 ("pc" 或 "mobile")
        
    Returns:
        AnalysisSummary: 分析结果摘要
        
    Example:
        >>> from rdc_analyzer.main import analyze
        >>> # 基本用法
        >>> result = analyze("capture.rdc", output_dir="./report")
        >>> print(f"发现 {result.warning_count} 个警告")
        >>> 
        >>> # 启用 Mali GPU 分析
        >>> result = analyze("capture.rdc", 
        ...                  enable_mali_analysis=True,
        ...                  mali_gpu="Mali-G78")
    """
    # 创建选项
    options = AnalysisOptions(output_dir=output_dir, **kwargs)
    
    # 创建并运行管线
    pipeline = AnalysisPipeline(rdc_path, options)
    return pipeline.run()


def analyze_with_progress(
    rdc_path: str,
    output_dir: str = "./output",
    progress_callback: Optional[ProgressCallback] = None,
    **kwargs
) -> AnalysisSummary:
    """
    带进度回调的分析函数
    
    Args:
        rdc_path: RDC 文件路径
        output_dir: 输出目录
        progress_callback: 进度回调函数
        **kwargs: 传递给 AnalysisOptions 的其他参数
        
    Returns:
        AnalysisSummary: 分析结果摘要
    """
    options = AnalysisOptions(output_dir=output_dir, **kwargs)
    pipeline = AnalysisPipeline(rdc_path, options, progress_callback)
    return pipeline.run()


if __name__ == "__main__":
    # 简单测试
    import sys
    if len(sys.argv) > 1:
        result = analyze(sys.argv[1])
        print(f"\n分析完成:")
        print(f"  Draw Calls: {result.draw_call_count}")
        print(f"  纹理: {result.texture_count}")
        print(f"  Buffer: {result.buffer_count}")
        print(f"  警告: {result.warning_count}")
        print(f"  输出文件: {result.output_files}")
    else:
        print("用法: python -m rdc_analyzer.main <rdc_file>")
