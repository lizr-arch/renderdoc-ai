#!/usr/bin/env python3
"""
验证 ResourceLifetime 数据能否正确传递到 HTML 报告

测试目标：
1. 确认 ResourceLifetime 能正确构建
2. 确认 JSONExporter 能正确序列化 lifetimes
3. 确认 HTMLExporter 能生成包含 lifetimes 的 HTML
"""
import sys
from pathlib import Path

# 添加父目录到路径
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

import json
from rdc_analyzer.analysis.resource_tracker import ResourceLifetime, ResourceType
from rdc_analyzer.exporters.json_exporter import JSONExporter, JSONExportConfig
from rdc_analyzer.exporters.html_exporter import HTMLExporter, HTMLExportConfig


def create_mock_draw_call():
    """创建模拟的 DrawCallDetail 对象"""
    return type('DrawCallDetail', (), {
        'event_id': 1,
        'name': 'DrawIndexed(100)',
        'draw_type': 'DrawIndexed',
        'vertex_count': 100,
        'instance_count': 1,
        'topology': 'TriangleList',
        'start_index': 0,
        'base_vertex': 0,
        'render_targets': [],
        'depth_target': None,
        'pipeline': None,
    })()


def create_mock_lifetimes():
    """创建模拟的 ResourceLifetime 字典"""
    lifetimes = {}
    
    # 纹理资源
    tex1 = ResourceLifetime(
        resource_id=1001,
        resource_name="MainAlbedo",
        resource_type=ResourceType.TEXTURE_2D,
        format="BC3_UNORM",
        width=2048,
        height=2048,
    )
    tex1.first_access_event = 5
    tex1.last_access_event = 100
    tex1.read_count = 10
    tex1.write_count = 0
    lifetimes[1001] = tex1
    
    # 缓冲区资源
    buf1 = ResourceLifetime(
        resource_id=2001,
        resource_name="ConstantBuffer_PerFrame",
        resource_type=ResourceType.BUFFER,
        size_bytes=256,
    )
    buf1.first_access_event = 1
    buf1.last_access_event = 200
    buf1.read_count = 50
    buf1.write_count = 1
    lifetimes[2001] = buf1
    
    # 渲染目标
    rt1 = ResourceLifetime(
        resource_id=3001,
        resource_name="GBuffer_Normal",
        resource_type=ResourceType.RENDER_TARGET,
        format="R16G16B16A16_FLOAT",
        width=1920,
        height=1080,
    )
    rt1.first_access_event = 10
    rt1.last_access_event = 150
    rt1.read_count = 5
    rt1.write_count = 3
    lifetimes[3001] = rt1
    
    return lifetimes


def test_json_export():
    """测试 JSON 导出"""
    print("=" * 60)
    print("测试 1: JSON 导出 ResourceLifetime")
    print("=" * 60)
    
    config = JSONExportConfig(
        include_dependencies=True,
        include_pipeline_state=True,
    )
    exporter = JSONExporter(config)
    
    draws = [create_mock_draw_call()]
    lifetimes = create_mock_lifetimes()
    
    json_str = exporter.export(
        draws=draws,
        issues=[],
        dependencies=[],
        lifetimes=lifetimes,
        source_file="test.rdc",
        api_type="D3D11",
    )
    
    data = json.loads(json_str)
    
    # 验证 resource_lifetimes 存在
    resource_lifetimes = data.get('resource_lifetimes', [])
    print(f"[OK] Exported {len(resource_lifetimes)} resource lifetimes")
    
    for lt in resource_lifetimes:
        print(f"  - {lt['resource_name']} ({lt['resource_type']})")
        print(f"    Events: #{lt['first_access_event']} - #{lt['last_access_event']}")
        print(f"    Reads: {lt['read_count']}, Writes: {lt['write_count']}")
    
    # 验证统计
    stats = data.get('statistics', {})
    print(f"\n[OK] Statistics: total_resources = {stats.get('total_resources', 0)}")
    
    assert len(resource_lifetimes) == 3, f"Expected 3 lifetimes, got {len(resource_lifetimes)}"
    assert stats.get('total_resources') == 3, "Statistics mismatch"
    
    print("\n[PASS] JSON export test passed!")
    return True


def test_html_export():
    """测试 HTML 导出"""
    print("\n" + "=" * 60)
    print("测试 2: HTML 导出 ResourceLifetime")
    print("=" * 60)
    
    config = HTMLExportConfig(
        title="Lifetime Test Report",
        theme="dark",
    )
    exporter = HTMLExporter(config)
    
    draws = [create_mock_draw_call()]
    lifetimes = create_mock_lifetimes()
    
    html_content = exporter.export(
        draws=draws,
        issues=[],
        dependencies=[],
        lifetimes=lifetimes,
        source_file="test.rdc",
        api_type="D3D11",
    )
    
    # 检查 HTML 中是否包含资源名称
    assert "MainAlbedo" in html_content, "Missing texture name in HTML"
    assert "ConstantBuffer_PerFrame" in html_content, "Missing buffer name in HTML"
    assert "GBuffer_Normal" in html_content, "Missing RT name in HTML"
    
    # 检查 HTML 中是否包含生命周期面板
    assert "Resource Lifetime Overview" in html_content, "Missing lifetime overview section"
    
    print("[OK] HTML contains resource names: MainAlbedo, ConstantBuffer_PerFrame, GBuffer_Normal")
    print("[OK] HTML contains Resource Lifetime Overview panel")
    
    # 保存测试输出
    output_path = SCRIPT_DIR / "_test_output_lifetimes.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"[OK] Test HTML saved: {output_path}")
    
    print("\n[PASS] HTML export test passed!")
    return True


def main():
    """运行所有测试"""
    print("ResourceLifetime 集成测试")
    print("=" * 60)
    
    try:
        test_json_export()
        test_html_export()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Runtime error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
