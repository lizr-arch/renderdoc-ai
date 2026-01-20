# -*- coding: utf-8 -*-
"""
Resource Inspector Test Script
==============================

This script can be executed within RenderDoc's Python environment to test
the ResourceInspector functionality.

Usage in RenderDoc Python Shell:
    exec(open('d:/Code/git/renderdoc/scripts/rdc_analyzer/tests/test_resource_inspector.py').read())
"""

import sys
import os

# Add module path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def test_buffer_format_parser():
    """Test BufferFormatParser without RenderDoc dependency"""
    import struct
    from core.resource_inspector import BufferFormatParser, format_buffer_preview
    
    print("\n" + "="*60)
    print("TEST: BufferFormatParser")
    print("="*60)
    
    parser = BufferFormatParser()
    
    # Test 1: Float parsing
    print("\n[Test 1] Float4 parsing...")
    float_data = struct.pack('<8f', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    result = parser.parse_as_floats(float_data, 4)
    assert len(result) == 2, f"Expected 2 vectors, got {len(result)}"
    assert result[0] == (1.0, 2.0, 3.0, 4.0), f"Unexpected values: {result[0]}"
    print("  PASSED: Float4 parsing works correctly")
    
    # Test 2: Index parsing (16-bit)
    print("\n[Test 2] 16-bit index parsing...")
    index_data = struct.pack('<6H', 0, 1, 2, 3, 4, 5)
    indices = parser.parse_as_indices(index_data, 'R16_UINT')
    assert indices == [0, 1, 2, 3, 4, 5], f"Unexpected indices: {indices}"
    print("  PASSED: 16-bit index parsing works correctly")
    
    # Test 3: Index parsing (32-bit)
    print("\n[Test 3] 32-bit index parsing...")
    index_data32 = struct.pack('<3I', 100, 200, 300)
    indices32 = parser.parse_as_indices(index_data32, 'R32_UINT')
    assert indices32 == [100, 200, 300], f"Unexpected indices: {indices32}"
    print("  PASSED: 32-bit index parsing works correctly")
    
    # Test 4: Vertex buffer parsing
    print("\n[Test 4] Vertex buffer parsing...")
    vertex_data = b''
    for i in range(5):
        vertex_data += struct.pack('<3f', float(i), 0.0, 0.0)  # Position
        vertex_data += struct.pack('<2f', float(i)/10, 0.5)     # UV
    
    layout = [
        {'name': 'POSITION', 'format': 'R32G32B32_FLOAT', 'offset': 0},
        {'name': 'TEXCOORD', 'format': 'R32G32_FLOAT', 'offset': 12},
    ]
    vertices = parser.parse_vertex_buffer(vertex_data, layout)
    assert len(vertices) == 5, f"Expected 5 vertices, got {len(vertices)}"
    assert vertices[2]['POSITION'][0] == 2.0, f"Unexpected position: {vertices[2]['POSITION']}"
    print("  PASSED: Vertex buffer parsing works correctly")
    
    # Test 5: Constant buffer parsing
    print("\n[Test 5] Constant buffer parsing...")
    identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
    cb_data = struct.pack('<16f', *identity)
    cb_data += struct.pack('<4f', 1.0, 0.5, 0.25, 1.0)
    
    cb_layout = [
        {'name': 'WorldMatrix', 'type': 'float4x4', 'offset': 0},
        {'name': 'Color', 'type': 'float4', 'offset': 64},
    ]
    constants = parser.parse_constant_buffer(cb_data, cb_layout)
    assert constants['WorldMatrix'][0][0] == 1.0, f"Matrix error"
    assert constants['Color'][1] == 0.5, f"Color error"
    print("  PASSED: Constant buffer parsing works correctly")
    
    # Test 6: Hex dump
    print("\n[Test 6] Hex dump generation...")
    hex_output = parser.hex_dump(b'\x00\x01\x02\x03\x41\x42\x43\x44', max_lines=2)
    assert '00 01 02 03' in hex_output
    assert 'ABCD' in hex_output
    print("  PASSED: Hex dump generation works correctly")
    
    print("\n" + "="*60)
    print("ALL BUFFER FORMAT PARSER TESTS PASSED!")
    print("="*60)
    return True


def _run_resource_inspector_with_replay(controller):
    """Test ResourceInspector with a real RenderDoc controller (internal helper)"""
    from core.resource_inspector import (
        ResourceInspector, ResourceType, BufferFormatParser
    )
    
    print("\n" + "="*60)
    print("TEST: ResourceInspector with ReplayController")
    print("="*60)
    
    inspector = ResourceInspector(controller)
    
    # Test 1: List all resources
    print("\n[Test 1] Listing all resources...")
    all_resources = inspector.list_resources()
    print(f"  Found {len(all_resources)} total resources")
    
    # Test 2: List buffers only
    print("\n[Test 2] Listing buffers only...")
    buffers = inspector.list_resources(ResourceType.BUFFER)
    print(f"  Found {len(buffers)} buffers")
    
    if buffers:
        # Show first 5 buffers
        print("\n  First 5 buffers:")
        for buf in buffers[:5]:
            print(f"    ID: {buf.resource_id}, Size: {buf.size:,} bytes, Name: {buf.name}")
    
    # Test 3: List textures
    print("\n[Test 3] Listing textures...")
    textures = [r for r in all_resources if r.resource_type != ResourceType.BUFFER]
    print(f"  Found {len(textures)} textures")
    
    if textures:
        print("\n  First 5 textures:")
        for tex in textures[:5]:
            dims = f"{tex.width}x{tex.height}"
            print(f"    ID: {tex.resource_id}, Dims: {dims}, Format: {tex.format}")
    
    # Test 4: Read buffer data
    if buffers:
        print("\n[Test 4] Reading buffer data...")
        test_buffer = buffers[0]
        
        # Get first draw event
        draw_events = controller.GetDrawcalls()
        if draw_events:
            first_event = draw_events[0].eventId
        else:
            first_event = 1
            
        buffer_data = inspector.get_buffer_data(test_buffer.resource_id, first_event)
        
        if buffer_data:
            print(f"  Read {buffer_data.size:,} bytes from buffer {test_buffer.resource_id}")
            
            # Show hex dump preview
            parser = BufferFormatParser()
            print("\n  First 64 bytes:")
            print(parser.hex_dump(buffer_data.data[:64], max_lines=4))
        else:
            print("  [WARN] Could not read buffer data")
    
    # Test 5: Read texture data
    if textures:
        print("\n[Test 5] Reading texture data...")
        test_texture = textures[0]
        
        draw_events = controller.GetDrawcalls()
        if draw_events:
            first_event = draw_events[0].eventId
        else:
            first_event = 1
            
        texture_data = inspector.get_texture_data(test_texture.resource_id, first_event)
        
        if texture_data:
            print(f"  Read {len(texture_data.data):,} bytes from texture {test_texture.resource_id}")
            print(f"  Dimensions: {texture_data.width}x{texture_data.height}")
            print(f"  Format: {texture_data.format}")
        else:
            print("  [WARN] Could not read texture data (may be expected for some formats)")
    
    print("\n" + "="*60)
    print("RESOURCE INSPECTOR TESTS COMPLETED!")
    print("="*60)
    return True


def run_standalone_tests():
    """Run tests that don't require RenderDoc"""
    print("\n" + "#"*60)
    print("# RESOURCE INSPECTOR STANDALONE TESTS")
    print("#"*60)
    
    try:
        test_buffer_format_parser()
        print("\n[SUCCESS] All standalone tests passed!")
        return True
    except Exception as e:
        print(f"\n[FAILED] Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_replay_tests(rdc_path=None):
    """Run tests with a real RDC file"""
    try:
        import renderdoc as rd
    except ImportError:
        print("[ERROR] renderdoc module not available")
        print("Run this script within RenderDoc's Python environment")
        return False
    
    print("\n" + "#"*60)
    print("# RESOURCE INSPECTOR REPLAY TESTS")
    print("#"*60)
    
    if rdc_path is None:
        # Try to find an RDC file
        search_paths = [
            'd:/Code/git/renderdoc/Resource/Game_x64h_2026.01.07_05.35.50_frame3996.rdc',
            os.path.expanduser('~/Documents/RenderDoc/*.rdc'),
        ]
        for path in search_paths:
            if os.path.exists(path):
                rdc_path = path
                break
    
    if rdc_path is None or not os.path.exists(rdc_path):
        print(f"[ERROR] No RDC file found")
        return False
    
    print(f"\nLoading: {rdc_path}")
    
    # Open capture
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_path, '', None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to open file: {status}")
        return False
    
    if not cap.LocalReplaySupport():
        print("[ERROR] Capture does not support local replay")
        cap.Shutdown()
        return False
    
    # Create replay controller
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    if result[0] != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to create replay: {result[0]}")
        cap.Shutdown()
        return False
    
    controller = result[1]
    
    try:
        _run_resource_inspector_with_replay(controller)
        print("\n[SUCCESS] All replay tests passed!")
        return True
    except Exception as e:
        print(f"\n[FAILED] Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        controller.Shutdown()
        cap.Shutdown()


# =============================================================================
# pytest-compatible Test Classes
# =============================================================================

import pytest


class TestBufferFormatParser:
    """pytest wrapper for BufferFormatParser tests."""
    
    def test_buffer_format_parser(self):
        """Run the standalone buffer format parser tests."""
        assert test_buffer_format_parser() is True


class TestResourceInspectorReplay:
    """pytest wrapper for replay-dependent tests (skipped by default)."""
    
    @pytest.mark.skip(reason="Requires RenderDoc Python environment with live controller")
    def test_resource_inspector_with_replay(self):
        """This test requires a real RenderDoc controller, skip in CI."""
        pass


# =============================================================================
# Standalone execution entry point
# =============================================================================

if __name__ == '__main__':
    import sys
    
    # Run standalone tests first
    standalone_ok = run_standalone_tests()
    
    # Try replay tests if possible
    if '--replay' in sys.argv or len(sys.argv) > 1:
        rdc_path = None
        for arg in sys.argv[1:]:
            if arg.endswith('.rdc') and os.path.exists(arg):
                rdc_path = arg
                break
        run_replay_tests(rdc_path)
    elif standalone_ok:
        print("\n[INFO] Run with --replay or an RDC file path to test with real data")
