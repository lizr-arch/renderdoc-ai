#!/usr/bin/env python3
"""
完整的 RDC 兼容性修改脚本

修改内容：
1. 禁用 VRS feature flag (pipelineFragmentShadingRate = 0)
2. 移除 VK_KHR_fragment_shading_rate 扩展
3. 将 memoryTypeIndex 5 改为 4 (兼容 RTX 4070 Ti)

用法: py -3 fix_rdc_compatibility.py <input.zip.xml> <output_prefix>
"""

import re
import os
import sys
import shutil


def fix_xml(input_xml: str, output_xml: str) -> dict:
    """修改 XML 文件"""
    
    stats = {}
    
    print(f'[1/3] 读取 XML 文件: {input_xml}')
    print(f'      文件大小: {os.path.getsize(input_xml) / 1024 / 1024:.1f} MB')
    
    with open(input_xml, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f'      读取完成, {len(content):,} 字符')
    
    print(f'\n[2/3] 应用修改...')
    
    # 修改 1: 禁用 VRS feature flag
    pattern1 = r'(<uint name="pipelineFragmentShadingRate"[^>]*>)1(</uint>)'
    content, n1 = re.subn(pattern1, r'\g<1>0\2', content)
    stats['pipelineFragmentShadingRate'] = n1
    print(f'      [VRS] pipelineFragmentShadingRate 1->0: {n1} 处')
    
    # 修改 2: 移除 VK_KHR_fragment_shading_rate 扩展
    pattern2 = r'\s*<string typename="string">VK_KHR_fragment_shading_rate</string>\s*'
    content, n2 = re.subn(pattern2, '\n', content)
    stats['VK_KHR_fragment_shading_rate_removed'] = n2
    print(f'      [VRS] 移除 VK_KHR_fragment_shading_rate 扩展: {n2} 处')
    
    # 修改 3: 如果移除了扩展，需要更新 enabledExtensionCount
    if n2 > 0:
        # 找到值为 5 的 enabledExtensionCount 并减 1
        pattern3 = r'(<uint name="enabledExtensionCount"[^>]*>)5(</uint>)'
        content, n3 = re.subn(pattern3, r'\g<1>4\2', content, count=1)
        stats['enabledExtensionCount_adjusted'] = n3
        print(f'      [VRS] enabledExtensionCount 5->4: {n3} 处')
    
    # 修改 4: 将 memoryTypeIndex 5 改为 4 (RTX 4070 兼容)
    pattern4 = r'(<uint name="memoryTypeIndex"[^>]*>)5(</uint>)'
    content, n4 = re.subn(pattern4, r'\g<1>4\2', content)
    stats['memoryTypeIndex_5_to_4'] = n4
    print(f'      [Memory] memoryTypeIndex 5->4: {n4} 处')
    
    print(f'\n[3/3] 写入修改后的 XML: {output_xml}')
    with open(output_xml, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'      写入完成, {os.path.getsize(output_xml) / 1024 / 1024:.1f} MB')
    
    return stats


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print(f'\n用法: py -3 {sys.argv[0]} <input.zip.xml> <output_prefix>')
        print(f'示例: py -3 {sys.argv[0]} capture.zip.xml capture_fixed')
        sys.exit(1)
    
    input_xml = sys.argv[1]
    output_prefix = sys.argv[2]
    
    if not os.path.exists(input_xml):
        print(f'错误: 输入文件不存在: {input_xml}')
        sys.exit(1)
    
    # 推断 ZIP 文件路径
    if input_xml.endswith('.zip.xml'):
        input_zip = input_xml.replace('.zip.xml', '.zip')
    else:
        print(f'错误: 输入文件必须是 .zip.xml 格式')
        sys.exit(1)
    
    if not os.path.exists(input_zip):
        print(f'错误: 配套 ZIP 文件不存在: {input_zip}')
        sys.exit(1)
    
    output_xml = f'{output_prefix}.zip.xml'
    output_zip = f'{output_prefix}.zip'
    
    print('=' * 60)
    print('RDC 兼容性修复工具')
    print('=' * 60)
    print(f'输入 XML: {input_xml}')
    print(f'输入 ZIP: {input_zip}')
    print(f'输出 XML: {output_xml}')
    print(f'输出 ZIP: {output_zip}')
    print('=' * 60)
    
    # 修改 XML
    stats = fix_xml(input_xml, output_xml)
    
    # 复制 ZIP
    print(f'\n复制 ZIP 文件...')
    shutil.copy2(input_zip, output_zip)
    print(f'复制完成: {output_zip}')
    
    print(f'\n' + '=' * 60)
    print('修改统计:')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    print('=' * 60)
    print(f'\n下一步: 使用 renderdoccmd 将 {output_xml} 转换回 RDC:')
    print(f'  renderdoccmd convert -f {output_xml} -i zip.xml -o {output_prefix}.rdc -c rdc')


if __name__ == '__main__':
    main()
