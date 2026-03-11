#!/usr/bin/env python3
"""RDC File Loader - Convert RDC files to CaptureData format.

This module provides utilities to convert RDC files to the unified
CaptureData format used by the comparison pipeline.

Architecture:
    RDC File -> renderdoccmd.exe -> XML -> RdcXmlParser -> CaptureData

Usage:
    from rdc_analyzer.parsers.rdc_loader import load_rdc_file
    
    capture_data = load_rdc_file("capture.rdc")
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from .rdc_xml_parser import parse_rdc_xml
from .rdc_xml_converter import xml_to_capture_data


# Common paths for renderdoccmd.exe
RENDERDOCCMD_SEARCH_PATHS = [
    # Environment variable
    os.environ.get("RENDERDOC_CMD", ""),
    # Common installation paths
    r"C:\Program Files\RenderDoc\renderdoccmd.exe",
    r"C:\Program Files (x86)\RenderDoc\renderdoccmd.exe",
    # Development build paths (relative to project root)
    r"build\bin\Release\renderdoccmd.exe",
    r"build\bin\Debug\renderdoccmd.exe",
    r"x64\Release\renderdoccmd.exe",
    r"x64\Development\renderdoccmd.exe",
    # Linux paths
    "/usr/bin/renderdoccmd",
    "/usr/local/bin/renderdoccmd",
]


def find_renderdoccmd() -> Optional[str]:
    """Find the renderdoccmd executable.
    
    Searches common installation paths and environment variables.
    
    Returns:
        Path to renderdoccmd if found, None otherwise.
    """
    # First check PATH
    import shutil
    cmd_in_path = shutil.which("renderdoccmd")
    if cmd_in_path:
        return cmd_in_path
    
    # Search common paths
    for path in RENDERDOCCMD_SEARCH_PATHS:
        if path and os.path.isfile(path):
            return path
    
    return None


def convert_rdc_to_xml(
    rdc_path: str,
    output_path: Optional[str] = None,
    renderdoccmd: Optional[str] = None,
    timeout: int = 300
) -> str:
    """Convert an RDC file to XML using renderdoccmd.
    
    Args:
        rdc_path: Path to the RDC file.
        output_path: Optional output XML path. If None, creates a temp file.
        renderdoccmd: Optional path to renderdoccmd executable.
        timeout: Timeout in seconds for the conversion.
        
    Returns:
        Path to the generated XML file.
        
    Raises:
        FileNotFoundError: If RDC file or renderdoccmd not found.
        subprocess.CalledProcessError: If conversion fails.
        subprocess.TimeoutExpired: If conversion times out.
    """
    # Validate input
    rdc_file = Path(rdc_path)
    if not rdc_file.exists():
        raise FileNotFoundError(f"RDC file not found: {rdc_path}")
    
    # Find renderdoccmd
    cmd_path = renderdoccmd or find_renderdoccmd()
    if not cmd_path:
        raise FileNotFoundError(
            "renderdoccmd not found. Please install RenderDoc or set RENDERDOC_CMD environment variable."
        )
    
    # Determine output path
    if output_path:
        xml_path = Path(output_path)
    else:
        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=".xml", prefix=f"rdc_{rdc_file.stem}_")
        os.close(fd)
        xml_path = Path(temp_path)
    
    # Run conversion
    # renderdoccmd convert -c xml -o output.xml input.rdc
    cmd = [
        cmd_path,
        "convert",
        "-c", "xml",
        "-o", str(xml_path),
        "-f", str(rdc_file),
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    if result.returncode != 0:
        error_msg = result.stderr or result.stdout or "Unknown error"
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )
    
    return str(xml_path)


def load_rdc_file(
    rdc_path: str,
    keep_xml: bool = False,
    xml_output_dir: Optional[str] = None,
    renderdoccmd: Optional[str] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """Load an RDC file and convert to CaptureData format.
    
    This is the main entry point for loading RDC files.
    
    Args:
        rdc_path: Path to the RDC file.
        keep_xml: Whether to keep the intermediate XML file.
        xml_output_dir: Directory to save XML file (if keep_xml is True).
        renderdoccmd: Optional path to renderdoccmd executable.
        verbose: Enable verbose output.
        
    Returns:
        Dictionary in CaptureData format, compatible with DiffEngine.
        
    Raises:
        FileNotFoundError: If RDC file or renderdoccmd not found.
        Exception: If conversion or parsing fails.
    """
    rdc_file = Path(rdc_path)
    
    if verbose:
        print(f"[*] Loading RDC: {rdc_path}")
    
    # Determine XML output path
    if keep_xml:
        if xml_output_dir:
            xml_dir = Path(xml_output_dir)
            xml_dir.mkdir(parents=True, exist_ok=True)
            xml_path = str(xml_dir / f"{rdc_file.stem}.xml")
        else:
            xml_path = str(rdc_file.with_suffix('.xml'))
    else:
        xml_path = None
    
    # Convert RDC to XML
    if verbose:
        print(f"[*] Converting to XML...")
    
    xml_file = convert_rdc_to_xml(
        rdc_path,
        output_path=xml_path,
        renderdoccmd=renderdoccmd
    )
    
    try:
        if verbose:
            print(f"[*] Parsing XML: {xml_file}")
        
        # Parse XML
        xml_data = parse_rdc_xml(xml_file)
        
        if verbose:
            print(f"    Driver: {xml_data.driver}")
            print(f"    Draw Calls: {len(xml_data.draw_calls)}")
            print(f"    Resources: {len(xml_data.resources)}")
        
        # Convert to CaptureData format
        capture_data = xml_to_capture_data(xml_data, str(rdc_path))
        
        if verbose:
            print(f"[+] Loaded successfully")
        
        return capture_data
        
    finally:
        # Clean up temp XML file
        if not keep_xml and xml_file and os.path.exists(xml_file):
            try:
                os.remove(xml_file)
            except Exception:
                pass  # Ignore cleanup errors


def is_rdc_file(path: str) -> bool:
    """Check if a file is an RDC file.
    
    Args:
        path: File path to check.
        
    Returns:
        True if the file has .rdc extension.
    """
    return Path(path).suffix.lower() == '.rdc'


def _convert_schema_v1_to_capture_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """将 Canonical Schema v1.0 格式转换为 CaptureData 格式。
    
    analyze 命令输出的 JSON 使用 schema_version=1.0 格式，
    但 compare/DiffEngine 期望的是 CaptureData 格式（列表格式）。
    
    Schema v1.0 格式:
        {
            "schema_version": "1.0",
            "resources": {
                "textures": { "id": {...}, ... },  # dict
                "buffers": { "id": {...}, ... },   # dict
            },
            "summary": {...}
        }
    
    CaptureData 格式:
        {
            "textures": [...],    # list
            "buffers": [...],     # list
            "statistics": {...}
        }
    
    Args:
        data: 输入的 JSON 数据
        
    Returns:
        转换后的 CaptureData 格式数据。如果不是 v1.0 格式，原样返回。
    """
    # 检测是否为 schema v1.0
    if data.get('schema_version') != '1.0':
        return data  # 不是 v1.0，原样返回
    
    # 获取资源
    resources = data.get('resources', {})
    
    # textures: dict → list
    # 注意：DiffEngine 使用 'resourceId' 作为索引键 (diff_engine.py:207-208)
    textures_dict = resources.get('textures', {})
    textures_list = []
    for tex_id, tex_info in textures_dict.items():
        tex_entry = {
            'resourceId': tex_id,  # DiffEngine 期望 resourceId
            'id': tex_id,          # 保留 id 以兼容其他消费者
            'name': tex_info.get('name', ''),
            'width': tex_info.get('width', 0),
            'height': tex_info.get('height', 0),
            'format': tex_info.get('format', ''),
            'memorySize': tex_info.get('size_bytes', 0),  # DiffEngine 使用 memorySize
            'size_bytes': tex_info.get('size_bytes', 0),  # 保留原字段
            'mipLevels': tex_info.get('mips', 1),  # DiffEngine 使用 mipLevels
            'mips': tex_info.get('mips', 1),       # 保留原字段
            'type': tex_info.get('type', 'Texture2D'),
            # 保留原始数据中的其他字段
            **{k: v for k, v in tex_info.items() if k not in ['name', 'width', 'height', 'format', 'size_bytes', 'mips', 'type']}
        }
        textures_list.append(tex_entry)
    
    # buffers: dict → list
    # 注意：DiffEngine 使用 'resourceId' 和 'size' (diff_engine.py:336-337, 349)
    buffers_dict = resources.get('buffers', {})
    buffers_list = []
    for buf_id, buf_info in buffers_dict.items():
        size_value = buf_info.get('size_bytes', buf_info.get('length', 0))
        buf_entry = {
            'resourceId': buf_id,  # DiffEngine 期望 resourceId
            'id': buf_id,          # 保留 id 以兼容其他消费者
            'name': buf_info.get('name', ''),
            'size': size_value,    # DiffEngine 使用 size
            'size_bytes': size_value,  # 保留原字段
            'usage': buf_info.get('usage', ''),
            **{k: v for k, v in buf_info.items() if k not in ['name', 'size_bytes', 'length', 'usage']}
        }
        buffers_list.append(buf_entry)
    
    # shaders: dict → list (如果存在)
    # 注意：DiffEngine 使用 'resourceId' (diff_engine.py:277-278)
    shaders_dict = resources.get('shaders', {})
    if isinstance(shaders_dict, dict):
        shaders_list = []
        for shader_id, shader_info in shaders_dict.items():
            shader_entry = {
                'resourceId': shader_id,  # DiffEngine 期望 resourceId
                'id': shader_id,          # 保留 id 以兼容其他消费者
                **shader_info
            }
            shaders_list.append(shader_entry)
    else:
        shaders_list = shaders_dict if isinstance(shaders_dict, list) else []
    
    # 构建 CaptureData 格式
    capture_data = {
        'textures': textures_list,
        'buffers': buffers_list,
        'shaders': shaders_list,
        'events': data.get('events', []),
        'statistics': data.get('summary', data.get('statistics', {})),
        # 保留元数据以便追踪来源
        '_source_schema': '1.0',
        '_meta': data.get('meta', {}),
    }
    
    # 复制其他顶级字段（保持向后兼容）
    for key in ['passes', 'pipelines', 'render_targets']:
        if key in data:
            capture_data[key] = data[key]
    
    return capture_data


def _load_rdc_via_analyze(
    path: str,
    verbose: bool = False
) -> Optional[Dict[str, Any]]:
    """优先使用 analyze 产出的 Canonical Schema 解析 RDC（可用时）。

    Returns:
        CaptureData dict if analyze pipeline is available, otherwise None.
    """
    try:
        from ..main import AnalysisPipeline, AnalysisOptions
    except Exception:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            options = AnalysisOptions(
                output_formats=['json'],
                output_dir=tmpdir,
                sample_textures=False,
                sample_buffers=False,
                enable_mali_analysis=False,
            )
            pipeline = AnalysisPipeline(path, options)
            summary = pipeline.run()

            json_outputs = [p for p in summary.output_files if str(p).endswith('.json')]
            if not json_outputs:
                return None

            import json
            with open(json_outputs[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('schema_version') == '1.0':
                return _convert_schema_v1_to_capture_data(data)
            return data
    except Exception as e:
        if verbose:
            print(f"[!] analyze pipeline unavailable, fallback to renderdoccmd: {e}")
        return None


def load_capture_file(
    path: str,
    verbose: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Load a capture file (RDC or JSON) into CaptureData format.
    
    Automatically detects file type and uses appropriate loader.
    
    Args:
        path: Path to the capture file (.rdc or .json).
        verbose: Enable verbose output.
        **kwargs: Additional arguments passed to the loader.
        
    Returns:
        Dictionary in CaptureData format.
        
    Raises:
        ValueError: If file type is not supported.
        FileNotFoundError: If file not found.
    """
    import json
    
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    ext = file_path.suffix.lower()
    
    if ext == '.rdc':
        analyze_data = _load_rdc_via_analyze(path, verbose=verbose)
        if analyze_data is not None:
            return analyze_data
        return load_rdc_file(path, verbose=verbose, **kwargs)
    elif ext == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            raise ValueError("Phase1 列表格式已弃用，请使用 Canonical Schema (dict) 输入")
        if not isinstance(data, dict):
            raise ValueError("JSON 顶层必须是 dict (Canonical Schema)")
        if data.get('schema_version') == '1.0':
            return _convert_schema_v1_to_capture_data(data)
        return data
    elif ext == '.xml':
        # Direct XML loading
        xml_data = parse_rdc_xml(path)
        return xml_to_capture_data(xml_data, path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .rdc, .json, .xml")


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python rdc_loader.py <rdc_file> [output.json]")
        print()
        print("Environment variables:")
        print("  RENDERDOC_CMD - Path to renderdoccmd executable")
        sys.exit(1)
    
    rdc_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        data = load_rdc_file(rdc_file, verbose=True)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[+] Saved to: {output_file}")
        else:
            print(f"\n=== Summary ===")
            print(f"Draw Calls: {data['summary']['draw_call_count']}")
            print(f"Triangles: {data['summary']['total_triangles']}")
            print(f"Textures: {data['summary']['texture_count']}")
            print(f"Buffers: {data['summary']['buffer_count']}")
    except FileNotFoundError as e:
        print(f"[!] Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Failed: {e}")
        sys.exit(1)
