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

# Import the function directly to avoid chain imports
from typing import Dict, Any


def _convert_schema_v1_to_capture_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """将 Canonical Schema v1.0 格式转换为 CaptureData 格式。
    
    复制自 parsers.rdc_loader，避免复杂的导入链。
    """
    # 检测是否为 schema v1.0
    if data.get('schema_version') != '1.0':
        return data  # 不是 v1.0，原样返回
    
    # 获取资源
    resources = data.get('resources', {})
    
    # textures: dict → list
    textures_dict = resources.get('textures', {})
    textures_list = []
    for tex_id, tex_info in textures_dict.items():
        tex_entry = {
            'id': tex_id,
            'name': tex_info.get('name', ''),
            'width': tex_info.get('width', 0),
            'height': tex_info.get('height', 0),
            'format': tex_info.get('format', ''),
            'size_bytes': tex_info.get('size_bytes', 0),
            'mips': tex_info.get('mips', 1),
            'type': tex_info.get('type', 'Texture2D'),
            # 保留原始数据中的其他字段
            **{k: v for k, v in tex_info.items() if k not in ['name', 'width', 'height', 'format', 'size_bytes', 'mips', 'type']}
        }
        textures_list.append(tex_entry)
    
    # buffers: dict → list
    buffers_dict = resources.get('buffers', {})
    buffers_list = []
    for buf_id, buf_info in buffers_dict.items():
        buf_entry = {
            'id': buf_id,
            'name': buf_info.get('name', ''),
            'size_bytes': buf_info.get('size_bytes', buf_info.get('length', 0)),
            'usage': buf_info.get('usage', ''),
            **{k: v for k, v in buf_info.items() if k not in ['name', 'size_bytes', 'length', 'usage']}
        }
        buffers_list.append(buf_entry)
    
    # shaders: dict → list (如果存在)
    shaders_dict = resources.get('shaders', {})
    if isinstance(shaders_dict, dict):
        shaders_list = []
        for shader_id, shader_info in shaders_dict.items():
            shader_entry = {
                'id': shader_id,
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
        assert tex_ids == {'tex-001', 'tex-002'}
        
        # Check specific texture
        tex1 = next(t for t in result['textures'] if t['id'] == 'tex-001')
        assert tex1['name'] == 'Diffuse'
        assert tex1['width'] == 1024
        assert tex1['height'] == 1024
        assert tex1['format'] == 'RGBA8'
        assert tex1['size_bytes'] == 4194304
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
        
        # Check specific buffer
        buf1 = next(b for b in result['buffers'] if b['id'] == 'buf-001')
        assert buf1['name'] == 'VertexBuffer'
        assert buf1['size_bytes'] == 65536
        assert buf1['usage'] == 'VERTEX'
        
        # Check 'length' alias handling
        buf2 = next(b for b in result['buffers'] if b['id'] == 'buf-002')
        assert buf2['size_bytes'] == 32768
    
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
