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
from typing import List, Dict, Any

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from rdc_parser import RDCParser, ShaderInfo, extract_shaders, extract_textures, extract_resource_renames, TextureInfo, VK_FORMAT_NAMES, DrawEventContext, PipelineInfo
from mali_analyzer import MaliOfflineCompiler, ShaderAnalysisResult, MaliPerformanceMetrics


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
    textures = extract_textures(rdc_path)
    print(f"  Textures found: {len(textures)}")
    
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
    
    # 加载导出的纹理数据（包含缩略图和完整元数据）
    export_data = load_textures_from_export(rdc_path, as_base64=True)
    thumbnail_map = export_data.get("thumbnails", {})
    exported_texture_list = export_data.get("texture_list", [])
    
    if thumbnail_map:
        print(f"  Thumbnails available: {len(thumbnail_map)}")
    
    if textures:
        # Vulkan / OpenGL：使用 extract_textures 解析的原始数据
        for tex in textures:
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
    elif exported_texture_list:
        # D3D11 / D3D12：使用 renderdoccmd export 导出的 textures.json 数据
        print(f"  [INFO] Using exported texture metadata ({len(exported_texture_list)} textures)")
        texture_details = exported_texture_list
    
    # 更新 summary 包含纹理统计
    summary["total_textures"] = len(texture_details)
    
    return {
        "summary": summary,
        "shaders": shader_details,
        "textures": texture_details
    }


import hashlib


def compute_shader_hash(spirv_data: bytes) -> str:
    """计算 SPIR-V 数据的 SHA256 哈希（用于跨文件匹配）"""
    return hashlib.sha256(spirv_data).hexdigest()[:16]


