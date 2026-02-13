#!/usr/bin/env python3
"""
RDC Shader 分析工具

从 RenderDoc 捕获文件中提取 shader 并使用 Mali Offline Compiler 进行性能分析。

用法:
    python analyze_rdc.py <rdc_file> [--core Mali-G715] [--output report.html]

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import sys
import os
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from rdc_parser import RDCParser, ShaderInfo, extract_shaders, extract_textures, extract_resource_renames, TextureInfo, VK_FORMAT_NAMES, DrawEventContext, PipelineInfo
from mali_analyzer import MaliOfflineCompiler, ShaderAnalysisResult, MaliPerformanceMetrics
from schema import rdc_manifest
from tools import report_linking

RECONCILE_RATIO_THRESHOLD = 0.9

try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False


def compute_reconcile_summary(
    shader_chunk_total: int,
    texture_chunk_total: int,
    shader_count: int,
    texture_count: int,
    threshold: float = RECONCILE_RATIO_THRESHOLD,
    texture_total_label: str = "chunk",
) -> Dict[str, Any]:
    """Compute reconciliation ratios and approval requirement."""
    def ratio(count: int, total: int) -> float:
        if total <= 0:
            return 1.0 if count == 0 else 0.0
        return round(count / float(total), 2)

    shader_ratio = ratio(shader_count, shader_chunk_total)
    texture_ratio = ratio(texture_count, texture_chunk_total)

    issues = []
    if shader_ratio < threshold:
        missing = max(shader_chunk_total - shader_count, 0)
        issues.append(
            f"Shader ratio below threshold: {shader_ratio:.2f} < {threshold:.2f} "
            f"(missing {missing} of {shader_chunk_total}). Allow pass?"
        )
    if texture_ratio < threshold:
        missing = max(texture_chunk_total - texture_count, 0)
        issues.append(
            f"Texture ratio below threshold: {texture_ratio:.2f} < {threshold:.2f} "
            f"(missing {missing} of {texture_chunk_total}). Allow pass?"
        )

    return {
        "shader_chunk_total": shader_chunk_total,
        "texture_chunk_total": texture_chunk_total,
        "shader_count": shader_count,
        "texture_count": texture_count,
        "shader_ratio": shader_ratio,
        "texture_ratio": texture_ratio,
        "threshold": threshold,
        "texture_total_label": texture_total_label,
        "approval_required": bool(issues),
        "issues": issues,
    }


def choose_texture_source(
    exported_texture_list: List[Dict[str, Any]],
    replay_textures: List[Dict[str, Any]],
    chunk_textures: List[TextureInfo],
) -> Tuple[List[Any], str]:
    """Select texture source by priority: manifest -> replay API -> chunk parse."""
    if exported_texture_list:
        return exported_texture_list, "manifest"
    if replay_textures:
        return replay_textures, "replay_api"
    if chunk_textures:
        return chunk_textures, "chunk_parse"
    return [], "none"


def _infer_image_type(width: int, height: int, depth: int) -> int:
    if depth > 1:
        return 2
    if height > 1:
        return 1
    return 0


def _texture_detail_from_replay(tex_desc: Any, thumbnail_map: Dict[int, str]) -> Dict[str, Any]:
    format_name = tex_desc.format.Name() if hasattr(tex_desc.format, "Name") else str(tex_desc.format)
    resource_id = int(tex_desc.resourceId)
    mip_levels = getattr(tex_desc, "mips", getattr(tex_desc, "mipLevels", 1))
    array_layers = getattr(tex_desc, "arraysize", getattr(tex_desc, "arraySize", 1))
    samples = getattr(tex_desc, "samples", 1)
    usage = getattr(tex_desc, "usage", 0)
    width = int(tex_desc.width)
    height = int(tex_desc.height)
    depth = int(tex_desc.depth)
    image_type = _infer_image_type(width, height, depth)

    return {
        "resource_id": resource_id,
        "custom_name": getattr(tex_desc, "name", ""),
        "width": width,
        "height": height,
        "depth": depth,
        "format": format_name,
        "format_name": format_name,
        "mip_levels": int(mip_levels),
        "array_layers": int(array_layers),
        "samples": int(samples),
        "usage": usage,
        "image_type": image_type,
        "thumbnail": thumbnail_map.get(resource_id, ""),
    }


def extract_textures_via_replay(rdc_path: str) -> Tuple[List[Dict[str, Any]], str]:
    """Extract texture metadata via RenderDoc replay API (authoritative)."""
    if not HAS_RENDERDOC:
        return [], "renderdoc module not available"

    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_path, "", None)
    if status != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return [], f"OpenFile failed: {status}"

    if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
        cap.Shutdown()
        return [], "Local replay not supported"

    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return [], f"OpenCapture failed: {status}"

    try:
        textures = controller.GetTextures()
        return list(textures), ""
    finally:
        controller.Shutdown()
        cap.Shutdown()


def load_texture_thumbnails(rdc_path: str, as_base64: bool = True) -> Dict[int, str]:
    """加载纹理缩略图映射
    
    查找 RDC 文件同目录下的纹理导出目录，支持多种格式：
    - manifest.json (Python export_textures.py 输出)
    - textures.json (C++ renderdoccmd export 输出)
    
    返回 resource_id/index -> thumbnail_data 的映射。
    
    Args:
        rdc_path: RDC 文件路径
        as_base64: 是否转换为 Base64 Data URI（用于嵌入HTML）
        
    Returns:
        resource_id -> thumbnail_data 映射（Base64 Data URI 或文件路径）
    """
    # 委托给新函数，只返回缩略图部分
    result = load_textures_from_export(rdc_path, as_base64)
    return result.get("thumbnails", {})


def load_textures_from_export(rdc_path: str, as_base64: bool = True) -> Dict[str, Any]:
    """从导出目录加载完整的纹理元数据和缩略图
    
    支持两种导出格式：
    - manifest.json (Python export_textures.py 输出)
    - textures.json (C++ renderdoccmd export 输出)
    
    Args:
        rdc_path: RDC 文件路径
        as_base64: 是否转换缩略图为 Base64 Data URI
        
    Returns:
        {
            "thumbnails": {resource_id: thumbnail_data, ...},
            "texture_list": [完整纹理信息列表（用于 D3D11 fallback）]
        }
    """
    import base64
    from pathlib import Path
    
    rdc_path = Path(rdc_path)
    capture_name = rdc_path.stem
    
    # 尝试多个可能的路径和文件名（兼容 Python 和 C++ 导出工具）
    possible_paths = [
        # Python export_textures.py 格式
        rdc_path.parent / f"{capture_name}_textures" / "manifest.json",
        rdc_path.parent / "textures" / "manifest.json",
        rdc_path.parent / "output" / "textures" / "manifest.json",
        # C++ renderdoccmd export 格式
        rdc_path.parent / f"{capture_name}_textures" / "textures.json",
        rdc_path.parent / "textures" / "textures.json",
        rdc_path.parent / "output" / "textures" / "textures.json",
        rdc_path.parent / "output" / "textures.json",
    ]
    
    for manifest_path in possible_paths:
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                thumbnail_map = {}
                texture_list = []
                textures_dir = manifest_path.parent
                
                for tex in manifest.get("textures", []):
                    # 兼容两种格式：resource_id (Python) 或 id (C++)
                    res_id = tex.get("resource_id") or tex.get("id")
                    # 兼容两种格式：filename (Python) 或 file (C++)
                    filename = tex.get("filename") or tex.get("file")
                    
                    thumbnail_data = ""
                    if res_id is not None and filename:
                        full_path = textures_dir / filename
                        if full_path.exists():
                            if as_base64:
                                try:
                                    with open(full_path, 'rb') as img_file:
                                        img_data = img_file.read()
                                        b64_data = base64.b64encode(img_data).decode('utf-8')
                                        # 根据文件扩展名确定 MIME 类型
                                        ext = full_path.suffix.lower()
                                        mime_type = {
                                            '.png': 'image/png',
                                            '.jpg': 'image/jpeg',
                                            '.jpeg': 'image/jpeg',
                                            '.webp': 'image/webp',
                                        }.get(ext, 'image/png')
                                        thumbnail_data = f"data:{mime_type};base64,{b64_data}"
                                        thumbnail_map[res_id] = thumbnail_data
                                except IOError as e:
                                    print(f"  [WARN] Failed to read thumbnail: {full_path}: {e}")
                            else:
                                thumbnail_data = str(full_path)
                                thumbnail_map[res_id] = thumbnail_data
                        else:
                            print(f"  [WARN] Texture file not found: {full_path}")
                    
                    # 构建完整的纹理信息（用于 D3D11/D3D12 fallback）
                    texture_list.append({
                        "resource_id": res_id,
                        "custom_name": tex.get("name", ""),  # C++ export 的 name 字段
                        "width": tex.get("width", 0),
                        "height": tex.get("height", 0),
                        "depth": tex.get("depth", 1),
                        "format": 0,  # D3D11 没有 VK_FORMAT 枚举
                        "format_name": tex.get("format", "UNKNOWN"),  # C++ export 直接给格式名
                        "mip_levels": tex.get("mips", 1),
                        "array_layers": tex.get("arrayLayers", 1),
                        "samples": tex.get("samples", 1),
                        "usage": 0,
                        "image_type": 1,  # 默认 2D
                        "thumbnail": thumbnail_data
                    })
                
                if thumbnail_map:
                    print(f"  [INFO] Loaded {len(thumbnail_map)} texture thumbnails from {manifest_path}")
                    return {"thumbnails": thumbnail_map, "texture_list": texture_list}
            except (json.JSONDecodeError, IOError) as e:
                print(f"  [WARN] Failed to load manifest: {manifest_path}: {e}")
    
    print(f"  [INFO] No texture manifest found for {rdc_path.name}")
    return {"thumbnails": {}, "texture_list": []}


def resolve_full_report_json(rdc_path: str, explicit_json: str) -> str:
    """Resolve capture.json for full HTML report generation."""
    candidates = []
    if explicit_json:
        candidates.append(Path(explicit_json))
    base_path = Path(rdc_path)
    candidates.append(base_path.with_suffix(".json"))
    candidates.append(base_path.with_name(f"{base_path.stem}_data.json"))

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return ""


def normalize_full_report_json(json_path: str) -> str:
    """Ensure full report input is a single capture dict, not a list wrapper."""
    path = Path(json_path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return json_path

    if not isinstance(payload, list):
        return json_path

    if len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValueError("Full report requires JSON object or single-item result list")

    normalized_path = path.with_name(f"{path.stem}_single.json")
    with open(normalized_path, "w", encoding="utf-8") as f:
        json.dump(payload[0], f, indent=2, ensure_ascii=False)

    return str(normalized_path)


def resolve_textures_dir(rdc_path: str, explicit_dir: str) -> str:
    """Resolve textures directory that contains manifest.json or textures.json."""
    if explicit_dir:
        explicit_path = Path(explicit_dir)
        if explicit_path.exists():
            return str(explicit_path)
        print(f"  [WARN] Textures dir not found: {explicit_dir}")

    base_path = Path(rdc_path)
    capture_name = base_path.stem
    candidates = [
        base_path.parent / f"{capture_name}_textures",
        base_path.parent / "textures",
        base_path.parent / "output" / "textures",
        base_path.parent / "output",
    ]
    for candidate in candidates:
        if (candidate / "manifest.json").exists() or (candidate / "textures.json").exists():
            return str(candidate)
    return ""


def _normalize_report_event_type(event_type: str) -> str:
    """Normalize parser event subtype into report event type buckets."""
    if not event_type:
        return "unknown"
    if event_type.startswith("draw"):
        return "draw"
    if event_type.startswith("dispatch"):
        return "dispatch"
    return event_type


def convert_pipelines_to_capture_pipelines(pipelines: Dict[int, PipelineInfo]) -> List[Dict[str, Any]]:
    """Convert parser PipelineInfo map into JSON-safe capture schema."""
    pipeline_details: List[Dict[str, Any]] = []
    for pipeline_id in sorted(pipelines.keys()):
        pipeline_info = pipelines[pipeline_id]
        shader_stages: Dict[str, int] = {}
        for stage, shader_id in pipeline_info.shader_stages.items():
            stage_name = str(stage).upper()
            if stage_name == "FS":
                stage_name = "PS"
            shader_stages[stage_name] = int(shader_id)

        pipeline_details.append(
            {
                "resourceId": int(pipeline_info.resource_id),
                "pipelineType": pipeline_info.pipeline_type,
                "shaderStages": shader_stages,
            }
        )

    return pipeline_details


def convert_draw_events_to_capture_events(
    draw_events: List[DrawEventContext],
    pipelines: Dict[int, PipelineInfo],
) -> List[Dict[str, Any]]:
    """Convert DrawEventContext list into capture-event records for full report input."""
    capture_events: List[Dict[str, Any]] = []

    for draw_event in draw_events:
        raw_type = draw_event.event_type
        event_type = _normalize_report_event_type(raw_type)
        pipeline_id = int(draw_event.pipeline_resource_id)

        event_payload: Dict[str, Any] = {
            "eventId": int(draw_event.chunk_index),
            "chunkId": int(draw_event.chunk_id),
            "name": draw_event.event_name,
            "type": event_type,
            "subtype": raw_type,
            "pipeline": pipeline_id,
            "markerPath": draw_event.marker_path,
            "flags": [],
            "params": [],
        }

        pipeline_info = pipelines.get(pipeline_id)
        if pipeline_info is not None:
            shader_stage_payload: Dict[str, Dict[str, int]] = {}
            for stage, shader_id in pipeline_info.shader_stages.items():
                stage_name = str(stage).upper()
                if stage_name == "FS":
                    stage_name = "PS"
                shader_stage_payload[stage_name] = {"resourceId": int(shader_id)}

            event_payload["pipelineState"] = {
                "resourceId": int(pipeline_info.resource_id),
                "pipelineType": pipeline_info.pipeline_type,
                "shaders": shader_stage_payload,
            }

        capture_events.append(event_payload)

    return capture_events


def analyze_rdc_file(
    rdc_path: str,
    gpu_core: str = "Mali-G715",
    max_workers: int = 4,
    verbose: bool = False
) -> Dict[str, Any]:
    """分析单个 RDC 文件
    
    支持的图形 API:
    - Vulkan: 完整分析（Shader + Mali 编译器 + 资源）
    - D3D11/D3D12: 基础分析（资源信息，无 Mali 分析）
    
    Returns:
        分析结果字典
    """
    print(f"\n{'='*60}")
    print(f"Analyzing: {rdc_path}")
    print(f"{'='*60}")

    chunk_counts = {}
    # 1. 解析 RDC 文件头
    print("\n[1/5] Parsing RDC file...")
    with RDCParser(rdc_path) as parser:
        info = parser.parse_header()
        driver_name = info.metadata.driver_name
        is_vulkan = info.is_vulkan
        is_d3d11 = info.is_d3d11
        is_d3d12 = info.is_d3d12
        
        print(f"  Driver: {driver_name}")
        print(f"  File size: {info.file_size / 1024 / 1024:.2f} MB")
        
        # 根据 API 类型分发不同的解析路径
        if is_vulkan:
            chunk_counts = parser.count_vulkan_chunks()
            # Vulkan: 完整分析（SPIR-V + Mali）
            shaders = parser.extract_vulkan_shaders()
            print("\n[2/5] Extracting draw events and pipelines...")
            draw_events, pipelines = parser.extract_draw_events()
        elif is_d3d11 or is_d3d12:
            # D3D11/D3D12: 基础分析（无 Mali）
            print(f"  [INFO] {driver_name} capture detected - Mali analysis not applicable")
            print("  [INFO] Generating basic resource report...")
            shaders = []  # D3D11/D3D12 shader 需要不同的解析器
            draw_events = []
            pipelines = {}
        else:
            # 未知 API
            print(f"  [WARN] Unknown driver: {driver_name}")
            shaders = []
            draw_events = []
            pipelines = {}
    
    print(f"  Driver: {info.metadata.driver_name}")
    # 打印解析结果统计
    if shaders:
        print(f"  Shaders found: {len(shaders)}")
    print(f"  Draw events: {len(draw_events)}")
    print(f"  Pipelines: {len(pipelines)}")
    
    # 1.5. 提取纹理信息
    print("\n[3/5] Extracting texture metadata...")

    # 优先读取导出的纹理清单（manifest/textures.json）
    export_data = load_textures_from_export(rdc_path, as_base64=True)
    thumbnail_map = export_data.get("thumbnails", {})
    exported_texture_list = export_data.get("texture_list", [])

    if thumbnail_map:
        print(f"  Thumbnails available: {len(thumbnail_map)}")

    # 若未导出清单，尝试 Replay API 获取权威纹理元数据
    replay_textures = []
    replay_reason = ""
    if not exported_texture_list:
        replay_textures, replay_reason = extract_textures_via_replay(rdc_path)

    # 若 Replay 不可用，才回退到 chunk 解析
    chunk_textures = []
    if not exported_texture_list and not replay_textures:
        chunk_textures = extract_textures(rdc_path)

    _, texture_source = choose_texture_source(
        exported_texture_list, replay_textures, chunk_textures
    )

    if texture_source == "manifest":
        print(f"  Textures found: {len(exported_texture_list)} (manifest)")
    elif texture_source == "replay_api":
        print(f"  Textures found: {len(replay_textures)} (replay API)")
    elif texture_source == "chunk_parse":
        print(f"  Textures found: {len(chunk_textures)} (chunk)")
    else:
        print("  Textures found: 0")
    
    # 1.5.1 提取用户自定义资源名称
    resource_renames = extract_resource_renames(rdc_path)
    if resource_renames:
        print(f"  Custom resource names: {len(resource_renames)}")
    
    # 1.6 建立 ShaderModule -> 使用统计的映射（仅 Vulkan）
    shader_usage_stats: Dict[int, Dict[str, Any]] = {}
    
    if shaders:
        for pipeline_id, pipeline_info in pipelines.items():
            for stage, shader_module_id in pipeline_info.shader_stages.items():
                if shader_module_id not in shader_usage_stats:
                    shader_usage_stats[shader_module_id] = {
                        "pipeline_ids": set(),
                        "event_count": 0,
                        "marker_paths": set()
                    }
                shader_usage_stats[shader_module_id]["pipeline_ids"].add(pipeline_id)
        
        # 统计每个 shader 的 event count
        for event in draw_events:
            pipeline_id = event.pipeline_resource_id
            if pipeline_id in pipelines:
                pipeline_info = pipelines[pipeline_id]
                for stage, shader_module_id in pipeline_info.shader_stages.items():
                    if shader_module_id in shader_usage_stats:
                        shader_usage_stats[shader_module_id]["event_count"] += 1
                        if event.marker_path:
                            shader_usage_stats[shader_module_id]["marker_paths"].add(event.marker_path)
    
    # 2. Mali 分析（仅 Vulkan SPIR-V）
    results = []
    valid_results = []
    
    if shaders and is_vulkan:
        print(f"\n[4/5] Analyzing shaders with Mali Offline Compiler ({gpu_core})...")
        
        malioc = MaliOfflineCompiler()
        print(f"  Compiler version: {malioc.version.split(chr(10))[0]}")
        
        spirv_data_list = [s.spirv_data for s in shaders]
        
        def progress(current, total):
            pct = current * 100 // total
            bar = '#' * (pct // 5) + '-' * (20 - pct // 5)
            print(f"\r  Progress: [{bar}] {current}/{total} ({pct}%)", end='', flush=True)
        
        results = malioc.analyze_shaders_batch(
            spirv_data_list,
            gpu_core=gpu_core,
            max_workers=max_workers,
            progress_callback=progress
        )
        print()  # 换行
        valid_results = [r for r in results if r.is_valid]
        print(f"  Valid analyses: {len(valid_results)}/{len(results)}")
    else:
        print(f"\n[4/5] Skipping Mali analysis (not applicable for {driver_name})")
    
    # 3. 汇总结果
    print("\n[5/5] Generating summary...")
    
    # 统计
    total_cycles = sum(r.metrics.longest_path for r in valid_results)
    avg_cycles = total_cycles / len(valid_results) if valid_results else 0
    max_cycles = max((r.metrics.longest_path for r in valid_results), default=0)
    min_cycles = min((r.metrics.longest_path for r in valid_results), default=0)
    
    spill_count = sum(1 for r in valid_results if r.metrics.has_stack_spilling)
    
    # Shader 类型统计
    type_counts = {}
    for r in valid_results:
        t = r.metrics.shader_type or "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1
    
    shader_data_reason = ""
    if not shaders:
        if is_vulkan:
            shader_data_reason = (
                "No SPIR-V extracted from vkCreateShaderModule/vkCreateShadersEXT. "
                "Capture may use shader objects or an unsupported chunk layout."
            )
        else:
            shader_data_reason = f"{driver_name} capture - shader extraction not implemented."

    summary = {
        "file": rdc_path,
        "file_name": os.path.basename(rdc_path),
        "driver": info.metadata.driver_name,
        "gpu_core": gpu_core,
        "total_shaders": len(shaders),
        "analyzed_shaders": len(valid_results),
        "failed_analyses": len(results) - len(valid_results),
        "shader_types": type_counts,
        "cycles": {
            "total": total_cycles,
            "average": avg_cycles,
            "max": max_cycles,
            "min": min_cycles
        },
        "spilling_shaders": spill_count,
        "timestamp": datetime.now().isoformat(),
        # Pipeline/Event statistics
        "total_draw_events": len(draw_events),
        "total_pipelines": len(pipelines),
        "graphics_pipelines": sum(1 for p in pipelines.values() if p.pipeline_type == 'graphics'),
        "compute_pipelines": sum(1 for p in pipelines.values() if p.pipeline_type == 'compute'),
    }
    if shader_data_reason:
        summary["shader_data_reason"] = shader_data_reason
    
    # 详细结果
    shader_details = []
    for i, (shader, result) in enumerate(zip(shaders, results)):
        # 计算 shader hash 用于跨文件匹配
        shader_hash = compute_shader_hash(shader.spirv_data)
        
        # 获取 shader 名称信息
        shader_name = shader.display_name  # 如 "VS:main" 或 "PS:fragment_main"
        entry_name = shader.entry_name     # 如 "main"
        stage = shader.stage               # 如 "VS", "PS", "CS"
        friendly_label = shader.friendly_label  # 如 "ReflectionCapture" 或 "EyeAdaptation"
        
        # 资源统计
        res_summary = shader.resource_summary
        all_resources = [{"id": r.spirv_id, "name": r.name, "category": r.category} 
                        for r in shader.all_resources]
        
        detail = {
            "index": i,
            "hash": shader_hash,
            "name": shader_name,
            "entry_name": entry_name,
            "stage": stage,
            "friendly_label": friendly_label,
            "size": shader.code_size,
            "spirv_version": shader.spirv_version,
            "valid": result.is_valid,
            # 资源统计
            "resource_count": res_summary["total"],
            "texture_count": res_summary["texture_count"],
            "sampler_count": res_summary["sampler_count"],
            "buffer_count": res_summary["buffer_count"],
            "uniform_count": res_summary["uniform_count"],
            "resources": all_resources,  # 完整资源列表
        }
        
        if result.is_valid:
            m = result.metrics
            detail.update({
                "type": m.shader_type,
                "work_registers": m.work_registers,
                "uniform_registers": m.uniform_registers,
                "total_cycles": m.total_cycles,
                "shortest_path": m.shortest_path,
                "longest_path": m.longest_path,
                "fma_cycles": m.fma_cycles,
                "cvt_cycles": m.cvt_cycles,
                "sfu_cycles": m.sfu_cycles,
                "load_store_cycles": m.load_store_cycles,
                "texture_cycles": m.texture_cycles,
                "varying_cycles": m.varying_cycles,
                "has_spilling": m.has_stack_spilling,
                "spill_count": m.spill_count
            })
        else:
            detail["error"] = result.metrics.error_message
        
        shader_details.append(detail)
    
    # 纹理详情
    texture_details = []

    if texture_source == "chunk_parse":
        # Vulkan / OpenGL：使用 extract_textures 解析的原始数据
        for tex in chunk_textures:
            format_name = VK_FORMAT_NAMES.get(tex.format, f"VK_FORMAT_{tex.format}")
            # 查找用户自定义名称
            custom_name = resource_renames.get(tex.resource_id, "")
            # 查找缩略图 Base64 数据
            thumbnail = thumbnail_map.get(tex.resource_id, "")
            texture_details.append({
                "resource_id": tex.resource_id,
                "custom_name": custom_name,  # 用户自定义名称
                "width": tex.width,
                "height": tex.height,
                "depth": tex.depth,
                "format": tex.format,
                "format_name": format_name,
                "mip_levels": tex.mip_levels,
                "array_layers": tex.array_layers,
                "samples": tex.samples,
                "usage": tex.usage,
                "image_type": tex.image_type,  # 0=1D, 1=2D, 2=3D
                "thumbnail": thumbnail  # Base64 Data URI（如果可用）
            })
    elif texture_source == "replay_api":
        for tex_desc in replay_textures:
            detail = _texture_detail_from_replay(tex_desc, thumbnail_map)
            # 优先使用资源重命名信息
            resource_id = detail.get("resource_id", 0)
            if resource_id in resource_renames:
                detail["custom_name"] = resource_renames[resource_id]
            texture_details.append(detail)
    elif texture_source == "manifest":
        # 导出清单（manifest/textures.json）直接使用
        texture_details = exported_texture_list
    
    texture_data_reason = ""
    if not texture_details:
        reasons = []
        if replay_reason:
            reasons.append(f"Replay API unavailable: {replay_reason}.")
        if is_vulkan:
            reasons.append(
                "No vkCreateImage parsed and no manifest.json/textures.json found. "
                "Run export_textures_rdoc.py or renderdoccmd export to provide texture metadata."
            )
        else:
            reasons.append(f"{driver_name} capture - texture extraction not implemented.")
        texture_data_reason = " ".join(reasons)

    # 更新 summary 包含纹理统计
    summary["total_textures"] = len(texture_details)
    summary["texture_source"] = texture_source
    if texture_source == "manifest":
        summary["ui_texture_count"] = len(exported_texture_list)
    elif texture_source == "replay_api":
        summary["ui_texture_count"] = len(replay_textures)
    if texture_data_reason:
        summary["texture_data_reason"] = texture_data_reason

    if chunk_counts:
        texture_total_label = "chunk"
        texture_total_for_ratio = chunk_counts.get("vkCreateImage", 0)
        ui_texture_count = summary.get("ui_texture_count")
        if ui_texture_count is not None:
            texture_total_label = "ui"
            texture_total_for_ratio = ui_texture_count

        reconcile = compute_reconcile_summary(
            shader_chunk_total=chunk_counts.get("vkCreateShaderModule", 0)
            + chunk_counts.get("vkCreateShadersEXT", 0),
            texture_chunk_total=texture_total_for_ratio,
            shader_count=len(shader_details),
            texture_count=len(texture_details),
            texture_total_label=texture_total_label,
        )
        if texture_total_label == "ui":
            reconcile["texture_chunk_total_raw"] = chunk_counts.get("vkCreateImage", 0)
        summary["reconcile_chunks"] = reconcile
    
    event_details = convert_draw_events_to_capture_events(draw_events, pipelines)
    pipeline_details = convert_pipelines_to_capture_pipelines(pipelines)

    api_type = driver_name
    if is_vulkan:
        api_type = "Vulkan"
    elif is_d3d11:
        api_type = "D3D11"
    elif is_d3d12:
        api_type = "D3D12"

    return {
        "apiType": api_type,
        "summary": summary,
        "shaders": shader_details,
        "textures": texture_details,
        "events": event_details,
        "pipelines": pipeline_details,
    }


import hashlib


def compute_shader_hash(spirv_data: bytes) -> str:
    """计算 SPIR-V 数据的 SHA256 哈希（用于跨文件匹配）"""
    return hashlib.sha256(spirv_data).hexdigest()[:16]


def write_v3_manifest(
    output_path: Path | str,
    analysis_results: List[Dict],
    capture_id: str | None = None,
) -> Dict[str, Any]:
    output_path = Path(output_path)

    if not capture_id:
        source_paths = []
        for result in analysis_results:
            summary = result.get("summary", {})
            source_path = summary.get("file")
            if source_path:
                source_paths.append(source_path)
        if not source_paths:
            source_paths = [str(output_path)]
        capture_id = report_linking.compute_capture_id(source_paths)

    total_events = 0
    total_textures = 0
    total_shaders = 0
    texture_source = "unknown"

    missing_reason = []
    missing_seen = set()

    for result in analysis_results:
        summary = result.get("summary", {})
        total_events += summary.get("total_draw_events", 0)

        textures = result.get("textures", [])
        texture_count = len(textures) if isinstance(textures, list) else 0
        if texture_count == 0:
            texture_count = summary.get("total_textures", 0)
        total_textures += texture_count

        shaders = result.get("shaders", [])
        shader_count = len(shaders) if isinstance(shaders, list) else 0
        if shader_count == 0:
            shader_count = summary.get("total_shaders", summary.get("analyzed_shaders", 0))
        total_shaders += shader_count

        candidate_texture_source = summary.get("texture_source")
        if candidate_texture_source:
            texture_source = candidate_texture_source

        texture_reason = summary.get("texture_data_reason")
        if texture_reason:
            key = ("textures", texture_reason)
            if key not in missing_seen:
                missing_seen.add(key)
                missing_reason.append({"field": "textures", "reason": texture_reason})

        shader_reason = summary.get("shader_data_reason")
        if shader_reason:
            key = ("shaders", shader_reason)
            if key not in missing_seen:
                missing_seen.add(key)
                missing_reason.append({"field": "shaders", "reason": shader_reason})

    counts = {
        "events": total_events,
        "textures": total_textures,
        "shaders": total_shaders,
    }

    count_reason = {
        "events": "rdc_log",
        "textures": texture_source,
        "shaders": "chunk_parse",
    }

    report_links = report_linking.default_report_links(output_path, "v3")
    manifest = rdc_manifest.build_manifest(
        capture_id=capture_id,
        source="A",
        counts=counts,
        count_reason=count_reason,
        missing=missing_reason,
        report_links=report_links,
    )
    report_linking.write_manifest_bundle(output_path, manifest, report_links)
    return manifest


def generate_html_report(analysis_results: List[Dict], output_path: str):
    """生成 HTML 报告 V3 - 深色主题 + 左侧概览 + 纹理网格视图 + Lightbox"""
    # Load external CSS/JS assets
    from string import Template
    
    _assets_dir = Path(__file__).parent / "assets"
    _css_path = _assets_dir / "styles" / "mali_report.css"
    _js_path = _assets_dir / "scripts" / "mali_report.js"
    
    _inline_css = _css_path.read_text(encoding="utf-8") if _css_path.exists() else "/* CSS not found */"
    _inline_js = _js_path.read_text(encoding="utf-8") if _js_path.exists() else "// JS not found"
    # Replace $ANALYSIS_DATA placeholder in JS (will be handled separately)
    _inline_js = _inline_js.replace("$ANALYSIS_DATA", "null")  # Placeholder, actual data injected via string concat

    
    # 准备 JavaScript 数据
    results_for_html = []
    for r in analysis_results:
        if isinstance(r, dict):
            r2 = dict(r)
            r2.pop("events", None)
            r2.pop("draw_events", None)
            r2.pop("pipelines", None)
            results_for_html.append(r2)
        else:
            results_for_html.append(r)

    all_shaders_json = json.dumps(results_for_html, ensure_ascii=False)
    
    # 计算汇总统计
    total_shaders = sum(r["summary"]["analyzed_shaders"] for r in analysis_results)
    total_textures = sum(len(r.get("textures", [])) for r in analysis_results)
    total_buffers = sum(r["summary"].get("total_buffers", 0) for r in analysis_results)
    total_draw_events = sum(r["summary"].get("total_draw_events", 0) for r in analysis_results)
    total_spilling = sum(r["summary"]["spilling_shaders"] for r in analysis_results)
    
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RDC Analyzer Report V3</title>
    
    <!-- 100% 离线版本 - 无外部依赖 -->
    
    <style>
$INLINE_CSS
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                    <polyline points="2 17 12 22 22 17"></polyline>
                    <polyline points="2 12 12 17 22 12"></polyline>
                </svg>
                Mali Shader Analysis Report
            </h1>
            <div class="header-meta">
                Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
            </div>
        </div>
"""
    
    # 生成 Tab 导航
    tab_items = []
    if len(analysis_results) > 1:
        tab_items.append(('comparison', '📊 Comparison'))
    for i, result in enumerate(analysis_results):
        fname = result["summary"]["file_name"]
        short_name = fname[:20] + "..." if len(fname) > 23 else fname
        tab_items.append((f'file{i}', f'📁 {short_name}'))
    
    # 添加纹理 Tab
    tab_items.append(('textures', '🖼️ Textures'))
    
    html += """
        <div class="tabs">
"""
    for i, (tab_id, tab_label) in enumerate(tab_items):
        active = ' active' if i == 0 else ''
        html += f'            <button class="tab{active}" data-tab="{tab_id}">{tab_label}</button>\n'
    html += """        </div>
"""
    
    # 比较视图（如果有多个文件）
    if len(analysis_results) > 1:
        html += """
        <div id="comparison" class="tab-content active">
            <div class="card">
                <div class="card-title">📊 Files Overview</div>
                <div class="summary-grid">
"""
        for i, result in enumerate(analysis_results):
            s = result["summary"]
            html += f"""
                    <div class="stat-card">
                        <div class="stat-label">{s['file_name'][:15]}...</div>
                        <div class="stat-value">{s['analyzed_shaders']}</div>
                        <div class="stat-label">Shaders</div>
                    </div>
"""
        html += """
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">🔍 Shader Comparison (by Hash)</div>
                <table id="comparison-table" class="display" style="width:100%">
                    <thead>
                        <tr>
                            <th>Index</th>
                            <th>Stage</th>
                            <th>Hash</th>
                            <th>Resource Hint</th>
                            <th>Size</th>
"""
        for result in analysis_results:
            fname = result["summary"]["file_name"][:12]
            html += f'                            <th>{fname} Cycles</th>\n'
        html += """                            <th>Diff</th>
                        </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
            </div>
        </div>
"""
    
    # 每个文件的详细视图
    for file_idx, result in enumerate(analysis_results):
        s = result["summary"]
        active = ' active' if (len(analysis_results) == 1 and file_idx == 0) else ''
        
        # Extract context stats with defaults
        total_events = s.get('total_draw_events', 0)
        total_pipelines = s.get('total_pipelines', 0)
        
        shader_reason = s.get("shader_data_reason", "")
        shader_reason_html = f'<div class="placeholder-hint">{shader_reason}</div>' if shader_reason else ""
        reconcile = s.get("reconcile_chunks")
        reconcile_html = ""
        if reconcile:
            shader_ratio = reconcile.get("shader_ratio", 0.0)
            texture_ratio = reconcile.get("texture_ratio", 0.0)
            threshold = reconcile.get("threshold", RECONCILE_RATIO_THRESHOLD)
            approval_required = reconcile.get("approval_required", False)
            issues = reconcile.get("issues", [])
            issues_html = "<br>".join(issues) if issues else ""
            reconcile_html = f"""
            <div class="card">
                <div class="card-title">✅ Reconciliation</div>
                <div class="summary-grid">
                    <div class="stat-card">
                        <div class="stat-value {'danger' if shader_ratio < threshold else 'success'}">{shader_ratio:.2f}</div>
                        <div class="stat-label">Shader Ratio</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value {'danger' if texture_ratio < threshold else 'success'}">{texture_ratio:.2f}</div>
                        <div class="stat-label">Texture Ratio</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value info">{threshold:.2f}</div>
                        <div class="stat-label">Threshold</div>
                    </div>
                </div>
                {f'<div class="placeholder-hint">{issues_html}</div>' if approval_required else ''}
            </div>
            """

        html += f"""
        <div id="file{file_idx}" class="tab-content{active}">
            <div class="card">
                <div class="card-title">📈 Summary - {s['file_name']}</div>
                <div class="summary-grid">
                    <div class="stat-card">
                        <div class="stat-value">{s['analyzed_shaders']}</div>
                        <div class="stat-label">Shaders</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{s['cycles']['average']:.1f}</div>
                        <div class="stat-label">Avg Cycles</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value warning">{s['cycles']['max']:.1f}</div>
                        <div class="stat-label">Max Cycles</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value {'danger' if s['spilling_shaders'] > 0 else 'success'}">{s['spilling_shaders']}</div>
                        <div class="stat-label">Spilling</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value info">{total_events}</div>
                        <div class="stat-label">Draw Events</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{total_pipelines}</div>
                        <div class="stat-label">Pipelines</div>
                    </div>
                </div>
            </div>
            {reconcile_html}
            <div class="card">
                <div class="card-title">📋 Shader Details <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: normal;">(Click row to expand resources)</span></div>
                <table id="shader-table-{file_idx}" class="display" style="width:100%">
                    <thead>
                        <tr>
                            <th></th>
                            <th>Index</th>
                            <th>Stage</th>
                            <th>Hash</th>
                            <th>Resource Hint</th>
                            <th>Res</th>
                            <th>Size (B)</th>
                            <th>Work Reg</th>
                            <th>Uniform Reg</th>
                            <th>Cycles</th>
                            <th>FMA</th>
                            <th>CVT</th>
                            <th>SFU</th>
                            <th>LS</th>
                            <th>Tex</th>
                            <th>Spill</th>
                        </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
                {shader_reason_html}
            </div>
        </div>
"""
    
    # 纹理 Tab 内容 - V3 Grid/Table 双视图 + Lightbox
    total_textures = sum(len(r.get("textures", [])) for r in analysis_results)
    html += f"""
        <div id="textures" class="tab-content">
            <div class="card">
                <div class="card-title">🖼️ Texture Overview</div>
                <div class="summary-grid">
"""
    for i, result in enumerate(analysis_results):
        tex_count = len(result.get("textures", []))
        fname = result["summary"]["file_name"][:15]
        html += f"""
                    <div class="stat-card">
                        <div class="stat-label">{fname}...</div>
                        <div class="stat-value">{tex_count}</div>
                        <div class="stat-label">Textures</div>
                    </div>
"""
    html += """
                </div>
            </div>
            
            <div class="card">
                <div class="card-title" style="justify-content: space-between;">
                    <span>📋 Texture Details</span>
                    <div class="view-toggle">
                        <button class="view-btn active" data-view="grid" title="Grid View">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <rect x="3" y="3" width="7" height="7" rx="1"/>
                                <rect x="14" y="3" width="7" height="7" rx="1"/>
                                <rect x="3" y="14" width="7" height="7" rx="1"/>
                                <rect x="14" y="14" width="7" height="7" rx="1"/>
                            </svg>
                        </button>
                        <button class="view-btn" data-view="table" title="Table View">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <rect x="3" y="4" width="18" height="3" rx="1"/>
                                <rect x="3" y="10" width="18" height="3" rx="1"/>
                                <rect x="3" y="16" width="18" height="3" rx="1"/>
                            </svg>
                        </button>
                    </div>
                </div>
                
                <!-- Grid View -->
                <div id="texture-grid-view" class="texture-view active">
                    <div class="texture-grid-controls">
                        <input type="text" id="texture-grid-search" placeholder="🔍 Search textures..." class="grid-search">
                        <select id="texture-grid-filter" class="grid-filter">
                            <option value="">All Types</option>
                            <option value="2D">2D Textures</option>
                            <option value="3D">3D Textures</option>
                            <option value="1D">1D Textures</option>
                        </select>
                    </div>
                    <div id="texture-grid" class="texture-grid">
                        <!-- Populated by JavaScript -->
                    </div>
                </div>
                
                <!-- Table View -->
                <div id="texture-table-view" class="texture-view">
                    <table id="texture-table" class="display" style="width:100%">
                        <thead>
                            <tr>
                                <th>File</th>
                                <th>Resource ID</th>
                                <th>Custom Name</th>
                                <th>Type</th>
                                <th>Dimensions</th>
                                <th>Format</th>
                                <th>Mips</th>
                                <th>Layers</th>
                                <th>Samples</th>
                                <th>Usage</th>
                            </tr>
                        </thead>
                        <tbody>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- Lightbox Modal -->
        <div id="texture-lightbox" class="lightbox">
            <div class="lightbox-content">
                <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
                <button class="lightbox-nav lightbox-prev" onclick="navigateLightbox(-1)">&#10094;</button>
                <button class="lightbox-nav lightbox-next" onclick="navigateLightbox(1)">&#10095;</button>
                
                <div class="lightbox-image-container" id="lightbox-image-container">
                    <!-- 真实图片预览（如果有缩略图） -->
                    <img id="lightbox-preview-img" class="lightbox-preview-img" style="display: none;" alt="Texture Preview">
                    
                    <!-- 占位符（没有缩略图时显示） -->
                    <div id="lightbox-placeholder" class="lightbox-placeholder">
                        <svg width="120" height="120" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                            <circle cx="8.5" cy="8.5" r="1.5"/>
                            <polyline points="21 15 16 10 5 21"/>
                        </svg>
                        <div class="placeholder-text">Texture Preview</div>
                        <div class="placeholder-hint">Run export_textures.py first to generate thumbnails</div>
                    </div>
                </div>
                
                <div class="lightbox-info">
                    <h3 id="lightbox-title">Texture Name</h3>
                    <div class="lightbox-props">
                        <div class="lightbox-prop">
                            <span class="prop-label">Resource ID</span>
                            <span class="prop-value" id="lightbox-resid">-</span>
                        </div>
                        <div class="lightbox-prop">
                            <span class="prop-label">Dimensions</span>
                            <span class="prop-value" id="lightbox-dims">-</span>
                        </div>
                        <div class="lightbox-prop">
                            <span class="prop-label">Format</span>
                            <span class="prop-value" id="lightbox-format">-</span>
                        </div>
                        <div class="lightbox-prop">
                            <span class="prop-label">Mip Levels</span>
                            <span class="prop-value" id="lightbox-mips">-</span>
                        </div>
                        <div class="lightbox-prop">
                            <span class="prop-label">Array Layers</span>
                            <span class="prop-value" id="lightbox-layers">-</span>
                        </div>
                        <div class="lightbox-prop">
                            <span class="prop-label">Samples</span>
                            <span class="prop-value" id="lightbox-samples">-</span>
                        </div>
                    </div>
                    <div class="lightbox-channels">
                        <span class="channel-label">Channels:</span>
                        <button class="channel-btn active" data-channel="rgba">RGBA</button>
                        <button class="channel-btn" data-channel="r">R</button>
                        <button class="channel-btn" data-channel="g">G</button>
                        <button class="channel-btn" data-channel="b">B</button>
                        <button class="channel-btn" data-channel="a">A</button>
                    </div>
                </div>
            </div>
        </div>
"""
    
    html += """
        <footer>
            RenderDoc Mali Analyzer v2.0 | Powered by Mali Offline Compiler
        </footer>
    </div>
    
    <script>
        // Analysis data
        const analysisData = """ + all_shaders_json + """;

$INLINE_JS
    </script>
</body>
</html>
"""

    manifest = write_v3_manifest(output_path, analysis_results)
    manifest_json = json.dumps(manifest, ensure_ascii=False)
    report_links_json = json.dumps(manifest.get("report_links", {}), ensure_ascii=False)

    html = html.replace(
        "<script>",
        "<script>\n"
        f"        const manifestData = {manifest_json};\n"
        f"        const reportLinks = {report_links_json};\n",
        1,
    )

    panel_js = """
        function renderConsistencyPanel() {
            const panel = document.createElement('div');
            panel.id = 'consistency-panel';
            panel.style.position = 'fixed';
            panel.style.right = '16px';
            panel.style.bottom = '16px';
            panel.style.zIndex = '9999';
            panel.style.background = 'rgba(22, 27, 34, 0.95)';
            panel.style.border = '1px solid #30363d';
            panel.style.padding = '10px 12px';
            panel.style.borderRadius = '8px';
            panel.style.fontSize = '12px';
            panel.style.maxWidth = '320px';
            const counts = (manifestData && manifestData.counts) ? manifestData.counts : {};
            const missing = (manifestData && manifestData.missing_reason) ? manifestData.missing_reason : [];
            const missingHtml = missing.length
                ? missing.map(item => `<li>${item.field}: ${item.reason}</li>`).join('')
                : '<li>none</li>';
            panel.innerHTML = `
                <div style="font-weight:600;margin-bottom:6px;">Consistency</div>
                <div>Events: ${counts.events ?? 0}</div>
                <div>Textures: ${counts.textures ?? 0}</div>
                <div>Shaders: ${counts.shaders ?? 0}</div>
                <div style="margin-top:6px;">Missing:</div>
                <ul style="margin:4px 0 0 16px;padding:0;">${missingHtml}</ul>
            `;
            document.body.appendChild(panel);
        }

        function applyHashJump() {
            if (!location.hash) return;
            const [key, value] = location.hash.slice(1).split('=');
            if (!key || !value) return;
            const selectors = [
                `[data-${key}='${value}']`,
                `#${key}-${value}`,
                `#${value}`
            ];
            let target = null;
            for (const sel of selectors) {
                const node = document.querySelector(sel);
                if (node) { target = node; break; }
            }
            if (target) {
                target.scrollIntoView({behavior: 'smooth', block: 'center'});
                target.classList.add('jump-highlight');
            } else {
                const panel = document.getElementById('consistency-panel');
                if (panel) {
                    panel.innerHTML += `<div style="margin-top:6px;color:#f85149;">Jump target not found: ${key}=${value}</div>`;
                }
            }
        }

        window.addEventListener('load', () => {
            renderConsistencyPanel();
            applyHashJump();
        });
"""
    html = html.replace("</script>", panel_js + "\n    </script>", 1)

    # Apply Template substitution for CSS/JS
    html = Template(html).safe_substitute(
        INLINE_CSS=_inline_css,
        INLINE_JS=_inline_js
    )


    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n[OK] Report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze RDC capture files with Mali Offline Compiler"
    )
    parser.add_argument(
        "rdc_files",
        nargs="+",
        help="RDC file(s) to analyze"
    )
    parser.add_argument(
        "--core",
        default="Mali-G715",
        help="Target GPU core (default: Mali-G715)"
    )
    parser.add_argument(
        "--output", "-o",
        default="mali_analysis_report.html",
        help="Output HTML report path"
    )
    parser.add_argument(
        "--html-mode",
        choices=["lite", "full"],
        default="lite",
        help="HTML output mode: lite (current) or full (generate_real_report)"
    )
    parser.add_argument(
        "--full-json",
        help="Capture JSON path for full HTML report (capture.json / *_data.json)"
    )
    parser.add_argument(
        "--textures",
        help="Textures directory for full HTML report (contains manifest.json)"
    )
    parser.add_argument(
        "--json",
        help="Also save raw results to JSON file"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()

    if args.html_mode == "full":
        if len(args.rdc_files) != 1:
            print("Error: --html-mode full expects a single RDC file.")
            return 1

        json_path = resolve_full_report_json(args.rdc_files[0], args.full_json)
        if not json_path:
            print("[ERROR] Full report requires capture JSON. Provide --full-json or place")
            print("        <rdc>.json / <rdc>_data.json next to the capture.")
            return 1

        textures_dir = resolve_textures_dir(args.rdc_files[0], args.textures)
        if not textures_dir:
            print("[WARN] Texture manifest missing. Run export_textures_rdoc.py first.")

        try:
            json_path = normalize_full_report_json(json_path)
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1

        report_script = Path(__file__).parent / "generate_real_report.py"
        cmd = [sys.executable, str(report_script), json_path, args.output]
        if textures_dir:
            cmd += ["--textures", textures_dir]
        print(f"[INFO] Full report cmd: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode
    
    # 分析所有文件
    all_results = []
    for rdc_path in args.rdc_files:
        if not os.path.exists(rdc_path):
            print(f"Error: File not found: {rdc_path}")
            continue
        
        try:
            result = analyze_rdc_file(
                rdc_path,
                gpu_core=args.core,
                max_workers=args.workers,
                verbose=args.verbose
            )
            all_results.append(result)
        except Exception as e:
            print(f"Error analyzing {rdc_path}: {e}")
            import traceback
            traceback.print_exc()
    
    if not all_results:
        print("No files were successfully analyzed.")
        return 1
    
    # 生成报告
    generate_html_report(all_results, args.output)
    
    # 保存 JSON
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"[OK] JSON results saved to: {args.json}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
