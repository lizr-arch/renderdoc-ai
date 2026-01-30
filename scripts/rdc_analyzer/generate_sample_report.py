#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成完整的 Mali Shader 分析报告 - 可折叠交互式列表"""

import subprocess
import tempfile
import json
import os

MALIOC = r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe"
OUTPUT = r"d:\Code\git\renderdoc\scripts\rdc_analyzer\output\mali_shader_report.html"
TARGET_GPU = "Mali-G78"

# 示例 Shader (模拟从 RDC 提取的多个 shader)
SHADERS = [
    ("VS_Main_EID100", "vertex", """#version 300 es
precision highp float;
in vec4 a_pos; in vec2 a_uv; in vec3 a_normal;
out vec2 v_uv; out vec3 v_normal; out vec3 v_worldPos;
uniform mat4 u_mvp, u_model;
void main() {
    v_uv = a_uv;
    v_normal = mat3(u_model) * a_normal;
    v_worldPos = (u_model * a_pos).xyz;
    gl_Position = u_mvp * a_pos;
}"""),
    ("PS_Main_EID100", "fragment", """#version 300 es
precision highp float;
in vec2 v_uv; in vec3 v_normal; in vec3 v_worldPos;
out vec4 fragColor;
uniform sampler2D u_albedo, u_normal;
uniform vec3 u_lightDir; uniform vec4 u_color;
void main() {
    vec4 albedo = texture(u_albedo, v_uv);
    vec3 normalMap = texture(u_normal, v_uv).rgb * 2.0 - 1.0;
    vec3 N = normalize(v_normal + normalMap);
    float NdotL = max(dot(N, u_lightDir), 0.0);
    fragColor = vec4(albedo.rgb * (NdotL + 0.1), albedo.a) * u_color;
}"""),
    ("VS_Shadow_EID200", "vertex", """#version 300 es
precision highp float;
in vec4 a_pos;
uniform mat4 u_lightMVP;
void main() { gl_Position = u_lightMVP * a_pos; }"""),
    ("PS_Shadow_EID200", "fragment", """#version 300 es
precision highp float;
out vec4 fragColor;
void main() { fragColor = vec4(gl_FragCoord.z, 0.0, 0.0, 1.0); }"""),
    ("VS_UI_EID300", "vertex", """#version 300 es
precision highp float;
in vec4 a_pos; in vec4 a_color; in vec2 a_uv;
out vec4 v_color; out vec2 v_uv;
uniform mat4 u_proj;
void main() { v_color = a_color; v_uv = a_uv; gl_Position = u_proj * a_pos; }"""),
    ("PS_UI_EID300", "fragment", """#version 300 es
precision highp float;
in vec4 v_color; in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_tex;
void main() { fragColor = texture(u_tex, v_uv) * v_color; }"""),
    ("VS_Skybox_EID400", "vertex", """#version 300 es
precision highp float;
in vec3 a_pos;
out vec3 v_texCoord;
uniform mat4 u_viewProj;
void main() { v_texCoord = a_pos; gl_Position = (u_viewProj * vec4(a_pos, 0.0)).xyww; }"""),
    ("PS_Skybox_EID400", "fragment", """#version 300 es
precision highp float;
in vec3 v_texCoord;
out vec4 fragColor;
uniform samplerCube u_skybox;
void main() { fragColor = texture(u_skybox, v_texCoord); }"""),
    ("PS_PBR_EID500", "fragment", """#version 300 es
precision highp float;
in vec2 v_uv; in vec3 v_normal; in vec3 v_viewDir;
out vec4 fragColor;
uniform sampler2D u_albedo, u_normal, u_roughness, u_metallic;
uniform samplerCube u_envMap;
uniform vec3 u_lightDir, u_lightColor;
const float PI = 3.14159265359;
float DistributionGGX(vec3 N, vec3 H, float r) {
    float a = r*r, a2 = a*a, NdotH = max(dot(N,H),0.0), d = NdotH*NdotH*(a2-1.0)+1.0;
    return a2 / (PI*d*d);
}
float GeometrySchlickGGX(float NdotV, float r) {
    float k = (r+1.0)*(r+1.0)/8.0;
    return NdotV / (NdotV*(1.0-k)+k);
}
vec3 fresnelSchlick(float c, vec3 F0) { return F0 + (1.0-F0)*pow(1.0-c,5.0); }
void main() {
    vec3 albedo = texture(u_albedo, v_uv).rgb;
    vec3 nm = texture(u_normal, v_uv).rgb * 2.0 - 1.0;
    float roughness = texture(u_roughness, v_uv).r;
    float metallic = texture(u_metallic, v_uv).r;
    vec3 N = normalize(v_normal + nm), V = normalize(v_viewDir), L = normalize(u_lightDir), H = normalize(V+L);
    vec3 F0 = mix(vec3(0.04), albedo, metallic);
    float NDF = DistributionGGX(N, H, roughness);
    float G = GeometrySchlickGGX(max(dot(N,V),0.0), roughness) * GeometrySchlickGGX(max(dot(N,L),0.0), roughness);
    vec3 F = fresnelSchlick(max(dot(H,V),0.0), F0);
    vec3 spec = (NDF*G*F) / (4.0*max(dot(N,V),0.0)*max(dot(N,L),0.0)+0.001);
    vec3 kD = (1.0-F)*(1.0-metallic);
    float NdotL = max(dot(N,L),0.0);
    vec3 Lo = (kD*albedo/PI + spec)*u_lightColor*NdotL;
    vec3 ambient = texture(u_envMap, reflect(-V,N)).rgb * albedo * 0.03;
    vec3 color = ambient + Lo;
    color = color/(color+1.0);
    color = pow(color, vec3(1.0/2.2));
    fragColor = vec4(color, 1.0);
}"""),
    ("PS_Bloom_EID600", "fragment", """#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_scene;
uniform float u_threshold;
void main() {
    vec3 c = texture(u_scene, v_uv).rgb;
    float brightness = dot(c, vec3(0.2126, 0.7152, 0.0722));
    fragColor = brightness > u_threshold ? vec4(c, 1.0) : vec4(0.0);
}"""),
    ("PS_GaussBlur_EID700", "fragment", """#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_tex;
uniform vec2 u_dir;
const float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
void main() {
    vec2 ts = 1.0 / vec2(textureSize(u_tex, 0));
    vec3 r = texture(u_tex, v_uv).rgb * w[0];
    for(int i = 1; i < 5; i++) {
        r += texture(u_tex, v_uv + u_dir * ts * float(i)).rgb * w[i];
        r += texture(u_tex, v_uv - u_dir * ts * float(i)).rgb * w[i];
    }
    fragColor = vec4(r, 1.0);
}"""),
]

