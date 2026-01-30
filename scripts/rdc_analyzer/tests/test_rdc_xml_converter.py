#!/usr/bin/env python3
"""Tests for RDC XML to CaptureData Converter."""

import pytest
from rdc_analyzer.parsers.rdc_xml_parser import (
    RdcXmlData, D3D11DrawCall, D3D11Resource
)
from rdc_analyzer.parsers.rdc_xml_converter import (
    xml_to_capture_data,
    _estimate_texture_memory,
    _get_draw_type,
)


# ========== Fixtures ==========

@pytest.fixture
def sample_draw_calls():
    """Create sample draw calls for testing."""
    return [
        D3D11DrawCall(
            event_id=100,
            name="ID3D11DeviceContext::DrawIndexed",
            index_count=1500,
            vertex_count=0,
            instance_count=1,
            debug_marker="MainPass/Opaque",
            timestamp=0.0,
            duration=0.0
        ),
        D3D11DrawCall(
            event_id=150,
            name="ID3D11DeviceContext::Draw",
            index_count=0,
            vertex_count=600,
            instance_count=1,
            debug_marker="MainPass/Sky",
            timestamp=0.0,
            duration=0.0
        ),
        D3D11DrawCall(
            event_id=200,
            name="ID3D11DeviceContext::DrawIndexedInstanced",
            index_count=300,
            vertex_count=0,
            instance_count=10,
            debug_marker="PostProcess/Blur",
            timestamp=0.0,
            duration=0.0
        ),
    ]


@pytest.fixture
def sample_resources():
    """Create sample resources for testing."""
    return {
        1: D3D11Resource(
            resource_id=1,
            name="Texture_1",
            resource_type="Texture2D",
            width=1024,
            height=1024,
            array_size=1,
            mip_levels=10,
            format="R8G8B8A8_UNORM",
            bind_flags="ShaderResource",
            byte_width=0,
            debug_name="Albedo"
        ),
        2: D3D11Resource(
            resource_id=2,
            name="Texture_2",
            resource_type="Texture2D",
            width=512,
            height=512,
            array_size=1,
            mip_levels=1,
            format="BC1_UNORM",
            bind_flags="ShaderResource",
            byte_width=0,
            debug_name=""
        ),
        3: D3D11Resource(
            resource_id=3,
            name="Buffer_3",
            resource_type="Buffer",
            width=0,
            height=0,
            array_size=1,
            mip_levels=1,
            format="",
            bind_flags="VertexBuffer",
            byte_width=65536,
            debug_name="VertexBuffer"
        ),
        4: D3D11Resource(
            resource_id=4,
            name="Buffer_4",
            resource_type="Buffer",
            width=0,
            height=0,
            array_size=1,
            mip_levels=1,
            format="",
            bind_flags="IndexBuffer",
            byte_width=32768,
            debug_name=""
        ),
    }


@pytest.fixture
def sample_xml_data(sample_draw_calls, sample_resources):
    """Create sample RdcXmlData for testing."""
    return RdcXmlData(
        driver="D3D11",
        machine_ident="TestMachine",
        total_chunks=500,
        draw_calls=sample_draw_calls,
        resources=sample_resources
    )


# ========== Unit Tests ==========

