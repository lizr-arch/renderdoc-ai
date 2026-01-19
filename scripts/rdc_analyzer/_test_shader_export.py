#!/usr/bin/env python3
"""
验证 TASK-P1-02: Draw Call 关联 Shader/Texture 功能

测试 json_exporter 是否正确输出 shaders 和 bound_textures 字段
"""

import sys
import json
from pathlib import Path

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.resolve()

# 把 scripts 目录加入 path，这样 rdc_analyzer 可以作为包被导入
sys.path.insert(0, str(SCRIPT_DIR.parent))

# 现在可以正常导入
from rdc_analyzer.core.pipeline_state import (
    DrawCallDetail, DrawType, PipelineSnapshot, ShaderBindings, ResourceBinding,
    ShaderStage, ResourceType
)
from rdc_analyzer.exporters.json_exporter import JSONExporter, JSONExportConfig


def create_test_draw_call() -> DrawCallDetail:
    """创建带有 Shader 绑定的测试 Draw Call"""
    
    # 创建 Vertex Shader
    vs = ShaderBindings(
        stage=ShaderStage.VERTEX,
        resource_id=1001,
        name="MainVS",
    )
    vs.constant_buffers = [
        ResourceBinding(slot=0, stage=ShaderStage.VERTEX, resource_id=2001, resource_name="ViewProj_CB"),
        ResourceBinding(slot=1, stage=ShaderStage.VERTEX, resource_id=2002, resource_name="Model_CB"),
    ]
    
    # 创建 Pixel Shader
    ps = ShaderBindings(
        stage=ShaderStage.PIXEL,
        resource_id=1002,
        name="MainPS",
    )
    ps.constant_buffers = [
        ResourceBinding(slot=0, stage=ShaderStage.PIXEL, resource_id=2003, resource_name="Material_CB"),
    ]
    ps.shader_resources = [
        ResourceBinding(
            slot=0, stage=ShaderStage.PIXEL, resource_id=3001, 
            resource_name="DiffuseTexture", resource_type=ResourceType.TEXTURE_2D,
            width=1024, height=1024, format="BC7_UNORM"
        ),
        ResourceBinding(
            slot=1, stage=ShaderStage.PIXEL, resource_id=3002,
            resource_name="NormalMap", resource_type=ResourceType.TEXTURE_2D,
            width=512, height=512, format="BC5_UNORM"
        ),
    ]
    
    # 创建 Pipeline Snapshot
    pipeline = PipelineSnapshot(
        vertex_shader=vs,
        pixel_shader=ps,
    )
    
    # 创建 DrawCallDetail
    draw = DrawCallDetail(
        event_id=100,
        name="DrawIndexed",
        draw_type=DrawType.DRAW_INDEXED,
        vertex_count=1000,
        instance_count=1,
        pipeline=pipeline,
    )
    
    return draw


def main():
    print("=" * 60)
    print("TASK-P1-02 Verification: Draw Call Shader/Texture Export")
    print("=" * 60)
    
    # 创建测试数据
    draw = create_test_draw_call()
    draws = [draw]
    
    # 导出
    exporter = JSONExporter(JSONExportConfig(
        include_pipeline_state=True,
        include_shader_details=True,
    ))
    
    json_str = exporter.export(draws, source_file="test.rdc", api_type="D3D11")
    
    data = json.loads(json_str)
    
    # 验证结果
    print("\n[1] Checking draw_calls structure...")
    draw_calls = data.get('draw_calls', [])
    assert len(draw_calls) == 1, f"Expected 1 draw call, got {len(draw_calls)}"
    print(f"    OK: Found {len(draw_calls)} draw call(s)")
    
    dc = draw_calls[0]
    
    print("\n[2] Checking 'shaders' field...")
    shaders = dc.get('shaders', [])
    print(f"    shaders count: {len(shaders)}")
    for s in shaders:
        print(f"      - {s.get('type')}: {s.get('name')} (resource_id={s.get('resource_id')})")
        print(f"        constant_blocks: {len(s.get('constant_blocks', []))}")
        print(f"        read_only_resources: {len(s.get('read_only_resources', []))}")
    
    assert len(shaders) == 2, f"Expected 2 shaders (VS+PS), got {len(shaders)}"
    
    vs_found = any(s['type'] == 'VS' for s in shaders)
    ps_found = any(s['type'] == 'PS' for s in shaders)
    assert vs_found, "VS shader not found"
    assert ps_found, "PS shader not found"
    print("    OK: VS and PS shaders exported correctly")
    
    print("\n[3] Checking 'bound_textures' field...")
    textures = dc.get('bound_textures', [])
    print(f"    bound_textures count: {len(textures)}")
    for t in textures:
        print(f"      - slot {t.get('slot')}: {t.get('name')} ({t.get('width')}x{t.get('height')}, {t.get('format')})")
    
    assert len(textures) == 2, f"Expected 2 textures, got {len(textures)}"
    print("    OK: bound_textures exported correctly")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All verifications passed!")
    print("=" * 60)
    
    # 保存完整 JSON 供查看
    output_path = Path(__file__).parent / "_test_shader_export_result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json_str)
    print(f"\nFull JSON saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)