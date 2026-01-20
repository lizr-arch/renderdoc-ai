"""
RT Timeline Integration Test

Test RTTracker + generate_offline_report.py integration
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rt_tracker import RTTracker
from generate_offline_report import generate_offline_html


def test_rt_integration():
    """Test RT data integration into HTML report"""
    
    # Create sample RT tracking data
    tracker = RTTracker()
    
    # Simulate a render pass sequence
    # Pass 1: Clear and render to main RT
    tracker.record_clear(10, "RT_Main", "Main Render Target", "ClearRenderTargetView")
    tracker.record_bind(15, ["RT_Main"], "Depth_Main", "OMSetRenderTargets")
    tracker.record_draw(20, "DrawIndexed")
    tracker.record_draw(25, "DrawIndexed")
    tracker.record_draw(30, "DrawInstanced")
    
    # Pass 2: Switch to post-process RT (with redundant clear issue)
    tracker.record_clear(40, "RT_PostFX", "Post Process RT", "ClearRenderTargetView")
    tracker.record_clear(41, "RT_PostFX", "Post Process RT", "ClearRenderTargetView")  # Redundant!
    tracker.record_bind(45, ["RT_PostFX"], None, "OMSetRenderTargets")
    tracker.record_draw(50, "DrawIndexed")
    
    # Pass 3: Bind multiple RTs (MRT)
    tracker.record_bind(60, ["RT_GBuffer0", "RT_GBuffer1", "RT_GBuffer2"], "Depth_GBuffer", "OMSetRenderTargets")
    tracker.record_draw(65, "DrawIndexed")
    tracker.record_draw(70, "DrawIndexed")
    
    # Finalize and get results
    issues = tracker.finalize()
    
    # Convert to dict format expected by report generator
    rt_data = {
        "render_targets": [
            {
                "resource_id": lc.resource_id,
                "first_eid": lc.first_bind_eid or lc.first_clear_eid or 0,
                "last_eid": lc.last_draw_eid or lc.first_bind_eid or 0,
                "clear_count": lc.total_clears,
                "bind_count": lc.total_binds,
                "draw_count": lc.total_draws,
                "redundant_clear_count": lc.redundant_clear_count,
                "events": [
                    {"eid": op.eid, "type": op.op_type.name, "api_name": op.api_name}
                    for op in tracker.operations
                    if op.resource_id == lc.resource_id
                ]
            }
            for lc in tracker.lifecycles.values()
        ],
        "issues": [
            {
                "type": issue.issue_type,
                "severity": issue.severity,
                "resource_id": issue.resource_id,
                "description": issue.message,
                "event_ids": issue.event_ids,
                "recommendation": issue.suggestion
            }
            for issue in issues
        ],
        "summary": {
            "total_rts": len(tracker.lifecycles),
            "total_issues": len(issues),
            "total_clears": sum(lc.total_clears for lc in tracker.lifecycles.values()),
            "total_binds": sum(lc.total_binds for lc in tracker.lifecycles.values())
        }
    }
    
    # Create sample texture data
    textures = [
        {
            "id": "1",
            "name": "TestTexture",
            "width": 512,
            "height": 512,
            "format": "R8G8B8A8_UNORM",
            "mips": 1,
            "thumbnail": ""
        }
    ]
    
    # Generate report with RT data
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'test_rt_integration.html')
    
    generate_offline_html(
        textures=textures,
        rdc_name="test_rt_integration.rdc",
        output_path=output_path,
        rt_tracking_data=rt_data
    )
    
    # Verify the output
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that RT Timeline components are present
    checks = [
        ("rt-timeline-panel", "RT Timeline panel"),
        ("RT_Main", "Main RT data"),
        ("RT_PostFX", "PostFX RT data"),
        ("toggleRTTimelinePanel", "Toggle function"),
    ]
    
    all_passed = True
    for pattern, name in checks:
        if pattern in content:
            print(f"[OK] Found: {name}")
        else:
            print(f"[FAIL] Missing: {name}")
            all_passed = False
    
    # Check for issues
    if "redundant_clear" in content.lower() or "Redundant" in content:
        print("[OK] Found: Redundant clear issue")
    else:
        print("[WARN] Redundant clear issue may not be visible in timeline")
    
    if all_passed:
        print(f"\n[SUCCESS] Integration test passed!")
        print(f"Report generated: {output_path}")
    else:
        print(f"\n[FAIL] Some checks failed")
        return False
    
    return True


if __name__ == "__main__":
    success = test_rt_integration()
    sys.exit(0 if success else 1)
