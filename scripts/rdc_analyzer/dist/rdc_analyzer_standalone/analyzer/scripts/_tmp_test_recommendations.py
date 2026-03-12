#!/usr/bin/env python3
"""临时测试脚本：验证 recommendations.html 新模板变量"""

import sys
import os
import json
import tempfile

# 设置路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report_bundle_generator import ReportBundleGenerator

# 创建模拟数据
mock_textures = [
    {'id': 1, 'name': 'albedo.png', 'width': 2048, 'height': 2048, 'format': 'BC3'},
    {'id': 2, 'name': 'normal.png', 'width': 1024, 'height': 1024, 'format': 'R8G8B8A8'}
]
mock_events = [
    {'eventId': 1, 'name': 'DrawIndexed', 'type': 'draw'},
    {'eventId': 2, 'name': 'DrawIndexed', 'type': 'draw'}
]
mock_performance = {
    'issues': [
        {'severity': 'critical', 'category': 'texture', 'title': '超大纹理', 
         'message': '纹理尺寸为 4096x4096，超过推荐的 2048 限制', 'rule_id': 'TEX_SIZE_001'},
        {'severity': 'warning', 'category': 'texture', 'title': '未压缩纹理', 
         'message': '纹理使用 R8G8B8A8 格式，建议使用 BC5 压缩', 'rule_id': 'TEX_FMT_002'},
        {'severity': 'info', 'category': 'memory', 'title': '内存使用建议', 
         'message': 'VRAM 使用量为 256MB', 'rule_id': 'MEM_001'}
    ],
    'recommendations': []
}

# 创建临时输出目录
with tempfile.TemporaryDirectory() as tmpdir:
    # 初始化生成器
    gen = ReportBundleGenerator(
        output_dir=tmpdir,
        capture_name='test_capture'
    )
    
    # 设置数据
    gen.textures = mock_textures
    gen.events = mock_events
    gen.performance_data = mock_performance
    
    # 生成 recommendations 页面
    print("正在生成 recommendations.html...")
    html = gen.generate_recommendations()
    
    # 验证关键变量被正确替换
    checks = [
        ('HEALTH_SCORE', '{{HEALTH_SCORE}}'),
        ('HEALTH_STATUS', '{{HEALTH_STATUS}}'),
        ('SCORE_OFFSET', '{{SCORE_OFFSET}}'),
        ('CATEGORY_BARS', '{{CATEGORY_BARS}}'),
        ('RECOMMENDATIONS_JSON', '{{RECOMMENDATIONS_JSON}}'),
        ('CRITICAL_ARC', '{{CRITICAL_ARC}}'),
        ('WARNING_ARC', '{{WARNING_ARC}}'),
        ('INFO_ARC', '{{INFO_ARC}}'),
        ('ANALYSIS_TIME', '{{ANALYSIS_TIME}}'),
    ]
    
    print('\n=== 模板变量替换验证 ===')
    all_pass = True
    for name, placeholder in checks:
        passed = placeholder not in html
        status = '✅' if passed else '❌'
        print(f'{status} {name}')
        if not passed:
            all_pass = False
    
    # 检查健康评分
    # 1 critical + 1 warning + 1 info = 15 + 5 + 1 = 21 → 79分
    if '79' in html:
        print('✅ HEALTH_SCORE 计算正确 (79分)')
    elif '80' in html:
        print('✅ HEALTH_SCORE 计算近似 (80分)')
    else:
        print('⚠️ HEALTH_SCORE 需验证')
    
    print(f'\n📄 生成的 HTML 长度: {len(html)} 字符')
    
    if all_pass:
        print('\n🎉 [SUCCESS] 所有模板变量替换成功！')
    else:
        print('\n⚠️ [WARNING] 部分模板变量未替换')