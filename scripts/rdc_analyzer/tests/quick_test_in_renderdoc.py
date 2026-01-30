# -*- coding: utf-8 -*-
"""
Quick Test for RenderDoc Python Shell
======================================

Copy and paste this entire script into RenderDoc's Python Shell
(Window -> Python Shell) after loading an RDC file.

Or run from the command line in demo mode to verify parsing works.
"""

# === PASTE START ===

import sys
import os

# Setup path
script_path = 'd:/Code/git/renderdoc/scripts/rdc_analyzer'
if script_path not in sys.path:
    sys.path.insert(0, script_path)

print("="*60)
print("RDC Analyzer - Resource Inspector Quick Test")
print("="*60)

# Import our modules
try:
    from core.resource_inspector import (
        ResourceInspector, ResourceType, BufferFormatParser, format_buffer_preview
    )
    print("[OK] Imported resource_inspector module")
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    raise

# Check if we have a controller (only available in RenderDoc)
try:
    # pyrenderdoc is available in RenderDoc's Python shell
    import renderdoc as rd
    
    # Get controller from current context
    if 'pyrenderdoc' in dir():
        ctx = pyrenderdoc
        controller = ctx.Replay().GetController()
        print("[OK] Got ReplayController from RenderDoc context")
        HAS_CONTROLLER = True
    else:
        HAS_CONTROLLER = False
        print("[INFO] Not running in RenderDoc GUI, will use standalone tests")
except ImportError:
    HAS_CONTROLLER = False
    print("[INFO] renderdoc module not available, will use standalone tests")

# Run tests
def run_quick_test():
    parser = BufferFormatParser()
    
    print("\n--- Test 1: Hex Dump ---")
    test_bytes = bytes(range(32))
    print(parser.hex_dump(test_bytes, max_lines=2))
    
    print("\n--- Test 2: Float Parsing ---")
    import struct
    float_data = struct.pack('<4f', 1.0, 2.0, 3.0, 4.0)
    result = parser.parse_as_floats(float_data, 4)
    print(f"Parsed float4: {result[0]}")
    
    print("\n--- Test 3: Index Parsing ---")
    index_data = struct.pack('<6H', 0, 1, 2, 3, 4, 5)
    indices = parser.parse_as_indices(index_data, 'R16_UINT')
    print(f"Parsed indices: {indices}")
    
    print("\n[OK] All quick tests passed!")

run_quick_test()

# If we have a controller, test with real data
if HAS_CONTROLLER:
    print("\n--- Real Data Test ---")
    inspector = ResourceInspector(controller)
    
    # List resources
    all_res = inspector.list_resources()
    buffers = [r for r in all_res if r.resource_type == ResourceType.BUFFER]
    textures = [r for r in all_res if r.resource_type != ResourceType.BUFFER]
    
    print(f"Found {len(buffers)} buffers, {len(textures)} textures")
    
    if buffers:
        print("\nFirst 3 buffers:")
        for b in buffers[:3]:
            print(f"  [{b.resource_id}] {b.name} - {b.size:,} bytes")
    
    if textures:
        print("\nFirst 3 textures:")
        for t in textures[:3]:
            print(f"  [{t.resource_id}] {t.name} - {t.width}x{t.height} {t.format}")

print("\n" + "="*60)
print("Test Complete!")
print("="*60)

# === PASTE END ===
