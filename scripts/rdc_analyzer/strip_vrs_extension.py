#!/usr/bin/env python3
"""
移除 RDC 中的 VK_KHR_fragment_shading_rate 扩展依赖

用法: py -3 strip_vrs_extension.py
"""

import re
import os
import shutil

INPUT_XML = r'D:\backup\scene209_novrs.zip.xml'
OUTPUT_XML = r'D:\backup\scene209_novrs2.zip.xml'
INPUT_ZIP = r'D:\backup\scene209_novrs.zip'
OUTPUT_ZIP = r'D:\backup\scene209_novrs2.zip'


def main():
    print('=' * 60)
    print('Strip VRS Extension from RDC XML')
    print('=' * 60)
    
    print(f'\n[1/4] 读取 XML 文件: {INPUT_XML}')
    print(f'      文件大小: {os.path.getsize(INPUT_XML) / 1024 / 1024:.1f} MB')
    
    with open(INPUT_XML, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f'      读取完成, {len(content):,} 字符')
    
    print(f'\n[2/4] 修改 XML...')
    
    # 1. 移除 VK_KHR_fragment_shading_rate 扩展行
    pattern1 = r'\s*<string typename="string">VK_KHR_fragment_shading_rate</string>\s*'
    content, n1 = re.subn(pattern1, '\n', content)
    print(f'      移除 VK_KHR_fragment_shading_rate 扩展行: {n1} 处')
    
    # 2. 将 enabledExtensionCount 从 5 改为 4
    pattern2 = r'(<uint name="enabledExtensionCount"[^>]*>)5(</uint>)'
    content, n2 = re.subn(pattern2, r'\g<1>4\2', content, count=1)
    print(f'      修改 enabledExtensionCount 5->4: {n2} 处')
    
    # 3. 确保 pipelineFragmentShadingRate = 0
    pattern3 = r'(<uint name="pipelineFragmentShadingRate"[^>]*>)1(</uint>)'
    content, n3 = re.subn(pattern3, r'\g<1>0\2', content)
    print(f'      修改 pipelineFragmentShadingRate 1->0: {n3} 处')
    
    print(f'\n[3/4] 写入修改后的 XML: {OUTPUT_XML}')
    with open(OUTPUT_XML, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'      写入完成, {os.path.getsize(OUTPUT_XML) / 1024 / 1024:.1f} MB')
    
    print(f'\n[4/4] 复制 ZIP 文件...')
    shutil.copy2(INPUT_ZIP, OUTPUT_ZIP)
    print(f'      复制完成: {OUTPUT_ZIP}')
    
    print(f'\n' + '=' * 60)
    print('完成!')
    print(f'输出 XML: {OUTPUT_XML}')
    print(f'输出 ZIP: {OUTPUT_ZIP}')
    print('=' * 60)


if __name__ == '__main__':
    main()
