#!/usr/bin/env python3
"""RDC XML Parser - Parse RenderDoc XML exports to CaptureData format.

This module parses XML files exported from RDC captures using:
    renderdoccmd.exe convert -f input.rdc -o output.xml -c xml

Usage:
    from rdc_analyzer.parsers.rdc_xml_parser import RdcXmlParser
    
    parser = RdcXmlParser("capture.xml")
    capture_data = parser.parse()
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import re


@dataclass
class D3D11DrawCall:
    """Represents a D3D11 draw call extracted from XML."""
    event_id: int
    name: str
    index_count: int = 0
    vertex_count: int = 0
    instance_count: int = 1
    start_index: int = 0
    base_vertex: int = 0
    start_instance: int = 0
    timestamp: int = 0
    duration: int = 0
    context_id: int = 0
    debug_marker: str = ""
    
    @property
    def triangle_count(self) -> int:
        """Estimate triangle count (assuming triangle list topology)."""
        if self.index_count > 0:
            return self.index_count // 3
        return self.vertex_count // 3
    
    @property
    def total_vertices(self) -> int:
        """Total vertices considering instancing."""
        base = self.index_count if self.index_count > 0 else self.vertex_count
        return base * self.instance_count


@dataclass
class D3D11Resource:
    """Represents a D3D11 resource (buffer, texture, etc.)."""
    resource_id: int
    name: str
    resource_type: str  # "Buffer", "Texture2D", "Texture3D", etc.
    debug_name: str = ""
    
    # Buffer specific
    byte_width: int = 0
    bind_flags: str = ""
    usage: str = ""
    
    # Texture specific
    width: int = 0
    height: int = 0
    depth: int = 1
    mip_levels: int = 1
    array_size: int = 1
    format: str = ""


@dataclass
class D3D11PipelineState:
    """Snapshot of D3D11 pipeline state at a draw call."""
    vs_shader: int = 0
    ps_shader: int = 0
    gs_shader: int = 0
    hs_shader: int = 0
    ds_shader: int = 0
    cs_shader: int = 0
    
    render_targets: List[int] = field(default_factory=list)
    depth_target: int = 0
    
    viewport_count: int = 0
    scissor_count: int = 0


@dataclass
class RdcXmlData:
    """Parsed data from an RDC XML export."""
    # Header info
    driver: str = "Unknown"
    machine_ident: str = ""
    thumbnail_width: int = 0
    thumbnail_height: int = 0
    
    # Extracted data
    draw_calls: List[D3D11DrawCall] = field(default_factory=list)
    resources: Dict[int, D3D11Resource] = field(default_factory=dict)
    debug_names: Dict[int, str] = field(default_factory=dict)
    
    # Statistics
    total_chunks: int = 0
    frame_duration: int = 0


class RdcXmlParser:
    """Parser for RenderDoc XML exports."""
    
    # D3D11 Draw call chunk names
    DRAW_CALLS = {
        "ID3D11DeviceContext::Draw",
        "ID3D11DeviceContext::DrawIndexed",
        "ID3D11DeviceContext::DrawInstanced",
        "ID3D11DeviceContext::DrawIndexedInstanced",
        "ID3D11DeviceContext::DrawAuto",
        "ID3D11DeviceContext::DrawIndexedInstancedIndirect",
        "ID3D11DeviceContext::DrawInstancedIndirect",
    }
    
    DISPATCH_CALLS = {
        "ID3D11DeviceContext::Dispatch",
        "ID3D11DeviceContext::DispatchIndirect",
    }
    
    CLEAR_CALLS = {
        "ID3D11DeviceContext::ClearRenderTargetView",
        "ID3D11DeviceContext::ClearDepthStencilView",
        "ID3D11DeviceContext::ClearUnorderedAccessViewFloat",
        "ID3D11DeviceContext::ClearUnorderedAccessViewUint",
    }
    
    def __init__(self, xml_path: str):
        """Initialize parser with XML file path.
        
        Args:
            xml_path: Path to the XML file exported from RDC.
        """
        self.xml_path = Path(xml_path)
        if not self.xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        
        self._tree: Optional[ET.ElementTree] = None
        self._root: Optional[ET.Element] = None
        self._current_marker_stack: List[str] = []
    
    def parse(self) -> RdcXmlData:
        """Parse the XML file and return structured data.
        
        Returns:
            RdcXmlData containing all extracted information.
        """
        self._tree = ET.parse(self.xml_path)
        self._root = self._tree.getroot()
        
        data = RdcXmlData()
        
        # Parse header
        self._parse_header(data)
        
        # Parse chunks
        chunks = self._root.find("chunks")
        if chunks is not None:
            data.total_chunks = len(list(chunks))
            self._parse_chunks(chunks, data)
        
        # Apply debug names to resources
        self._apply_debug_names(data)
        
        return data
    
    def _parse_header(self, data: RdcXmlData) -> None:
        """Parse the RDC header section."""
        header = self._root.find("header")
        if header is None:
            return
        
        driver = header.find("driver")
        if driver is not None:
            data.driver = driver.text or "Unknown"
        
        machine = header.find("machineIdent")
        if machine is not None:
            data.machine_ident = machine.text or ""
        
        thumb = header.find("thumbnail")
        if thumb is not None:
            data.thumbnail_width = int(thumb.get("width", 0))
            data.thumbnail_height = int(thumb.get("height", 0))
    
    def _parse_chunks(self, chunks: ET.Element, data: RdcXmlData) -> None:
        """Parse all chunks to extract draw calls, resources, etc."""
        for chunk in chunks:
            name = chunk.get("name", "")
            chunk_index = int(chunk.get("chunkIndex", 0))
            
            # Track debug markers
            if "BeginEvent" in name:
                marker_text = self._extract_marker_text(chunk)
                self._current_marker_stack.append(marker_text)
            elif "EndEvent" in name:
                if self._current_marker_stack:
                    self._current_marker_stack.pop()
            
            # Extract draw calls
            if name in self.DRAW_CALLS:
                draw_call = self._parse_draw_call(chunk, chunk_index)
                draw_call.debug_marker = "/".join(self._current_marker_stack)
                data.draw_calls.append(draw_call)
            
            # Extract resources
            elif "CreateBuffer" in name:
                resource = self._parse_buffer(chunk)
                if resource:
                    data.resources[resource.resource_id] = resource
            
            elif "CreateTexture2D" in name:
                resource = self._parse_texture2d(chunk)
                if resource:
                    data.resources[resource.resource_id] = resource
            
            # Extract debug names
            elif "SetDebugName" in name:
                res_id, debug_name = self._parse_debug_name(chunk)
                if res_id > 0:
                    data.debug_names[res_id] = debug_name
    
    def _extract_marker_text(self, chunk: ET.Element) -> str:
        """Extract the marker text from a BeginEvent chunk."""
        for child in chunk:
            if child.get("name") == "Name" or child.tag == "string":
                return child.text or ""
        return ""
    
    def _parse_draw_call(self, chunk: ET.Element, event_id: int) -> D3D11DrawCall:
        """Parse a draw call chunk."""
        name = chunk.get("name", "")
        
        draw = D3D11DrawCall(
            event_id=event_id,
            name=name,
            timestamp=int(chunk.get("timestamp", 0)),
            duration=int(chunk.get("duration", 0)),
        )
        
        for child in chunk:
            child_name = child.get("name", "")
            
            if child_name == "IndexCount":
                draw.index_count = int(child.text or 0)
            elif child_name == "VertexCount":
                draw.vertex_count = int(child.text or 0)
            elif child_name == "InstanceCount":
                draw.instance_count = int(child.text or 1)
            elif child_name == "StartIndexLocation":
                draw.start_index = int(child.text or 0)
            elif child_name == "BaseVertexLocation":
                draw.base_vertex = int(child.text or 0)
            elif child_name == "StartInstanceLocation":
                draw.start_instance = int(child.text or 0)
            elif child_name == "Context":
                draw.context_id = int(child.text or 0)
        
        return draw
    
    def _parse_buffer(self, chunk: ET.Element) -> Optional[D3D11Resource]:
        """Parse a CreateBuffer chunk."""
        resource_id = 0
        byte_width = 0
        bind_flags = ""
        usage = ""
        
        for child in chunk:
            child_name = child.get("name", "")
            
            if child_name == "pBuffer":
                resource_id = int(child.text or 0)
            elif child_name == "pDesc":
                # Parse nested struct
                for desc_child in child:
                    desc_name = desc_child.get("name", "")
                    if desc_name == "ByteWidth":
                        byte_width = int(desc_child.text or 0)
                    elif desc_name == "BindFlags":
                        bind_flags = desc_child.get("string", "")
                    elif desc_name == "Usage":
                        usage = desc_child.get("string", "")
        
        if resource_id > 0:
            return D3D11Resource(
                resource_id=resource_id,
                name=f"Buffer_{resource_id}",
                resource_type="Buffer",
                byte_width=byte_width,
                bind_flags=bind_flags,
                usage=usage,
            )
        return None
    
    def _parse_texture2d(self, chunk: ET.Element) -> Optional[D3D11Resource]:
        """Parse a CreateTexture2D chunk."""
        resource_id = 0
        width = 0
        height = 0
        mip_levels = 1
        array_size = 1
        tex_format = ""
        bind_flags = ""
        
        for child in chunk:
            child_name = child.get("name", "")
            
            if child_name == "pTexture":
                resource_id = int(child.text or 0)
            elif child_name == "Descriptor" or child_name == "pDesc":
                for desc_child in child:
                    desc_name = desc_child.get("name", "")
                    if desc_name == "Width":
                        width = int(desc_child.text or 0)
                    elif desc_name == "Height":
                        height = int(desc_child.text or 0)
                    elif desc_name == "MipLevels":
                        mip_levels = int(desc_child.text or 1)
                    elif desc_name == "ArraySize":
                        array_size = int(desc_child.text or 1)
                    elif desc_name == "Format":
                        tex_format = desc_child.get("string", "")
                    elif desc_name == "BindFlags":
                        bind_flags = desc_child.get("string", "")
        
        if resource_id > 0:
            return D3D11Resource(
                resource_id=resource_id,
                name=f"Texture2D_{resource_id}",
                resource_type="Texture2D",
                width=width,
                height=height,
                mip_levels=mip_levels,
                array_size=array_size,
                format=tex_format,
                bind_flags=bind_flags,
            )
        return None
    
    def _parse_debug_name(self, chunk: ET.Element) -> tuple:
        """Parse a SetDebugName chunk."""
        resource_id = 0
        debug_name = ""
        
        for child in chunk:
            child_name = child.get("name", "")
            
            if child_name == "pResource":
                resource_id = int(child.text or 0)
            elif child_name == "Name":
                debug_name = child.text or ""
        
        return resource_id, debug_name
    
    def _apply_debug_names(self, data: RdcXmlData) -> None:
        """Apply debug names to resources."""
        for res_id, debug_name in data.debug_names.items():
            if res_id in data.resources:
                data.resources[res_id].debug_name = debug_name


def parse_rdc_xml(xml_path: str) -> RdcXmlData:
    """Convenience function to parse an RDC XML file.
    
    Args:
        xml_path: Path to the XML file.
        
    Returns:
        Parsed RdcXmlData.
    """
    parser = RdcXmlParser(xml_path)
    return parser.parse()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python rdc_xml_parser.py <xml_file>")
        sys.exit(1)
    
    xml_file = sys.argv[1]
    print(f"Parsing: {xml_file}")
    
    data = parse_rdc_xml(xml_file)
    
    print(f"\n=== RDC XML Summary ===")
    print(f"Driver: {data.driver}")
    print(f"Total Chunks: {data.total_chunks}")
    print(f"Draw Calls: {len(data.draw_calls)}")
    print(f"Resources: {len(data.resources)}")
    print(f"Debug Names: {len(data.debug_names)}")
    
    if data.draw_calls:
        print(f"\n=== Draw Calls ===")
        total_tris = 0
        total_verts = 0
        for dc in data.draw_calls:
            print(f"  [EID {dc.event_id}] {dc.name}: "
                  f"idx={dc.index_count}, vtx={dc.vertex_count}, "
                  f"tris={dc.triangle_count}")
            if dc.debug_marker:
                print(f"           Marker: {dc.debug_marker}")
            total_tris += dc.triangle_count
            total_verts += dc.total_vertices
        
        print(f"\n=== Totals ===")
        print(f"Total Triangles: {total_tris}")
        print(f"Total Vertices: {total_verts}")
