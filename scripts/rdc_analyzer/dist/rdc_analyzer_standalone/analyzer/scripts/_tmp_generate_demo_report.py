#!/usr/bin/env python3
"""生成演示报告：验证 recommendations.html 新 UI 效果"""

import sys
import os
import json
import shutil
from pathlib import Path

# 设置路径
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

from report_bundle_generator import ReportBundleGenerator

# 输出目录
OUTPUT_DIR = script_dir / "test_captures" / "export_output" / "demo_report"

# 创建丰富的模拟数据
MOCK_TEXTURES = [
    {'id': '1', 'name': 'MainCharacter_Albedo', 'width': 4096, 'height': 4096, 'format': 'R8G8B8A8_UNORM', 'sizeBytes': 67108864},
    {'id': '2', 'name': 'MainCharacter_Normal', 'width': 2048, 'height': 2048, 'format': 'BC5_UNORM', 'sizeBytes': 4194304},
    {'id': '3', 'name': 'Environment_Diffuse', 'width': 2048, 'height': 2048, 'format': 'BC7_UNORM', 'sizeBytes': 8388608},
    {'id': '4', 'name': 'UI_Atlas', 'width': 1024, 'height': 1024, 'format': 'R8G8B8A8_UNORM', 'sizeBytes': 4194304},
    {'id': '5', 'name': 'ShadowMap_Main', 'width': 4096, 'height': 4096, 'format': 'D32_FLOAT', 'sizeBytes': 67108864},
    {'id': '6', 'name': 'PostFX_Bloom', 'width': 1920, 'height': 1080, 'format': 'R16G16B16A16_FLOAT', 'sizeBytes': 16588800},
    {'id': '7', 'name': 'Skybox_HDR', 'width': 2048, 'height': 2048, 'format': 'R32G32B32A32_FLOAT', 'sizeBytes': 67108864},
]

MOCK_EVENTS = [
    {'eventId': i, 'name': f'DrawIndexed', 'type': 'draw', 'drawcallInfo': {'numIndices': 3000 + i * 100}}
    for i in range(1, 201)  # 200 个 Draw Call
] + [
    {'eventId': 201, 'name': 'ClearRenderTargetView', 'type': 'clear'},
    {'eventId': 202, 'name': 'Dispatch', 'type': 'dispatch'},
]

MOCK_SHADERS = [
    {'id': '1', 'name': 'PBR_Standard_VS', 'type': 'vertex', 'stage': 'VS', 'instructionCount': 45},
    {'id': '2', 'name': 'PBR_Standard_PS', 'type': 'pixel', 'stage': 'PS', 'instructionCount': 320},
    {'id': '3', 'name': 'ShadowCaster_VS', 'type': 'vertex', 'stage': 'VS', 'instructionCount': 28},
    {'id': '4', 'name': 'PostFX_Bloom_PS', 'type': 'pixel', 'stage': 'PS', 'instructionCount': 156},
]

# 模拟性能问题（丰富的测试数据）
MOCK_PERFORMANCE = {
    'issues': [
        # 严重问题 (Critical)
        {'severity': 'critical', 'category': 'texture', 'title': '超大纹理 (4K×4K)', 
         'message': 'MainCharacter_Albedo 纹理尺寸为 4096×4096，在移动端会导致严重的内存压力和带宽消耗。', 
         'suggestion': '压缩到 2048×2048；使用 Mipmap；考虑 BC7 压缩格式',
         'rule_id': 'TEX_SIZE_001', 'impact_score': 9, 'resource_id': '1'},
        {'severity': 'critical', 'category': 'texture', 'title': '未压缩 4K 纹理', 
         'message': 'ShadowMap_Main 使用 D32_FLOAT 格式，占用 64MB 显存。', 
         'suggestion': '使用 D24_UNORM_S8_UINT 格式；降低分辨率到 2048',
         'rule_id': 'TEX_FMT_001', 'impact_score': 8, 'resource_id': '5'},
        
        # 警告 (Warning)
        {'severity': 'warning', 'category': 'texture', 'title': 'HDR 格式优化', 
         'message': 'Skybox_HDR 使用 R32G32B32A32_FLOAT (128bpp)，带宽消耗大。', 
         'suggestion': '使用 R16G16B16A16_FLOAT 或 BC6H 压缩',
         'rule_id': 'TEX_FMT_002', 'impact_score': 6, 'resource_id': '7'},
        {'severity': 'warning', 'category': 'drawcall', 'title': 'Draw Call 数量较多', 
         'message': '当前帧有 200 个 Draw Call，超过推荐的 150 个阈值。', 
         'suggestion': '合并静态网格；使用 GPU Instancing；实现批处理',
         'rule_id': 'DC_COUNT_001', 'impact_score': 7},
        {'severity': 'warning', 'category': 'shader', 'title': 'PBR Shader 指令较多', 
         'message': 'PBR_Standard_PS 有 320 条指令，可能在低端设备造成瓶颈。', 
         'suggestion': '拆分为 LOD Shader；减少采样次数；简化光照模型',
         'rule_id': 'SHADER_ALU_001', 'impact_score': 5, 'resource_id': '2'},
        
        # 建议 (Info)
        {'severity': 'info', 'category': 'memory', 'title': '显存使用分析', 
         'message': '当前帧纹理显存占用约 234MB，处于中等水平。', 
         'suggestion': '持续监控；考虑纹理流送',
         'rule_id': 'MEM_INFO_001', 'impact_score': 3},
        {'severity': 'info', 'category': 'bandwidth', 'title': '带宽使用提示', 
         'message': 'PostFX_Bloom 每帧读写 16MB 数据，建议优化后处理链。', 
         'suggestion': '使用半分辨率渲染；合并后处理 Pass',
         'rule_id': 'BW_INFO_001', 'impact_score': 4},
        {'severity': 'info', 'category': 'general', 'title': 'Mipmap 建议', 
         'message': 'UI_Atlas 未启用 Mipmap，在缩放时可能出现锯齿。', 
         'suggestion': '为 UI 纹理启用 Mipmap',
         'rule_id': 'TEX_MIP_001', 'impact_score': 2, 'resource_id': '4'},
    ],
    'recommendations': [],
    'total_vram': 234881024,  # ~224 MB
    'large_texture_count': 3,
    'uncompressed_count': 2,
}