def run_malioc(name, shader_type, source):
    """运行 malioc 并返回完整原始数据"""
    suffix = '.vert' if shader_type == 'vertex' else '.frag'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(source)
        path = f.name
    try:
        flag = '--vertex' if shader_type == 'vertex' else '--fragment'
        r = subprocess.run([MALIOC, '--format', 'json', '--core', TARGET_GPU, flag, path],
                          capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return parse_full_result(name, shader_type, json.loads(r.stdout))
        return {'name': name, 'type': shader_type, 'success': False, 'error': r.stderr[:200]}
    except Exception as e:
        return {'name': name, 'type': shader_type, 'success': False, 'error': str(e)}
    finally:
        os.unlink(path)

def parse_full_result(name, stype, data):
    """解析完整的 malioc 输出"""
    result = {
        'name': name, 'type': stype, 'success': True,
        'hardware': {}, 'shader_properties': [], 'variant_properties': [],
        'performance': {'shortest_path': {}, 'longest_path': {}, 'total': {}, 'pipelines': []},
        'bound': 'Unknown', 'warnings': [], 'notes': []
    }
    try:
        shader = data['shaders'][0]
        hw = shader.get('hardware', {})
        result['hardware'] = {'architecture': hw.get('architecture', 'Unknown'), 'core': hw.get('core', 'Unknown')}
        result['shader_properties'] = shader.get('properties', [])
        result['notes'] = shader.get('notes', [])
        variant = shader['variants'][0]
        result['variant_properties'] = variant.get('properties', [])
        result['warnings'] = shader.get('warnings', [])
        
        perf = variant.get('performance', {})
        pipelines = perf.get('pipelines', [])
        result['performance']['pipelines'] = pipelines
        
        for path_name in ['shortest_path_cycles', 'longest_path_cycles', 'total_cycles']:
            p = perf.get(path_name, {})
            cycles = p.get('cycle_count', [])
            bound = p.get('bound_pipelines', [])
            key = path_name.replace('_cycles', '').replace('_path', '')
            result['performance'][key] = {'cycles': dict(zip(pipelines, cycles)), 'bound': bound}
        
        sp_bound = result['performance']['shortest']['bound']
        if sp_bound:
            bn = sp_bound[0].lower()
            if 'arith' in bn: result['bound'] = 'Arithmetic'
            elif 'load' in bn or 'store' in bn: result['bound'] = 'Load/Store'
            elif 'tex' in bn: result['bound'] = 'Texture'
            elif 'vary' in bn: result['bound'] = 'Varying'
            else: result['bound'] = sp_bound[0]
    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
    return result

def gen_html(results, rdc_name):
    """生成可折叠交互式 HTML 报告"""
    
    # 统计
    success = [r for r in results if r.get('success')]
    vs_count = sum(1 for r in success if r['type'] == 'vertex')
    ps_count = sum(1 for r in success if r['type'] == 'fragment')
    
    bound_stats = {}
    total_cycles = {'arith': 0, 'tex': 0, 'ls': 0, 'vary': 0}
    for r in success:
        b = r.get('bound', 'Unknown')
        bound_stats[b] = bound_stats.get(b, 0) + 1
        sp = r.get('performance', {}).get('shortest', {}).get('cycles', {})
        total_cycles['arith'] += sp.get('arith_total', 0)
        total_cycles['tex'] += sp.get('texture', 0)
        total_cycles['ls'] += sp.get('load_store', 0)
        total_cycles['vary'] += sp.get('varying', 0)
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mali Shader Analysis - {rdc_name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.5; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        
        /* Header */
        .header {{ background: linear-gradient(135deg, #161b22 0%, #21262d 100%); border-radius: 12px; padding: 30px; margin-bottom: 20px; border: 1px solid #30363d; }}
        .header h1 {{ color: #58a6ff; font-size: 1.8em; margin-bottom: 10px; }}
        .header-info {{ display: flex; gap: 20px; flex-wrap: wrap; color: #8b949e; font-size: 0.9em; }}
        .header-info span {{ background: #21262d; padding: 4px 12px; border-radius: 20px; }}
        
        /* Summary Cards */
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 25px; }}
        .summary-card {{ background: #161b22; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #30363d; }}
        .summary-card .value {{ font-size: 2.5em; font-weight: bold; color: #58a6ff; }}
        .summary-card .label {{ color: #8b949e; font-size: 0.85em; margin-top: 5px; }}
        .summary-card.highlight {{ border-color: #f85149; }}
        .summary-card.highlight .value {{ color: #f85149; }}
        
        /* Bound Stats */
        .bound-stats {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 25px; }}
        .bound-chip {{ padding: 8px 16px; border-radius: 20px; font-size: 0.85em; font-weight: 600; }}
        .bound-chip.arithmetic {{ background: #f8514933; color: #f85149; border: 1px solid #f85149; }}
        .bound-chip.texture {{ background: #58a6ff33; color: #58a6ff; border: 1px solid #58a6ff; }}
        .bound-chip.load-store {{ background: #3fb95033; color: #3fb950; border: 1px solid #3fb950; }}
        .bound-chip.varying {{ background: #a371f733; color: #a371f7; border: 1px solid #a371f7; }}
        
        /* Filter Bar */
        .filter-bar {{ background: #161b22; border-radius: 8px; padding: 15px; margin-bottom: 20px; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; border: 1px solid #30363d; }}
        .filter-bar label {{ color: #8b949e; font-size: 0.85em; }}
        .filter-bar select, .filter-bar input {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; }}
        .filter-bar button {{ background: #238636; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }}
        .filter-bar button:hover {{ background: #2ea043; }}
        .filter-bar button.secondary {{ background: #21262d; border: 1px solid #30363d; }}
        
        /* Shader List */
        .shader-list {{ display: flex; flex-direction: column; gap: 8px; }}
        
        /* Shader Item (Collapsed) */
        .shader-item {{ background: #161b22; border-radius: 8px; border: 1px solid #30363d; overflow: hidden; }}
        .shader-header {{ display: flex; align-items: center; padding: 15px 20px; cursor: pointer; transition: background 0.2s; }}
        .shader-header:hover {{ background: #21262d; }}
        .shader-header .expand-icon {{ color: #8b949e; margin-right: 12px; transition: transform 0.2s; font-size: 0.8em; }}
        .shader-item.expanded .expand-icon {{ transform: rotate(90deg); }}
        .shader-header .name {{ font-weight: 600; color: #58a6ff; flex: 1; }}
        .shader-header .type-badge {{ font-size: 0.75em; padding: 2px 8px; border-radius: 4px; margin-right: 10px; }}
        .shader-header .type-badge.vertex {{ background: #388bfd33; color: #58a6ff; }}
        .shader-header .type-badge.fragment {{ background: #a371f733; color: #a371f7; }}
        .shader-header .bound-badge {{ font-size: 0.75em; padding: 2px 10px; border-radius: 12px; font-weight: 600; }}
        .shader-header .bound-badge.arithmetic {{ background: #f85149; color: #fff; }}
        .shader-header .bound-badge.texture {{ background: #58a6ff; color: #fff; }}
        .shader-header .bound-badge.load-store {{ background: #3fb950; color: #fff; }}
        .shader-header .bound-badge.varying {{ background: #a371f7; color: #fff; }}
        .shader-header .cycles {{ color: #8b949e; font-size: 0.85em; margin-left: 15px; }}
        
        /* Shader Details (Expanded) */
        .shader-details {{ display: none; padding: 0 20px 20px; border-top: 1px solid #30363d; }}
        .shader-item.expanded .shader-details {{ display: block; }}
        
        .detail-section {{ margin-top: 15px; }}
        .detail-section h4 {{ color: #8b949e; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }}
        
        /* Cycles Grid */
        .cycles-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; }}
        .cycle-box {{ background: #21262d; padding: 10px; border-radius: 6px; text-align: center; }}
        .cycle-box .label {{ font-size: 0.7em; color: #8b949e; }}
        .cycle-box .value {{ font-size: 1.2em; font-weight: bold; color: #58a6ff; }}
        .cycle-box.bound {{ border: 2px solid #f85149; }}
        .cycle-box.bound .value {{ color: #f85149; }}
        
        /* Properties Grid */
        .props-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }}
        .prop-box {{ background: #21262d; padding: 8px 12px; border-radius: 6px; display: flex; justify-content: space-between; }}
        .prop-box .name {{ color: #8b949e; font-size: 0.8em; }}
        .prop-box .val {{ font-weight: 600; }}
        .prop-box .val.good {{ color: #3fb950; }}
        .prop-box .val.warn {{ color: #d29922; }}
        .prop-box .val.bad {{ color: #f85149; }}
        
        /* Mini Bar */
        .mini-bar {{ height: 4px; background: #30363d; border-radius: 2px; margin-top: 4px; overflow: hidden; }}
        .mini-bar .fill {{ height: 100%; border-radius: 2px; }}
        .mini-bar .fill.arith {{ background: #f85149; }}
        .mini-bar .fill.tex {{ background: #58a6ff; }}
        .mini-bar .fill.ls {{ background: #3fb950; }}
        .mini-bar .fill.vary {{ background: #a371f7; }}
        
        /* Error State */
        .shader-item.error {{ border-left: 3px solid #f85149; }}
        .shader-item.error .shader-header .name {{ color: #f85149; }}
        
        /* Footer */
        .footer {{ text-align: center; padding: 30px; color: #8b949e; font-size: 0.85em; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Mali Shader Analysis Report</h1>
        <div class="header-info">
            <span>Target: {TARGET_GPU}</span>
            <span>Architecture: Valhall</span>
            <span>RDC: {rdc_name}</span>
            <span>Shaders: {len(results)}</span>
        </div>
    </div>
    
    <div class="summary">
        <div class="summary-card">
            <div class="value">{len(success)}</div>
            <div class="label">Total Analyzed</div>
        </div>
        <div class="summary-card">
            <div class="value">{vs_count}</div>
            <div class="label">Vertex Shaders</div>
        </div>
        <div class="summary-card">
            <div class="value">{ps_count}</div>
            <div class="label">Fragment Shaders</div>
        </div>
        <div class="summary-card highlight">
            <div class="value">{total_cycles["arith"]:.1f}</div>
            <div class="label">Total Arith Cycles</div>
        </div>
        <div class="summary-card">
            <div class="value">{total_cycles["tex"]:.1f}</div>
            <div class="label">Total Texture Cycles</div>
        </div>
    </div>
    
    <div class="bound-stats">
        <span style="color:#8b949e;margin-right:10px;">Bottleneck Distribution:</span>
'''
    for bound, count in sorted(bound_stats.items(), key=lambda x: -x[1]):
        css = bound.lower().replace('/', '-')
        html += f'<span class="bound-chip {css}">{bound}: {count}</span>\n'
    
    html += '''
    </div>
    
    <div class="filter-bar">
        <label>Filter:</label>
        <select id="filterType">
            <option value="all">All Types</option>
            <option value="vertex">Vertex Only</option>
            <option value="fragment">Fragment Only</option>
        </select>
        <select id="filterBound">
            <option value="all">All Bounds</option>
            <option value="arithmetic">Arithmetic</option>
            <option value="texture">Texture</option>
            <option value="load-store">Load/Store</option>
            <option value="varying">Varying</option>
        </select>
        <label>Sort:</label>
        <select id="sortBy">
            <option value="name">Name</option>
            <option value="cycles-desc">Cycles (High to Low)</option>
            <option value="cycles-asc">Cycles (Low to High)</option>
        </select>
        <button onclick="expandAll()">Expand All</button>
        <button class="secondary" onclick="collapseAll()">Collapse All</button>
    </div>
    
    <div class="shader-list" id="shaderList">
'''
    
    for r in results:
        name = r.get('name', 'Unknown')
        stype = r.get('type', 'unknown')
        success_flag = r.get('success', False)
        bound = r.get('bound', '?')
        bound_css = bound.lower().replace('/', '-')
        
        sp = r.get('performance', {}).get('shortest', {}).get('cycles', {})
        max_cycle = max(sp.values()) if sp and sp.values() else 0
        
        error_class = '' if success_flag else ' error'
        
        html += f'''
        <div class="shader-item{error_class}" data-type="{stype}" data-bound="{bound_css}" data-cycles="{max_cycle:.3f}">
            <div class="shader-header" onclick="toggleShader(this)">
                <span class="expand-icon">▶</span>
                <span class="type-badge {stype}">{stype.upper()[:2]}</span>
                <span class="name">{name}</span>
'''
        if success_flag:
            html += f'''
                <span class="bound-badge {bound_css}">{bound}</span>
                <span class="cycles">{max_cycle:.2f} cyc</span>
'''
        else:
            html += f'<span style="color:#f85149;">Error</span>'
        
        html += '</div>'
        
        # Details section
        html += '<div class="shader-details">'
        
        if not success_flag:
            html += f'<p style="color:#f85149;padding:10px;">Error: {r.get("error", "Unknown")}</p>'
        else:
            # Cycles
            html += '<div class="detail-section"><h4>Performance Cycles (Shortest Path)</h4><div class="cycles-grid">'
            sp_bound = r.get('performance', {}).get('shortest', {}).get('bound', [])
            for key, label in [('arith_total', 'Arith'), ('arith_fma', 'FMA'), ('arith_cvt', 'CVT'), 
                               ('arith_sfu', 'SFU'), ('load_store', 'L/S'), ('texture', 'Tex'), ('varying', 'Vary')]:
                if key in sp:
                    val = sp[key]
                    is_bound = key in sp_bound
                    bound_class = ' bound' if is_bound else ''
                    pct = (val / max_cycle * 100) if max_cycle > 0 else 0
                    css_type = 'arith' if 'arith' in key else ('tex' if key == 'texture' else ('ls' if key == 'load_store' else 'vary'))
                    html += f'''
                    <div class="cycle-box{bound_class}">
                        <div class="label">{label}</div>
                        <div class="value">{val:.2f}</div>
                        <div class="mini-bar"><div class="fill {css_type}" style="width:{pct}%"></div></div>
                    </div>'''
            html += '</div></div>'
            
            # Properties
            vprops = r.get('variant_properties', [])
            if vprops:
                html += '<div class="detail-section"><h4>Shader Properties</h4><div class="props-grid">'
                for p in vprops:
                    pname = p.get('display_name', p.get('name', '?'))
                    val = p.get('value', '?')
                    val_class = ''
                    if 'spill' in pname.lower():
                        val_class = ' bad' if val else ' good'
                    elif 'occupancy' in pname.lower() and isinstance(val, (int, float)):
                        val_class = ' good' if val >= 75 else (' warn' if val >= 50 else ' bad')
                    if isinstance(val, bool):
                        val = 'Yes' if val else 'No'
                    elif isinstance(val, float):
                        val = f'{val:.1f}'
                    html += f'<div class="prop-box"><span class="name">{pname}</span><span class="val{val_class}">{val}</span></div>'
                html += '</div></div>'
        
        html += '</div></div>'  # Close details and item
    
    html += '''
    </div>
    
    <div class="footer">
        Generated by RenderDoc Mali Analysis Tool | Target: Mali-G78 (Valhall)
    </div>
</div>

<script>
function toggleShader(header) {
    header.parentElement.classList.toggle('expanded');
}
function expandAll() {
    document.querySelectorAll('.shader-item').forEach(el => el.classList.add('expanded'));
}
function collapseAll() {
    document.querySelectorAll('.shader-item').forEach(el => el.classList.remove('expanded'));
}

// Filtering
document.getElementById('filterType').addEventListener('change', applyFilters);
document.getElementById('filterBound').addEventListener('change', applyFilters);
document.getElementById('sortBy').addEventListener('change', applyFilters);

function applyFilters() {
    const typeFilter = document.getElementById('filterType').value;
    const boundFilter = document.getElementById('filterBound').value;
    const sortBy = document.getElementById('sortBy').value;
    
    const list = document.getElementById('shaderList');
    const items = Array.from(list.querySelectorAll('.shader-item'));
    
    items.forEach(item => {
        const type = item.dataset.type;
        const bound = item.dataset.bound;
        const showType = typeFilter === 'all' || type === typeFilter;
        const showBound = boundFilter === 'all' || bound === boundFilter;
        item.style.display = (showType && showBound) ? '' : 'none';
    });
    
    // Sort
    items.sort((a, b) => {
        if (sortBy === 'name') return a.querySelector('.name').textContent.localeCompare(b.querySelector('.name').textContent);
        if (sortBy === 'cycles-desc') return parseFloat(b.dataset.cycles) - parseFloat(a.dataset.cycles);
        if (sortBy === 'cycles-asc') return parseFloat(a.dataset.cycles) - parseFloat(b.dataset.cycles);
        return 0;
    });
    items.forEach(item => list.appendChild(item));
}
</script>
</body>
</html>'''
    
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Report saved to: {OUTPUT}")

def main():
    print(f"Generating Interactive Mali Shader Report...")
    print(f"Target GPU: {TARGET_GPU}")
    print(f"Analyzing {len(SHADERS)} shaders...\n")
    
    results = []
    for name, stype, source in SHADERS:
        print(f"  [{stype[:1].upper()}] {name}...", end=' ')
        r = run_malioc(name, stype, source)
        results.append(r)
        if r.get('success'):
            sp = r.get('performance', {}).get('shortest', {}).get('cycles', {})
            print(f"OK - {r.get('bound')} bound, {max(sp.values()) if sp else 0:.2f} cyc")
        else:
            print(f"ERROR")
    
    print()
    gen_html(results, "Game_x64h_frame3996.rdc")
    print("\n[OK] Interactive report generated!")
    print(f"Open in browser: {OUTPUT}")

if __name__ == "__main__":
    main()