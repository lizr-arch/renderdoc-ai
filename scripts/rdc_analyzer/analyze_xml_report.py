#!/usr/bin/env python3


"""


XML 离线分析报告生成器





从 RenderDoc 导出的 XML 文件生成包含性能分析的 HTML 报告。


整合 parse_rdc_xml -> XMLToContextBridge -> PerformanceAnalyzer -> generate_offline_html 流程。





用法:


    py -3 analyze_xml_report.py capture.xml -o report.html


    py -3 analyze_xml_report.py capture.xml --texture-dir textures/


    


依赖:


    - parse_rdc_xml.py (XML 解析器)


    - core/bridge.py (XMLToContextBridge)


    - analyzers/performance_analyzer.py (PerformanceAnalyzer)


    - generate_offline_report.py (HTML 生成器)





Author: RenderDoc Analyzer


Version: 1.0.0


"""





import sys
import os
import importlib.util
import shutil
import subprocess

import json

import argparse

from pathlib import Path

from datetime import datetime

from typing import Dict, List, Any, Optional



# Data richness baseline (RenderDoc fields)

from schema.data_richness_baseline import (

    ACTION_FIELD_MAP,

    TEXTURE_FIELD_MAP,

    compute_field_coverage,

    MISSING_REASON_REPLAY,

)

# 确保可以导入本地模块


SCRIPT_DIR = Path(__file__).parent.resolve()


if str(SCRIPT_DIR) not in sys.path:


    sys.path.insert(0, str(SCRIPT_DIR))

from schema import rdc_manifest
from tools import report_linking









def log(msg: str):


    """输出日志"""


    print(f"[analyze_xml_report] {msg}")