class TestEstimateTextureMemory:
    """Tests for _estimate_texture_memory function."""
    
    def test_rgba8_format(self):
        """Test RGBA8 format estimation."""
        res = D3D11Resource(
            resource_id=1, name="tex", resource_type="Texture2D",
            width=256, height=256, array_size=1, mip_levels=1,
            format="R8G8B8A8_UNORM", bind_flags="", byte_width=0, debug_name=""
        )
        size = _estimate_texture_memory(res)
        assert size == 256 * 256 * 4  # 262144
    
    def test_rgba16_format(self):
        """Test RGBA16 format estimation."""
        res = D3D11Resource(
            resource_id=1, name="tex", resource_type="Texture2D",
            width=256, height=256, array_size=1, mip_levels=1,
            format="R16G16B16A16_FLOAT", bind_flags="", byte_width=0, debug_name=""
        )
        size = _estimate_texture_memory(res)
        assert size == 256 * 256 * 8
    
    def test_bc1_compressed(self):
        """Test BC1 compressed format estimation."""
        res = D3D11Resource(
            resource_id=1, name="tex", resource_type="Texture2D",
            width=1024, height=1024, array_size=1, mip_levels=1,
            format="BC1_UNORM", bind_flags="", byte_width=0, debug_name=""
        )
        size = _estimate_texture_memory(res)
        assert size == int(1024 * 1024 * 0.5)  # 0.5 bpp
    
    def test_mipmaps_add_33_percent(self):
        """Test that mipmaps increase size by ~33%."""
        res_no_mip = D3D11Resource(
            resource_id=1, name="tex", resource_type="Texture2D",
            width=512, height=512, array_size=1, mip_levels=1,
            format="R8G8B8A8_UNORM", bind_flags="", byte_width=0, debug_name=""
        )
        res_with_mip = D3D11Resource(
            resource_id=2, name="tex", resource_type="Texture2D",
            width=512, height=512, array_size=1, mip_levels=9,
            format="R8G8B8A8_UNORM", bind_flags="", byte_width=0, debug_name=""
        )
        
        base = _estimate_texture_memory(res_no_mip)
        with_mip = _estimate_texture_memory(res_with_mip)
        
        assert with_mip == int(base * 1.33)
    
    def test_non_texture_returns_zero(self):
        """Test that non-texture resources return 0."""
        res = D3D11Resource(
            resource_id=1, name="buf", resource_type="Buffer",
            width=0, height=0, array_size=1, mip_levels=1,
            format="", bind_flags="", byte_width=65536, debug_name=""
        )
        assert _estimate_texture_memory(res) == 0


class TestGetDrawType:
    """Tests for _get_draw_type function."""
    
    def test_extract_from_d3d11(self):
        """Test extraction from D3D11 call name."""
        assert _get_draw_type("ID3D11DeviceContext::DrawIndexed") == "DrawIndexed"
        assert _get_draw_type("ID3D11DeviceContext::Draw") == "Draw"
        assert _get_draw_type("ID3D11DeviceContext::DrawInstanced") == "DrawInstanced"
    
    def test_simple_name(self):
        """Test simple name without namespace."""
        assert _get_draw_type("DrawIndexed") == "DrawIndexed"


