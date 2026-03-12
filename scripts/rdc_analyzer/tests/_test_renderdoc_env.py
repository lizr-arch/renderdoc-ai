#!/usr/bin/env python3
"""Test script to verify RenderDoc Python environment.

This script should be run inside RenderDoc's Python environment:
    qrenderdoc.exe --python scripts/rdc_analyzer/tests/_test_renderdoc_env.py

Or from RenderDoc's Python Shell (Ctrl+P).
"""
import sys
import os

def main():
    print("=" * 60)
    print("RenderDoc Python Environment Check")
    print("=" * 60)
    
    # 1. Check Python version
    print(f"\n[1] Python Version: {sys.version}")
    
    # 2. Check renderdoc module
    print("\n[2] Checking renderdoc module...")
    try:
        import renderdoc as rd
        attrs = [a for a in dir(rd) if not a.startswith('_')]
        print(f"    - Module loaded: YES")
        print(f"    - Available attributes: {len(attrs)}")
        
        # Key classes we need
        key_classes = [
            'OpenCaptureFile', 'CaptureFile', 'ReplayController',
            'ReplayOptions', 'GetLogFile', 'ResourceId'
        ]
        for cls in key_classes:
            has_it = hasattr(rd, cls)
            status = "✓" if has_it else "✗"
            print(f"    - {status} rd.{cls}")
            
    except ImportError as e:
        print(f"    - Module loaded: NO")
        print(f"    - Error: {e}")
        return 1
    
    # 3. Check qrenderdoc module (if in GUI mode)
    print("\n[3] Checking qrenderdoc module...")
    try:
        import qrenderdoc as qrd
        attrs = [a for a in dir(qrd) if not a.startswith('_')]
        print(f"    - Module loaded: YES")
        print(f"    - Available attributes: {len(attrs)}")
    except ImportError as e:
        print(f"    - Module loaded: NO (expected if running headless)")
        print(f"    - Error: {e}")
    
    # 4. Test opening a capture file (if path provided)
    print("\n[4] Capture file test...")
    if len(sys.argv) > 1:
        rdc_path = sys.argv[1]
        print(f"    - Testing file: {rdc_path}")
        try:
            cap = rd.OpenCaptureFile()
            result = cap.OpenFile(rdc_path, "", None)
            if result == rd.ResultCode.Succeeded:
                print(f"    - Open result: SUCCESS")
                print(f"    - Driver: {cap.DriverName()}")
                print(f"    - API: {cap.APIProps().pipelineType}")
                cap.Shutdown()
            else:
                print(f"    - Open result: FAILED ({result})")
        except Exception as e:
            print(f"    - Error: {e}")
    else:
        print("    - No RDC file provided, skipping")
        print("    - Usage: script.py <path_to.rdc>")
    
    print("\n" + "=" * 60)
    print("Environment check complete!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
