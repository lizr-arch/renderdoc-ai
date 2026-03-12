#!/usr/bin/env python3
"""Tests for RDC XML Parser."""

import pytest
import tempfile
import os
from pathlib import Path

from rdc_analyzer.parsers.rdc_xml_parser import (
    RdcXmlParser,
    RdcXmlData,
    D3D11DrawCall,
    D3D11Resource,
    parse_rdc_xml,
)


# Sample XML content for testing
SAMPLE_XML = '''<?xml version="1.0"?>
<rdc>
    <header>
        <driver id="1">D3D11</driver>
        <machineIdent>8449</machineIdent>
        <thumbnail width="1920" height="1080">thumb.png</thumbnail>
    </header>
    <chunks version="19">
        <chunk id="1" chunkIndex="0" name="Internal::Driver Initialisation Parameters" length="100" threadID="1" timestamp="1000" duration="0">
            <callstack />
        </chunk>
        <chunk id="100" chunkIndex="1" name="ID3DUserDefinedAnnotation::BeginEvent" length="20" threadID="1" timestamp="1100" duration="0">
            <callstack />
            <string name="Name">MainPass</string>
        </chunk>
        <chunk id="1006" chunkIndex="2" name="ID3D11Device::CreateBuffer" length="100" threadID="1" timestamp="1200" duration="10">
            <callstack />
            <struct name="pDesc" typename="D3D11_BUFFER_DESC">
                <uint name="ByteWidth" typename="uint32_t" width="4">65536</uint>
                <enum name="Usage" typename="D3D11_USAGE" width="4" string="D3D11_USAGE_DYNAMIC">2</enum>
                <enum name="BindFlags" typename="D3D11_BIND_FLAG" width="4" string="D3D11_BIND_VERTEX_BUFFER">1</enum>
            </struct>
            <ResourceId name="pBuffer" typename="ID3D11Buffer *" width="8">100</ResourceId>
        </chunk>
        <chunk id="1007" chunkIndex="3" name="ID3D11Device::CreateTexture2D" length="200" threadID="1" timestamp="1300" duration="20">
            <callstack />
            <struct name="Descriptor" typename="D3D11_TEXTURE2D_DESC">
                <uint name="Width" typename="uint32_t" width="4">1024</uint>
                <uint name="Height" typename="uint32_t" width="4">1024</uint>
                <uint name="MipLevels" typename="uint32_t" width="4">10</uint>
                <uint name="ArraySize" typename="uint32_t" width="4">1</uint>
                <enum name="Format" typename="DXGI_FORMAT" width="4" string="DXGI_FORMAT_R8G8B8A8_UNORM">28</enum>
                <enum name="BindFlags" typename="D3D11_BIND_FLAG" width="4" string="D3D11_BIND_SHADER_RESOURCE">8</enum>
            </struct>
            <ResourceId name="pTexture" typename="ID3D11Texture2D *" width="8">200</ResourceId>
        </chunk>
        <chunk id="1090" chunkIndex="4" name="ID3D11Resource::SetDebugName" length="50" threadID="1" timestamp="1400" duration="0">
            <callstack />
            <ResourceId name="pResource" typename="ID3D11Resource *" width="8">200</ResourceId>
            <string name="Name">Albedo Texture</string>
        </chunk>
        <chunk id="1071" chunkIndex="5" name="ID3D11DeviceContext::DrawIndexed" length="28" threadID="1" timestamp="1500" duration="100">
            <callstack />
            <ResourceId name="Context" typename="ID3D11DeviceContext *" width="8">1</ResourceId>
            <uint name="IndexCount" typename="uint32_t" width="4">3000</uint>
            <uint name="StartIndexLocation" typename="uint32_t" width="4">0</uint>
            <int name="BaseVertexLocation" typename="int32_t" width="4">0</int>
        </chunk>
        <chunk id="1070" chunkIndex="6" name="ID3D11DeviceContext::Draw" length="20" threadID="1" timestamp="1600" duration="50">
            <callstack />
            <ResourceId name="Context" typename="ID3D11DeviceContext *" width="8">1</ResourceId>
            <uint name="VertexCount" typename="uint32_t" width="4">300</uint>
            <uint name="StartVertexLocation" typename="uint32_t" width="4">0</uint>
        </chunk>
        <chunk id="101" chunkIndex="7" name="ID3DUserDefinedAnnotation::EndEvent" length="10" threadID="1" timestamp="1700" duration="0">
            <callstack />
        </chunk>
        <chunk id="1072" chunkIndex="8" name="ID3D11DeviceContext::DrawInstanced" length="32" threadID="1" timestamp="1800" duration="80">
            <callstack />
            <ResourceId name="Context" typename="ID3D11DeviceContext *" width="8">1</ResourceId>
            <uint name="VertexCount" typename="uint32_t" width="4">36</uint>
            <uint name="InstanceCount" typename="uint32_t" width="4">100</uint>
            <uint name="StartVertexLocation" typename="uint32_t" width="4">0</uint>
            <uint name="StartInstanceLocation" typename="uint32_t" width="4">0</uint>
        </chunk>
    </chunks>
</rdc>
'''


