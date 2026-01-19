# -*- coding: utf-8 -*-
"""Test HTML export with full features"""

import sys
import os
import base64
import io

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rdc_analyzer.exporters.html_exporter import HTMLExporter, HTMLExportConfig
from rdc_analyzer.core.pipeline_state import DrawCallDetail
from rdc_analyzer.analysis.call_analyzer import BindingIssue, IssueSeverity, IssueCategory
from rdc_analyzer.analysis.resource_tracker import ResourceLifetime, ResourceDependency, DependencyType, AccessType

from rdc_analyzer.core.pipeline_state import DrawType

# Create test data
draws = [
    DrawCallDetail(event_id=100, name='DrawIndexed_GBuffer', draw_type=DrawType.DRAW_INDEXED),
    DrawCallDetail(event_id=200, name='DrawInstanced_Shadows', draw_type=DrawType.DRAW_INSTANCED),
    DrawCallDetail(event_id=300, name='DrawIndexed_Lighting', draw_type=DrawType.DRAW_INDEXED),
]

issues = [
    BindingIssue(rule_id='BIND001', severity=IssueSeverity.ERROR, category=IssueCategory.BINDING, 
                 event_id=100, message='Missing vertex shader'),
    BindingIssue(rule_id='BIND002', severity=IssueSeverity.WARNING, category=IssueCategory.BINDING, 
                 event_id=200, message='Null constant buffer at slot 0'),
]

deps = [
    ResourceDependency(source_event_id=100, target_event_id=200, resource_id=1001, 
                       resource_name='GBuffer_Color', dependency_type=DependencyType.RAW,
                       source_access=AccessType.WRITE, target_access=AccessType.READ),
    ResourceDependency(source_event_id=200, target_event_id=300, resource_id=1002, 
                       resource_name='ShadowMap', dependency_type=DependencyType.RAW,
                       source_access=AccessType.WRITE, target_access=AccessType.READ),
]

# Create resource lifetimes
lifetimes = {}

# Buffer resource
buf = ResourceLifetime(resource_id=1001, resource_name='GBuffer_Color', resource_type='RENDER_TARGET')
buf.first_access_event = 100
buf.last_access_event = 300
buf.read_count = 2
buf.write_count = 1
lifetimes[1001] = buf

# Texture resource
tex = ResourceLifetime(resource_id=1002, resource_name='ShadowMap', resource_type='TEXTURE')
tex.first_access_event = 200
tex.last_access_event = 300
tex.read_count = 1
tex.write_count = 1
lifetimes[1002] = tex

# Another buffer
cb = ResourceLifetime(resource_id=2001, resource_name='PerFrame_CB', resource_type='BUFFER')
cb.first_access_event = 100
cb.last_access_event = 300
cb.read_count = 3
cb.write_count = 0
lifetimes[2001] = cb

