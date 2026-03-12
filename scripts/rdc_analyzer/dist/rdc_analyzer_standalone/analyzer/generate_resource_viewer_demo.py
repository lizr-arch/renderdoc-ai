# -*- coding: utf-8 -*-
"""
生成带资源查看功能的测试 HTML 报告
=================================

此脚本生成一个完整的 HTML 报告，包含：
- 资源生命周期数据
- 资源样本数据（模拟数据用于演示）
- 可点击的资源链接
- 资源详情模态框
"""

import sys
import os
import json
import struct

# 添加模块路径 - 需要将父目录加入以支持包导入
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# 直接导入 html_exporter 模块而不是通过包
sys.path.insert(0, os.path.join(script_dir, 'exporters'))
from html_exporter import HTMLExporter, HTMLExportConfig

def generate_mock_resource_samples():
    """生成模拟的资源样本数据"""
    samples = {}
    
    # 模拟 Vertex Buffer (Resource 1001)
    vertex_data = []
    for i in range(20):
        vertex_data.append({
            'index': i,
            'POSITION': [float(i), float(i*2), float(i*3)],
            'NORMAL': [0.0, 1.0, 0.0],
            'TEXCOORD': [float(i)/20, float(i)/20]
        })
    
    # 生成对应的字节数据
    vertex_bytes = []
    for v in vertex_data:
        # Position (3 floats)
        for f in v['POSITION']:
            vertex_bytes.extend(list(struct.pack('<f', f)))
        # Normal (3 floats)
        for f in v['NORMAL']:
            vertex_bytes.extend(list(struct.pack('<f', f)))
        # TexCoord (2 floats)
        for f in v['TEXCOORD']:
            vertex_bytes.extend(list(struct.pack('<f', f)))
    
    samples[1001] = {
        'type': 'VERTEX_BUFFER',
        'size': len(vertex_bytes),
        'stride': 32,
        'layout': [
            {'name': 'POSITION', 'format': 'R32G32B32_FLOAT', 'offset': 0},
            {'name': 'NORMAL', 'format': 'R32G32B32_FLOAT', 'offset': 12},
            {'name': 'TEXCOORD', 'format': 'R32G32_FLOAT', 'offset': 24}
        ],
        'vertices': vertex_data[:10],  # 只显示前10个
        'vertex_count': 20,
        'bytes': vertex_bytes[:256]  # 前256字节用于hex dump
    }
    
    # 模拟 Index Buffer (Resource 1002)
    index_data = []
    for i in range(0, 60, 3):
        index_data.extend([i, i+1, i+2])
    
    index_bytes = []
    for idx in index_data:
        index_bytes.extend(list(struct.pack('<H', idx)))
    
    samples[1002] = {
        'type': 'INDEX_BUFFER',
        'size': len(index_bytes),
        'format': 'R16_UINT',
        'indices': index_data[:30],  # 只显示前30个
        'index_count': len(index_data),
        'bytes': index_bytes[:128]
    }
    
    # 模拟 Constant Buffer (Resource 2001)
    identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
    cb_bytes = []
    for f in identity:
        cb_bytes.extend(list(struct.pack('<f', float(f))))
    # 添加颜色
    for f in [1.0, 0.5, 0.2, 1.0]:
        cb_bytes.extend(list(struct.pack('<f', f)))
    
    samples[2001] = {
        'type': 'CONSTANT_BUFFER',
        'size': len(cb_bytes),
        'constants': {
            'WorldMatrix': [[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]],
            'DiffuseColor': [1.0, 0.5, 0.2, 1.0]
        },
        'layout': [
            {'name': 'WorldMatrix', 'type': 'float4x4', 'offset': 0},
            {'name': 'DiffuseColor', 'type': 'float4', 'offset': 64}
        ],
        'bytes': cb_bytes
    }
    
    # 模拟 Texture (Resource 3001)
    samples[3001] = {
        'type': 'TEXTURE_2D',
        'width': 1024,
        'height': 1024,
        'format': 'R8G8B8A8_UNORM',
        'mip_levels': 10,
        'size': 1024 * 1024 * 4,
        'preview_url': None,  # 可以是 base64 编码的小预览图
        'bytes': list(range(256))  # 模拟前256字节
    }
    
    return samples


def generate_mock_resource_lifetimes():
    """生成模拟的资源生命周期数据"""
    return [
        {
            'resource_id': 1001,
            'resource_name': 'VB_MainCharacter',
            'resource_type': 'BUFFER',
            'first_access_event': 10,
            'last_access_event': 500,
            'read_count': 45,
            'write_count': 1,
            'accesses': [
                {'event_id': 10, 'access_type': 'Write', 'usage': 'CreateBuffer'},
                {'event_id': 50, 'access_type': 'Read', 'usage': 'IA VertexBuffer'},
                {'event_id': 120, 'access_type': 'Read', 'usage': 'IA VertexBuffer'},
                {'event_id': 250, 'access_type': 'Read', 'usage': 'IA VertexBuffer'},
                {'event_id': 400, 'access_type': 'Read', 'usage': 'IA VertexBuffer'},
            ]
        },
        {
            'resource_id': 1002,
            'resource_name': 'IB_MainCharacter',
            'resource_type': 'BUFFER',
            'first_access_event': 10,
            'last_access_event': 500,
            'read_count': 45,
            'write_count': 1,
            'accesses': [
                {'event_id': 10, 'access_type': 'Write', 'usage': 'CreateBuffer'},
                {'event_id': 50, 'access_type': 'Read', 'usage': 'IA IndexBuffer'},
            ]
        },
        {
            'resource_id': 2001,
            'resource_name': 'CB_PerObject',
            'resource_type': 'BUFFER',
            'first_access_event': 20,
            'last_access_event': 520,
            'read_count': 200,
            'write_count': 50,
            'accesses': [
                {'event_id': 20, 'access_type': 'Write', 'usage': 'UpdateBuffer'},
                {'event_id': 50, 'access_type': 'Read', 'usage': 'VS ConstantBuffer'},
            ]
        },
        {
            'resource_id': 3001,
            'resource_name': 'Tex_Diffuse',
            'resource_type': 'TEXTURE',
            'first_access_event': 5,
            'last_access_event': 520,
            'read_count': 100,
            'write_count': 0,
            'accesses': [
                {'event_id': 5, 'access_type': 'Read', 'usage': 'CreateTexture2D'},
                {'event_id': 50, 'access_type': 'Read', 'usage': 'PS SRV'},
            ]
        },
        {
            'resource_id': 4001,
            'resource_name': 'RT_GBuffer_Albedo',
            'resource_type': 'TEXTURE',
            'first_access_event': 100,
            'last_access_event': 450,
            'read_count': 10,
            'write_count': 5,
            'accesses': [
                {'event_id': 100, 'access_type': 'Write', 'usage': 'OM RenderTarget'},
                {'event_id': 300, 'access_type': 'Read', 'usage': 'PS SRV'},
            ]
        },
    ]


