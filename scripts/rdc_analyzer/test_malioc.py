#!/usr/bin/env python3
"""测试 malioc 输出格式和解析器

这是一个独立执行的测试脚本，不是 pytest 测试用例。
请直接运行：py -3 test_malioc.py
"""
import sys
sys.path.insert(0, 'd:/Code/git/renderdoc/scripts/rdc_analyzer')

from rdc_parser import RDCParser
from mali_analyzer import MaliOfflineCompiler

if __name__ == "__main__":
    # 提取一个shader
    with RDCParser('D:/renderdoc/goog pixel-9/g145.rdc') as parser:
        parser.parse_header()
        shaders = parser.extract_vulkan_shaders()
        print(f"Found {len(shaders)} shaders")
        
        # 测试前几个 shader
        malioc = MaliOfflineCompiler()
        print(f"Mali Compiler: {malioc.version.split(chr(10))[0]}")
        
        for i in range(min(5, len(shaders))):
            spv = shaders[i].spirv_data
            metrics = malioc.analyze_spirv(spv, "Mali-G715")
            
            print(f"\n--- Shader {i} ({len(spv)} bytes) ---")
            print(f"  Type: {metrics.shader_type}")
            print(f"  GPU: {metrics.gpu_name}")
            print(f"  Work Registers: {metrics.work_registers}")
            print(f"  Uniform Registers: {metrics.uniform_registers}")
            print(f"  Total Cycles: {metrics.total_cycles:.2f}")
            print(f"  Shortest Path: {metrics.shortest_path:.2f}")
            print(f"  Longest Path: {metrics.longest_path:.2f}")
            print(f"  FMA/CVT/SFU: {metrics.fma_cycles:.2f}/{metrics.cvt_cycles:.2f}/{metrics.sfu_cycles:.2f}")
            print(f"  Load/Store: {metrics.load_store_cycles:.2f}")
            print(f"  Texture: {metrics.texture_cycles:.2f}")
            print(f"  Varying: {metrics.varying_cycles:.2f}")
            print(f"  Stack Spilling: {metrics.has_stack_spilling} ({metrics.spill_count})")
            print(f"  Parse Success: {metrics.parse_success}")
            if metrics.error_message:
                print(f"  Error: {metrics.error_message}")