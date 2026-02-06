#!/usr/bin/env python3
"""RDC XML to CaptureData Converter.

Converts RdcXmlData from the XML parser to the dictionary format
expected by the compare/diff pipeline.

Usage:
    from rdc_analyzer.parsers.rdc_xml_converter import xml_to_capture_data
    
    xml_data = parse_rdc_xml("capture.xml")
    capture_data = xml_to_capture_data(xml_data, "capture.rdc")
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from .rdc_xml_parser import RdcXmlData, D3D11DrawCall, D3D11Resource


def _estimate_texture_memory(resource: D3D11Resource) -> int:
    """Estimate texture memory size in bytes.
    
    Args:
        resource: D3D11Resource with texture information.
        
    Returns:
        Estimated memory size in bytes.
    """
    if resource.resource_type != "Texture2D":
        return 0
    
    # Estimate bytes per pixel from format string
    # Order matters: check more specific patterns first
    bpp = 4  # Default RGBA8
    fmt = resource.format.upper()
    
    if "R32G32B32A32" in fmt:
        bpp = 16
    elif "R16G16B16A16" in fmt:
        bpp = 8
    elif "R8G8B8A8" in fmt or "B8G8R8A8" in fmt:
        bpp = 4  # Common RGBA8 formats
    elif "R32G32" in fmt:
        bpp = 8
    elif "R16G16" in fmt or "R32" in fmt:
        bpp = 4
    elif "R8G8" in fmt or "R16" in fmt:
        bpp = 2
    elif "R8" in fmt or "A8" in fmt:
        bpp = 1
    elif "BC1" in fmt or "BC4" in fmt:
        bpp = 0.5  # Compressed
    elif "BC2" in fmt or "BC3" in fmt or "BC5" in fmt or "BC6" in fmt or "BC7" in fmt:
        bpp = 1  # Compressed
    elif "D32" in fmt:
        bpp = 4
    elif "D24" in fmt or "D16" in fmt:
        bpp = 4  # Usually padded
    
    base_size = int(resource.width * resource.height * resource.array_size * bpp)
    
    # Account for mipmaps (adds ~33%)
    if resource.mip_levels > 1:
        base_size = int(base_size * 1.33)
    
    return base_size


def xml_to_capture_data(
    xml_data: RdcXmlData,
    source_file: str = "",
    include_events: bool = True
) -> Dict[str, Any]:
    """Convert RdcXmlData to the capture data dictionary format.
    
    This format is compatible with:
    - compare_rdc.py pipeline
    - DiffEngine.compare()
    - RegressionDetector.detect()
    
    Args:
        xml_data: Parsed RDC XML data.
        source_file: Original source file path (for metadata).
        include_events: Whether to include detailed event list.
        
    Returns:
        Dictionary in the expected capture data format.
    """
    # Calculate totals from draw calls
    total_triangles = sum(dc.triangle_count for dc in xml_data.draw_calls)
    total_vertices = sum(dc.total_vertices for dc in xml_data.draw_calls)
    
    # Count resources by type
    texture_count = sum(1 for r in xml_data.resources.values() if r.resource_type == "Texture2D")
    buffer_count = sum(1 for r in xml_data.resources.values() if r.resource_type == "Buffer")
    
    # Calculate memory
    total_texture_memory = sum(
        _estimate_texture_memory(r) 
        for r in xml_data.resources.values() 
        if r.resource_type == "Texture2D"
    )
    total_buffer_memory = sum(
        r.byte_width 
        for r in xml_data.resources.values() 
        if r.resource_type == "Buffer"
    )
    
    result = {
        "file_path": source_file,
        "api_type": xml_data.driver,
        
        # Summary section
        "summary": {
            "draw_call_count": len(xml_data.draw_calls),
            "total_vertices": total_vertices,
            "total_triangles": total_triangles,
            "texture_count": texture_count,
            "buffer_count": buffer_count,
            "shader_count": 0,  # Not extracted from XML currently
            "driver": xml_data.driver,
            "machine_ident": xml_data.machine_ident,
            "total_chunks": xml_data.total_chunks,
        },
        
        # Statistics section (DiffEngine reads from here)
        "statistics": {
            "totalDrawCalls": len(xml_data.draw_calls),
            "totalVertices": total_vertices,
            "totalTriangles": total_triangles,
            "dispatchCalls": 0,  # TODO: Count dispatch calls
            "textureCount": texture_count,
            "bufferCount": buffer_count,
            "shaderCount": 0,
            "textureMemory": total_texture_memory,
            "bufferMemory": total_buffer_memory,
        },
        
        # Resource lists
        "textures": [],
        "buffers": [],
        "shaders": [],
        "draw_calls": [],
        "events": [],
    }
    
    # Convert textures
    for res_id, res in xml_data.resources.items():
        if res.resource_type == "Texture2D":
            result["textures"].append({
                "resourceId": str(res_id),
                "name": res.debug_name or res.name,
                "width": res.width,
                "height": res.height,
                "depth": 1,
                "format": res.format,
                "mipLevels": res.mip_levels,
                "arraySize": res.array_size,
                "samples": 1,
                "size_bytes": _estimate_texture_memory(res),
                "bind_flags": res.bind_flags,
            })
    
    # Convert buffers
    for res_id, res in xml_data.resources.items():
        if res.resource_type == "Buffer":
            result["buffers"].append({
                "resourceId": str(res_id),
                "name": res.debug_name or res.name,
                "size": res.byte_width,
                "usage": res.usage,
                "bind_flags": res.bind_flags,
            })
    
    # Convert draw calls
    for dc in xml_data.draw_calls:
        draw_entry = {
            "event_id": dc.event_id,
            "name": dc.name,
            "draw_type": _get_draw_type(dc.name),
            "index_count": dc.index_count,
            "vertex_count": dc.vertex_count,
            "instance_count": dc.instance_count,
            "triangle_count": dc.triangle_count,
            "marker_path": dc.debug_marker,
            "timestamp": dc.timestamp,
            "duration": dc.duration,
        }
        result["draw_calls"].append(draw_entry)
        
        # Also add to events list for compatibility
        if include_events:
            result["events"].append({
                "eventId": dc.event_id,
                "name": dc.name,
                "type": "draw",
                "indexCount": dc.index_count,
                "vertexCount": dc.vertex_count,
                "instanceCount": dc.instance_count,
                "markerPath": dc.debug_marker,
            })
    
    return result


def _get_draw_type(name: str) -> str:
    """Extract draw type from API call name.
    
    Args:
        name: Full API call name (e.g., "ID3D11DeviceContext::DrawIndexed")
        
    Returns:
        Short draw type (e.g., "DrawIndexed")
    """
    if "::" in name:
        return name.split("::")[-1]
    return name


def xml_file_to_capture_data(
    xml_path: str,
    source_rdc: Optional[str] = None
) -> Dict[str, Any]:
    """Load and convert an XML file to capture data format.
    
    Convenience function that combines parsing and conversion.
    
    Args:
        xml_path: Path to the XML file.
        source_rdc: Original RDC file path (optional, for metadata).
        
    Returns:
        Dictionary in the capture data format.
    """
    from .rdc_xml_parser import parse_rdc_xml
    
    xml_data = parse_rdc_xml(xml_path)
    source = source_rdc or xml_path
    
    return xml_to_capture_data(xml_data, source)


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python rdc_xml_converter.py <xml_file> [output.json]")
        sys.exit(1)
    
    xml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Converting: {xml_file}")
    
    data = xml_file_to_capture_data(xml_file)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved to: {output_file}")
    else:
        # Print summary
        print(f"\n=== Capture Data Summary ===")
        print(f"Driver: {data['summary']['driver']}")
        print(f"Draw Calls: {data['summary']['draw_call_count']}")
        print(f"Triangles: {data['summary']['total_triangles']}")
        print(f"Vertices: {data['summary']['total_vertices']}")
        print(f"Textures: {data['summary']['texture_count']}")
        print(f"Buffers: {data['summary']['buffer_count']}")
        print(f"Texture Memory: {data['statistics']['textureMemory']:,} bytes")
        print(f"Buffer Memory: {data['statistics']['bufferMemory']:,} bytes")
