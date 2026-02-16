#!/usr/bin/env python3
"""Tests for Schema v1.0 to CaptureData bridge conversion.

Validates that _convert_schema_v1_to_capture_data() correctly transforms
analyze command output (schema v1.0) to CaptureData format for comparison.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from parsers.rdc_loader import _convert_schema_v1_to_capture_data

# Import the function directly to avoid chain imports


class TestSchemaV1ToCaptureData:
    """Test suite for schema v1.0 → CaptureData conversion."""
    
    def test_non_v1_data_unchanged(self):
        """Non-v1.0 data should be returned unchanged."""
        data = {
            'textures': [{'id': '1', 'name': 'tex1'}],
            'buffers': [],
        }
        result = _convert_schema_v1_to_capture_data(data)
        assert result == data
    
    def test_v1_with_no_schema_version_unchanged(self):
        """Data without schema_version should be returned unchanged."""
        data = {
            'resources': {'textures': {}},
        }
        result = _convert_schema_v1_to_capture_data(data)
        assert result == data
    
    def test_v1_textures_dict_to_list(self):
        """Schema v1.0 textures dict should convert to list."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {
                    'tex-001': {
                        'name': 'Diffuse',
                        'width': 1024,
                        'height': 1024,
                        'format': 'RGBA8',
                        'size_bytes': 4194304,
                        'mips': 10,
                    },
                    'tex-002': {
                        'name': 'Normal',
                        'width': 512,
                        'height': 512,
                        'format': 'RG8',
                    }
                },
                'buffers': {},
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        # Check structure
        assert 'textures' in result
        assert isinstance(result['textures'], list)
        assert len(result['textures']) == 2
        
        # Check content
        tex_ids = {t['id'] for t in result['textures']}
        tex_resource_ids = {t['resourceId'] for t in result['textures']}
        assert tex_resource_ids == {'tex-001', 'tex-002'}
        assert tex_ids == {'tex-001', 'tex-002'}
        
        # Check specific texture
        tex1 = next(t for t in result['textures'] if t['id'] == 'tex-001')
        assert tex1['name'] == 'Diffuse'
        assert tex1['width'] == 1024
        assert tex1['height'] == 1024
        assert tex1['format'] == 'RGBA8'
        assert tex1['size_bytes'] == 4194304
        assert tex1['resourceId'] == 'tex-001'
        assert tex1['memorySize'] == 4194304
        assert tex1['mipLevels'] == 10
        assert tex1['mips'] == 10
    
    def test_v1_buffers_dict_to_list(self):
        """Schema v1.0 buffers dict should convert to list."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {},
                'buffers': {
                    'buf-001': {
                        'name': 'VertexBuffer',
                        'size_bytes': 65536,
                        'usage': 'VERTEX',
                    },
                    'buf-002': {
                        'name': 'IndexBuffer',
                        'length': 32768,  # 'length' alias for size_bytes
                        'usage': 'INDEX',
                    }
                },
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        # Check structure
        assert 'buffers' in result
        assert isinstance(result['buffers'], list)
        assert len(result['buffers']) == 2
        buf_resource_ids = {b['resourceId'] for b in result['buffers']}
        assert buf_resource_ids == {'buf-001', 'buf-002'}
        
        # Check specific buffer
        buf1 = next(b for b in result['buffers'] if b['id'] == 'buf-001')
        assert buf1['name'] == 'VertexBuffer'
        assert buf1['resourceId'] == 'buf-001'
        assert buf1['size'] == 65536
        assert buf1['size_bytes'] == 65536
        assert buf1['usage'] == 'VERTEX'
        
        # Check 'length' alias handling
        buf2 = next(b for b in result['buffers'] if b['id'] == 'buf-002')
        assert buf2['size_bytes'] == 32768
        assert buf2['resourceId'] == 'buf-002'
        assert buf2['size'] == 32768
    
    def test_v1_shaders_dict_to_list(self):
        """Schema v1.0 shaders dict should convert to list."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {},
                'buffers': {},
                'shaders': {
                    'shader-vs': {
                        'name': 'VertexShader',
                        'stage': 'VERTEX',
                    },
                    'shader-ps': {
                        'name': 'PixelShader',
                        'stage': 'PIXEL',
                    }
                },
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        # Check structure
        assert 'shaders' in result
        assert isinstance(result['shaders'], list)
        assert len(result['shaders']) == 2
        
        # Check IDs are preserved
        shader_ids = {s['id'] for s in result['shaders']}
        shader_resource_ids = {s['resourceId'] for s in result['shaders']}
        assert shader_resource_ids == {'shader-vs', 'shader-ps'}
        assert shader_ids == {'shader-vs', 'shader-ps'}
    
    def test_v1_empty_resources(self):
        """Schema v1.0 with empty resources should produce empty lists."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {},
                'buffers': {},
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert result['textures'] == []
        assert result['buffers'] == []
        assert result['shaders'] == []
    
    def test_v1_missing_resources(self):
        """Schema v1.0 with missing resources should produce empty lists."""
        data = {
            'schema_version': '1.0',
            # No 'resources' key
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert result['textures'] == []
        assert result['buffers'] == []
    
    def test_v1_summary_to_statistics(self):
        """Schema v1.0 'summary' should map to 'statistics'."""
        data = {
            'schema_version': '1.0',
            'resources': {},
            'summary': {
                'draw_call_count': 100,
                'total_triangles': 50000,
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert 'statistics' in result
        assert result['statistics']['draw_call_count'] == 100
        assert result['statistics']['total_triangles'] == 50000
    
    def test_v1_metadata_preserved(self):
        """Schema v1.0 meta and source info should be preserved."""
        data = {
            'schema_version': '1.0',
            'resources': {},
            'meta': {
                'source_file': 'test.rdc',
                'timestamp': '2025-01-21T10:00:00Z',
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert result['_source_schema'] == '1.0'
        assert result['_meta']['source_file'] == 'test.rdc'
    
    def test_v1_extra_fields_preserved(self):
        """Extra fields in texture/buffer info should be preserved."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {
                    'tex-001': {
                        'name': 'Test',
                        'width': 100,
                        'height': 100,
                        'format': 'RGBA8',
                        'custom_field': 'custom_value',
                        'another_field': 42,
                    }
                },
                'buffers': {},
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        tex = result['textures'][0]
        assert tex['custom_field'] == 'custom_value'
        assert tex['another_field'] == 42
    
    def test_v1_toplevel_fields_copied(self):
        """Top-level fields like passes, pipelines should be copied."""
        data = {
            'schema_version': '1.0',
            'resources': {},
            'passes': [{'name': 'Pass1'}],
            'pipelines': [{'name': 'Pipeline1'}],
            'render_targets': [{'name': 'RT1'}],
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert result['passes'] == [{'name': 'Pass1'}]
        assert result['pipelines'] == [{'name': 'Pipeline1'}]
        assert result['render_targets'] == [{'name': 'RT1'}]
    
    def test_v1_events_preserved(self):
        """Events field should be preserved in output."""
        data = {
            'schema_version': '1.0',
            'resources': {},
            'events': [
                {'id': 1, 'name': 'DrawIndexed'},
                {'id': 2, 'name': 'Dispatch'},
            ]
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert result['events'] == [
            {'id': 1, 'name': 'DrawIndexed'},
            {'id': 2, 'name': 'Dispatch'},
        ]


class TestSchemaV1EdgeCases:
    """Edge case tests for schema v1.0 conversion."""
    
    def test_texture_with_missing_optional_fields(self):
        """Textures with missing optional fields get defaults."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {
                    'tex-001': {}  # Minimal entry
                },
                'buffers': {},
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        tex = result['textures'][0]
        assert tex['id'] == 'tex-001'
        assert tex['resourceId'] == 'tex-001'
        assert tex['memorySize'] == 0
        assert tex['mipLevels'] == 1
        assert tex['name'] == ''
        assert tex['width'] == 0
        assert tex['height'] == 0
        assert tex['format'] == ''
        assert tex['size_bytes'] == 0
        assert tex['mips'] == 1
        assert tex['type'] == 'Texture2D'
    
    def test_buffer_with_missing_optional_fields(self):
        """Buffers with missing optional fields get defaults."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {},
                'buffers': {
                    'buf-001': {}  # Minimal entry
                },
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        buf = result['buffers'][0]
        assert buf['id'] == 'buf-001'
        assert buf['resourceId'] == 'buf-001'
        assert buf['size'] == 0
        assert buf['name'] == ''
        assert buf['size_bytes'] == 0
        assert buf['usage'] == ''
    
    def test_shaders_already_list(self):
        """Shaders that are already a list should be preserved."""
        data = {
            'schema_version': '1.0',
            'resources': {
                'textures': {},
                'buffers': {},
                'shaders': [
                    {'id': 's1', 'name': 'Shader1'},
                ]
            }
        }
        result = _convert_schema_v1_to_capture_data(data)
        
        assert result['shaders'] == [{'id': 's1', 'name': 'Shader1'}]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
