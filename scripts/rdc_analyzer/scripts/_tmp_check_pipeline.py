import json
import os

json_path = os.path.join(os.path.dirname(__file__), '..', 'output', 'e2e_test', 'capture_data.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Top-level keys: {list(data.keys())}")
print(f"Events count: {len(data.get('events', []))}")

# Check first few events structure
for i, e in enumerate(data.get('events', [])[:10]):
    if isinstance(e, dict):
        name = e.get('name', 'unnamed')[:50]
        print(f"\nEvent {i}: {name}")
        if 'pipelineState' in e:
            ps = e['pipelineState']
            vp = ps.get('viewport') if ps else None
            if vp:
                print(f"  Viewport: {vp.get('width', 0)}x{vp.get('height', 0)}")
            else:
                print(f"  Viewport: None")
    elif isinstance(e, list):
        print(f"\nEvent {i}: list with {len(e)} items")