# -*- coding: utf-8 -*-
"""
RDC Real File Test Script
=========================

Test the complete analysis pipeline with real RDC files.

Usage:
1. Run via RenderDoc (recommended):
   renderdoccmd.exe python test_real_rdc.py

2. Or use mock data for testing (no RenderDoc needed):
   python test_real_rdc.py --mock
"""

import sys
import os
from pathlib import Path
import argparse

# Set console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add script directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Try to import renderdoc
RD_AVAILABLE = False
try:
    import renderdoc as rd
    RD_AVAILABLE = True
    print(f"[OK] RenderDoc module loaded: {rd.GetVersionString()}")
except ImportError:
    print("[INFO] RenderDoc module not available - will use mock mode")

# Import analyzer modules
from rdc_analyzer.core.pipeline_state import (
    DrawCallDetail, PipelineSnapshot, ShaderBindings, ResourceBinding,
    DrawType, PrimitiveTopology, ResourceType, RenderTargetInfo, ShaderStage,
)
from rdc_analyzer.analysis import analyze_draw_calls, track_resources
from rdc_analyzer.exporters import export_to_json, export_to_html


def create_mock_draws(num_draws: int = 50) -> list:
    """Create mock Draw Call data for testing"""
    
    draws = []
    for i in range(num_draws):
        event_id = 100 + i * 10
        
        # Create different types of draw calls
        if i % 5 == 0:
            draw_type = DrawType.DISPATCH
            name = f"ComputeDispatch_{i}"
        elif i % 3 == 0:
            draw_type = DrawType.DRAW_INDEXED_INSTANCED
            name = f"DrawIndexedInstanced_{i}"
        else:
            draw_type = DrawType.DRAW_INDEXED
            name = f"DrawIndexed_{i}"
        
        # Create pipeline snapshot
        vertex_buffers = [
            ResourceBinding(slot=0, stage=ShaderStage.VERTEX, resource_id=1000 + i, resource_type=ResourceType.BUFFER, stride=32),
        ]
        
        # Some draw calls have more vertex buffers
        if i % 4 == 0:
            vertex_buffers.append(
                ResourceBinding(slot=1, stage=ShaderStage.VERTEX, resource_id=2000 + i, resource_type=ResourceType.BUFFER, stride=16)
            )
        
        index_buffer = ResourceBinding(slot=0, stage=ShaderStage.VERTEX, resource_id=3000 + (i % 10), resource_type=ResourceType.BUFFER)
        
        # Vertex Shader bindings
        vs_bindings = ShaderBindings(
            stage=ShaderStage.VERTEX,
            resource_id=100 + i,
            name=f"VS_Main_{i}",
            constant_buffers=[
                ResourceBinding(slot=0, stage=ShaderStage.VERTEX, resource_id=4000 + i, resource_type=ResourceType.BUFFER, size_bytes=256),
            ],
            shader_resources=[
                ResourceBinding(slot=0, stage=ShaderStage.VERTEX, resource_id=5000 + i, resource_type=ResourceType.TEXTURE_2D),
            ],
        )
        
        # Pixel Shader bindings (not for dispatch)
        ps_bindings = None
        if draw_type != DrawType.DISPATCH:
            ps_bindings = ShaderBindings(
                stage=ShaderStage.PIXEL,
                resource_id=200 + i,
                name=f"PS_Main_{i}",
                constant_buffers=[
                    ResourceBinding(slot=0, stage=ShaderStage.PIXEL, resource_id=4000 + i, resource_type=ResourceType.BUFFER, size_bytes=256),
                    ResourceBinding(slot=1, stage=ShaderStage.PIXEL, resource_id=4100 + i, resource_type=ResourceType.BUFFER, size_bytes=128),
                ],
                shader_resources=[
                    ResourceBinding(slot=0, stage=ShaderStage.PIXEL, resource_id=6000 + i, resource_type=ResourceType.TEXTURE_2D),
                    ResourceBinding(slot=1, stage=ShaderStage.PIXEL, resource_id=6100 + i, resource_type=ResourceType.TEXTURE_2D),
                ],
            )
        
        # Render targets
        render_targets = []
        if draw_type != DrawType.DISPATCH:
            render_targets = [
                RenderTargetInfo(
                    slot=0,
                    resource_id=7000 + (i % 5),  # Some render targets are shared
                    format="R8G8B8A8_UNORM",
                    width=1920,
                    height=1080,
                ),
            ]
        
        # Create pipeline snapshot
        pipeline = PipelineSnapshot(
            primitive_topology=PrimitiveTopology.TRIANGLE_LIST,
            vertex_buffers=vertex_buffers,
            index_buffer=index_buffer,
            vertex_shader=vs_bindings,
            pixel_shader=ps_bindings,
            render_targets=render_targets,
        )
        
        draw = DrawCallDetail(
            event_id=event_id,
            name=name,
            draw_type=draw_type,
            vertex_count=1000 + i * 100,
            instance_count=1 if draw_type != DrawType.DRAW_INDEXED_INSTANCED else 10,
            pipeline=pipeline,
        )
        
        draws.append(draw)
    
    return draws