class TestD3D11DrawCall:
    """Tests for D3D11DrawCall dataclass."""
    
    def test_triangle_count_indexed(self):
        """Triangle count from indexed draw."""
        dc = D3D11DrawCall(event_id=1, name="DrawIndexed", index_count=3000)
        assert dc.triangle_count == 1000
    
    def test_triangle_count_non_indexed(self):
        """Triangle count from non-indexed draw."""
        dc = D3D11DrawCall(event_id=1, name="Draw", vertex_count=300)
        assert dc.triangle_count == 100
    
    def test_total_vertices_instanced(self):
        """Total vertices with instancing."""
        dc = D3D11DrawCall(event_id=1, name="DrawInstanced", vertex_count=36, instance_count=100)
        assert dc.total_vertices == 3600
    
    def test_total_vertices_indexed(self):
        """Total vertices from indexed draw."""
        dc = D3D11DrawCall(event_id=1, name="DrawIndexed", index_count=3000, instance_count=1)
        assert dc.total_vertices == 3000


class TestRdcXmlParser:
    """Tests for RdcXmlParser class."""
    
    @pytest.fixture
    def sample_xml_file(self, tmp_path):
        """Create a temporary XML file for testing."""
        xml_file = tmp_path / "test_capture.xml"
        xml_file.write_text(SAMPLE_XML, encoding="utf-8")
        return str(xml_file)
    
    def test_parse_header(self, sample_xml_file):
        """Test header parsing."""
        data = parse_rdc_xml(sample_xml_file)
        
        assert data.driver == "D3D11"
        assert data.machine_ident == "8449"
        assert data.thumbnail_width == 1920
        assert data.thumbnail_height == 1080
    
    def test_parse_draw_calls(self, sample_xml_file):
        """Test draw call extraction."""
        data = parse_rdc_xml(sample_xml_file)
        
        assert len(data.draw_calls) == 3
        
        # DrawIndexed
        dc0 = data.draw_calls[0]
        assert dc0.event_id == 5
        assert dc0.index_count == 3000
        assert dc0.triangle_count == 1000
        assert dc0.debug_marker == "MainPass"
        
        # Draw
        dc1 = data.draw_calls[1]
        assert dc1.event_id == 6
        assert dc1.vertex_count == 300
        assert dc1.triangle_count == 100
        assert dc1.debug_marker == "MainPass"
        
        # DrawInstanced (after EndEvent, no marker)
        dc2 = data.draw_calls[2]
        assert dc2.event_id == 8
        assert dc2.vertex_count == 36
        assert dc2.instance_count == 100
        assert dc2.total_vertices == 3600
        assert dc2.debug_marker == ""  # After EndEvent
    
    def test_parse_resources(self, sample_xml_file):
        """Test resource extraction."""
        data = parse_rdc_xml(sample_xml_file)
        
        assert len(data.resources) == 2
        
        # Buffer
        buf = data.resources[100]
        assert buf.resource_type == "Buffer"
        assert buf.byte_width == 65536
        assert "VERTEX_BUFFER" in buf.bind_flags
        
        # Texture
        tex = data.resources[200]
        assert tex.resource_type == "Texture2D"
        assert tex.width == 1024
        assert tex.height == 1024
        assert tex.mip_levels == 10
        assert "R8G8B8A8_UNORM" in tex.format
    
    def test_debug_names_applied(self, sample_xml_file):
        """Test debug names are applied to resources."""
        data = parse_rdc_xml(sample_xml_file)
        
        tex = data.resources[200]
        assert tex.debug_name == "Albedo Texture"
    
    def test_file_not_found(self):
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            RdcXmlParser("nonexistent.xml")
    
    def test_total_chunks_count(self, sample_xml_file):
        """Test total chunks count."""
        data = parse_rdc_xml(sample_xml_file)
        assert data.total_chunks == 9


class TestRealXmlFile:
    """Tests using the real exported XML file (if available)."""
    
    REAL_XML_PATH = "scripts/rdc_analyzer/test_captures/test_d3d11.xml"
    
    @pytest.fixture
    def real_xml_file(self):
        """Get the real XML file path if it exists."""
        if os.path.exists(self.REAL_XML_PATH):
            return self.REAL_XML_PATH
        pytest.skip("Real XML file not available")
    
    def test_parse_real_file(self, real_xml_file):
        """Test parsing the real exported XML."""
        data = parse_rdc_xml(real_xml_file)
        
        assert data.driver == "D3D11"
        assert data.total_chunks > 0
        assert len(data.draw_calls) > 0
    
    def test_real_file_has_markers(self, real_xml_file):
        """Test that real file has debug markers."""
        data = parse_rdc_xml(real_xml_file)
        
        markers = [dc.debug_marker for dc in data.draw_calls if dc.debug_marker]
        assert len(markers) > 0, "Expected some draw calls to have debug markers"
    
    def test_real_file_triangle_count(self, real_xml_file):
        """Test triangle count calculation for real file."""
        data = parse_rdc_xml(real_xml_file)
        
        total_tris = sum(dc.triangle_count for dc in data.draw_calls)
        assert total_tris > 0, "Expected positive triangle count"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