def generate_mock_draw_calls():
    """生成模拟的 Draw Call 数据"""
    draw_calls = []
    
    for i in range(20):
        event_id = 50 + i * 25
        draw_calls.append({
            'event_id': event_id,
            'name': f'DrawIndexed({100+i*50})',
            'draw_type': 'DrawIndexed',
            'vertex_count': 100 + i * 50,
            'instance_count': 1,
            'issues': [],
            'pipeline_state': {
                'input_assembly': {
                    'topology': 'TriangleList',
                    'vertex_buffers': [
                        {'slot': 0, 'resource_id': 1001, 'stride': 32, 'size_bytes': 640}
                    ],
                    'index_buffer': {
                        'resource_id': 1002,
                        'format': 'R16_UINT',
                        'size_bytes': 120
                    }
                },
                'shaders': {
                    'vs': {'name': 'MainVS', 'resource_id': 5001},
                    'ps': {'name': 'MainPS', 'resource_id': 5002}
                },
                'rasterizer': {
                    'fill_mode': 'Solid',
                    'cull_mode': 'Back',
                    'front_ccw': False,
                    'scissor_enabled': False
                },
                'output_merger': {
                    'render_targets': [
                        {'slot': 0, 'resource_id': 4001, 'format': 'R8G8B8A8_UNORM'}
                    ],
                    'depth_stencil': {
                        'resource_id': 4002,
                        'format': 'D24_UNORM_S8_UINT'
                    }
                }
            }
        })
    
    return draw_calls


def generate_mock_dependencies():
    """生成模拟的资源依赖数据"""
    return [
        {'source_event': 50, 'target_event': 120, 'resource_id': 1001, 'resource_name': 'VB_MainCharacter'},
        {'source_event': 50, 'target_event': 120, 'resource_id': 1002, 'resource_name': 'IB_MainCharacter'},
        {'source_event': 120, 'target_event': 250, 'resource_id': 1001, 'resource_name': 'VB_MainCharacter'},
        {'source_event': 100, 'target_event': 300, 'resource_id': 4001, 'resource_name': 'RT_GBuffer_Albedo'},
    ]


def main():
    """主函数 - 生成测试 HTML"""
    
    print("="*60)
    print("生成带资源查看功能的 HTML 报告")
    print("="*60)
    
    # 准备数据
    analysis_data = {
        'frame_info': {
            'capture_file': 'demo_capture.rdc',
            'api': 'D3D11',
            'resolution': '1920x1080'
        },
        'draw_calls': generate_mock_draw_calls(),
        'issues': [],
        'resource_lifetimes': generate_mock_resource_lifetimes(),
        'resource_dependencies': generate_mock_dependencies(),
        'resource_samples': generate_mock_resource_samples()  # 这是关键！
    }
    
    # 统计
    stats = {
        'total_draws': len(analysis_data['draw_calls']),
        'total_issues': 0,
        'total_resources': len(analysis_data['resource_lifetimes']),
        'vertex_count': sum(d['vertex_count'] for d in analysis_data['draw_calls'])
    }
    analysis_data['statistics'] = stats
    
    print(f"  Draw Calls: {stats['total_draws']}")
    print(f"  Resources: {stats['total_resources']}")
    print(f"  Resource Samples: {len(analysis_data['resource_samples'])}")
    
    # 使用 HTMLExporter 生成报告
    config = HTMLExportConfig(
        title="RDC Analyzer - Resource Viewer Demo",
        theme="dark",
        include_dependency_graph=True,
        include_timeline=True
    )
    
    exporter = HTMLExporter(config)
    
    # 输出路径
    output_path = os.path.join(script_dir, '..', 'resource_viewer_demo.html')
    output_path = os.path.abspath(output_path)
    
    try:
        exporter.export(analysis_data, output_path)
        print(f"\n[OK] HTML 报告已生成: {output_path}")
        print("\n提示: 在浏览器中打开此文件，然后：")
        print("  1. 点击 'Resources' 标签查看资源列表")
        print("  2. 点击任意资源名称打开详情模态框")
        print("  3. 在模态框中切换 Structured/Hex/Raw 视图")
        
        return output_path
        
    except Exception as e:
        print(f"\n[ERROR] 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    output = main()
    if output:
        # 尝试在浏览器中打开
        import webbrowser
        print(f"\n正在打开浏览器...")
        webbrowser.open(f'file:///{output}')