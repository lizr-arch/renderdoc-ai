"""
M1.2 ResourceUsageBuilder 验证脚本

验证 ResourceUsageBuilder 能正确从模拟的 ParsedData 中构建索引。
"""
import sys
sys.path.insert(0, '.')

from dataclasses import dataclass, field
from typing import List, Dict, Any


# 模拟 ParsedData 的最小结构
@dataclass
class MockParsedData:
    draws: List[Any] = field(default_factory=list)
    dispatches: List[Any] = field(default_factory=list)
    textures: List[Any] = field(default_factory=list)
    shaders: List[Any] = field(default_factory=list)
    render_passes: List[Any] = field(default_factory=list)


def test_basic_draw_processing():
    """测试基本 Draw 处理"""
    from core.resource_usage_builder import ResourceUsageBuilder
    
    data = MockParsedData(
        draws=[
            {
                'eid': 100,
                'name': 'DrawIndexed',
                'vs_id': '0xVS001',
                'ps_id': '0xPS001',
                'rt_ids': ['0xRT001', '0xRT002'],
                'ds_id': '0xDS001',
            },
            {
                'eid': 200,
                'name': 'DrawIndexedInstanced',
                'vs_id': '0xVS001',  # 复用 VS
                'ps_id': '0xPS002',  # 新 PS
                'rt_ids': ['0xRT001'],
            },
        ],
        textures=[
            {'id': '0xTex001', 'name': 'Albedo_BaseColor.dds', 'format': 'BC7', 'width': 2048, 'height': 2048},
            {'id': '0xTex002', 'name': 'Normal_Detail.dds', 'format': 'BC5', 'width': 1024, 'height': 1024},
        ]
    )
    
    builder = ResourceUsageBuilder()
    index = builder.build(data)
    
    # 验证 Shader 索引
    vs_usages = index.get_shader_usages('0xVS001')
    assert len(vs_usages) == 2, f"Expected 2 VS usages, got {len(vs_usages)}"
    assert vs_usages[0].event_id == 100
    assert vs_usages[1].event_id == 200
    
    ps001_usages = index.get_shader_usages('0xPS001')
    assert len(ps001_usages) == 1
    
    # 验证 RT 索引
    rt_usages = index.get_rt_usages('0xRT001')
    assert len(rt_usages) == 2, f"Expected 2 RT usages, got {len(rt_usages)}"
    
    # 验证 DSV 索引
    ds_usages = index.get_rt_usages('0xDS001')
    assert len(ds_usages) == 1
    assert ds_usages[0].binding_type == 'DSV'
    
    print("✅ test_basic_draw_processing: PASSED")
    print(f"   索引统计: {index.get_statistics()}")
    return True


def test_texture_binding_extraction():
    """测试纹理绑定提取"""
    from core.resource_usage_builder import ResourceUsageBuilder
    
    data = MockParsedData(
        draws=[
            {
                'eid': 100,
                'name': 'DrawIndexed',
                'vs_id': 'VS',
                'ps_id': 'PS',
                'pipelineState': {
                    'shaderResources': {
                        'ps': [
                            {'resourceId': '0xTex001', 'slot': 0},
                            {'resourceId': '0xTex002', 'slot': 1},
                        ]
                    }
                }
            },
        ],
        textures=[
            {'id': '0xTex001', 'name': 'Albedo_Diffuse.dds', 'format': 'BC7'},
            {'id': '0xTex002', 'name': 'Normal_Map.dds', 'format': 'BC5'},
        ]
    )
    
    builder = ResourceUsageBuilder()
    index = builder.build(data)
    
    # 验证纹理索引
    tex1_usages = index.get_texture_usages('0xTex001')
    assert len(tex1_usages) == 1
    assert tex1_usages[0].slot == 0
    assert tex1_usages[0].purpose_hint == 'Albedo'  # 名称推测
    
    tex2_usages = index.get_texture_usages('0xTex002')
    assert len(tex2_usages) == 1
    assert tex2_usages[0].purpose_hint == 'Normal'  # 名称推测
    
    print("✅ test_texture_binding_extraction: PASSED")
    print(f"   纹理1用途: {tex1_usages[0].purpose_hint}")
    print(f"   纹理2用途: {tex2_usages[0].purpose_hint}")
    return True