# Generate test texture images as Base64 PNG
def generate_test_texture_png(width, height, pattern='gradient'):
    """Generate a simple test texture as PNG Base64 string"""
    try:
        from PIL import Image
        import struct
        
        img = Image.new('RGBA', (width, height))
        pixels = img.load()
        
        for y in range(height):
            for x in range(width):
                if pattern == 'gradient':
                    # Colorful gradient pattern
                    r = int(255 * x / width)
                    g = int(255 * y / height)
                    b = int(255 * (1 - x / width))
                    pixels[x, y] = (r, g, b, 255)
                elif pattern == 'checker':
                    # Checkerboard pattern for depth texture
                    size = max(1, min(width, height) // 16)
                    is_white = ((x // size) + (y // size)) % 2 == 0
                    gray = 200 if is_white else 50
                    pixels[x, y] = (gray, gray, gray, 255)
        
        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except ImportError:
        # PIL not available, use minimal PNG generator
        return generate_minimal_png(width, height, pattern)

def generate_minimal_png(width, height, pattern='gradient'):
    """Generate a minimal valid PNG without PIL - creates a thumbnail"""
    import zlib
    
    # Create a smaller thumbnail to keep size manageable
    thumb_w = min(width, 128)
    thumb_h = min(height, 128)
    
    # Generate raw pixel data (RGBA)
    raw_data = []
    for y in range(thumb_h):
        raw_data.append(0)  # Filter byte for each row
        for x in range(thumb_w):
            if pattern == 'gradient':
                r = int(255 * x / thumb_w)
                g = int(255 * y / thumb_h)
                b = int(255 * (1 - x / thumb_w))
                a = 255
            else:  # checker
                size = max(1, thumb_w // 8)
                is_white = ((x // size) + (y // size)) % 2 == 0
                gray = 200 if is_white else 50
                r = g = b = gray
                a = 255
            raw_data.extend([r, g, b, a])
    
    raw_bytes = bytes(raw_data)
    compressed = zlib.compress(raw_bytes, 9)
    
    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return len(data).to_bytes(4, 'big') + chunk + crc.to_bytes(4, 'big')
    
    # PNG signature
    png = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk
    ihdr_data = (
        thumb_w.to_bytes(4, 'big') +
        thumb_h.to_bytes(4, 'big') +
        bytes([8, 6, 0, 0, 0])  # 8-bit RGBA
    )
    png += png_chunk(b'IHDR', ihdr_data)
    
    # IDAT chunk
    png += png_chunk(b'IDAT', compressed)
    
    # IEND chunk
    png += png_chunk(b'IEND', b'')
    
    return base64.b64encode(png).decode('utf-8')

# Generate texture thumbnails
gbuffer_thumbnail = generate_test_texture_png(128, 72, 'gradient')  # 16:9 aspect
shadowmap_thumbnail = generate_test_texture_png(128, 128, 'checker')  # Square

# Add resource samples for textures/buffers
resource_samples = {
    1001: {  # GBuffer_Color - RENDER_TARGET
        'width': 1920,
        'height': 1080,
        'format': 'R8G8B8A8_UNORM',
        'mip_levels': 1,
        'array_size': 1,
        'thumbnail': gbuffer_thumbnail  # Add thumbnail preview
    },
    1002: {  # ShadowMap - TEXTURE
        'width': 2048,
        'height': 2048,
        'format': 'D32_FLOAT',
        'mip_levels': 1,
        'array_size': 4,
        'thumbnail': shadowmap_thumbnail  # Add thumbnail preview
    },
    2001: {  # PerFrame_CB - BUFFER
        'size_bytes': 256,
        'constants': [
            {'name': 'ViewMatrix', 'type': 'float4x4', 'offset': 0},
            {'name': 'ProjMatrix', 'type': 'float4x4', 'offset': 64},
            {'name': 'CameraPos', 'type': 'float3', 'offset': 128, 'value': [10.5, 20.0, -5.0]},
            {'name': 'Time', 'type': 'float', 'offset': 140, 'value': 1.234}
        ]
    }
}

# Export with resource samples
exporter = HTMLExporter()

# Modify export to include resource_samples in JSON data
import json
from rdc_analyzer.exporters.json_exporter import JSONExporter

json_exporter = JSONExporter()
json_str = json_exporter.export(draws, issues, deps, lifetimes, 'test_capture.rdc', 'D3D11')
json_data = json.loads(json_str)
json_data['resource_samples'] = resource_samples

# Generate HTML with embedded resource samples
html = exporter.export(draws, issues, deps, lifetimes, 'test_capture.rdc', 'D3D11')
# Inject resource_samples into the JSON data in HTML
html = html.replace(
    'const analysisData = ',
    f'const analysisData = {json.dumps(json_data)}; const _unused = '
)

output_path = 'd:\\Code\\git\\renderdoc\\scripts\\test_new_report.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Generated HTML report: {output_path}")
print(f"File size: {len(html)} characters")
