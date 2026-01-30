#!/usr/bin/env python3
"""
生成简化版 HTML 报告 - 不使用 Virtual Scroll
确保在任何浏览器都能正常显示纹理列表
"""

import json
from datetime import datetime


def generate_simple_html(textures: list, rdc_name: str, output_path: str,
                         duplicate_analysis: dict = None, usage_analysis: dict = None):
    """生成简化版 HTML 报告（无 Virtual Scroll）"""
    
    # 生成纹理列表 HTML
    texture_items = []
    for tex in textures:
        vram_mb = tex.get('vram_bytes', 0) / (1024 * 1024)
        texture_items.append(f'''
        <div class="tex-item" data-id="{tex['id']}">
            <div class="tex-id">#{tex['id']}</div>
            <div class="tex-name">{tex.get('name', 'Unknown')}</div>
            <div class="tex-size">{tex.get('width', 0)}x{tex.get('height', 0)}</div>
            <div class="tex-format">{tex.get('format', 'UNKNOWN')}</div>
            <div class="tex-vram">{vram_mb:.2f} MB</div>
        </div>''')
    
    texture_list_html = '\n'.join(texture_items)
    
    # 去重分析摘要
    dup_summary = ""
    if duplicate_analysis and duplicate_analysis.get('duplicate_groups'):
        groups = duplicate_analysis['duplicate_groups']
        wasted = duplicate_analysis.get('total_wasted_bytes', 0) / (1024 * 1024)
        dup_summary = f'''
        <div class="summary-card warning">
            <h3>🔁 重复纹理</h3>
            <div class="stat">{len(groups)} 组重复</div>
            <div class="detail">浪费 {wasted:.1f} MB VRAM</div>
        </div>'''
    
    # 使用分析摘要
    usage_summary = ""
    if usage_analysis:
        unused = usage_analysis.get('unused_textures', 0)
        unused_vram = usage_analysis.get('unused_vram_bytes', 0) / (1024 * 1024)
        if unused > 0:
            usage_summary = f'''
            <div class="summary-card danger">
                <h3>⚠️ 未使用纹理</h3>
                <div class="stat">{unused} 个</div>
                <div class="detail">占用 {unused_vram:.1f} MB VRAM</div>
            </div>'''
    
    # 计算总 VRAM
    total_vram = sum(t.get('vram_bytes', 0) for t in textures) / (1024 * 1024)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>纹理报告 - {rdc_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            padding: 20px;
        }}
        .header {{
            background: #161b22;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .header h1 {{ color: #58a6ff; margin-bottom: 10px; }}
        .header .meta {{ color: #8b949e; font-size: 14px; }}
        
        .summary {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .summary-card {{
            background: #161b22;
            padding: 15px 20px;
            border-radius: 8px;
            border-left: 4px solid #58a6ff;
            min-width: 200px;
        }}
        .summary-card.warning {{ border-left-color: #f0883e; }}
        .summary-card.danger {{ border-left-color: #e94560; }}
        .summary-card h3 {{ font-size: 14px; color: #8b949e; margin-bottom: 8px; }}
        .summary-card .stat {{ font-size: 28px; font-weight: bold; }}
        .summary-card .detail {{ font-size: 12px; color: #8b949e; margin-top: 5px; }}
        
        .texture-list {{
            background: #161b22;
            border-radius: 8px;
            overflow: hidden;
        }}
        .list-header {{
            display: grid;
            grid-template-columns: 80px 1fr 120px 150px 100px;
            gap: 10px;
            padding: 12px 15px;
            background: #21262d;
            font-weight: bold;
            color: #8b949e;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .tex-item {{
            display: grid;
            grid-template-columns: 80px 1fr 120px 150px 100px;
            gap: 10px;
            padding: 12px 15px;
            border-bottom: 1px solid #30363d;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .tex-item:hover {{ background: #21262d; }}
        .tex-item:nth-child(odd) {{ background: #0d1117; }}
        .tex-item:nth-child(odd):hover {{ background: #21262d; }}
        
        .tex-id {{ color: #58a6ff; font-weight: bold; }}
        .tex-name {{ color: #e6edf3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .tex-size {{ color: #8b949e; }}
        .tex-format {{ 
            color: #3fb950; 
            font-family: monospace;
            font-size: 12px;
        }}
        .tex-vram {{ color: #f0883e; text-align: right; }}
        
        .search-bar {{
            margin-bottom: 15px;
        }}
        .search-bar input {{
            width: 100%;
            max-width: 400px;
            padding: 10px 15px;
            border: 1px solid #30363d;
            border-radius: 6px;
            background: #0d1117;
            color: #e6edf3;
            font-size: 14px;
        }}
        .search-bar input:focus {{
            outline: none;
            border-color: #58a6ff;
        }}
        
        .count {{ color: #8b949e; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 RDC 纹理分析报告</h1>
        <div class="meta">
            文件: {rdc_name} | 生成时间: {timestamp}
        </div>
    </div>
    
    <div class="summary">
        <div class="summary-card">
            <h3>📦 纹理总数</h3>
            <div class="stat">{len(textures)}</div>
        </div>
        <div class="summary-card">
            <h3>💾 VRAM 占用</h3>
            <div class="stat">{total_vram:.1f} MB</div>
        </div>
        {dup_summary}
        {usage_summary}
    </div>
    
    <div class="search-bar">
        <input type="text" id="searchInput" placeholder="搜索纹理名称或格式..." onkeyup="filterTextures()">
    </div>
    
    <div class="count" id="countDisplay">显示 {len(textures)} 个纹理</div>
    
    <div class="texture-list">
        <div class="list-header">
            <div>ID</div>
            <div>名称</div>
            <div>尺寸</div>
            <div>格式</div>
            <div>VRAM</div>
        </div>
        <div id="textureContainer">
            {texture_list_html}
        </div>
    </div>
    
    <script>
        function filterTextures() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const items = document.querySelectorAll('.tex-item');
            let visible = 0;
            
            items.forEach(item => {{
                const text = item.textContent.toLowerCase();
                if (text.includes(query)) {{
                    item.style.display = 'grid';
                    visible++;
                }} else {{
                    item.style.display = 'none';
                }}
            }});
            
            document.getElementById('countDisplay').textContent = `显示 ${{visible}} 个纹理`;
        }}
    </script>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"[OK] Simple report saved: {output_path}")
    return output_path


if __name__ == "__main__":
    # 测试：生成 145 个模拟纹理
    import random
    
    FORMATS = ['BC7_UNORM', 'BC7_UNORM_SRGB', 'BC5_UNORM', 'BC3_UNORM_SRGB', 
               'R8G8B8A8_UNORM', 'D32_FLOAT', 'BC6H_UF16']
    PREFIXES = ['T_Character', 'T_Env', 'T_UI', 'T_Normal', 'T_Shadow', 
                'T_Terrain', 'T_VFX', 'T_LightMap', 'T_ORM', 'T_Misc']
    
    textures = []
    for i in range(145):
        prefix = random.choice(PREFIXES)
        fmt = random.choice(FORMATS)
        size = random.choice([256, 512, 1024, 2048, 4096])
        
        # 计算 VRAM
        bpp = 1.0 if fmt.startswith('BC') else 4.0
        vram = size * size * bpp
        
        textures.append({
            'id': 1000 + i,
            'name': f"{prefix}_{i:02d}",
            'width': size,
            'height': size,
            'format': fmt,
            'vram_bytes': int(vram)
        })
    
    # 模拟去重分析
    dup_analysis = {
        'duplicate_groups': [
            {'fingerprint': 'abc123', 'count': 3, 'textures': []},
            {'fingerprint': 'def456', 'count': 2, 'textures': []},
        ],
        'total_wasted_bytes': 73 * 1024 * 1024
    }
    
    # 模拟使用分析
    usage_analysis = {
        'unused_textures': 8,
        'unused_vram_bytes': 2.75 * 1024 * 1024
    }
    
    generate_simple_html(
        textures, 
        'Game_x64h.rdc',
        'd:\\Code\\git\\renderdoc\\scripts\\rdc_analyzer\\simple_145_report.html',
        dup_analysis,
        usage_analysis
    )