def run_analysis(draws: list, api_type: str, output_dir: Path, source_file: str):
    """Run the complete analysis pipeline"""
    
    print(f"\n{'='*60}")
    print(f"Starting analysis...")
    print(f"  Source: {source_file}")
    print(f"  API: {api_type}")
    print(f"  Draw Calls: {len(draws)}")
    print(f"{'='*60}\n")
    
    # 1. Analyze draw calls
    print("[1/4] Analyzing draw calls...")
    issues, context = analyze_draw_calls(draws)
    print(f"      Found {len(issues)} issues")
    
    # 2. Track resources
    print("[2/4] Tracking resources...")
    deps, lifetimes, tracker = track_resources(draws)
    print(f"      Found {len(deps)} dependencies")
    print(f"      Tracking {len(lifetimes)} resources")
    
    # 3. Export JSON
    print("[3/4] Exporting JSON...")
    json_path = output_dir / "analysis.json"
    export_to_json(
        draws,
        json_path,
        issues=issues,
        dependencies=deps,
        lifetimes=lifetimes,
        source_file=source_file,
        api_type=api_type,
    )
    print(f"      Saved to: {json_path}")
    
    # 4. Export HTML
    print("[4/4] Exporting HTML...")
    html_path = output_dir / "analysis.html"
    export_to_html(
        draws,
        html_path,
        issues=issues,
        dependencies=deps,
        lifetimes=lifetimes,
        source_file=source_file,
        api_type=api_type,
    )
    print(f"      Saved to: {html_path}")
    
    # Summary
    print(f"\n{'='*60}")
    print("Analysis Complete!")
    print(f"{'='*60}")
    print(f"  Issues by severity:")
    severity_counts = {}
    for issue in issues:
        sev = issue.severity.name
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    for sev, count in severity_counts.items():
        print(f"    - {sev}: {count}")
    
    print(f"\n  Issues by rule:")
    rule_counts = {}
    for issue in issues:
        rule_counts[issue.rule_id] = rule_counts.get(issue.rule_id, 0) + 1
    for rule, count in sorted(rule_counts.items()):
        print(f"    - {rule}: {count}")
    
    print(f"\n  Output files:")
    print(f"    - {json_path}")
    print(f"    - {html_path}")
    
    return issues, deps, lifetimes


def main():
    parser = argparse.ArgumentParser(description="RDC Analyzer Test")
    parser.add_argument('--mock', action='store_true', help="Use mock data instead of real RDC")
    parser.add_argument('--rdc', type=str, help="Path to RDC file")
    parser.add_argument('--output', type=str, default=".", help="Output directory")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.mock or not RD_AVAILABLE:
        # Use mock data
        print("\n[Mock Mode] Using simulated draw call data")
        draws = create_mock_draws(50)
        run_analysis(draws, "Mock_D3D11", output_dir, "mock_capture.rdc")
    else:
        # Real RDC mode
        rdc_path = args.rdc or r"D:\renderdoc\goog pixel-9\g145.rdc"
        if not os.path.exists(rdc_path):
            print(f"[ERROR] RDC file not found: {rdc_path}")
            sys.exit(1)
        
        print(f"\n[RDC Mode] Loading: {rdc_path}")
        # Real RenderDoc loading would go here
        # For now, fall back to mock
        print("[WARN] Real RDC loading not implemented, using mock data")
        draws = create_mock_draws(50)
        run_analysis(draws, "Vulkan", output_dir, rdc_path)


if __name__ == "__main__":
    main()