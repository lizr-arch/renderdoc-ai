#!/usr/bin/env python3
"""XML Adapter - Convert RDC XML data to ReportDataContract.

This adapter bridges the gap between RdcXmlParser output and the
report_engine's ReportDataContract, enabling unified report generation
from XML exports.

Usage:
    from rdc_analyzer.report_engine.adapters.xml_adapter import XmlAdapter
    
    adapter = XmlAdapter()
    contract = adapter.from_xml_file("capture.xml")
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..contract import MetaData, ReportDataContract

# Lazy import to avoid circular dependencies
_parser_module = None


def _get_parser():
    """Lazy load the XML parser module."""
    global _parser_module
    if _parser_module is None:
        from ...parsers import rdc_xml_parser
        _parser_module = rdc_xml_parser
    return _parser_module


class XmlAdapter:
    """Adapter to convert RDC XML exports to ReportDataContract.
    
    This class provides a clean interface for:
    1. Parsing XML files using RdcXmlParser
    2. Transforming parsed data to ReportDataContract format
    3. Supporting incremental data enhancement
    """
    
    def __init__(self):
        """Initialize the adapter."""
        self._parser_cache: Dict[str, Any] = {}
    
    def from_xml_file(self, xml_path: str, 
                      rdc_name: Optional[str] = None) -> ReportDataContract:
        """Load and convert an XML file to ReportDataContract.
        
        Args:
            xml_path: Path to the XML file
            rdc_name: Optional capture name (defaults to XML filename)
            
        Returns:
            ReportDataContract populated with parsed data
        """
        parser_mod = _get_parser()
        
        path = Path(xml_path)
        if not path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        
        # Parse XML
        xml_data = parser_mod.parse_rdc_xml(str(path))
        
        # Convert to contract
        return self._convert_to_contract(
            xml_data, 
            rdc_name or path.stem
        )
    
    def from_parsed_data(self, xml_data: Any, 
                         rdc_name: str = "Unknown") -> ReportDataContract:
        """Convert already-parsed RdcXmlData to ReportDataContract.
        
        Args:
            xml_data: RdcXmlData instance from RdcXmlParser
            rdc_name: Capture name for metadata
            
        Returns:
            ReportDataContract populated with data
        """
        return self._convert_to_contract(xml_data, rdc_name)
    
    def _convert_to_contract(self, xml_data: Any, 
                             rdc_name: str) -> ReportDataContract:
        """Internal conversion logic.
        
        Args:
            xml_data: RdcXmlData instance
            rdc_name: Capture name
            
        Returns:
            Populated ReportDataContract
        """
        # Build metadata
        meta = MetaData(
            capture_name=rdc_name,
            api=xml_data.driver,
            source="xml",
            frame_thumbnail=""  # XML doesn't contain embedded thumbnail
        )
        
        # Convert draw calls
        draw_calls = self._convert_draw_calls(xml_data.draw_calls)
        
        # Convert resources to textures and buffers
        textures = self._extract_textures(xml_data.resources)
        buffers = self._extract_buffers(xml_data.resources)
        
        # Build contract
        return ReportDataContract(
            meta=meta,
            textures=textures,
            buffers=buffers,
            events=draw_calls,  # Contract uses 'events' for draw calls
            shaders=[],  # XML parsing doesn't extract shader details
            performance={
                "total_draw_calls": len(draw_calls),
                "total_textures": len(textures),
                "total_buffers": len(buffers),
            }
        )
    
    def _convert_draw_calls(self, 
                            draw_calls: List[Any]) -> List[Dict[str, Any]]:
        """Convert D3D11DrawCall list to dict format.
        
        Args:
            draw_calls: List of D3D11DrawCall objects
            
        Returns:
            List of draw call dictionaries
        """
        result = []
        for dc in draw_calls:
            result.append({
                "event_id": dc.event_id,
                "name": dc.name,
                "index_count": dc.index_count,
                "vertex_count": dc.vertex_count,
                "instance_count": dc.instance_count,
                "triangle_count": dc.triangle_count,
                "total_vertices": dc.total_vertices,
                "debug_marker": dc.debug_marker,
            })
        return result
    
    def _extract_textures(self, 
                          resources: Dict[int, Any]) -> List[Dict[str, Any]]:
        """Extract texture resources.
        
        Args:
            resources: Dict of resource_id -> D3D11Resource objects
            
        Returns:
            List of texture dictionaries
        """
        textures = []
        tex_id = 0
        
        for res_id, res in resources.items():
            if res.resource_type in ("Texture2D", "Texture3D", "TextureCube"):
                tex_id += 1
                textures.append({
                    "id": tex_id,
                    "resource_id": res.resource_id,
                    "name": res.debug_name or res.name,
                    "width": res.width,
                    "height": res.height,
                    "depth": res.depth,
                    "format": res.format,
                    "mip_levels": res.mip_levels,
                    "array_size": res.array_size,
                    "type": res.resource_type,
                    "thumbnail": "",  # No thumbnail in XML
                })
        
        return textures
    
    def _extract_buffers(self, 
                         resources: Dict[int, Any]) -> List[Dict[str, Any]]:
        """Extract buffer resources.
        
        Args:
            resources: Dict of resource_id -> D3D11Resource objects
            
        Returns:
            List of buffer dictionaries
        """
        buffers = []
        buf_id = 0
        
        for res_id, res in resources.items():
            if res.resource_type == "Buffer":
                buf_id += 1
                buffers.append({
                    "id": buf_id,
                    "resource_id": res.resource_id,
                    "name": res.debug_name or res.name,
                    "size": res.byte_width,
                    "bind_flags": res.bind_flags,
                    "usage": res.usage,
                })
        
        return buffers


# Convenience function
def load_xml_to_contract(xml_path: str, 
                         rdc_name: Optional[str] = None) -> ReportDataContract:
    """Convenience function to load XML directly to contract.
    
    Args:
        xml_path: Path to XML file
        rdc_name: Optional capture name
        
    Returns:
        ReportDataContract instance
    """
    adapter = XmlAdapter()
    return adapter.from_xml_file(xml_path, rdc_name)
