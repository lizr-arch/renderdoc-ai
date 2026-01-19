#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XMLToContextBridge 独立测试脚本
================================

直接运行测试，不依赖 pytest 框架以避免包导入问题。

TASK-007 测试
Created: 2026-01-19
"""

import sys
from pathlib import Path

# 确保可以导入 core 模块（绕过 rdc_analyzer 包级导入问题）
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

# 直接从 core 子模块导入
from core.bridge import XMLToContextBridge
from core.context import AnalysisContext
from core.types import DrawCallInfo, TextureInfo, BufferInfo, FrameSummary


def test_convert_empty_data():
    """测试空数据转换"""
    xml_data = {}
    context = XMLToContextBridge.convert(xml_data)
    
    assert isinstance(context, AnalysisContext)
    assert context.api == 'Unknown'
    assert context.draw_calls == []
    assert context.textures == []
    assert context.buffers == []
    print("[PASS] test_convert_empty_data")


def test_convert_basic_metadata():
    """测试基础元数据转换"""
    xml_data = {
        'apiType': 'D3D11',
        'events': [],
        'textures': [],
        'buffers': [],
    }
    
    context = XMLToContextBridge.convert(xml_data, file_path='/test/capture.xml')
    
    assert context.api == 'D3D11'
    assert context.file_path == '/test/capture.xml'
    print("[PASS] test_convert_basic_metadata")


def test_convert_draw_calls_d3d11():
    """测试 D3D11 Draw Call 转换"""
    xml_data = {
        'apiType': 'D3D11',
        'events': [
            {
                'eventId': 100,
                'name': 'DrawIndexed',
                'params': {
                    'IndexCount': 3600,
                    'StartIndexLocation': 0,
                    'BaseVertexLocation': 0,
                },
                'pipelineState': {
                    'shaders': {
                        'VS': {'resourceId': '0x1234'},
                        'PS': {'resourceId': '0x5678'},
                    },
                    'outputMerger': {
                        'renderTargets': [
                            {'resourceId': '0xRT01'},
                        ],
                        'depthStencilView': {'resourceId': '0xDS01'},
                        'blendState': {
                            'renderTargets': [
                                {'blendEnable': True}
                            ]
                        },
                        'depthStencilState': {
                            'depthEnable': True,
                            'depthWriteMask': 'All',
                        }
                    },
                    'rasterizerState': {
                        'cullMode': 'Back',
                        'fillMode': 'Solid',
                    }
                }
            },
            {
                'eventId': 101,
                'name': 'IASetVertexBuffers',  # 非 Draw Call，应被跳过
                'params': {},
            }
        ],
        'textures': [],
        'buffers': [],
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    # 应只有 1 个 Draw Call
    assert len(context.draw_calls) == 1
    
    dc = context.draw_calls[0]
    assert dc.event_id == 100
    assert dc.type == 'DrawIndexed'
    assert dc.index_count == 3600
    assert dc.vertex_count == 3600  # 从 index_count 推断
    assert dc.vs_id == '0x1234'
    assert dc.ps_id == '0x5678'
    assert dc.rt_ids == ['0xRT01']
    assert dc.ds_id == '0xDS01'
    assert dc.blend_enabled == True
    assert dc.depth_test == True
    assert dc.cull_mode == 'back'
    print("[PASS] test_convert_draw_calls_d3d11")


def test_convert_draw_calls_vulkan():
    """测试 Vulkan Draw Call 转换"""
    xml_data = {
        'apiType': 'Vulkan',
        'events': [
            {
                'eventId': 50,
                'name': 'vkCmdDrawIndexed',
                'params': {
                    'indexCount': 1200,
                    'instanceCount': 5,
                    'IndexCount': 1200,  # 兼容大写
                    'InstanceCount': 5,
                },
                'pipelineState': {
                    'shaders': {
                        'Vertex': {'resourceId': '0xVS'},
                        'Fragment': {'resourceId': '0xFS'},
                    },
                    'framebuffer': {
                        'colorAttachments': [
                            {'imageResourceId': '0xColor0'},
                            {'imageResourceId': '0xColor1'},
                        ],
                        'depthAttachment': {'imageResourceId': '0xDepth'},
                    },
                    'colorBlend': {
                        'attachments': [
                            {'blendEnable': False},
                        ]
                    },
                    'depthStencil': {
                        'depthTestEnable': True,
                        'depthWriteEnable': False,
                    }
                }
            }
        ],
        'textures': [],
        'buffers': [],
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    assert len(context.draw_calls) == 1
    
    dc = context.draw_calls[0]
    assert dc.event_id == 50
    assert dc.type == 'vkCmdDrawIndexed'
    assert dc.index_count == 1200
    assert dc.instance_count == 5
    assert dc.vs_id == '0xVS'
    assert dc.ps_id == '0xFS'
    assert dc.rt_ids == ['0xColor0', '0xColor1']
    assert dc.ds_id == '0xDepth'
    assert dc.blend_enabled == False
    assert dc.depth_write == False
    print("[PASS] test_convert_draw_calls_vulkan")


def test_convert_textures():
    """测试纹理转换"""
    xml_data = {
        'apiType': 'D3D11',
        'events': [],
        'textures': [
            {
                'resourceId': '0xTex01',
                'name': 'Diffuse Texture',
                'width': 2048,
                'height': 2048,
                'format': 'BC3_UNORM',
                'mipLevels': 11,
                'arraySize': 1,
            },
            {
                'resourceId': '0xTex02',
                'name': 'Depth Buffer',
                'width': 1920,
                'height': 1080,
                'format': 'D24_UNORM_S8_UINT',
                'mipLevels': 1,
            },
        ],
        'buffers': [],
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    assert len(context.textures) == 2
    
    # 检查压缩纹理
    tex1 = context.textures[0]
    assert tex1.resource_id == '0xTex01'
    assert tex1.name == 'Diffuse Texture'
    assert tex1.width == 2048
    assert tex1.height == 2048
    assert tex1.format == 'BC3_UNORM'
    assert tex1.format_category == 'compressed'
    assert tex1.mip_levels == 11
    assert tex1.memory_size > 0
    
    # 检查深度纹理
    tex2 = context.textures[1]
    assert tex2.format_category == 'depth'
    print("[PASS] test_convert_textures")


def test_convert_buffers():
    """测试缓冲区转换"""
    xml_data = {
        'apiType': 'D3D11',
        'events': [],
        'textures': [],
        'buffers': [
            {
                'resourceId': '0xBuf01',
                'name': 'Vertex Buffer',
                'size': 65536,
                'stride': 32,
                'usage': ['VertexBuffer'],
            },
            {
                'resourceId': '0xBuf02',
                'name': 'Constant Buffer',
                'size': 256,
                'usage': ['ConstantBuffer', 'Dynamic'],
                'cpuAccess': 'Write',
            },
        ],
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    assert len(context.buffers) == 2
    
    buf1 = context.buffers[0]
    assert buf1.resource_id == '0xBuf01'
    assert buf1.size == 65536
    assert buf1.stride == 32
    assert buf1.is_constant_buffer == False
    
    buf2 = context.buffers[1]
    assert buf2.is_constant_buffer == True
    assert buf2.is_dynamic == True
    print("[PASS] test_convert_buffers")


def test_convert_statistics():
    """测试统计数据转换"""
    xml_data = {
        'apiType': 'D3D11',
        'events': [
            {'eventId': 1, 'name': 'DrawIndexed', 'params': {'IndexCount': 100}},
            {'eventId': 2, 'name': 'DrawIndexed', 'params': {'IndexCount': 200}},
            {'eventId': 3, 'name': 'Dispatch', 'params': {}},
        ],
        'textures': [
            {'resourceId': '0x1', 'width': 256, 'height': 256, 'format': 'R8G8B8A8'},
        ],
        'buffers': [
            {'resourceId': '0x2', 'size': 1024},
        ],
        'statistics': {
            'totalDrawCalls': 2,
            'dispatchCalls': 1,
        },
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    assert context.frame_summary.draw_call_count == 2
    assert context.frame_summary.dispatch_count == 1
    assert context.frame_summary.vertex_count == 300  # 100 + 200
    assert context.frame_summary.texture_count == 1
    assert context.frame_summary.buffer_count == 1
    print("[PASS] test_convert_statistics")


def test_is_draw_call_detection():
    """测试 Draw Call 类型检测"""
    bridge = XMLToContextBridge
    
    # D3D11
    assert bridge._is_draw_call('DrawIndexed') == True
    assert bridge._is_draw_call('DrawIndexedInstanced') == True
    assert bridge._is_draw_call('Draw') == True
    
    # Vulkan
    assert bridge._is_draw_call('vkCmdDraw') == True
    assert bridge._is_draw_call('vkCmdDrawIndexed') == True
    
    # OpenGL
    assert bridge._is_draw_call('glDrawElements') == True
    assert bridge._is_draw_call('glDrawArrays') == True
    
    # 非 Draw Call
    assert bridge._is_draw_call('IASetVertexBuffers') == False
    assert bridge._is_draw_call('vkCmdBindPipeline') == False
    assert bridge._is_draw_call('ClearRenderTargetView') == False
    print("[PASS] test_is_draw_call_detection")


def test_texture_format_categorization():
    """测试纹理格式分类"""
    bridge = XMLToContextBridge
    
    # 压缩格式
    assert bridge._categorize_texture_format('BC1_UNORM') == 'compressed'
    assert bridge._categorize_texture_format('BC3_UNORM_SRGB') == 'compressed'
    assert bridge._categorize_texture_format('DXT5') == 'compressed'
    assert bridge._categorize_texture_format('ASTC_4x4') == 'compressed'
    
    # 深度格式
    assert bridge._categorize_texture_format('D24_UNORM_S8_UINT') == 'depth'
    assert bridge._categorize_texture_format('D32_FLOAT') == 'depth'
    assert bridge._categorize_texture_format('DEPTH24_STENCIL8') == 'depth'
    
    # 未压缩
    assert bridge._categorize_texture_format('R8G8B8A8_UNORM') == 'uncompressed'
    assert bridge._categorize_texture_format('R32G32B32A32_FLOAT') == 'uncompressed'
    print("[PASS] test_texture_format_categorization")


def test_state_change_counting():
    """测试状态变更计数"""
    draw_calls = [
        DrawCallInfo(event_id=1, vs_id='A', ps_id='1'),
        DrawCallInfo(event_id=2, vs_id='A', ps_id='1'),  # 无变化
        DrawCallInfo(event_id=3, vs_id='B', ps_id='1'),  # vs 变化
        DrawCallInfo(event_id=4, vs_id='B', ps_id='2'),  # ps 变化
    ]
    
    changes = XMLToContextBridge._count_state_changes(draw_calls, 'vs_id', 'ps_id')
    assert changes == 2  # 事件3和事件4各有一次变化
    print("[PASS] test_state_change_counting")


def test_missing_pipeline_state():
    """测试缺少 pipeline state 的情况"""
    xml_data = {
        'apiType': 'D3D11',
        'events': [
            {
                'eventId': 1,
                'name': 'DrawIndexed',
                'params': {'IndexCount': 100},
                # 无 pipelineState
            }
        ],
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    assert len(context.draw_calls) == 1
    dc = context.draw_calls[0]
    assert dc.vs_id == ''
    assert dc.ps_id == ''
    assert dc.rt_ids == []
    print("[PASS] test_missing_pipeline_state")


def test_parsed_data_preservation():
    """测试原始数据保留"""
    xml_data = {
        'apiType': 'Vulkan',
        'events': [
            {'eventId': 1, 'name': 'vkCmdDrawIndexed', 'params': {}},
            {'eventId': 2, 'name': 'vkCmdBindPipeline', 'params': {}},
            {'eventId': 3, 'name': 'vkCmdDispatch', 'params': {}},
        ],
        'textures': [{'resourceId': '0x1'}],
        'buffers': [{'resourceId': '0x2'}],
    }
    
    context = XMLToContextBridge.convert(xml_data)
    
    # parsed 应保留原始数据
    assert context.parsed.api == 'Vulkan'
    assert context.parsed.total_events == 3
    assert len(context.parsed.draws) == 1  # 只有 draw
    assert len(context.parsed.dispatches) == 1  # 只有 dispatch
    assert len(context.parsed.textures) == 1
    assert len(context.parsed.buffers) == 1
    print("[PASS] test_parsed_data_preservation")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("XMLToContextBridge 单元测试")
    print("=" * 60)
    
    tests = [
        test_convert_empty_data,
        test_convert_basic_metadata,
        test_convert_draw_calls_d3d11,
        test_convert_draw_calls_vulkan,
        test_convert_textures,
        test_convert_buffers,
        test_convert_statistics,
        test_is_draw_call_detection,
        test_texture_format_categorization,
        test_state_change_counting,
        test_missing_pipeline_state,
        test_parsed_data_preservation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"测试完成: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