def main():
    print("=" * 60)
    print("🎨 生成 Grafana/Datadog 风格演示报告")
    print("=" * 60)
    
    # 清理并创建输出目录
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 初始化生成器
    gen = ReportBundleGenerator(
        output_dir=OUTPUT_DIR,
        capture_name='Demo_Performance_Capture'
    )
    
    # 设置数据
    gen.textures = MOCK_TEXTURES
    gen.events = MOCK_EVENTS
    gen.shaders = MOCK_SHADERS
    gen.performance_data = MOCK_PERFORMANCE
    
    # 更新统计数据
    gen.stats = {
        'total_textures': len(MOCK_TEXTURES),
        'total_events': len(MOCK_EVENTS),
        'total_shaders': len(MOCK_SHADERS),
        'draw_calls': sum(1 for e in MOCK_EVENTS if e.get('type') == 'draw'),
        'dispatch_calls': sum(1 for e in MOCK_EVENTS if e.get('type') == 'dispatch'),
        'clear_calls': sum(1 for e in MOCK_EVENTS if e.get('type') == 'clear'),
        'vram_usage': MOCK_PERFORMANCE['total_vram'],
        'issues_count': len(MOCK_PERFORMANCE['issues']),
        'issues': MOCK_PERFORMANCE['issues']
    }
    
    # 生成各页面
    print("\n📄 生成页面...")
    
    # 1. recommendations.html (重点验证)
    print("   • recommendations.html (新 Grafana/Datadog UI)")
    recommendations_html = gen.generate_recommendations()
    (OUTPUT_DIR / "recommendations.html").write_text(recommendations_html, encoding='utf-8')
    
    # 2. 复制 CSS 文件
    print("   • 复制 CSS 文件")
    templates_dir = script_dir / "templates"
    shutil.copy(templates_dir / "common.css", OUTPUT_DIR / "common.css")
    shutil.copy(templates_dir / "recommendations.css", OUTPUT_DIR / "recommendations.css")
    
    # 3. index.html (概览页)
    print("   • index.html (概览页)")
    try:
        index_html = gen.generate_index()
        (OUTPUT_DIR / "index.html").write_text(index_html, encoding='utf-8')
    except Exception as e:
        print(f"     ⚠️ index.html 生成跳过: {e}")
    
    # 4. textures.html
    print("   • textures.html")
    try:
        textures_html = gen.generate_textures()
        (OUTPUT_DIR / "textures.html").write_text(textures_html, encoding='utf-8')
    except Exception as e:
        print(f"     ⚠️ textures.html 生成跳过: {e}")
    
    # 5. events.html
    print("   • events.html")
    try:
        events_html = gen.generate_events()
        (OUTPUT_DIR / "events.html").write_text(events_html, encoding='utf-8')
    except Exception as e:
        print(f"     ⚠️ events.html 生成跳过: {e}")
    
    # 6. shaders.html
    print("   • shaders.html")
    try:
        shaders_html = gen.generate_shaders()
        (OUTPUT_DIR / "shaders.html").write_text(shaders_html, encoding='utf-8')
    except Exception as e:
        print(f"     ⚠️ shaders.html 生成跳过: {e}")
    
    # 7. manifest.json
    print("   • manifest.json")
    manifest = gen.generate_manifest()
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    
    # 输出结果
    print("\n" + "=" * 60)
    print("✅ 演示报告生成完成！")
    print("=" * 60)
    print(f"\n📁 输出目录: {OUTPUT_DIR}")
    print(f"\n🌐 打开浏览器访问:")
    print(f"   file:///{OUTPUT_DIR.as_posix()}/recommendations.html")
    print(f"\n📊 问题统计:")
    critical = sum(1 for i in MOCK_PERFORMANCE['issues'] if i['severity'] == 'critical')
    warning = sum(1 for i in MOCK_PERFORMANCE['issues'] if i['severity'] == 'warning')
    info = sum(1 for i in MOCK_PERFORMANCE['issues'] if i['severity'] == 'info')
    health_score = max(0, 100 - (critical * 15 + warning * 5 + info * 1))
    print(f"   • 严重: {critical} | 警告: {warning} | 建议: {info}")
    print(f"   • 健康评分: {health_score}/100")
    
    return str(OUTPUT_DIR / "recommendations.html")

if __name__ == "__main__":
    main()
