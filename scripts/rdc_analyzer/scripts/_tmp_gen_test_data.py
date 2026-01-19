"""生成有实际可见内容的测试纹理数据"""
from PIL import Image
import base64
from io import BytesIO
import json
from pathlib import Path

# 生成不同颜色的测试纹理
textures = []
test_cases = [
    (101, "DiffuseTexture_001", "BC7_UNORM", (255, 100, 100), 2048, 2048),
    (102, "NormalMap_Brick", "BC5_UNORM", (128, 128, 255), 1024, 1024),
    (103, "AlbedoMap_Metal", "R8G8B8A8_SRGB", (200, 200, 200), 512, 512),
    (104, "ShadowMap_Cascaded", "D32_FLOAT", (50, 50, 50), 4096, 4096),
    (105, "HDREnvMap_Sky", "R16G16B16A16_FLOAT", (135, 206, 235), 1024, 512),
]

for res_id, name, fmt, color, w, h in test_cases:
    # 创建 128x128 的彩色缩略图
    img = Image.new('RGB', (128, 128), color)
    
    # 添加一些纹理变化（简单的棋盘格）
    for x in range(0, 128, 16):
        for y in range(0, 128, 16):
            if (x // 16 + y // 16) % 2 == 0:
                for px in range(x, min(x+16, 128)):
                    for py in range(y, min(y+16, 128)):
                        r, g, b = color
                        img.putpixel((px, py), (r//2, g//2, b//2))
    
    # 转换为 base64
    buf = BytesIO()
    img.save(buf, 'PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    
    textures.append({
        "id": res_id,
        "name": name,
        "format": fmt,
        "width": w,
        "height": h,
        "depth": 1,
        "mips": 11,
        "arrayLayers": 1 if "EnvMap" not in name else 6,
        "thumbnail": f"data:image/png;base64,{b64}"
    })

# 保存到测试目录
output_path = Path(__file__).parent.parent / "test_captures" / "test_game_textures" / "textures.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(textures, f, indent=2)

print(f"[OK] Generated {len(textures)} test textures to {output_path}")