def _supports_renderdoccmd_export(binary: Path) -> bool:
    """检测 renderdoccmd 是否支持 export 子命令"""
    try:
        result = subprocess.run(
            [str(binary), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return False

    output = "\n".join([result.stdout or "", result.stderr or ""]).lower()
    return "\n  export" in output or " export " in output


def _resolve_renderdoccmd(
    explicit_path: Optional[str] = None,
    require_export: bool = False,
) -> Optional[Path]:
    """尝试解析 renderdoccmd.exe 的绝对路径（可要求支持 export）"""
    def _is_usable(path: Path) -> bool:
        if not path.exists():
            return False
        return (not require_export) or _supports_renderdoccmd_export(path)

    if explicit_path:
        candidate = Path(explicit_path)
        if _is_usable(candidate):
            return candidate

    env_path = os.environ.get("RENDERDOCCMD")
    if env_path:
        candidate = Path(env_path)
        if _is_usable(candidate):
            return candidate

    repo_root = SCRIPT_DIR.parent.parent
    preferred = [
        repo_root / "x64" / "Development" / "renderdoccmd.exe",
        repo_root / "dist" / "RenderDoc-CrossGPU-Patch" / "renderdoccmd.exe",
    ]
    fallback = [
        Path(r"C:\Program Files\RenderDoc\renderdoccmd.exe"),
        Path(r"C:\Program Files\RenderDoc\x86\renderdoccmd.exe"),
    ]

    resolved = shutil.which("renderdoccmd")
    if not resolved:
        resolved = shutil.which("renderdoccmd.exe")
    if resolved:
        fallback.append(Path(resolved))

    for candidate in preferred + fallback:
        if _is_usable(candidate):
            return candidate

    return None


def _resolve_zip_path(xml_path: Path) -> Optional[Path]:
    """根据 XML 路径推断 ZIP 资产文件路径"""
    if xml_path.name.endswith(".zip.xml"):
        return xml_path.parent / xml_path.name[:-4]
    if xml_path.suffix.lower() == ".xml":
        return xml_path.with_suffix("")
    return None


def _resolve_rdc_from_xml(xml_path: Path, rdc_hint: Optional[Path] = None) -> Optional[Path]:
    """根据 XML/ZIP.XML 输入推断对应的 RDC 路径"""
    if rdc_hint and rdc_hint.exists():
        return rdc_hint

    if xml_path.suffix.lower() == ".rdc" and xml_path.exists():
        return xml_path

    candidates: List[Path] = []
    if xml_path.name.endswith(".zip.xml"):
        base = xml_path.name[:-len(".zip.xml")]
        candidates.append(xml_path.with_name(base + ".rdc"))
    elif xml_path.suffix.lower() == ".xml":
        candidates.append(xml_path.with_suffix(".rdc"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _derive_report_stem(input_path: Path) -> str:
    """生成输出报告的基础名字"""
    if input_path.name.endswith(".zip.xml"):
        return input_path.name[:-len(".zip.xml")]
    return input_path.stem


def _convert_rdc_to_zipxml(rdc_path: Path, xml_path: Path, renderdoccmd: Path) -> bool:
    """使用 renderdoccmd 生成 zip.xml + zip 资产"""
    log(f"[AUTO] Converting RDC -> ZIP+XML: {rdc_path.name}")
    cmd = [
        str(renderdoccmd),
        "convert",
        "-f",
        str(rdc_path),
        "-o",
        str(xml_path),
        "-c",
        "zip.xml",
    ]
    log(f"[AUTO] CMD: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        log("[AUTO] renderdoccmd failed:")
        log(result.stdout.strip() if result.stdout else "(no output)")
        return False
    return True


def _ensure_zipxml_assets(input_path: Path, rdc_hint: Optional[Path]) -> Path:
    """确保 zip.xml + zip 资产存在，必要时自动调用 renderdoccmd"""
    xml_path = input_path
    rdc_path: Optional[Path] = None

    if input_path.suffix.lower() == ".rdc":
        rdc_path = input_path
        xml_path = input_path.with_suffix(".zip.xml")
    elif rdc_hint and rdc_hint.exists():
        rdc_path = rdc_hint
    else:
        if input_path.name.endswith(".zip.xml"):
            base = input_path.name[:-len(".zip.xml")]
            candidate = input_path.with_name(base + ".rdc")
        elif input_path.suffix.lower() == ".xml":
            candidate = input_path.with_suffix(".rdc")
        else:
            candidate = None
        if candidate and candidate.exists():
            rdc_path = candidate

    zip_path = _resolve_zip_path(xml_path)
    if xml_path.exists() and zip_path and zip_path.exists():
        return xml_path

    if rdc_path and rdc_path.exists():
        renderdoccmd = _resolve_renderdoccmd()
        if not renderdoccmd:
            log("[AUTO] renderdoccmd.exe not found (set RENDERDOCCMD or add to PATH).")
            return xml_path

        if _convert_rdc_to_zipxml(rdc_path, xml_path, renderdoccmd):
            zip_path = _resolve_zip_path(xml_path)
            if xml_path.exists() and zip_path and zip_path.exists():
                log(f"[AUTO] ZIP+XML ready: {xml_path.name}")
            else:
                log("[AUTO] ZIP+XML conversion finished but assets missing.")
    else:
        log("[AUTO] Skip ZIP+XML conversion (RDC not found).")

    return xml_path








# ============================================================================


# 简化版性能分析数据类型 (避免包导入问题)


# ============================================================================





from dataclasses import dataclass, field








@dataclass


class SimplePerformanceIssue:


    """简化版性能问题"""


    rule_id: str


    severity: str  # critical | warning | info


    category: str


    title: str


    message: str


    event_id: Optional[int] = None


    resource_id: Optional[str] = None


    impact_score: float = 0.0


    suggestion: str = ""


    actual_value: Any = None


    threshold_value: Any = None








@dataclass


class SimplePerformanceReport:


    """简化版性能报告"""


    total_draw_calls: int = 0


    total_triangles: int = 0


    total_vertices: int = 0


    total_instances: int = 0


    total_shader_changes: int = 0


    total_rt_changes: int = 0


    total_blend_changes: int = 0


    unique_textures: int = 0


    unique_buffers: int = 0


    total_texture_memory_mb: float = 0.0


    issues: List[SimplePerformanceIssue] = field(default_factory=list)


    critical_count: int = 0


    warning_count: int = 0


    info_count: int = 0


    overall_score: float = 100.0


    recommendations: List[Any] = field(default_factory=list)  # 支持字符串或字典格式








# 压缩纹理格式列表


COMPRESSED_FORMATS = {


    "BC1", "BC2", "BC3", "BC4", "BC5", "BC6H", "BC7",


    "DXGI_FORMAT_BC1_UNORM", "DXGI_FORMAT_BC1_UNORM_SRGB",


    "DXGI_FORMAT_BC2_UNORM", "DXGI_FORMAT_BC2_UNORM_SRGB",


    "DXGI_FORMAT_BC3_UNORM", "DXGI_FORMAT_BC3_UNORM_SRGB",


    "DXGI_FORMAT_BC4_UNORM", "DXGI_FORMAT_BC4_SNORM",


    "DXGI_FORMAT_BC5_UNORM", "DXGI_FORMAT_BC5_SNORM",


    "DXGI_FORMAT_BC6H_UF16", "DXGI_FORMAT_BC6H_SF16",


    "DXGI_FORMAT_BC7_UNORM", "DXGI_FORMAT_BC7_UNORM_SRGB",


    "ETC1", "ETC2", "ASTC", "DXT1", "DXT3", "DXT5",


}








def is_compressed_format(format_str: str) -> bool:


    """检查纹理格式是否为压缩格式"""


    format_upper = format_str.upper()


    for cf in COMPRESSED_FORMATS:


        if cf in format_upper:


            return True


    return False








def _run_simplified_performance_analysis(context: 'AnalysisContext') -> SimplePerformanceReport:


    """


    简化版性能分析


    


    实现 PERF001-PERF007 的核心检测逻辑，无需依赖复杂的模块导入。


    """


    report = SimplePerformanceReport()


    


    # 基础统计


    total_verts = 0


    total_tris = 0


    total_instances = 0


    small_batch_count = 0


    small_batch_threshold = 100


    


    for dc in context.draw_calls:


        vc = dc.index_count or dc.vertex_count or 0


        inst = dc.instance_count or 1


        


        total_verts += vc * inst


        total_tris += (vc // 3) * inst


        total_instances += inst


        


        if vc < small_batch_threshold and vc > 0:


            small_batch_count += 1


    


    report.total_draw_calls = len(context.draw_calls)


    report.total_vertices = total_verts


    report.total_triangles = total_tris


    report.total_instances = total_instances


    


    # 状态变更统计 (使用 frame_summary 属性)


    fs = context.frame_summary if hasattr(context, 'frame_summary') else None


    report.total_shader_changes = getattr(fs, 'shader_changes', 0) if fs else 0


    report.total_rt_changes = getattr(fs, 'render_target_changes', 0) if fs else 0


    report.total_blend_changes = getattr(fs, 'blend_state_changes', 0) if fs else 0


    


    # 纹理统计


    report.unique_textures = len(context.textures)


    report.unique_buffers = len(context.buffers)


    


    total_texture_mem = 0.0


    uncompressed_count = 0


    large_texture_count = 0


    large_threshold = 2048


    


    for tex in context.textures:


        w = tex.width


        h = tex.height


        fmt = tex.format


        


        # 估算内存


        bpp = 4.0


        if is_compressed_format(fmt):


            bpp = 0.5


        else:


            uncompressed_count += 1


            


        mem = w * h * bpp


        total_texture_mem += mem


        


        # PERF004: 大纹理检测


        if w > large_threshold or h > large_threshold:


            large_texture_count += 1


            report.issues.append(SimplePerformanceIssue(


                rule_id='PERF004',


                severity='warning',


                category='texture',


                title='Large Texture',


                message=f'Texture {tex.name or tex.resource_id} ({w}x{h}) exceeds threshold {large_threshold}',


                resource_id=str(tex.resource_id),


                impact_score=5 + min((w * h) // (large_threshold * large_threshold), 10),


                actual_value=f'{w}x{h}',


                threshold_value=f'{large_threshold}x{large_threshold}',


                suggestion='Consider using mipmaps or reducing texture resolution'


            ))


        


        # PERF005: 未压缩纹理检测


        if not is_compressed_format(fmt) and w >= 256 and h >= 256:


            report.issues.append(SimplePerformanceIssue(


                rule_id='PERF005',


                severity='info',


                category='texture',


                title='Uncompressed Texture',


                message=f'Texture {tex.name or tex.resource_id} ({w}x{h}, {fmt}) is not compressed',


                resource_id=str(tex.resource_id),


                impact_score=3,


                actual_value=fmt,


                suggestion='Consider using BC/DXT compression for diffuse textures'


            ))


    


    report.total_texture_memory_mb = total_texture_mem / (1024 * 1024)


    


    # PERF003: 小批次检测


    if report.total_draw_calls > 0:


        small_batch_ratio = small_batch_count / report.total_draw_calls


        if small_batch_ratio > 0.3:


            report.issues.append(SimplePerformanceIssue(


                rule_id='PERF003',


                severity='warning',


                category='batch',


                title='Small Batch Draws',


                message=f'{small_batch_count}/{report.total_draw_calls} ({small_batch_ratio*100:.0f}%) draw calls have < {small_batch_threshold} vertices',


                impact_score=small_batch_ratio * 20,


                actual_value=f'{small_batch_ratio*100:.0f}%',


                threshold_value='30%',


                suggestion='Consider batching small draws together or using instancing'


            ))


    


    # PERF006: Alpha 混合过度使用检测


    blend_count = sum(1 for dc in context.draw_calls if dc.blend_enabled)


    if report.total_draw_calls > 0:


        blend_ratio = blend_count / report.total_draw_calls


        if blend_ratio > 0.5:


            report.issues.append(SimplePerformanceIssue(


                rule_id='PERF006',


                severity='info',


                category='blend',


                title='High Alpha Blend Usage',


                message=f'{blend_count}/{report.total_draw_calls} ({blend_ratio*100:.0f}%) draw calls use alpha blending',


                impact_score=blend_ratio * 10,


                actual_value=f'{blend_ratio*100:.0f}%',


                threshold_value='50%',


                suggestion='Review if all alpha blending is necessary'


            ))


    


    # 汇总问题统计


    for issue in report.issues:


        if issue.severity == 'critical':


            report.critical_count += 1


        elif issue.severity == 'warning':


            report.warning_count += 1


        else:


            report.info_count += 1


    


    # 计算总体评分


    deductions = (


        report.critical_count * 15 +


        report.warning_count * 5 +


        report.info_count * 1


    )


    report.overall_score = max(0, 100 - deductions)


    


    # 生成建议（结构化中文格式）
    
    if large_texture_count > 0:
        # 计算大纹理的内存占用（TextureInfo 是 dataclass，使用 getattr）
        large_tex_memory_mb = sum(
            (getattr(t, "width", 0) * getattr(t, "height", 0) * 4) / (1024 * 1024)
            for t in context.textures
            if getattr(t, "width", 0) >= 2048 or getattr(t, "height", 0) >= 2048
        )
        report.recommendations.append({
            "priority": "high" if large_texture_count > 10 else "medium",
            "rule": "PERF004",
            "title": "大纹理优化",
            "detail": f"检测到 {large_texture_count} 张大纹理（≥2048），占用约 {large_tex_memory_mb:.1f} MB",
            "action": "降低分辨率或使用 Mipmap 链，仅在需要时加载高分辨率版本",
            "impact": f"预计可节省 {large_tex_memory_mb * 0.5:.0f} MB 显存",
        })
    
    if uncompressed_count > 5:
        # 估算压缩后节省（TextureInfo 是 dataclass，使用 getattr）
        uncompressed_memory_mb = sum(
            (getattr(t, "width", 0) * getattr(t, "height", 0) * 4) / (1024 * 1024)
            for t in context.textures
            if getattr(t, "format", None) and not any(cf in str(getattr(t, "format", "")).upper() for cf in ["BC", "DXT", "ETC", "ASTC"])
        )
        report.recommendations.append({
            "priority": "high" if uncompressed_count > 20 else "medium",
            "rule": "PERF005",
            "title": "未压缩纹理",
            "detail": f"检测到 {uncompressed_count} 张未压缩纹理，占用约 {uncompressed_memory_mb:.1f} MB",
            "action": "使用 BC7（质量优先）或 BC1/BC3（性能优先）格式压缩纹理",
            "impact": f"BC7 压缩可减少约 75% 内存，预计节省 {uncompressed_memory_mb * 0.75:.0f} MB",
        })
    
    if small_batch_count > 10:
        small_batch_ratio = (small_batch_count / max(1, report.total_draw_calls)) * 100
        report.recommendations.append({
            "priority": "high" if small_batch_count > 50 else "medium",
            "rule": "PERF003",
            "title": "小批次绘制调用",
            "detail": f"检测到 {small_batch_count} 次小批次绘制（<100 顶点），占比 {small_batch_ratio:.1f}%",
            "action": "使用 GPU Instancing 或 Static/Dynamic Batching 合并小批次",
            "impact": f"预计可减少 {int(small_batch_count * 0.7)} 次 Draw Call",
        })
    
    # 添加内存总量建议
    total_tex_memory_mb = report.total_texture_memory_mb
    if total_tex_memory_mb > 512:
        report.recommendations.append({
            "priority": "high" if total_tex_memory_mb > 1024 else "medium",
            "rule": "PERF_MEMORY",
            "title": "纹理内存占用过高",
            "detail": f"纹理总内存 {total_tex_memory_mb:.1f} MB，共 {report.unique_textures} 张纹理",
            "action": "检查未使用纹理、重复加载、过大分辨率等问题",
            "impact": f"优化后预计可节省 {total_tex_memory_mb * 0.3:.0f} MB 内存",
        })
    
    return report








def _merge_event_bindings(

    pipeline_state: Optional[Dict[str, Any]],

    resource_bindings: Optional[Dict[str, Any]]

) -> Optional[Dict[str, Any]]:

    """

    将 XML 中的 resourceBindings / pipelineState 转换为 HTML 模板期望的 bindings 格式。

    该函数只在 A 路线使用，避免引入新的回放依赖。

    """

    if not pipeline_state and not resource_bindings:

        return pipeline_state



    try:

        # 复用 full 路线的转换逻辑（避免重复实现）

        from generate_real_report import (

            convert_resource_bindings_to_template_format,

            convert_pipeline_state_to_bindings,

        )

    except Exception as e:

        log(f"[WARN] Binding conversion unavailable: {e}")

        return pipeline_state



    bindings = {}

    if resource_bindings:

        bindings = convert_resource_bindings_to_template_format(resource_bindings)



    if pipeline_state:

        new_bindings = convert_pipeline_state_to_bindings(pipeline_state)

        if new_bindings:

            if bindings:

                # 轻量合并：列表追加，非列表覆盖

                for stage, data in new_bindings.items():

                    if stage not in bindings:

                        bindings[stage] = data

                        continue

                    stage_dict = bindings[stage]

                    for key, value in data.items():

                        if isinstance(value, list) and value:

                            stage_dict.setdefault(key, [])

                            stage_dict[key].extend(value)

                        elif value is not None:

                            stage_dict[key] = value

            else:

                bindings = new_bindings



    if bindings:

        if not pipeline_state:

            pipeline_state = {}

        pipeline_state["bindings"] = bindings



    return pipeline_state





def convert_perf_report_to_html_data(

    perf_report: 'PerformanceReport',

    context: 'AnalysisContext',

    xml_data: Optional[Dict[str, Any]] = None

) -> Dict[str, Any]:

    """


    将 PerformanceReport 转换为 HTML 模板可用的 dict 格式


    


    Args:


        perf_report: PerformanceAnalyzer 生成的报告


        context: 分析上下文


        


    Returns:


        event_pass_data 字典，可传递给 generate_offline_html()


    """


    # 基础统计


    summary = {


        'total_draw_calls': perf_report.total_draw_calls,


        'total_triangles': perf_report.total_triangles,


        'total_vertices': perf_report.total_vertices,


        'total_instances': perf_report.total_instances,


        'total_shader_changes': perf_report.total_shader_changes,


        'total_rt_changes': perf_report.total_rt_changes,


        'total_blend_changes': perf_report.total_blend_changes,


        'unique_textures': perf_report.unique_textures,


        'unique_buffers': perf_report.unique_buffers,


        'total_texture_memory_mb': round(perf_report.total_texture_memory_mb, 2),


        'overall_score': round(perf_report.overall_score, 1),


        'critical_count': perf_report.critical_count,


        'warning_count': perf_report.warning_count,


        'info_count': perf_report.info_count,


    }


    


    # 转换问题列表


    issues = []


    for issue in perf_report.issues:


        issues.append({


            'rule_id': issue.rule_id,


            'severity': issue.severity,


            'category': issue.category,


            'title': issue.title,


            'message': issue.message,


            'event_id': issue.event_id,


            'resource_id': issue.resource_id,


            'impact_score': issue.impact_score,


            'suggestion': issue.suggestion,


            'actual_value': str(issue.actual_value) if issue.actual_value is not None else None,


            'threshold_value': str(issue.threshold_value) if issue.threshold_value is not None else None,


        })


    


    # 转换绘制调用为事件列表 (使用 DrawCallInfo 的实际属性)


    # 构建 XML event 索引（按 eventId）

    xml_events_by_id = {}

    if xml_data:

        for evt in xml_data.get('events', []):

            eid = evt.get('eventId')

            if eid is not None:

                xml_events_by_id[eid] = evt



    # 转换绘制调用为事件列表 (使用 DrawCallInfo 的实际属性)

    events = []

    for dc in context.draw_calls:

        event = {

            'eid': dc.event_id,

            'name': dc.type or f'Draw {dc.event_id}',

            'index_count': dc.index_count,

            'vertex_count': dc.vertex_count,

            'instance_count': dc.instance_count,

            'shader_vs': dc.vs_id,

            'shader_ps': dc.ps_id,

            'render_targets': dc.rt_ids,

            'depth_target': dc.ds_id,

            'blend_enabled': dc.blend_enabled,

            'depth_test': dc.depth_test,

            'depth_write': dc.depth_write,

        }



        # 补充 XML 中的事件字段（用于 Event Browser）

        xml_event = xml_events_by_id.get(dc.event_id)

        if xml_event:

            event['name'] = xml_event.get('name', event['name'])

            event['type'] = xml_event.get('type', 'draw')

            event['flags'] = xml_event.get('flags', [])

            event['duration'] = xml_event.get('duration', 0)

            if 'params' in xml_event:

                event['params'] = xml_event.get('params', [])

            if 'meshInfo' in xml_event:

                event['meshInfo'] = xml_event.get('meshInfo')

            if 'pipelineState' in xml_event:

                event['pipelineState'] = xml_event.get('pipelineState')

            if 'resourceBindings' in xml_event:

                event['resourceBindings'] = xml_event.get('resourceBindings')



            # 确保 pipelineState.bindings 可用于 HTML

            event['pipelineState'] = _merge_event_bindings(

                event.get('pipelineState'),

                event.get('resourceBindings')

            )




        # 数据丰富度覆盖（不允许近似，缺失需给原因）

        event['coverage'] = compute_field_coverage(

            ACTION_FIELD_MAP,

            event,

            MISSING_REASON_REPLAY,

        )



        events.append(event)

    




    result = {


        'summary': summary,


        'issues': issues,


        'events': events,


        'recommendations': perf_report.recommendations,


        'generated_at': datetime.now().isoformat(),


        'analyzer_version': '1.0.0',


    }


    


    return result









def write_offline_manifest(
    output_path: Path | str,
    performance_data: Dict[str, Any],
    textures: List[Dict[str, Any]],
    shader_data: List[Dict[str, Any]],
    capture_id: Optional[str] = None,
    report_links: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    output_path = Path(output_path)

    if not capture_id:
        capture_id = report_linking.compute_capture_id([str(output_path)])

    summary = performance_data.get("summary", {})
    events = performance_data.get("events", [])
    event_count = len(events) if isinstance(events, list) else 0
    if event_count == 0:
        event_count = summary.get("total_draw_calls", performance_data.get("total_draw_calls", 0))

    texture_count = len(textures) if isinstance(textures, list) else 0
    if texture_count == 0:
        texture_count = summary.get("unique_textures", performance_data.get("unique_textures", 0))

    shader_count = len(shader_data) if isinstance(shader_data, list) else 0

    missing_reason = []
    if texture_count == 0:
        missing_reason.append({
            "field": "textures",
            "reason": "No textures.json or texture dir provided.",
        })
    if shader_count == 0:
        missing_reason.append({
            "field": "shaders",
            "reason": "No shader list found in XML.",
        })

    counts = {
        "events": event_count,
        "textures": texture_count,
        "shaders": shader_count,
    }
    count_reason = {
        "events": "xml",
        "textures": "xml",
        "shaders": "xml",
    }

    report_links = report_links or report_linking.default_report_links(output_path, "texture")
    manifest = rdc_manifest.build_manifest(
        capture_id=capture_id,
        source="C",
        counts=counts,
        count_reason=count_reason,
        missing=missing_reason,
        report_links=report_links,
    )
    report_linking.write_manifest_bundle(output_path, manifest, report_links)
    return manifest


def load_textures_if_available(


    texture_dir: Optional[str],


    xml_data: Dict[str, Any]


) -> List[Dict[str, Any]]:


    """


    尝试从目录或 XML 数据加载纹理信息


    


    Args:


        texture_dir: 纹理目录路径（可选）


        xml_data: 解析后的 XML 数据


        


    Returns:


        纹理列表，用于 HTML 报告


    """


    textures = []

    def _apply_texture_coverage(tex_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for tex in tex_list:
            if isinstance(tex, dict):
                tex['coverage'] = compute_field_coverage(
                    TEXTURE_FIELD_MAP,
                    tex,
                    MISSING_REASON_REPLAY,
                )
        return tex_list



    


    # 方式 1: 从指定目录加载


    if texture_dir:


        tex_path = Path(texture_dir)


        manifest_path = tex_path / "textures.json"


        if manifest_path.exists():


            try:


                with open(manifest_path, 'r', encoding='utf-8') as f:


                    manifest = json.load(f)


                tex_list = manifest if isinstance(manifest, list) else manifest.get('textures', [])


                log(f"Loaded {len(tex_list)} textures from {manifest_path}")


                return _apply_texture_coverage(tex_list)
            except Exception as e:


                log(f"[WARN] Failed to load texture manifest: {e}")


    


    # 方式 2: 从 XML 数据提取纹理元数据（无缩略图）


    xml_textures = xml_data.get('textures', [])


    if xml_textures:


        # 支持列表或字典格式


        if isinstance(xml_textures, dict):


            tex_items = list(xml_textures.items())


        else:


            # 列表格式，每个元素自带 id


            tex_items = [(t.get('id', f'tex_{i}'), t) for i, t in enumerate(xml_textures)]


        


        for tex_id, tex_info in tex_items:

            resource_id = tex_info.get("resourceId") or tex_info.get("resource_id")
            if (
                not resource_id
                and isinstance(tex_id, str)
                and tex_id.startswith("tex_")
                and tex_id[4:].isdigit()
            ):
                resource_id = tex_id[4:]

            textures.append({


                'id': tex_id,
                'resource_id': resource_id,


                'name': tex_info.get('name', ''),


                'width': tex_info.get('width', 0),


                'height': tex_info.get('height', 0),


                'depth': tex_info.get('depth', 1),


                'format': tex_info.get('format', 'Unknown'),


                'mips': tex_info.get('mipLevels', 1),


                'arrayLayers': tex_info.get('arrayLayers', 1),


                'thumbnail': '',  # XML 模式无缩略图


            })


        log(f"Extracted {len(textures)} texture metadata from XML")


    


    return _apply_texture_coverage(textures)


def map_exported_textures(textures: List[Dict[str, Any]], export_dir: Path) -> int:
    """
    将已导出的 PNG 缩略图映射到纹理列表

    Args:
        textures: 纹理数据列表
        export_dir: PNG 输出目录 (output_dir/textures)

    Returns:
        成功映射的数量
    """
    if not textures or not export_dir.exists():
        return 0

    updated = 0
    for tex in textures:
        if not isinstance(tex, dict):
            continue
        tex_id = tex.get("resource_id") or tex.get("resourceId") or tex.get("id")
        width = tex.get("width")
        height = tex.get("height")
        if not tex_id or not width or not height:
            continue

        filename = f"tex_{tex_id}_{width}x{height}.png"
        file_path = export_dir / filename
        if not file_path.exists():
            matches = list(export_dir.glob(f"tex_{tex_id}_*x*.png"))
            if len(matches) == 1:
                file_path = matches[0]
            else:
                continue

        tex["thumbnail"] = f"textures/{file_path.name}"
        updated += 1

    return updated


def _run_renderdoccmd_export(rdc_path: Path, export_dir: Path) -> Optional[Path]:
    """Run renderdoccmd export and return textures.json path if available."""
    renderdoccmd = _resolve_renderdoccmd(require_export=True)
    if not renderdoccmd:
        log("  [Texture Export] renderdoccmd.exe not found or missing export support.")
        return None

    export_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(renderdoccmd),
        "export",
        str(rdc_path),
        "--out",
        str(export_dir),
        "--format",
        "png",
        "--metadata",
    ]
    log(f"  [Texture Export] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as e:
        log(f"  [Texture Export] renderdoccmd failed: {e}")
        return None

    if result.stdout:
        log(result.stdout.strip())
    if result.stderr:
        log(result.stderr.strip())

    textures_json = export_dir / "textures.json"
    return textures_json if textures_json.exists() else None


def load_texture_exporter(force_fallback: bool = False):
    """加载纹理导出器（优先常规导入，失败则回退到直接加载文件）"""
    if not force_fallback:
        try:
            from exporters.texture_batch_exporter import create_export_engine
            return create_export_engine
        except Exception:
            pass

    export_path = Path(__file__).parent / "exporters" / "texture_batch_exporter.py"
    spec = importlib.util.spec_from_file_location("rdc_texture_batch_exporter", export_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_export_engine


def load_renderdoccmd_exporter(force_fallback: bool = False):
    """加载 renderdoccmd 导出选择器（优先常规导入，失败则回退到直接加载文件）"""
    if not force_fallback:
        try:
            from exporters.renderdoccmd_exporter import load_textures_json, select_textures
            return load_textures_json, select_textures
        except Exception:
            pass

    export_path = Path(__file__).parent / "exporters" / "renderdoccmd_exporter.py"
    spec = importlib.util.spec_from_file_location("rdc_renderdoccmd_exporter", export_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_textures_json, module.select_textures






def run_analysis(
    xml_path: str,
    output_path: str,
    texture_dir: Optional[str] = None,
    ui_version: str = "v1",
    rdc_path: Optional[Path] = None,
) -> bool:


    """


    执行完整的分析流程


    


    Args:


        xml_path: XML 文件路径


        output_path: 输出 HTML 路径


        texture_dir: 纹理目录（可选）
        ui_version: UI 版本 ("v1" 或 "v2")


        


    Returns:


        成功返回 True


    """


    xml_path = Path(xml_path)


    


    if not xml_path.exists():


        log(f"[ERROR] XML file not found: {xml_path}")


        return False


    


    log(f"Input: {xml_path}")


    log(f"Output: {output_path}")

    rdc_source_path = _resolve_rdc_from_xml(xml_path, rdc_path)


    


    # Step 1: 解析 XML


    log("Step 1/4: Parsing XML...")


    try:


        from parse_rdc_xml import parse_rdc_xml


        xml_data = parse_rdc_xml(str(xml_path))


        event_count = len(xml_data.get('events', []))


        texture_count = len(xml_data.get('textures', {}))


        log(f"  Parsed {event_count} events, {texture_count} textures")


    except Exception as e:


        log(f"[ERROR] Failed to parse XML: {e}")


        import traceback


        traceback.print_exc()


        return False


    


    # Step 2: Bridge 转换


    log("Step 2/4: Converting to AnalysisContext...")


    try:


        from core.bridge import XMLToContextBridge


        context = XMLToContextBridge.convert(xml_data, str(xml_path))


        log(f"  Context: {len(context.draw_calls)} draw calls, {len(context.textures)} textures")


    except Exception as e:


        log(f"[ERROR] Bridge conversion failed: {e}")


        import traceback


        traceback.print_exc()


        return False


    


    # Step 3: 性能分析


    log("Step 3/4: Running performance analysis...")


    try:


        # 使用 importlib 动态导入以避免相对导入问题


        import importlib.util


        


        # 加载 performance_analyzer 模块


        perf_analyzer_path = SCRIPT_DIR / "analyzers" / "performance_analyzer.py"


        spec = importlib.util.spec_from_file_location("performance_analyzer", perf_analyzer_path)


        perf_module = importlib.util.module_from_spec(spec)


        


        # 需要先确保依赖模块可用


        # 手动处理相对导入的依赖


        sys.modules['analyzers'] = type(sys)('analyzers')


        sys.modules['analyzers.performance_analyzer'] = perf_module


        


        # 加载 base 模块


        base_path = SCRIPT_DIR / "analyzers" / "base.py"


        base_spec = importlib.util.spec_from_file_location("base", base_path)


        base_module = importlib.util.module_from_spec(base_spec)


        sys.modules['analyzers.base'] = base_module


        


        # 执行加载 (可能会有相对导入问题，使用备用方案)


        # 备用方案：直接使用简化的性能分析


        perf_report = _run_simplified_performance_analysis(context)


        


        log(f"  Issues: {perf_report.critical_count} critical, {perf_report.warning_count} warning, {perf_report.info_count} info")


        log(f"  Score: {perf_report.overall_score:.1f}/100")


    except Exception as e:


        log(f"[ERROR] Performance analysis failed: {e}")


        import traceback


        traceback.print_exc()


        return False


    


    # Step 4: 生成 HTML 报告


    log("Step 4/4: Generating HTML report...")


    try:


        # 转换性能数据（两种 UI 都需要）


        # 转换性能数据

        performance_data = convert_perf_report_to_html_data(perf_report, context, xml_data)

        

        # 加载纹理

        textures = load_textures_if_available(texture_dir, xml_data)

        

        # 从 XML 数据中提取 Shader 列表（A 路线默认应包含）

        shader_data = xml_data.get('shaders', [])

        

        # ===== UI 版本分支 =====
        if ui_version == "bundle":
            # 4 页面互联报告包
            from report_bundle_generator import generate_report_bundle
            
            # 输出目录为 output_path 去掉后缀的目录
            output_dir = Path(output_path).with_suffix('')
            output_dir.mkdir(parents=True, exist_ok=True)
            export_source = os.getenv("RDC_TEX_EXPORT_SOURCE", "xmlzip").strip().lower()
            
            # ===== 纹理缩略图生成 =====
            # 尝试生成缩略图（需要 ZIP 格式的 XML 资产文件）
            if export_source == "renderdoccmd":
                log("  [Thumbnail] Skip XML/ZIP thumbnail generation (use renderdoccmd export)")
            else:
                try:
                    from thumbnail_generator import ThumbnailGenerator

                    # 查找伴随的 ZIP 文件（renderdoccmd convert 输出格式）
                    # 命名模式：
                    #   - xxx.zip.xml -> xxx.zip (主要模式)
                    #   - xxx.xml -> xxx (无后缀ZIP)
                    #   - xxx.xml -> xxx_assets/ (资产目录)
                    if xml_path.name.endswith('.zip.xml'):
                        # xxx.zip.xml -> xxx.zip
                        zip_path = xml_path.parent / xml_path.name[:-4]  # 去掉 .xml
                    else:
                        # xxx.xml -> xxx (无后缀)
                        zip_path = xml_path.with_suffix('')
                    assets_dir = xml_path.parent / (xml_path.stem + "_assets")

                    if zip_path.exists():
                        log(f"  [Thumbnail] Found ZIP asset file: {zip_path.name}")
                        thumb_gen = ThumbnailGenerator(str(xml_path), str(zip_path))
                        results = thumb_gen.generate_thumbnails(max_count=30, max_size=96)

                        # 转换为 ID -> Base64 映射
                        thumbnails = {str(r.resource_id): r.base64_data for r in results if r.success}

                        # 将缩略图添加到纹理数据
                        thumb_count = 0
                        for tex in textures:
                            tex_id = str(tex.get("id") or tex.get("resource_id", ""))
                            if tex_id in thumbnails:
                                tex["thumbnail"] = thumbnails[tex_id]
                                thumb_count += 1

                        if thumb_count > 0:
                            log(f"  [Thumbnail] Generated {thumb_count} thumbnails")
                        else:
                            log(f"  [Thumbnail] No thumbnails generated (textures may not match)")

                    elif assets_dir.exists():
                        log(f"  [Thumbnail] Found assets directory: {assets_dir.name}")
                        thumb_gen = ThumbnailGenerator(str(xml_path), str(assets_dir))
                        results = thumb_gen.generate_thumbnails(max_count=30, max_size=96)

                        # 转换为 ID -> Base64 映射
                        thumbnails = {str(r.resource_id): r.base64_data for r in results if r.success}

                        thumb_count = 0
                        for tex in textures:
                            tex_id = str(tex.get("id") or tex.get("resource_id", ""))
                            if tex_id in thumbnails:
                                tex["thumbnail"] = thumbnails[tex_id]
                                thumb_count += 1

                        if thumb_count > 0:
                            log(f"  [Thumbnail] Generated {thumb_count} thumbnails")
                    else:
                        log(f"  [Thumbnail] No ZIP/assets found, skipping thumbnails")

                except ImportError as e:
                    log(f"  [Thumbnail] Skipped: ThumbnailGenerator not available ({e})")
                except Exception as e:
                    log(f"  [Thumbnail] Warning: Failed to generate thumbnails: {e}")

            # ===== 全量 PNG 纹理导出 =====
            if textures:
                export_dir = output_dir / "textures"
                engine = None
                try:
                    limit_env = os.getenv("RDC_TEX_EXPORT_LIMIT", "").strip()
                    texture_export_limit = int(limit_env) if limit_env.isdigit() else 3

                    if export_source == "renderdoccmd":
                        load_textures_json, select_textures = load_renderdoccmd_exporter()

                        log("  [Texture Export] Using renderdoccmd export...")
                        if not rdc_source_path:
                            log("  [Texture Export] Skip: failed to resolve RDC path for renderdoccmd export")
                        else:
                            textures_json = _run_renderdoccmd_export(rdc_source_path, export_dir)
                            if textures_json:
                                entries = load_textures_json(textures_json)
                                selected = select_textures(entries, texture_export_limit)
                                selected_map: Dict[str, Dict[str, Any]] = {}
                                selected_files: set[str] = set()
                                for entry in selected:
                                    entry_id = entry.get("id")
                                    if entry_id is None:
                                        continue
                                    selected_map[str(entry_id)] = entry
                                    file_name = entry.get("file")
                                    if file_name:
                                        selected_files.add(str(file_name))

                                removed = 0
                                for png_path in export_dir.glob("*.png"):
                                    if png_path.name not in selected_files:
                                        try:
                                            png_path.unlink()
                                            removed += 1
                                        except Exception:
                                            pass

                                mapped = 0
                                for tex in textures:
                                    tex_id = tex.get("resource_id") or tex.get("resourceId") or tex.get("id")
                                    if tex_id is None:
                                        continue
                                    entry = selected_map.get(str(tex_id))
                                    if entry and entry.get("file"):
                                        tex["thumbnail"] = f"textures/{entry['file']}"
                                        mapped += 1

                                log(
                                    f"  [Texture Export] Done: {mapped}/{len(selected)} "
                                    f"(limit={texture_export_limit})"
                                )
                                log(
                                    f"  [Texture Export] Pruned {removed} PNG files, kept {len(selected_files)}"
                                )
                            else:
                                log("  [Texture Export] renderdoccmd export failed or no textures.json")
                    else:
                        create_export_engine = load_texture_exporter()

                        log("  [Texture Export] Exporting textures to PNG...")
                        engine = create_export_engine(xml_path)
                        summary = engine.export_all(
                            export_dir,
                            save_png=True,
                            save_bin=False,
                            limit=texture_export_limit,
                        )
                        log(
                            f"  [Texture Export] Done: {summary.success}/{summary.total} "
                            f"(failed {summary.failed}, skipped {summary.skipped}, "
                            f"limit={texture_export_limit})"
                        )

                        mapped = map_exported_textures(textures, export_dir)
                        if mapped > 0:
                            log(f"  [Texture Export] Mapped {mapped} thumbnails")
                        else:
                            log("  [Texture Export] No thumbnails mapped")
                except Exception as e:
                    log(f"  [Texture Export] Warning: {e}")
                finally:
                    if engine:
                        try:
                            engine.close()
                        except Exception:
                            pass
            
            # ===== Shader 源码提取 =====
            # 尝试从 ZIP 中提取 SPIR-V 并转换为 GLSL
            try:
                from shader_extractor import ShaderExtractor, extract_shaders_for_report
                
                # 查找伴随的 ZIP 文件（复用缩略图的检测逻辑）
                if xml_path.name.endswith('.zip.xml'):
                    shader_zip_path = xml_path.parent / xml_path.name[:-4]  # 去掉 .xml
                else:
                    shader_zip_path = xml_path.with_suffix('')
                shader_assets_dir = xml_path.parent / (xml_path.stem + "_assets")
                
                actual_zip = shader_zip_path if shader_zip_path.exists() else (shader_assets_dir if shader_assets_dir.exists() else None)
                
                if actual_zip:
                    log(f"  [Shader] Extracting shaders from: {actual_zip.name if hasattr(actual_zip, 'name') else actual_zip}")
                    
                    extractor = ShaderExtractor(xml_path, actual_zip)
                    available, reason = extractor.is_available()
                    
                    if available:
                        extracted = extractor.extract_shaders(max_count=30)
                        
                        # 更新 shader_data：为现有 shader 添加源码，或添加新的 shader
                        existing_ids = {s.get('id') or s.get('resource_id') for s in shader_data if s}
                        
                        # 创建 ID -> 源码映射
                        shader_source_map = {
                            s.resource_id: {
                                'source': s.display_source,
                                'glsl': s.glsl_source,
                                'has_glsl': s.has_glsl,
                                'stage': s.stage,
                            }
                            for s in extracted
                        }
                        
                        # 更新现有 shader 数据
                        updated_count = 0
                        for shader in shader_data:
                            shader_id = shader.get('id') or shader.get('resource_id')
                            if shader_id and shader_id in shader_source_map:
                                source_info = shader_source_map[shader_id]
                                shader['source'] = source_info['source']
                                shader['glsl'] = source_info['glsl']
                                shader['has_glsl'] = source_info['has_glsl']
                                if not shader.get('stage'):
                                    shader['stage'] = source_info['stage']
                                updated_count += 1
                        
                        # 添加新发现的 shader（不在现有列表中）
                        for shader in extracted:
                            if shader.resource_id not in existing_ids:
                                shader_data.append({
                                    'id': shader.resource_id,
                                    'resource_id': shader.resource_id,
                                    'name': f"Shader_{shader.resource_id}",
                                    'stage': shader.stage,
                                    'source': shader.display_source,
                                    'glsl': shader.glsl_source,
                                    'has_glsl': shader.has_glsl,
                                    'spirv_size': shader.code_size,
                                })
                        
                        glsl_count = sum(1 for s in extracted if s.has_glsl)
                        log(f"  [Shader] Extracted {len(extracted)} shaders ({glsl_count} with GLSL)")
                        log(f"  [Shader] Updated {updated_count} existing, added {len(extracted) - updated_count} new")
                    else:
                        log(f"  [Shader] Not available: {reason}")
                else:
                    log(f"  [Shader] No ZIP/assets found, shader source extraction skipped")
                    
            except ImportError as e:
                log(f"  [Shader] Skipped: ShaderExtractor not available ({e})")
            except Exception as e:
                log(f"  [Shader] Warning: Failed to extract shaders: {e}")
            
            # 构建性能数据（issues 列表）
            issues_list = []
            for issue in perf_report.issues:
                issues_list.append({
                    "severity": issue.severity.name.lower() if hasattr(issue.severity, 'name') else str(issue.severity),
                    "title": issue.title,
                    "description": issue.message[:100] if issue.message else "",
                })
            
            perf_data_for_bundle = {
                "api": xml_data.get("api", "Unknown"),
                "gpu": xml_data.get("gpu", "Unknown"),
                "resolution": f"{xml_data.get('width', 0)}x{xml_data.get('height', 0)}",
                "issues": issues_list,
                "recommendations": perf_report.recommendations,  # 结构化建议列表
            }
            
            # 生成报告包
            output_files = generate_report_bundle(
                output_dir=output_dir,
                capture_name=xml_path.stem,
                textures=textures,
                events=xml_data.get("events", []),
                shaders=shader_data,
                performance_data=perf_data_for_bundle,
                mali_data={},  # TODO: 集成 Mali 数据
                frame_thumbnail="",  # TODO: 提取帧缩略图
                texture_usage_map={},  # TODO: 构建纹理使用映射
            )
            
            log(f"  Report bundle generated: {output_dir}")
            for name, path in output_files.items():
                log(f"    - {name}: {Path(path).name}")
        
        elif ui_version == "v2":
            # 新四视图 UI
            from report_contract import ReportDataContract, build_manifest
            from report_ui import render_report_shell

            # performance 数据补充 passes（原字段来自 XML）
            performance_data["passes"] = xml_data.get("passes", [])

            # 构建 Data Contract（字段与 ReportDataContract 对齐）
            contract = ReportDataContract(
                textures=textures,
                shaders=shader_data,
                events=xml_data.get("events", []),
                performance=performance_data,
                meta={
                    "capture_name": xml_path.stem,
                    "source": "xml",
                    "xml_path": str(xml_path),
                },
            )
            
            # 生成 HTML
            html_content = render_report_shell(contract)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            log(f"  Report generated (v2 UI): {output_path}")
        else:
            # 传统 v1 UI
            from generate_offline_report import generate_offline_html
            
            report_links = report_linking.default_report_links(Path(output_path), "texture")
            manifest = write_offline_manifest(
                output_path=output_path,
                performance_data=performance_data,
                textures=textures,
                shader_data=shader_data,
                capture_id=report_linking.compute_capture_id([str(xml_path)]),
                report_links=report_links,
            )
            generate_offline_html(
                textures=textures,
                rdc_name=xml_path.stem,
                output_path=output_path,
                event_pass_data=performance_data,
                shader_data=shader_data,
                report_links=report_links,
                manifest_data=manifest,
            )

            log(f"  Report generated (v1 UI): {output_path}")


    except Exception as e:


        log(f"[ERROR] HTML generation failed: {e}")


        import traceback


        traceback.print_exc()


        return False


    


    return True








def main():


    parser = argparse.ArgumentParser(


        description="XML 离线分析报告生成器 - 从 RenderDoc XML 导出生成性能分析 HTML 报告",


        formatter_class=argparse.RawDescriptionHelpFormatter,


        epilog="""


示例:


  # 基本用法


  py -3 analyze_xml_report.py capture.xml


  


  # 指定输出路径


  py -3 analyze_xml_report.py capture.xml -o my_report.html


  


  # 包含纹理缩略图


  py -3 analyze_xml_report.py capture.xml --texture-dir ./textures/





注意:


  XML 文件由 RenderDoc 的 renderdoccmd 工具导出:


  renderdoccmd capture.rdc --export-xml capture.xml


"""


    )


    


    parser.add_argument(


        "xml_path",


        help="RenderDoc 导出的 XML 文件路径"


    )


    parser.add_argument(


        "-o", "--output",


        help="输出 HTML 文件路径 (默认: <xml_name>_report.html)"


    )


    parser.add_argument(


        "--texture-dir",


        help="纹理目录路径（包含 textures.json 和 PNG 文件）"


    )


    parser.add_argument(


        "-v", "--verbose",


        action="store_true",


        help="详细输出"


    )

    # UI 版本选择（新 UI 系统 Feature Flag）
    parser.add_argument(
        "--ui-version",
        choices=["v1", "v2", "bundle"],
        default="v1",
        help="报告 UI 版本: v1=传统视图(默认), v2=新四视图架构, bundle=4页面互联报告包"
    )
    parser.add_argument(
        "--auto-start-rt-server",
        action="store_true",
        help="Bundle 生成后自动启动 RT 预览服务"
    )
    parser.add_argument(
        "--rdc-path",
        help="RT 预览服务使用的 RDC 路径（与 --auto-start-rt-server 搭配）"
    )
    parser.add_argument(
        "--auto-open-textures",
        action="store_true",
        help="Bundle 生成后自动打开 textures.html"
    )


    


    args = parser.parse_args()


    


    # 确定输出路径


    input_path = Path(args.xml_path)

    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.parent / f"{_derive_report_stem(input_path)}_report.html")

    rdc_hint = Path(args.rdc_path) if getattr(args, "rdc_path", None) else None
    xml_path = _ensure_zipxml_assets(input_path, rdc_hint)


    


    # 执行分析


    success = run_analysis(


        xml_path=str(xml_path),


        output_path=output_path,


        texture_dir=args.texture_dir,
        ui_version=getattr(args, 'ui_version', 'v1'),
        rdc_path=rdc_hint,


    )


    


    if success:

        # 自动启动服务与打开页面（仅 bundle 有意义）
        if getattr(args, "auto_start_rt_server", False) and args.ui_version == "bundle":
            try:
                import subprocess
                rt_server = Path(__file__).parent / "rt_preview_server.py"
                if getattr(args, "rdc_path", None):
                    rdc_path = Path(args.rdc_path)
                else:
                    rdc_path = xml_path.with_suffix(".rdc")
                    if not rdc_path.exists() and xml_path.name.endswith(".zip.xml"):
                        rdc_path = xml_path.with_suffix("")
                if rdc_path.exists():
                    subprocess.Popen([
                        sys.executable,
                        str(rt_server),
                        "--rdc",
                        str(rdc_path),
                        "--port",
                        "8765"
                    ])
                    log(f"[AUTO] RT server started: {rt_server}")
                else:
                    log(f"[AUTO] Skip RT server (rdc not found): {rdc_path}")
            except Exception as e:
                log(f"[AUTO] Failed to start RT server: {e}")

        if getattr(args, "auto_open_textures", False) and args.ui_version == "bundle":
            try:
                textures_html = Path(output_path).with_suffix("") / "textures.html"
                if textures_html.exists():
                    os.startfile(str(textures_html))
                    log(f"[AUTO] Opened textures.html: {textures_html}")
            except Exception as e:
                log(f"[AUTO] Failed to open textures.html: {e}")

        log("Done!")


        return 0


    else:


        return 1








if __name__ == "__main__":


    sys.exit(main())


