#!/usr/bin/env python3
"""Tests for RDC File Loader."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from rdc_analyzer.parsers.rdc_loader import (
    find_renderdoccmd,
    convert_rdc_to_xml,
    load_rdc_file,
    is_rdc_file,
    load_capture_file,
    RENDERDOCCMD_SEARCH_PATHS,
)


# ========== Unit Tests ==========

class TestFindRenderdoccmd:
    """Tests for find_renderdoccmd function."""
    
    def test_find_in_path(self):
        """Test finding renderdoccmd in PATH."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/renderdoccmd"
            result = find_renderdoccmd()
            assert result == "/usr/bin/renderdoccmd"
    
    def test_find_from_search_paths(self):
        """Test finding renderdoccmd from search paths."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            with patch('os.path.isfile') as mock_isfile:
                def isfile_side_effect(path):
                    return path == r"C:\Program Files\RenderDoc\renderdoccmd.exe"
                mock_isfile.side_effect = isfile_side_effect
                
                result = find_renderdoccmd()
                assert result == r"C:\Program Files\RenderDoc\renderdoccmd.exe"
    
    def test_not_found(self):
        """Test when renderdoccmd is not found."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            with patch('os.path.isfile') as mock_isfile:
                mock_isfile.return_value = False
                
                result = find_renderdoccmd()
                assert result is None


class TestIsRdcFile:
    """Tests for is_rdc_file function."""
    
    def test_rdc_extension(self):
        """Test detection of .rdc extension."""
        assert is_rdc_file("capture.rdc") is True
        assert is_rdc_file("path/to/capture.RDC") is True
        assert is_rdc_file("capture.rdc.bak") is False
    
    def test_other_extensions(self):
        """Test rejection of other extensions."""
        assert is_rdc_file("capture.json") is False
        assert is_rdc_file("capture.xml") is False
        assert is_rdc_file("capture") is False