class TestXmlToCaptureData:
    """Tests for xml_to_capture_data function."""
    
    def test_basic_structure(self, sample_xml_data):
        """Test that output has required structure."""
        result = xml_to_capture_data(sample_xml_data, "test.rdc")
        
        # Required top-level keys
        assert "file_path" in result
        assert "summary" in result
        assert "statistics" in result
        assert "textures" in result
        assert "buffers" in result
        assert "draw_calls" in result
        assert "events" in result
        
        # File path preserved
        assert result["file_path"] == "test.rdc"
    
    def test_summary_fields(self, sample_xml_data):
        """Test summary field accuracy."""
        result = xml_to_capture_data(sample_xml_data)
        summary = result["summary"]
        
        assert summary["draw_call_count"] == 3
        assert summary["driver"] == "D3D11"
        assert summary["machine_ident"] == "TestMachine"
        assert summary["texture_count"] == 2
        assert summary["buffer_count"] == 2
    
    def test_triangle_calculation(self, sample_xml_data):
        """Test that triangles are correctly summed."""
        result = xml_to_capture_data(sample_xml_data)
        
        # Draw 1: 1500/3 = 500 triangles
        # Draw 2: 600/3 = 200 triangles  
        # Draw 3: 300/3 = 100 triangles
        expected_triangles = 500 + 200 + 100
        
        assert result["summary"]["total_triangles"] == expected_triangles
        assert result["statistics"]["totalTriangles"] == expected_triangles
    
    def test_vertex_calculation(self, sample_xml_data):
        """Test that vertices are correctly summed with instancing."""
        result = xml_to_capture_data(sample_xml_data)
        
        # total_vertices = base * instance_count
        # DC1: 1500 * 1 = 1500 (indexed)
        # DC2: 600 * 1 = 600 (non-indexed)
        # DC3: 300 * 10 = 3000 (indexed, instanced)
        expected = 1500 + 600 + 3000
        
        assert result["summary"]["total_vertices"] == expected
    
    def test_statistics_section(self, sample_xml_data):
        """Test statistics section (used by DiffEngine)."""
        result = xml_to_capture_data(sample_xml_data)
        stats = result["statistics"]
        
        assert stats["totalDrawCalls"] == 3
        assert stats["textureCount"] == 2
        assert stats["bufferCount"] == 2
        assert stats["bufferMemory"] == 65536 + 32768
    
    def test_texture_list(self, sample_xml_data):
        """Test texture list conversion."""
        result = xml_to_capture_data(sample_xml_data)
        textures = result["textures"]
        
        assert len(textures) == 2
        
        # Find the Albedo texture
        albedo = next(t for t in textures if t["name"] == "Albedo")
        assert albedo["width"] == 1024
        assert albedo["height"] == 1024
        assert albedo["format"] == "R8G8B8A8_UNORM"
        assert albedo["mipLevels"] == 10
    
    def test_buffer_list(self, sample_xml_data):
        """Test buffer list conversion."""
        result = xml_to_capture_data(sample_xml_data)
        buffers = result["buffers"]
        
        assert len(buffers) == 2
        
        # Find the vertex buffer
        vb = next(b for b in buffers if b["name"] == "VertexBuffer")
        assert vb["size"] == 65536
        assert vb["bind_flags"] == "VertexBuffer"
    
    def test_draw_call_list(self, sample_xml_data):
        """Test draw call list conversion."""
        result = xml_to_capture_data(sample_xml_data)
        draw_calls = result["draw_calls"]
        
        assert len(draw_calls) == 3
        
        # Check first draw call
        dc1 = draw_calls[0]
        assert dc1["event_id"] == 100
        assert dc1["draw_type"] == "DrawIndexed"
        assert dc1["index_count"] == 1500
        assert dc1["marker_path"] == "MainPass/Opaque"
        assert dc1["triangle_count"] == 500
    
    def test_events_list(self, sample_xml_data):
        """Test events list for compatibility."""
        result = xml_to_capture_data(sample_xml_data)
        events = result["events"]
        
        assert len(events) == 3
        
        evt = events[0]
        assert evt["eventId"] == 100
        assert evt["type"] == "draw"
        assert evt["markerPath"] == "MainPass/Opaque"
    
    def test_exclude_events(self, sample_xml_data):
        """Test that events can be excluded."""
        result = xml_to_capture_data(sample_xml_data, include_events=False)
        
        assert result["events"] == []
        assert len(result["draw_calls"]) == 3  # Draw calls still present


class TestIntegration:
    """Integration tests for the converter."""
    
    def test_empty_xml_data(self):
        """Test conversion of empty data."""
        empty_data = RdcXmlData(
            driver="Unknown",
            machine_ident="",
            total_chunks=0,
            draw_calls=[],
            resources={}
        )
        
        result = xml_to_capture_data(empty_data)
        
        assert result["summary"]["draw_call_count"] == 0
        assert result["summary"]["total_triangles"] == 0
        assert result["textures"] == []
        assert result["buffers"] == []
    
    def test_diffengine_compatibility(self, sample_xml_data):
        """Test that output is compatible with DiffEngine input format."""
        result = xml_to_capture_data(sample_xml_data, "baseline.rdc")
        
        # DiffEngine expects these exact keys
        required_stats_keys = [
            "totalDrawCalls", "totalVertices", "totalTriangles",
            "textureCount", "bufferCount"
        ]
        for key in required_stats_keys:
            assert key in result["statistics"], f"Missing stat key: {key}"
        
        # Textures must have resourceId
        if result["textures"]:
            assert "resourceId" in result["textures"][0]
        
        # Draw calls must have event_id and marker_path
        if result["draw_calls"]:
            assert "event_id" in result["draw_calls"][0]
            assert "marker_path" in result["draw_calls"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