def generate_html_report(analysis_results: List[Dict], output_path: str):
    """生成 HTML 报告 V3 - 深色主题 + 左侧概览 + 纹理网格视图 + Lightbox"""
    
    # 准备 JavaScript 数据
    all_shaders_json = json.dumps(analysis_results, ensure_ascii=False)
    
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
        /* ========================================
           V3 DESIGN SYSTEM - RenderDoc Theme
           ======================================== */
        :root {
            /* Core palette - RenderDoc inspired */
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #21262d;
            --bg-hover: #30363d;
            --bg-active: #388bfd1a;
            
            /* Text */
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            
            /* Accent - RenderDoc Red */
            --accent: #e94560;
            --accent-light: #ff6b6b;
            --accent-dark: #c73e54;
            
            /* Semantic colors */
            --success: #3fb950;
            --warning: #d29922;
            --danger: #f85149;
            --info: #58a6ff;
            
            /* Layout */
            --sidebar-width: 220px;
            --header-height: 56px;
            --border-color: #30363d;
            --border-radius: 8px;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid rgba(124, 58, 237, 0.3);
        }
        
        .header h1 {
            font-size: 1.75rem;
            font-weight: 600;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .header-meta {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            background: var(--bg-card);
            padding: 4px;
            border-radius: 12px;
            width: fit-content;
        }
        
        .tab {
            padding: 10px 20px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .tab:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }
        
        .tab.active {
            background: var(--accent);
            color: white;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* Cards */
        .card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* Summary Grid */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-hover) 100%);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-light);
            line-height: 1.2;
        }
        
        .stat-value.success { color: var(--success); }
        .stat-value.warning { color: var(--warning); }
        .stat-value.danger { color: var(--danger); }
        .stat-value.info { color: var(--info); }
        
        .stat-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        }
        
        /* DataTables Overrides */
        table.dataTable {
            border-collapse: collapse !important;
        }
        
        .dataTables_wrapper {
            color: var(--text-primary);
        }
        
        .dataTables_wrapper .dataTables_filter input,
        .dataTables_wrapper .dataTables_length select {
            background: var(--bg-secondary);
            border: 1px solid rgba(255,255,255,0.1);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
        }
        
        .dataTables_wrapper .dataTables_paginate .paginate_button {
            color: var(--text-secondary) !important;
            background: var(--bg-secondary) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 4px !important;
            margin: 0 2px;
        }
        
        .dataTables_wrapper .dataTables_paginate .paginate_button.current {
            background: var(--accent) !important;
            color: white !important;
            border-color: var(--accent) !important;
        }
        
        .dataTables_wrapper .dataTables_paginate .paginate_button:hover {
            background: var(--bg-hover) !important;
            color: var(--text-primary) !important;
        }
        
        .dataTables_wrapper .dataTables_info {
            color: var(--text-secondary);
        }
        
        table.dataTable thead th {
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-weight: 600;
            padding: 14px 12px;
            border-bottom: 2px solid var(--accent) !important;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        table.dataTable tbody td {
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            vertical-align: middle;
        }
        
        table.dataTable tbody tr:hover {
            background: var(--bg-hover) !important;
        }
        
        table.dataTable tbody tr.selected {
            background: rgba(124, 58, 237, 0.2) !important;
        }
        
        /* Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        
        .badge-vs { background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; }
        .badge-fs { background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: white; }
        .badge-cs { background: linear-gradient(135deg, #06b6d4, #0891b2); color: white; }
        .badge-error { background: linear-gradient(135deg, #6b7280, #4b5563); color: white; }
        
        /* Cycles Bar */
        .cycles-cell {
            min-width: 120px;
        }
        
        .cycles-value {
            font-weight: 600;
            font-size: 0.95rem;
        }
        
        .cycles-bar {
            height: 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 4px;
        }
        
        .cycles-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }
        
        .cycles-fill.low { background: var(--success); }
        .cycles-fill.medium { background: var(--warning); }
        .cycles-fill.high { background: var(--danger); }
        
        /* Comparison View */
        .comparison-header {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-secondary);
            border-radius: 8px;
            margin-bottom: 12px;
            font-weight: 600;
            font-size: 0.85rem;
        }
        
        .comparison-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-card);
            border-radius: 8px;
            margin-bottom: 8px;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }
        
        .comparison-row:hover {
            background: var(--bg-hover);
            border-color: var(--accent);
        }
        
        .diff-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .diff-same { background: rgba(255,255,255,0.1); color: var(--text-secondary); }
        .diff-better { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .diff-worse { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .diff-new { background: rgba(59, 130, 246, 0.2); color: var(--info); }
        .diff-removed { background: rgba(107, 114, 128, 0.2); color: var(--text-secondary); }
        
        /* Detail Panel */
        .detail-panel {
            display: none;
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            margin-top: 16px;
            border: 1px solid var(--accent);
        }
        
        .detail-panel.show {
            display: block;
            animation: slideDown 0.3s ease;
        }
        
        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .detail-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }
        
        .detail-item {
            background: var(--bg-card);
            padding: 12px;
            border-radius: 8px;
        }
        
        .detail-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        
        .detail-value {
            font-size: 1.1rem;
            font-weight: 600;
        }
        
        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: var(--accent);
            color: white;
        }
        
        .btn-primary:hover {
            background: var(--accent-light);
        }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .btn-secondary:hover {
            background: var(--bg-hover);
        }
        
        /* Footer */
        footer {
            text-align: center;
            padding: 24px;
            color: var(--text-secondary);
            font-size: 0.85rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-top: 40px;
        }
        
        /* DataTables Buttons */
        .dt-buttons {
            margin-bottom: 16px;
        }
        
        .dt-button {
            background: var(--bg-secondary) !important;
            color: var(--text-primary) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 6px !important;
            padding: 8px 16px !important;
            font-size: 0.85rem !important;
        }
        
        .dt-button:hover {
            background: var(--bg-hover) !important;
        }
        
        /* Hash/Name column */
        .shader-name {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
            color: var(--accent-light);
        }
        
        .shader-hash {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        /* Spill indicator */
        .spill-ok { color: var(--success); }
        .spill-warn { color: var(--danger); font-weight: 600; }
        
        /* Expandable Row Styles */
        td.details-control {
            cursor: pointer;
            text-align: center;
            width: 30px;
        }
        
        td.details-control::before {
            content: '+';
            display: inline-block;
            width: 20px;
            height: 20px;
            line-height: 18px;
            text-align: center;
            background: var(--accent);
            color: white;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
        }
        
        tr.shown td.details-control::before {
            content: '−';
            background: var(--danger);
        }
        
        /* Resource Detail Row */
        tr.resource-detail {
            background: var(--bg-secondary) !important;
        }
        
        tr.resource-detail:hover {
            background: var(--bg-secondary) !important;
        }
        
        tr.resource-detail > td {
            padding: 0 !important;
            border-bottom: 2px solid var(--accent) !important;
        }
        
        .resource-detail-inner {
            padding: 16px 24px;
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.05), rgba(59, 130, 246, 0.05));
        }
        
        .resource-detail-header {
            font-weight: 600;
            color: var(--accent-light);
            margin-bottom: 12px;
            font-size: 0.9rem;
        }
        
        .resource-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 8px;
        }
        
        .resource-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--bg-card);
            border-radius: 6px;
            border-left: 3px solid var(--text-secondary);
            font-size: 0.85rem;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        
        .resource-item.texture { border-left-color: #f59e0b; }
        .resource-item.sampler { border-left-color: #8b5cf6; }
        .resource-item.buffer { border-left-color: #10b981; }
        .resource-item.uniform { border-left-color: #3b82f6; }
        
        .resource-type-badge {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .resource-type-badge.texture { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
        .resource-type-badge.sampler { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
        .resource-type-badge.buffer { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        .resource-type-badge.uniform { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .resource-type-badge.other { background: rgba(107, 114, 128, 0.2); color: #6b7280; }
        
        .resource-name {
            color: var(--text-primary);
            word-break: break-all;
        }
        
        .no-resources {
            color: var(--text-secondary);
            font-style: italic;
            padding: 8px 0;
        }
        
        /* Search highlight animation */
        .search-highlight {
            animation: pulse-highlight 0.5s ease-in-out 3;
            box-shadow: 0 0 8px var(--accent) !important;
            border-color: var(--accent) !important;
        }
        
        @keyframes pulse-highlight {
            0%, 100% { box-shadow: 0 0 4px var(--accent); }
            50% { box-shadow: 0 0 12px var(--accent-light); }
        }
        
        /* Clickable texture items */
        .resource-item.texture:hover {
            background: var(--bg-hover);
            transform: translateX(4px);
            transition: all 0.2s;
        }
        
        /* ========================================
           V3 RESOURCE GROUP STYLES (Collapsible)
           ======================================== */
        
        .resource-detail-v3 {
            padding: 16px;
            background: var(--bg-primary);
            border-radius: 8px;
        }
        
        .res-summary-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: var(--bg-secondary);
            border-radius: 8px;
            margin-bottom: 12px;
        }
        
        .res-summary-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .res-summary-title svg {
            color: var(--accent);
        }
        
        .res-summary-stats {
            display: flex;
            gap: 12px;
        }
        
        .res-stat {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--stat-color, var(--text-secondary));
            padding: 4px 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            border-left: 3px solid var(--stat-color);
        }
        
        .res-group {
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .res-group-header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            background: var(--bg-secondary);
            cursor: pointer;
            transition: background 0.2s;
            user-select: none;
        }
        
        .res-group-header:hover {
            background: var(--bg-hover);
        }
        
        .res-group-icon {
            display: flex;
            align-items: center;
        }
        
        .res-group-name {
            font-weight: 600;
            color: var(--text-primary);
            flex: 1;
        }
        
        .res-group-count {
            font-size: 0.8rem;
            padding: 2px 8px;
            background: var(--bg-primary);
            border-radius: 10px;
            color: var(--text-secondary);
        }
        
        .res-group-chevron {
            display: flex;
            align-items: center;
            color: var(--text-secondary);
            transition: transform 0.2s;
        }
        
        .res-group-header.expanded .res-group-chevron {
            transform: rotate(180deg);
        }
        
        .res-group-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            background: var(--bg-card);
        }
        
        .res-group-content.expanded {
            max-height: 500px;
            overflow-y: auto;
        }
        
        .res-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 14px;
            border-bottom: 1px solid var(--border-color);
            transition: background 0.15s;
        }
        
        .res-item:last-child {
            border-bottom: none;
        }
        
        .res-item:hover {
            background: var(--bg-hover);
        }
        
        .res-item.clickable {
            cursor: pointer;
        }
        
        .res-item.clickable:hover {
            background: rgba(245, 158, 11, 0.1);
        }
        
        .res-item-badge {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            min-width: 32px;
            text-align: center;
        }
        
        .res-item-badge.texture { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
        .res-item-badge.sampler { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
        .res-item-badge.buffer { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        .res-item-badge.uniform { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .res-item-badge.other { background: rgba(107, 114, 128, 0.2); color: #6b7280; }
        
        .res-item-name {
            flex: 1;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
            color: var(--text-primary);
            word-break: break-all;
        }
        
        .res-item-binding {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'Consolas', monospace;
            padding: 2px 6px;
            background: var(--bg-primary);
            border-radius: 3px;
        }
        
        /* ========================================
           V3 TEXTURE GRID & LIGHTBOX STYLES
           ======================================== */
        
        /* View Toggle Buttons */
        .view-toggle {
            display: flex;
            gap: 4px;
            background: var(--bg-secondary);
            padding: 4px;
            border-radius: 8px;
        }
        
        .view-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .view-btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }
        
        .view-btn.active {
            background: var(--accent);
            color: white;
        }
        
        /* Texture View Container */
        .texture-view {
            display: none;
        }
        
        .texture-view.active {
            display: block;
        }
        
        /* Grid Controls */
        .texture-grid-controls {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }
        
        .grid-search {
            flex: 1;
            padding: 10px 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 0.9rem;
        }
        
        .grid-search:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(233, 69, 96, 0.2);
        }
        
        .grid-filter {
            padding: 10px 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 0.9rem;
            cursor: pointer;
        }
        
        /* Texture Grid */
        .texture-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 16px;
        }
        
        .texture-card {
            background: var(--bg-secondary);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border-color);
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .texture-card:hover {
            border-color: var(--accent);
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(233, 69, 96, 0.2);
        }
        
        .texture-card-thumb {
            width: 100%;
            height: 120px;
            background: var(--bg-primary);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            position: relative;
            overflow: hidden;
        }
        
        .texture-card-thumb svg {
            opacity: 0.5;
        }
        
        /* 缩略图图片样式 */
        .texture-card-thumb .texture-thumb-img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            background: repeating-conic-gradient(#21262d 0% 25%, #161b22 0% 50%) 50% / 16px 16px;
        }
        
        .texture-card.has-thumb .texture-card-thumb {
            background: repeating-conic-gradient(#21262d 0% 25%, #161b22 0% 50%) 50% / 16px 16px;
        }
        
        .texture-card-thumb .type-badge {
            position: absolute;
            top: 8px;
            right: 8px;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            background: rgba(0, 0, 0, 0.6);
            color: white;
        }
        
        .texture-card-info {
            padding: 12px;
        }
        
        .texture-card-name {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }
        
        .texture-card-dims {
            font-size: 0.75rem;
            color: var(--accent-light);
            font-family: 'Consolas', monospace;
        }
        
        .texture-card-format {
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }
        
        /* Lightbox Modal */
        .lightbox {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 40px;
        }
        
        .lightbox.show {
            display: flex;
            animation: fadeIn 0.2s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .lightbox-content {
            display: flex;
            max-width: 1200px;
            width: 100%;
            max-height: 90vh;
            background: var(--bg-card);
            border-radius: 16px;
            overflow: hidden;
            position: relative;
        }
        
        .lightbox-close {
            position: absolute;
            top: 16px;
            right: 16px;
            width: 40px;
            height: 40px;
            border: none;
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 24px;
            border-radius: 50%;
            cursor: pointer;
            z-index: 10;
            transition: all 0.2s;
        }
        
        .lightbox-close:hover {
            background: var(--danger);
            color: white;
        }
        
        .lightbox-nav {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            width: 48px;
            height: 48px;
            border: none;
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 20px;
            border-radius: 50%;
            cursor: pointer;
            z-index: 10;
            transition: all 0.2s;
        }
        
        .lightbox-nav:hover {
            background: var(--accent);
            color: white;
        }
        
        .lightbox-prev { left: 16px; }
        .lightbox-next { right: 16px; }
        
        .lightbox-image-container {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-primary);
            min-height: 400px;
        }
        
        .lightbox-placeholder {
            text-align: center;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        
        .lightbox-placeholder svg {
            opacity: 0.3;
            margin-bottom: 16px;
        }
        
        /* Lightbox 真实预览图片 */
        .lightbox-preview-img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            background: repeating-conic-gradient(#21262d 0% 25%, #161b22 0% 50%) 50% / 20px 20px;
            border-radius: 4px;
        }
        
        .placeholder-text {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .placeholder-hint {
            font-size: 0.85rem;
            opacity: 0.7;
        }
        
        .lightbox-info {
            width: 320px;
            padding: 24px;
            background: var(--bg-secondary);
            overflow-y: auto;
        }
        
        .lightbox-info h3 {
            font-size: 1.1rem;
            margin-bottom: 20px;
            color: var(--text-primary);
            word-break: break-all;
        }
        
        .lightbox-props {
            display: grid;
            gap: 12px;
        }
        
        .lightbox-prop {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: var(--bg-card);
            border-radius: 6px;
        }
        
        .prop-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .prop-value {
            font-family: 'Consolas', monospace;
            font-size: 0.85rem;
            color: var(--accent-light);
        }
        
        .lightbox-channels {
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .channel-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .channel-btn {
            padding: 6px 12px;
            border: 1px solid var(--border-color);
            background: var(--bg-card);
            color: var(--text-secondary);
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .channel-btn:hover {
            border-color: var(--accent);
            color: var(--accent-light);
        }
        
        .channel-btn.active {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .lightbox-content {
                flex-direction: column;
            }
            
            .lightbox-info {
                width: 100%;
            }
            
            .texture-grid {
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            }
        }
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
        
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            });
        });
        
        // Function to switch to Textures tab
        // Note: SPIR-V variable names (e.g. Material_Texture2D_0) cannot be directly mapped
        // to RenderDoc ResourceIDs, so we just switch tabs without searching.
        function switchToTexturesTab() {
            // Find and click the Textures tab
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => {
                if (tab.dataset.tab === 'textures') {
                    tab.click();
                    // Clear any existing search filter
                    if (window.textureTable) {
                        window.textureTable.search('').draw();
                    }
                    // Scroll to top of textures section
                    document.getElementById('textures').scrollIntoView({ behavior: 'smooth' });
                }
            });
        }
        
        // Function to format resource detail row - V3 Enhanced with collapsible groups
        function formatResourceDetail(shader) {
            const resources = shader.resources || [];
            if (resources.length === 0) {
                return '<div class="resource-detail-inner"><div class="no-resources">No resources found in SPIR-V metadata</div></div>';
            }
            
            // Group resources by category
            const grouped = {
                'Texture': [],
                'Sampler': [],
                'Buffer': [],
                'Uniform': [],
                'Other': []
            };
            
            resources.forEach(r => {
                const cat = grouped[r.category] ? r.category : 'Other';
                grouped[cat].push(r);
            });
            
            // Category icons (SVG)
            const categoryIcons = {
                'Texture': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>',
                'Sampler': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
                'Buffer': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="5" rx="1"/><rect x="2" y="10" width="20" height="5" rx="1"/><rect x="2" y="17" width="20" height="5" rx="1"/></svg>',
                'Uniform': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
                'Other': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><circle cx="12" cy="17" r="0.5"/></svg>'
            };
            
            // Category colors
            const categoryColors = {
                'Texture': '#f59e0b',
                'Sampler': '#8b5cf6',
                'Buffer': '#10b981',
                'Uniform': '#3b82f6',
                'Other': '#6b7280'
            };
            
            let html = '<div class="resource-detail-v3">';
            
            // Summary header
            html += `<div class="res-summary-bar">
                <div class="res-summary-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                        <line x1="12" y1="22.08" x2="12" y2="12"/>
                    </svg>
                    Shader Resources
                </div>
                <div class="res-summary-stats">
                    <span class="res-stat" style="--stat-color: #f59e0b;" title="Textures">T:${shader.texture_count || 0}</span>
                    <span class="res-stat" style="--stat-color: #8b5cf6;" title="Samplers">S:${shader.sampler_count || 0}</span>
                    <span class="res-stat" style="--stat-color: #10b981;" title="Buffers">B:${shader.buffer_count || 0}</span>
                    <span class="res-stat" style="--stat-color: #3b82f6;" title="Uniforms">U:${shader.uniform_count || 0}</span>
                </div>
            </div>`;
            
            // Render each category as collapsible group
            const uniqueId = 'res-' + Math.random().toString(36).substr(2, 9);
            
            ['Texture', 'Sampler', 'Buffer', 'Uniform', 'Other'].forEach((category, catIdx) => {
                const items = grouped[category];
                if (items.length === 0) return;
                
                const catLower = category.toLowerCase();
                const groupId = `${uniqueId}-${catLower}`;
                const isExpanded = (category === 'Texture' || category === 'Buffer'); // Default expand Texture and Buffer
                
                html += `<div class="res-group" data-category="${catLower}">
                    <div class="res-group-header ${isExpanded ? 'expanded' : ''}" onclick="toggleResGroup('${groupId}')">
                        <span class="res-group-icon" style="color: ${categoryColors[category]}">
                            ${categoryIcons[category]}
                        </span>
                        <span class="res-group-name">${category}s</span>
                        <span class="res-group-count">${items.length}</span>
                        <span class="res-group-chevron">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </span>
                    </div>
                    <div class="res-group-content ${isExpanded ? 'expanded' : ''}" id="${groupId}">`;
                
                items.forEach(r => {
                    // Make Texture items clickable
                    const clickable = (category === 'Texture') 
                        ? `onclick="event.stopPropagation(); switchToTexturesTab();" class="res-item clickable" title="View all textures (SPIR-V names may differ from ResourceIDs)"`
                        : `class="res-item"`;
                    
                    html += `<div ${clickable}>
                        <span class="res-item-badge ${catLower}">${category.substring(0, 3)}</span>
                        <span class="res-item-name">${r.name}</span>
                        ${r.set !== undefined ? `<span class="res-item-binding">set=${r.set}, binding=${r.binding}</span>` : ''}
                    </div>`;
                });
                
                html += `</div></div>`;
            });
            
            html += '</div>';
            return html;
        }
        
        // Toggle resource group collapse/expand
        function toggleResGroup(groupId) {
            const content = document.getElementById(groupId);
            const header = content?.previousElementSibling;
            if (content && header) {
                content.classList.toggle('expanded');
                header.classList.toggle('expanded');
            }
        }
        
        // Initialize DataTables
        $(document).ready(function() {
            // Per-file tables with expandable rows
            analysisData.forEach((fileData, fileIdx) => {
                const tableId = `#shader-table-${fileIdx}`;
                const maxCycles = fileData.summary.cycles.max || 1;
                
                const tableData = fileData.shaders.map(shader => {
                    // Stage badge
                    const stage = shader.stage || '??';
                    const stageClass = stage === 'VS' ? 'vs' : 
                                       stage === 'PS' ? 'fs' : 
                                       stage === 'CS' ? 'cs' : 'error';
                    const stageHtml = `<span class="badge badge-${stageClass}">${stage}</span>`;
                    
                    // Hash
                    const hashHtml = `<span class="shader-hash">${shader.hash || '-'}</span>`;
                    
                    // Resource Hint (friendly_label from OpName)
                    const hint = shader.friendly_label || '';
                    const hintHtml = hint 
                        ? `<span class="shader-name" title="${hint}">${hint.substring(0, 25)}${hint.length > 25 ? '...' : ''}</span>`
                        : '<span style="color: var(--text-secondary);">-</span>';
                    
                    // Resource count with breakdown
                    const resCount = shader.resource_count || 0;
                    const resHtml = resCount > 0 
                        ? `<span title="T:${shader.texture_count || 0} S:${shader.sampler_count || 0} B:${shader.buffer_count || 0} U:${shader.uniform_count || 0}">${resCount}</span>`
                        : '<span style="color: var(--text-secondary);">0</span>';
                    
                    if (!shader.valid) {
                        return [
                            '',  // Details control column
                            shader.index,
                            stageHtml,
                            hashHtml,
                            hintHtml,
                            resHtml,
                            shader.size,
                            '-', '-', '-', '-', '-', '-', '-', '-',
                            '<span class="spill-ok">-</span>'
                        ];
                    }
                    
                    const cyclesPct = Math.min(100, (shader.longest_path / maxCycles) * 100);
                    const cycleClass = cyclesPct < 33 ? 'low' : cyclesPct < 66 ? 'medium' : 'high';
                    
                    const cyclesHtml = `<div class="cycles-cell">
                        <span class="cycles-value">${shader.longest_path.toFixed(1)}</span>
                        <div class="cycles-bar"><div class="cycles-fill ${cycleClass}" style="width:${cyclesPct}%"></div></div>
                    </div>`;
                    
                    const spillHtml = shader.has_spilling 
                        ? `<span class="spill-warn">! ${shader.spill_count}</span>`
                        : '<span class="spill-ok">OK</span>';
                    
                    return [
                        '',  // Details control column
                        shader.index,
                        stageHtml,
                        hashHtml,
                        hintHtml,
                        resHtml,
                        shader.size,
                        shader.work_registers,
                        shader.uniform_registers,
                        cyclesHtml,
                        shader.fma_cycles?.toFixed(2) || '-',
                        shader.cvt_cycles?.toFixed(2) || '-',
                        shader.sfu_cycles?.toFixed(2) || '-',
                        shader.load_store_cycles?.toFixed(2) || '-',
                        shader.texture_cycles?.toFixed(2) || '-',
                        spillHtml
                    ];
                });
                
                const table = $(tableId).DataTable({
                    data: tableData,
                    pageLength: 25,
                    order: [[9, 'desc']], // Sort by cycles descending (column index shifted by 2)
                    dom: 'Bfrtip',
                    buttons: ['copy', 'csv', 'excel'],
                    columnDefs: [
                        {
                            className: 'details-control',
                            orderable: false,
                            data: null,
                            defaultContent: '',
                            targets: 0
                        }
                    ],
                    language: {
                        search: "Search:",
                        lengthMenu: "Show _MENU_ shaders",
                        info: "Showing _START_ to _END_ of _TOTAL_ shaders"
                    }
                });
                
                // Add click handler for expandable rows
                $(tableId + ' tbody').on('click', 'td.details-control', function() {
                    const tr = $(this).closest('tr');
                    const row = table.row(tr);
                    const rowIndex = row.data()[1]; // Index is in column 1 now
                    const shader = fileData.shaders[rowIndex];
                    
                    if (row.child.isShown()) {
                        row.child.hide();
                        tr.removeClass('shown');
                    } else {
                        row.child(formatResourceDetail(shader), 'resource-detail').show();
                        tr.addClass('shown');
                    }
                });
            });
            
            // Comparison table (if multiple files)
            if (analysisData.length > 1) {
                // Build hash map with shader info (改进版：分离各字段)
                const hashMap = new Map();
                
                analysisData.forEach((fileData, fileIdx) => {
                    fileData.shaders.forEach(shader => {
                        if (shader.valid && shader.hash) {
                            if (!hashMap.has(shader.hash)) {
                                hashMap.set(shader.hash, {
                                    hash: shader.hash,
                                    index: shader.index,
                                    stage: shader.stage || '??',
                                    entry_name: shader.entry_name || 'main',
                                    friendly_label: shader.friendly_label || '',
                                    size: shader.size,
                                    cycles: new Array(analysisData.length).fill(null)
                                });
                            }
                            hashMap.get(shader.hash).cycles[fileIdx] = shader.longest_path;
                        }
                    });
                });
                
                const comparisonData = [];
                hashMap.forEach(item => {
                    // 新的列结构: Index, Stage, Hash, Resource Hint, Size, [Cycles...], Diff
                    const stageClass = item.stage === 'VS' ? 'vs' : 
                                       item.stage === 'PS' ? 'fs' : 
                                       item.stage === 'CS' ? 'cs' : 'error';
                    const stageHtml = `<span class="badge badge-${stageClass}">${item.stage}</span>`;
                    const hashHtml = `<span class="shader-hash">${item.hash}</span>`;
                    const hintHtml = item.friendly_label 
                        ? `<span class="shader-name" title="${item.friendly_label}">${item.friendly_label.substring(0, 25)}${item.friendly_label.length > 25 ? '...' : ''}</span>`
                        : '<span class="text-muted">-</span>';
                    
                    const row = [
                        item.index,
                        stageHtml,
                        hashHtml,
                        hintHtml,
                        item.size
                    ];
                    
                    item.cycles.forEach(c => {
                        row.push(c !== null ? c.toFixed(1) : '-');
                    });
                    
                    // Calculate diff
                    const validCycles = item.cycles.filter(c => c !== null);
                    let diffHtml = '-';
                    if (validCycles.length === analysisData.length) {
                        const diff = item.cycles[1] - item.cycles[0];
                        if (Math.abs(diff) < 0.1) {
                            diffHtml = '<span class="diff-badge diff-same">=</span>';
                        } else if (diff > 0) {
                            diffHtml = `<span class="diff-badge diff-worse">+${diff.toFixed(1)}</span>`;
                        } else {
                            diffHtml = `<span class="diff-badge diff-better">${diff.toFixed(1)}</span>`;
                        }
                    } else if (item.cycles[0] === null) {
                        diffHtml = '<span class="diff-badge diff-new">NEW</span>';
                    } else if (item.cycles[1] === null) {
                        diffHtml = '<span class="diff-badge diff-removed">GONE</span>';
                    }
                    row.push(diffHtml);
                    
                    comparisonData.push(row);
                });
                
                $('#comparison-table').DataTable({
                    data: comparisonData,
                    pageLength: 50,
                    order: [[0, 'asc']], // Sort by index ascending
                    dom: 'Bfrtip',
                    buttons: ['copy', 'csv', 'excel']
                });
            }
            
            // Texture table
            const textureData = [];
            analysisData.forEach((fileData, fileIdx) => {
                const fileName = fileData.summary.file_name.substring(0, 15) + '...';
                const textures = fileData.textures || [];
                
                textures.forEach(tex => {
                    // Image type badge
                    const typeNames = ['1D', '2D', '3D'];
                    const typeName = typeNames[tex.image_type] || '2D';
                    const typeClass = typeName === '2D' ? 'fs' : typeName === '3D' ? 'cs' : 'vs';
                    const typeHtml = `<span class="badge badge-${typeClass}">${typeName}</span>`;
                    
                    // Dimensions
                    let dimStr = `${tex.width}×${tex.height}`;
                    if (tex.depth > 1) {
                        dimStr += `×${tex.depth}`;
                    }
                    
                    // Format - show short name
                    const formatName = tex.format_name.replace('VK_FORMAT_', '');
                    const formatHtml = `<span class="shader-hash" title="${tex.format_name}">${formatName}</span>`;
                    
                    // Usage flags as hex
                    const usageHex = '0x' + tex.usage.toString(16).toUpperCase();
                    
                    // Custom name display
                    const customName = tex.custom_name || '';
                    const customNameHtml = customName 
                        ? `<span class="shader-name" style="color: var(--success);">${customName}</span>`
                        : '<span style="color: var(--text-secondary);">-</span>';
                    
                    textureData.push([
                        fileName,
                        tex.resource_id,
                        customNameHtml,
                        typeHtml,
                        dimStr,
                        formatHtml,
                        tex.mip_levels,
                        tex.array_layers,
                        tex.samples,
                        usageHex
                    ]);
                });
            });
            
            // Store texture table globally for cross-reference function
            window.textureTable = $('#texture-table').DataTable({
                data: textureData,
                pageLength: 50,
                order: [[3, 'desc']], // Sort by dimensions descending
                dom: 'Bfrtip',
                buttons: ['copy', 'csv', 'excel'],
                language: {
                    search: "Search:",
                    info: "Showing _START_ to _END_ of _TOTAL_ textures"
                }
            });
            
            // ========================================
            // V3 TEXTURE GRID & LIGHTBOX SYSTEM
            // ========================================
            
            // Build texture list for grid view
            const allTextures = [];
            analysisData.forEach((fileData, fileIdx) => {
                const textures = fileData.textures || [];
                textures.forEach((tex, texIdx) => {
                    const typeNames = ['1D', '2D', '3D'];
                    const typeName = typeNames[tex.image_type] || '2D';
                    let dimStr = `${tex.width}×${tex.height}`;
                    if (tex.depth > 1) dimStr += `×${tex.depth}`;
                    
                    allTextures.push({
                        id: `tex-${fileIdx}-${texIdx}`,
                        fileIdx: fileIdx,
                        fileName: fileData.summary.file_name,
                        resourceId: tex.resource_id,
                        customName: tex.custom_name || '',
                        type: typeName,
                        dims: dimStr,
                        width: tex.width,
                        height: tex.height,
                        depth: tex.depth,
                        format: tex.format_name.replace('VK_FORMAT_', ''),
                        formatFull: tex.format_name,
                        mipLevels: tex.mip_levels,
                        arrayLayers: tex.array_layers,
                        samples: tex.samples,
                        usage: tex.usage,
                        thumbnail: tex.thumbnail || ''  // Base64 Data URI
                    });
                });
            });
            
            // Store globally for lightbox navigation
            window.allTextures = allTextures;
            window.currentLightboxIndex = 0;
            
            // Render texture grid cards
            function renderTextureGrid(textures) {
                const grid = document.getElementById('texture-grid');
                if (!grid) return;
                
                if (textures.length === 0) {
                    grid.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">No textures found</div>';
                    return;
                }
                
                grid.innerHTML = textures.map((tex, idx) => {
                    // 如果有缩略图则显示图片，否则显示占位符
                    const thumbContent = tex.thumbnail 
                        ? `<img src="${tex.thumbnail}" alt="${tex.customName || 'Texture'}" class="texture-thumb-img" loading="lazy">`
                        : `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                                <circle cx="8.5" cy="8.5" r="1.5"/>
                                <polyline points="21 15 16 10 5 21"/>
                           </svg>`;
                    
                    return `
                    <div class="texture-card ${tex.thumbnail ? 'has-thumb' : ''}" data-index="${allTextures.indexOf(tex)}" onclick="openLightbox(${allTextures.indexOf(tex)})">
                        <div class="texture-card-thumb">
                            ${thumbContent}
                            <span class="type-badge">${tex.type}</span>
                        </div>
                        <div class="texture-card-info">
                            <div class="texture-card-name" title="${tex.customName || 'ResourceID: ' + tex.resourceId}">
                                ${tex.customName || 'Texture #' + tex.resourceId}
                            </div>
                            <div class="texture-card-dims">${tex.dims}</div>
                            <div class="texture-card-format">${tex.format}</div>
                        </div>
                    </div>
                `}).join('');
            }
            
            // Initial render
            renderTextureGrid(allTextures);
            
            // Grid search and filter
            const gridSearch = document.getElementById('texture-grid-search');
            const gridFilter = document.getElementById('texture-grid-filter');
            
            function filterTextures() {
                const searchTerm = (gridSearch?.value || '').toLowerCase();
                const typeFilter = gridFilter?.value || '';
                
                const filtered = allTextures.filter(tex => {
                    const matchSearch = !searchTerm || 
                        tex.customName.toLowerCase().includes(searchTerm) ||
                        tex.resourceId.toString().includes(searchTerm) ||
                        tex.format.toLowerCase().includes(searchTerm);
                    const matchType = !typeFilter || tex.type.includes(typeFilter);
                    return matchSearch && matchType;
                });
                
                renderTextureGrid(filtered);
            }
            
            if (gridSearch) gridSearch.addEventListener('input', filterTextures);
            if (gridFilter) gridFilter.addEventListener('change', filterTextures);
            
            // View toggle (Grid/Table)
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const view = btn.dataset.view;
                    
                    // Update button states
                    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    
                    // Toggle views
                    document.querySelectorAll('.texture-view').forEach(v => v.classList.remove('active'));
                    const targetView = document.getElementById(`texture-${view}-view`);
                    if (targetView) targetView.classList.add('active');
                });
            });
        });
        
        // ========================================
        // LIGHTBOX FUNCTIONS (Global scope)
        // ========================================
        
        function openLightbox(index) {
            if (!window.allTextures || index < 0 || index >= window.allTextures.length) return;
            
            window.currentLightboxIndex = index;
            const tex = window.allTextures[index];
            
            // Update lightbox info
            document.getElementById('lightbox-title').textContent = tex.customName || 'Texture #' + tex.resourceId;
            document.getElementById('lightbox-resid').textContent = tex.resourceId;
            document.getElementById('lightbox-dims').textContent = tex.dims;
            document.getElementById('lightbox-format').textContent = tex.format;
            document.getElementById('lightbox-mips').textContent = tex.mipLevels;
            document.getElementById('lightbox-layers').textContent = tex.arrayLayers;
            document.getElementById('lightbox-samples').textContent = tex.samples;
            
            // Update preview image or show placeholder
            const previewImg = document.getElementById('lightbox-preview-img');
            const placeholder = document.getElementById('lightbox-placeholder');
            
            if (tex.thumbnail) {
                // 有缩略图：显示真实图片
                previewImg.src = tex.thumbnail;
                previewImg.style.display = 'block';
                placeholder.style.display = 'none';
            } else {
                // 无缩略图：显示占位符
                previewImg.style.display = 'none';
                placeholder.style.display = 'flex';
            }
            
            // Show lightbox
            document.getElementById('texture-lightbox').classList.add('show');
            document.body.style.overflow = 'hidden';
        }
        
        function closeLightbox() {
            document.getElementById('texture-lightbox').classList.remove('show');
            document.body.style.overflow = '';
        }
        
        function navigateLightbox(direction) {
            if (!window.allTextures) return;
            
            let newIndex = window.currentLightboxIndex + direction;
            if (newIndex < 0) newIndex = window.allTextures.length - 1;
            if (newIndex >= window.allTextures.length) newIndex = 0;
            
            openLightbox(newIndex);
        }
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            const lightbox = document.getElementById('texture-lightbox');
            if (!lightbox || !lightbox.classList.contains('show')) return;
            
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') navigateLightbox(-1);
            if (e.key === 'ArrowRight') navigateLightbox(1);
        });
        
        // Close on backdrop click
        document.addEventListener('click', (e) => {
            if (e.target.id === 'texture-lightbox') closeLightbox();
        });
        
        // Channel button toggle (visual only - actual channel filtering requires image data)
        document.querySelectorAll('.channel-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.channel-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    </script>
</body>
</html>
"""
    
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