def test_purpose_hinter():
    """测试用途推测器"""
    from core.resource_usage_builder import PurposeHinter
    
    tests = [
        # (name, format, expected)
        ('Albedo_BaseColor.dds', '', 'Albedo'),
        ('Normal_Detail.png', '', 'Normal'),
        ('', 'BC5', 'Normal'),
        ('', 'D24S8', 'Depth'),
        ('shadowmap_cascade0', '', 'Shadow'),
        ('gbuffer_normal', '', 'Normal'),  # normal 优先级更高
        ('env_cubemap', '', 'Environment'),
        ('', '', ''),  # 无法推测
    ]
    
    for name, fmt, expected in tests:
        result = PurposeHinter.guess_purpose(name=name, format_str=fmt)
        if result != expected:
            print(f"❌ PurposeHinter: '{name}' + '{fmt}' => '{result}', expected '{expected}'")
            return False
    
    # 测试 is_render_target 优先级
    result = PurposeHinter.guess_purpose(name='albedo', is_render_target=True)
    assert result == 'RenderTarget', f"Expected RenderTarget, got {result}"
    
    print("✅ test_purpose_hinter: PASSED (all 8 cases)")
    return True


def test_pass_name_mapping():
    """测试 Pass 名称映射"""
    from core.resource_usage_builder import ResourceUsageBuilder
    
    data = MockParsedData(
        draws=[
            {'eid': 100, 'name': 'Draw', 'vs_id': 'VS1'},
            {'eid': 150, 'name': 'Draw', 'vs_id': 'VS2'},
            {'eid': 300, 'name': 'Draw', 'vs_id': 'VS3'},
        ],
        render_passes=[
            {'start_event_id': 100, 'end_event_id': 200, 'name': 'GBuffer Pass'},
            {'start_event_id': 250, 'end_event_id': 400, 'name': 'Lighting Pass'},
        ]
    )
    
    builder = ResourceUsageBuilder()
    index = builder.build(data)
    
    vs1_usages = index.get_shader_usages('VS1')
    assert vs1_usages[0].pass_name == 'GBuffer Pass'
    
    vs2_usages = index.get_shader_usages('VS2')
    assert vs2_usages[0].pass_name == 'GBuffer Pass'
    
    vs3_usages = index.get_shader_usages('VS3')
    assert vs3_usages[0].pass_name == 'Lighting Pass'
    
    print("✅ test_pass_name_mapping: PASSED")
    return True


def test_dispatch_processing():
    """测试 Dispatch 处理"""
    from core.resource_usage_builder import ResourceUsageBuilder
    
    data = MockParsedData(
        dispatches=[
            {
                'eid': 500,
                'name': 'Dispatch',
                'cs_id': '0xCS001',
                'pipelineState': {
                    'uavs': [
                        {'resourceId': '0xUAV001', 'slot': 0},
                    ]
                }
            },
        ]
    )
    
    builder = ResourceUsageBuilder()
    index = builder.build(data)
    
    cs_usages = index.get_shader_usages('0xCS001')
    assert len(cs_usages) == 1
    assert cs_usages[0].binding_type == 'CS'
    
    uav_usages = index.get_texture_usages('0xUAV001')
    assert len(uav_usages) == 1
    assert uav_usages[0].binding_type == 'UAV'
    
    print("✅ test_dispatch_processing: PASSED")
    return True


def test_get_all_usages():
    """测试 get_all_usages 跨类型查询"""
    from core.resource_usage_builder import ResourceUsageBuilder
    
    data = MockParsedData(
        draws=[
            {
                'eid': 100,
                'name': 'Draw',
                'vs_id': '0xRES',  # 同一个 ID 作为 Shader
                'pipelineState': {
                    'shaderResources': {'ps': [{'resourceId': '0xRES', 'slot': 0}]}  # 也作为纹理
                }
            },
        ]
    )
    
    builder = ResourceUsageBuilder()
    index = builder.build(data)
    
    all_usages = index.get_all_usages('0xRES')
    assert len(all_usages) == 2, f"Expected 2 usages (shader + texture), got {len(all_usages)}"
    
    print("✅ test_get_all_usages: PASSED")
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("M1.2 ResourceUsageBuilder 验证")
    print("=" * 60)
    
    tests = [
        test_purpose_hinter,
        test_basic_draw_processing,
        test_texture_binding_extraction,
        test_pass_name_mapping,
        test_dispatch_processing,
        test_get_all_usages,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            import traceback
            print(f"❌ {test.__name__} 失败: {e}")
            traceback.print_exc()
    
    print("=" * 60)
    print(f"结果: {passed}/{len(tests)} 测试通过")
    print("=" * 60)
    
    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
