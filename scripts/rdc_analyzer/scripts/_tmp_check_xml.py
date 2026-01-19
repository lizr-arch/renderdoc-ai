#!/usr/bin/env python3
"""临时脚本：检查完整的 binding_records 为什么没被正确解析"""

import sys
sys.path.insert(0, '.')
from parse_rdc_xml import parse_rdc_xml, parse_pipeline_state_from_binding_records, parse_shader_from_params
import json

# 解析 XML
data = parse_rdc_xml('output/e2e_test/capture.xml')

# 找第一个 Draw 事件
draw = next(e for e in data['events'] if e.get('type') == 'draw')

print('=== First Draw Event ===')
print(f"EventId: {draw['eventId']}")
print(f"ChunkId: {draw['chunkId']}")

# 检查 pipelineState
ps = draw['pipelineState']
print(f"\n=== Pipeline State ===")
print(f"Viewport: {ps['viewport']}")
print(f"VS: {ps['shaders']['vs']}")
print(f"PS: {ps['shaders']['ps']}")

# 保存完整 JSON 以便分析
with open('output/e2e_test/_debug_first_draw.json', 'w') as f:
    json.dump(draw, f, indent=2, ensure_ascii=False)
print(f"\nSaved draw event to output/e2e_test/_debug_first_draw.json")