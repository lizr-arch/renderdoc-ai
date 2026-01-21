"""
RT Timeline 组件集成测试

生成包含 RT Timeline 面板的测试 HTML 报告
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.rt_timeline_component import (
    generate_rt_timeline_css,
    generate_rt_timeline_html,
    generate_rt_timeline_js,
    generate_mock_rt_data
)


def test_rt_timeline_component():
    """测试 RT Timeline 组件生成"""
    # 生成模拟数据
    rt_data = generate_mock_rt_data()
    
    # 生成各部分
    css = generate_rt_timeline_css()
    html = generate_rt_timeline_html(rt_data)
    js = generate_rt_timeline_js()
    
    # 创建完整测试页面
    full_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RT Timeline Component Test</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 40px;
        }}
        h1 {{ 
            text-align: center; 
            margin-bottom: 20px;
            color: #a78bfa;
        }}
        .info {{
            text-align: center;
            color: #94a3b8;
            margin-bottom: 40px;
        }}
        {css}
    </style>
</head>
<body>
    <h1>🎯 RT Timeline Component Test</h1>
    <p class="info">点击右下角按钮打开 RT Timeline 面板</p>
    
    {html}
    
    <script>
        {js}
    </script>
</body>
</html>'''
    
    # 保存测试文件
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                               'test_rt_timeline.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"[OK] RT Timeline test page generated: {output_path}")
    
    # 验证组件
    assert len(css) > 500, "CSS should contain enough styles"
    assert 'rt-timeline-panel' in html, "HTML should contain panel element"
    assert 'toggleRTTimelinePanel' in js, "JS should contain toggle function"
    assert 'RT_Color_Main' in html, "HTML should contain mock data"
    
    print("[OK] All component validations passed")
    # Assertions above prove success - no return value needed


if __name__ == "__main__":
    test_rt_timeline_component()