class TestConvertRdcToXml:
    """Tests for convert_rdc_to_xml function."""
    
    def test_file_not_found(self):
        """Test error when RDC file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="RDC file not found"):
            convert_rdc_to_xml("nonexistent.rdc")
    
    def test_renderdoccmd_not_found(self, tmp_path):
        """Test error when renderdoccmd not found."""
        # Create a dummy RDC file
        rdc_file = tmp_path / "test.rdc"
        rdc_file.write_bytes(b"dummy")
        
        with patch('rdc_analyzer.parsers.rdc_loader.find_renderdoccmd') as mock_find:
            mock_find.return_value = None
            
            with pytest.raises(FileNotFoundError, match="renderdoccmd not found"):
                convert_rdc_to_xml(str(rdc_file))
    
    def test_successful_conversion(self, tmp_path):
        """Test successful RDC to XML conversion."""
        # Create dummy files
        rdc_file = tmp_path / "test.rdc"
        rdc_file.write_bytes(b"dummy rdc")
        
        xml_output = tmp_path / "output.xml"
        
        with patch('rdc_analyzer.parsers.rdc_loader.find_renderdoccmd') as mock_find:
            mock_find.return_value = "/usr/bin/renderdoccmd"
            
            with patch('subprocess.run') as mock_run:
                # Simulate successful conversion
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result
                
                result = convert_rdc_to_xml(
                    str(rdc_file),
                    output_path=str(xml_output),
                    renderdoccmd="/usr/bin/renderdoccmd"
                )
                
                assert result == str(xml_output)
                mock_run.assert_called_once()
                
                # Verify command structure
                call_args = mock_run.call_args[0][0]
                assert "convert" in call_args
                assert "-c" in call_args
                assert "xml" in call_args


class TestLoadCaptureFile:
    """Tests for load_capture_file function."""
    
    def test_unsupported_extension(self, tmp_path):
        """Test error for unsupported file types."""
        bad_file = tmp_path / "test.txt"
        bad_file.write_text("dummy")
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_capture_file(str(bad_file))
    
    def test_file_not_found(self):
        """Test error for missing files."""
        with pytest.raises(FileNotFoundError):
            load_capture_file("nonexistent.json")
    
    def test_load_json_file(self, tmp_path):
        """Test loading a JSON file."""
        import json
        
        json_file = tmp_path / "test.json"
        data = {
            "summary": {"draw_call_count": 10},
            "statistics": {"totalDrawCalls": 10},
            "textures": [],
            "buffers": [],
        }
        json_file.write_text(json.dumps(data))
        
        result = load_capture_file(str(json_file))
        
        assert result["summary"]["draw_call_count"] == 10
    
    def test_load_xml_file(self, tmp_path):
        """Test loading an XML file directly."""
        # Create a minimal valid XML matching RenderDoc's actual format
        xml_content = '''<?xml version="1.0"?>
        <rdc version="1">
            <header>
                <driver>D3D11</driver>
                <machineIdent>TestMachine</machineIdent>
            </header>
            <chunks>
                <chunk name="ID3D11DeviceContext::DrawIndexed" chunkIndex="100">
                    <IndexCount>300</IndexCount>
                    <StartIndexLocation>0</StartIndexLocation>
                    <BaseVertexLocation>0</BaseVertexLocation>
                </chunk>
            </chunks>
        </rdc>
        '''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)
        
        result = load_capture_file(str(xml_file))
        
        assert result["summary"]["driver"] == "D3D11"
        assert result["summary"]["draw_call_count"] == 1

    def test_load_rdc_prefers_analyze_pipeline(self, tmp_path):
        """RDC 文件优先走 analyze canonical 路径（可用时）"""
        rdc_file = tmp_path / "test.rdc"
        rdc_file.write_bytes(b"dummy rdc")

        sentinel = {"textures": [], "buffers": [], "shaders": [], "events": [], "statistics": {}}

        with patch('rdc_analyzer.parsers.rdc_loader._load_rdc_via_analyze') as mock_analyze:
            with patch('rdc_analyzer.parsers.rdc_loader.load_rdc_file') as mock_xml:
                mock_analyze.return_value = sentinel

                result = load_capture_file(str(rdc_file))

                assert result == sentinel
                mock_analyze.assert_called_once()
                mock_xml.assert_not_called()


class TestIntegration:
    """Integration tests (require renderdoccmd)."""
    
    @pytest.fixture
    def renderdoccmd_available(self):
        """Check if renderdoccmd is available."""
        cmd = find_renderdoccmd()
        if not cmd:
            pytest.skip("renderdoccmd not available")
        return cmd
    
    @pytest.fixture
    def sample_rdc_file(self):
        """Path to a sample RDC file for testing."""
        # Check environment variable first
        env_file = os.environ.get("RDC_TEST_FILE", "")
        if env_file and Path(env_file).is_file():
            return env_file
        
        # Check common locations
        candidates = [
            Path(__file__).parent.parent / "test_data" / "sample.rdc",
            Path(__file__).parent.parent.parent / "test_data" / "sample.rdc",
        ]
        
        for path in candidates:
            if path.is_file():
                return str(path)
        
        pytest.skip("No sample RDC file available")
    
    def test_real_rdc_conversion(self, renderdoccmd_available, sample_rdc_file):
        """Test conversion of a real RDC file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_output = Path(tmpdir) / "output.xml"
            
            result = convert_rdc_to_xml(
                sample_rdc_file,
                output_path=str(xml_output),
                renderdoccmd=renderdoccmd_available
            )
            
            assert Path(result).exists()
            assert Path(result).stat().st_size > 0
    
    def test_real_rdc_loading(self, renderdoccmd_available, sample_rdc_file):
        """Test full loading of a real RDC file."""
        result = load_rdc_file(
            sample_rdc_file,
            renderdoccmd=renderdoccmd_available,
            verbose=False
        )
        
        assert "summary" in result
        assert "statistics" in result
        assert "draw_calls" in result
        assert result["summary"]["draw_call_count"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
