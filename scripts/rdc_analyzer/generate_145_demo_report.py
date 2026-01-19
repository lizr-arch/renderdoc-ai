#!/usr/bin/env python3
"""
生成 145 纹理演示报告
使用模拟数据展示完整的 Milestone 3 功能：
- 去重检测 (Duplicate Detection)
- 纹理热度分析 (Usage Analysis)
- 优化建议 (Optimization Advisor)
"""

import os
import sys
import random
import hashlib
import base64
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_offline_report import generate_offline_html


def generate_placeholder_thumbnail(name: str, width: int, height: int) -> str:
    """
    生成 SVG 占位符缩略图 (Base64 Data URI)
    颜色基于名称哈希，模拟不同纹理的视觉区分
    """
    # 基于名称生成稳定的颜色
    hash_val = 0
    for c in name:
        hash_val = (hash_val * 31 + ord(c)) & 0xFFFFFFFF
    
    # 生成 HSL 颜色（色相变化，保持饱和度和亮度）
    hue = hash_val % 360
    saturation = 60 + (hash_val >> 8) % 20  # 60-80%
    lightness = 45 + (hash_val >> 16) % 15   # 45-60%
    
    # 生成 SVG
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect fill="hsl({hue},{saturation}%,{lightness}%)" width="128" height="128"/>
  <text x="64" y="58" text-anchor="middle" fill="rgba(255,255,255,0.9)" font-size="11" font-family="Arial">{width}×{height}</text>
  <text x="64" y="76" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-size="9" font-family="Arial">{name[:12]}</text>
</svg>'''
    
    encoded = base64.b64encode(svg_content.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{encoded}"


def generate_145_textures():
    """生成 145 个模拟纹理数据"""
    textures = []
    
    # 纹理类别模板
    categories = [
        # (前缀, 格式, 尺寸范围, 数量)
        ("T_Character_", "BC7_UNORM_SRGB", [(2048, 2048), (1024, 1024)], 20),   # 角色纹理
        ("T_Env_", "BC7_UNORM_SRGB", [(2048, 2048), (1024, 1024), (512, 512)], 25),  # 环境纹理
        ("T_UI_", "R8G8B8A8_UNORM_SRGB", [(512, 512), (256, 256), (128, 128)], 15),  # UI纹理
        ("T_VFX_", "BC3_UNORM_SRGB", [(512, 512), (256, 256)], 15),  # 特效纹理
        ("T_Terrain_", "BC7_UNORM", [(1024, 1024), (512, 512)], 12),  # 地形纹理
        ("T_Normal_", "BC5_UNORM", [(2048, 2048), (1024, 1024)], 18),  # 法线贴图
        ("T_ORM_", "BC7_UNORM", [(1024, 1024), (512, 512)], 15),  # ORM贴图
        ("T_Shadow_", "D32_FLOAT", [(2048, 2048), (4096, 4096)], 8),  # 阴影贴图
        ("T_LightMap_", "BC6H_UF16", [(1024, 1024), (512, 512)], 10),  # 光照贴图
        ("T_Misc_", "R8G8B8A8_UNORM", [(256, 256), (128, 128)], 7),  # 杂项
    ]
    
    tex_id = 1000
    all_textures = []
    
    for prefix, fmt, sizes, count in categories:
        for i in range(count):
            size = random.choice(sizes)
            suffix_type = random.choice(["_D", "_N", "_ORM", "_A", "_E", ""])
            name = f"{prefix}{i:02d}{suffix_type}"
            
            # 计算VRAM (根据格式)
            bpp_map = {
                "BC7_UNORM_SRGB": 1.0,
                "BC7_UNORM": 1.0,
                "BC3_UNORM_SRGB": 1.0,
                "BC5_UNORM": 1.0,
                "BC6H_UF16": 1.0,
                "R8G8B8A8_UNORM_SRGB": 4.0,
                "R8G8B8A8_UNORM": 4.0,
                "D32_FLOAT": 4.0,
            }
            bpp = bpp_map.get(fmt, 1.0)
            vram = int(size[0] * size[1] * bpp)
            
            # Mipmap 层数
            mip_levels = 1
            min_dim = min(size)
            full_mips = 0
            while min_dim > 1:
                full_mips += 1
                min_dim //= 2
            full_mips += 1
            
            # 随机决定是否有完整mipmap
            if random.random() < 0.7:
                mip_levels = full_mips
            elif random.random() < 0.5:
                mip_levels = random.randint(2, max(2, full_mips - 2))
            
            tex = {
                "id": tex_id,
                "name": name,
                "width": size[0],
                "height": size[1],
                "depth": 1,
                "mips": mip_levels,
                "format": fmt,
                "dimension": "Texture2D",
                "samples": 1,
                "usage_flags": "ShaderResource",
                "vram_bytes": vram,
                "thumbnail": generate_placeholder_thumbnail(name, size[0], size[1]),
            }
            all_textures.append(tex)
            tex_id += 1
    
    # 打乱顺序
    random.shuffle(all_textures)
    
    # 重新编号
    for i, tex in enumerate(all_textures):
        tex["id"] = 1000 + i
    
    return all_textures[:145]


def generate_duplicate_groups(textures):
    """生成模拟的重复纹理组"""
    groups = []
    
    # 创建5组重复纹理
    dup_configs = [
        (3, "Character Albedo duplicates"),    # 3个重复
        (4, "Environment Normal duplicates"),  # 4个重复
        (2, "UI Icon duplicates"),             # 2个重复
        (3, "Shadow map duplicates"),          # 3个重复
        (2, "VFX texture duplicates"),         # 2个重复
    ]
    
    used_indices = set()
    total_wasted = 0
    total_dup_count = 0
    
    for count, desc in dup_configs:
        # 选择未使用的纹理
        available = [i for i in range(len(textures)) if i not in used_indices]
        if len(available) < count:
            continue
            
        selected_indices = random.sample(available, count)
        used_indices.update(selected_indices)
        
        # 选第一个作为原始，其余作为重复
        original_idx = selected_indices[0]
        original = textures[original_idx]
        
        # 生成一个假的MD5哈希
        fake_hash = hashlib.md5(f"{desc}_{original['id']}".encode()).hexdigest()
        
        dup_textures = []
        wasted = 0
        for idx in selected_indices:
            tex = textures[idx]
            dup_textures.append({
                "resource_id": tex["id"],
                "name": tex["name"],
                "vram_bytes": tex["vram_bytes"],
            })
            if idx != original_idx:
                wasted += tex["vram_bytes"]
        
        groups.append({
            "fingerprint": fake_hash,
            "count": count,
            "textures": dup_textures,
            "wasted_bytes": wasted,
            "canonical_id": original["id"],
        })
        
        total_wasted += wasted
        total_dup_count += count - 1  # 不算原始的
    
    return {
        "duplicate_groups": groups,
        "total_duplicate_count": total_dup_count,
        "total_wasted_bytes": total_wasted,
        "unique_textures": len(textures) - total_dup_count,
        "metadata_only": False,
    }


def generate_usage_analysis(textures):
    """生成模拟的纹理使用热度分析"""
    usage_data = []
    
    for tex in textures:
        # 根据纹理类型分配不同的使用概率
        name = tex["name"]
        if "_Character_" in name:
            use_count = random.randint(50, 200)  # 高频使用
        elif "_UI_" in name:
            use_count = random.randint(100, 500)  # 非常高频
        elif "_Shadow_" in name:
            use_count = random.randint(20, 100)  # 中频
        elif "_VFX_" in name:
            use_count = random.randint(10, 80)   # 中低频
        elif "_Terrain_" in name:
            use_count = random.randint(30, 150)  # 中高频
        else:
            # 随机，包含一些未使用的
            if random.random() < 0.15:
                use_count = 0  # 未使用
            else:
                use_count = random.randint(5, 100)
        
        # 生成模拟的使用事件列表
        if use_count > 0:
            first_eid = random.randint(100, 5000)
            last_eid = random.randint(5000, 15000)
            # 生成随机的 Event ID 列表（模拟真实使用场景）
            num_events = min(use_count, random.randint(3, 15))
            used_events = sorted(random.sample(range(first_eid, last_eid + 1), min(num_events, last_eid - first_eid + 1)))
        else:
            first_eid = None
            last_eid = None
            used_events = []
        
        usage_data.append({
            "resource_id": tex["id"],
            "name": tex["name"],
            "use_count": use_count,
            "vram_bytes": tex["vram_bytes"],
            "estimated_size": tex["vram_bytes"],  # 兼容字段
            "first_use_event": first_eid,
            "last_use_event": last_eid,
            "used_in_events": used_events,
        })
    
    # 排序
    hot_list = sorted([u for u in usage_data if u["use_count"] > 0], 
                      key=lambda x: -x["use_count"])[:20]
    cold_list = sorted([u for u in usage_data if u["use_count"] == 0],
                       key=lambda x: -x["vram_bytes"])
    
    # 所有使用数据列表（用于 EID 标签显示）
    all_usage_list = [u for u in usage_data if u["use_count"] > 0]
    
    used = sum(1 for u in usage_data if u["use_count"] > 0)
    unused = len(usage_data) - used
    unused_vram = sum(u["vram_bytes"] for u in usage_data if u["use_count"] == 0)
    
    return {
        "hot_list": hot_list,
        "cold_list": cold_list,
        "all_usage_list": all_usage_list,  # 新增：包含所有有使用数据的纹理
        "used_textures": used,
        "unused_textures": unused,
        "unused_vram_bytes": unused_vram,
        "total_events": 15000,
        "usage_by_resource": {str(u["resource_id"]): u["use_count"] for u in usage_data},
    }


def format_matrix_value(rows, cols, base_values=None):
    """
    格式化矩阵值，模拟 RenderDoc 的 RowString 格式
    返回类似 "{1, 0, 0, 0}\n{0, 1, 0, 0}\n..." 的字符串
    """
    result_rows = []
    for r in range(rows):
        row_values = []
        for c in range(cols):
            if base_values:
                # 使用提供的值
                idx = r * cols + c
                if idx < len(base_values):
                    row_values.append(f"{base_values[idx]:.4g}")
                else:
                    row_values.append("0")
            else:
                # 默认单位矩阵
                row_values.append("1" if r == c else "0")
        result_rows.append("{" + ", ".join(row_values) + "}")
    return "\n".join(result_rows)


def format_vector_value(components, values):
    """格式化向量值，返回 (x, y, z, w) 格式"""
    formatted = [f"{v:.4g}" for v in values[:components]]
    while len(formatted) < components:
        formatted.append("0")
    return "(" + ", ".join(formatted) + ")"


class PassBindingState:
    """
    维护 Pass 级别的 GPU 绑定状态
    
    确保同一 Pass 内的所有 Draw/Dispatch 共享相同的 Pipeline、DescriptorSet 等句柄，
    使 relatedCalls 中的句柄与 pipelineState 保持一致。
    
    模拟 RenderDoc 从真实捕获中读取的状态连续性。
    """
    
    def __init__(self, api_type: str, pass_index: int, pass_shaders: list, pass_outputs: list):
        """
        初始化 Pass 绑定状态
        
        Args:
            api_type: "D3D11", "D3D12", "Vulkan", "OpenGL"
            pass_index: Pass 序号（用于生成稳定的句柄）
            pass_shaders: Pass 使用的 shader 列表
            pass_outputs: Pass 的渲染目标列表
        """
        self.api_type = api_type
        self.pass_index = pass_index
        
        # 使用 pass_index 生成稳定的句柄基址（而非随机）
        base_seed = pass_index * 0x1000
        
        if api_type == "Vulkan":
            self.command_buffer = f"0x{0x7F000000 + base_seed:08X}"
            self.pipeline = f"0x{0x7F100000 + base_seed:08X}"
            self.pipeline_layout = f"0x{0x7F110000 + base_seed:08X}"
            self.descriptor_sets = [f"0x{0x7F200000 + base_seed + i * 0x100:08X}" for i in range(4)]
            self.vertex_buffers = [f"0x{0x7F300000 + base_seed + i * 0x100:08X}" for i in range(2)]
            self.index_buffer = f"0x{0x7F400000 + base_seed:08X}"
            self.indirect_buffer = f"0x{0x7F500000 + base_seed:08X}"
            self.render_pass = f"0x{0x7F600000 + base_seed:08X}"
            self.framebuffer = f"0x{0x7F700000 + base_seed:08X}"
            
        elif api_type == "D3D12":
            self.command_list = f"0x{0x00010000 + base_seed:08X}"
            self.pipeline_state = f"0x{0x00020000 + base_seed:08X}"
            self.root_signature = f"0x{0x00030000 + base_seed:08X}"
            self.vertex_buffer_views = [
                {"buffer": f"0x{0x00040000 + base_seed + i * 0x100:08X}", "stride": 32, "size": 65536}
                for i in range(2)
            ]
            self.index_buffer_view = {
                "buffer": f"0x{0x00050000 + base_seed:08X}",
                "format": "R32_UINT",
                "size": 65536
            }
            self.descriptor_heaps = [f"0x{0x00060000 + base_seed + i * 0x100:08X}" for i in range(2)]
            
        elif api_type == "D3D11":
            self.device_context = f"0x{0x00010000 + base_seed:08X}"
            self.vertex_shader = pass_shaders[0]["id"] if pass_shaders else f"VS_{base_seed:04X}"
            self.pixel_shader = pass_shaders[1]["id"] if len(pass_shaders) > 1 else f"PS_{base_seed:04X}"
            self.input_layout = f"0x{0x00020000 + base_seed:08X}"
            self.vertex_buffers = [f"0x{0x00030000 + base_seed + i * 0x100:08X}" for i in range(2)]
            self.index_buffer = f"0x{0x00040000 + base_seed:08X}"
            self.constant_buffers = [f"0x{0x00050000 + base_seed + i * 0x100:08X}" for i in range(4)]
            self.shader_resources = [f"0x{0x00060000 + base_seed + i * 0x100:08X}" for i in range(8)]
            self.samplers = [f"0x{0x00070000 + base_seed + i * 0x100:08X}" for i in range(4)]
            self.render_targets = [rt["id"] for rt in pass_outputs]
            
        elif api_type == "OpenGL":
            self.program = base_seed + 1
            self.vao = base_seed + 100
            self.vertex_buffers = [base_seed + 200 + i for i in range(2)]
            self.index_buffer = base_seed + 300
            self.textures = [base_seed + 400 + i for i in range(8)]
            self.samplers = [base_seed + 500 + i for i in range(4)]
            self.framebuffer = base_seed + 600
    
    def get_draw_related_calls(self, is_indexed: bool, is_indirect: bool, is_instanced: bool = False) -> list:
        """
        生成 Draw 调用的关联状态调用列表
        
        根据 Draw 类型生成差异化的关联调用：
        - 标准 Draw: 仅 Pipeline + VertexBuffer
        - Indexed Draw: 增加 IndexBuffer 绑定
        - Indirect Draw: 增加 Indirect Buffer 相关调用
        - Instanced Draw: 增加实例化相关参数
        
        Args:
            is_indexed: 是否为索引绘制
            is_indirect: 是否为间接绘制
            is_instanced: 是否为实例化绘制
            
        Returns:
            list: 关联调用字符串列表（带详细参数）
        """
        # 生成随机但合理的参数值
        vb_offset_0 = random.randint(0, 4) * 1024  # 对齐到 1KB
        vb_offset_1 = random.randint(0, 2) * 512
        vb_stride_0 = random.choice([32, 44, 48, 52])  # 常见顶点大小
        vb_stride_1 = random.choice([12, 16, 32])  # 法线/UV 等
        ib_offset = random.randint(0, 8) * 256
        
        if self.api_type == "Vulkan":
            calls = [
                f"vkCmdBindPipeline(commandBuffer: {self.command_buffer}, pipelineBindPoint: VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline: {self.pipeline})",
            ]
            
            # Descriptor Sets - 根据调用类型显示不同数量
            num_sets = 2 if is_indirect else 1
            if num_sets == 1:
                calls.append(
                    f"vkCmdBindDescriptorSets(commandBuffer: {self.command_buffer}, pipelineBindPoint: VK_PIPELINE_BIND_POINT_GRAPHICS, "
                    f"layout: {self.pipeline_layout}, firstSet: 0, descriptorSetCount: 1, pDescriptorSets: [{self.descriptor_sets[0]}], "
                    f"dynamicOffsetCount: 0, pDynamicOffsets: NULL)"
                )
            else:
                calls.append(
                    f"vkCmdBindDescriptorSets(commandBuffer: {self.command_buffer}, pipelineBindPoint: VK_PIPELINE_BIND_POINT_GRAPHICS, "
                    f"layout: {self.pipeline_layout}, firstSet: 0, descriptorSetCount: 2, "
                    f"pDescriptorSets: [{self.descriptor_sets[0]}, {self.descriptor_sets[1]}], "
                    f"dynamicOffsetCount: 0, pDynamicOffsets: NULL)"
                )
            
            # Vertex Buffers - 详细显示 offset
            calls.append(
                f"vkCmdBindVertexBuffers(commandBuffer: {self.command_buffer}, firstBinding: 0, bindingCount: 2, "
                f"pBuffers: [{self.vertex_buffers[0]}, {self.vertex_buffers[1]}], "
                f"pOffsets: [{vb_offset_0}, {vb_offset_1}])"
            )
            
            # Index Buffer - 仅 Indexed 类型需要
            if is_indexed:
                calls.append(
                    f"vkCmdBindIndexBuffer(commandBuffer: {self.command_buffer}, buffer: {self.index_buffer}, "
                    f"offset: {ib_offset}, indexType: VK_INDEX_TYPE_UINT32)"
                )
            
            # Push Constants - Instanced 调用通常需要
            if is_instanced:
                calls.append(
                    f"vkCmdPushConstants(commandBuffer: {self.command_buffer}, layout: {self.pipeline_layout}, "
                    f"stageFlags: VK_SHADER_STAGE_VERTEX_BIT, offset: 0, size: 64, pValues: [instanceData])"
                )
            
            # Indirect Buffer - 仅 Indirect 类型特有
            if is_indirect:
                # Indirect 调用不直接绑定 buffer，但通常需要额外的 descriptor 更新
                calls.append(
                    f"vkCmdSetViewport(commandBuffer: {self.command_buffer}, firstViewport: 0, viewportCount: 1, "
                    f"pViewports: [{{x: 0, y: 0, width: 1920, height: 1080, minDepth: 0, maxDepth: 1}}])"
                )
                calls.append(
                    f"vkCmdSetScissor(commandBuffer: {self.command_buffer}, firstScissor: 0, scissorCount: 1, "
                    f"pScissors: [{{offset: {{0, 0}}, extent: {{1920, 1080}}}}])"
                )
            
            return calls
            
        elif self.api_type == "D3D12":
            calls = [
                f"SetPipelineState(pPipelineState: {self.pipeline_state})",
                f"SetGraphicsRootSignature(pRootSignature: {self.root_signature})",
                f"IASetPrimitiveTopology(PrimitiveTopology: D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST)",
            ]
            
            # Vertex Buffers - 详细参数
            calls.append(
                f"IASetVertexBuffers(StartSlot: 0, NumViews: 2, pViews: ["
                f"{{BufferLocation: {self.vertex_buffer_views[0]['buffer']}, SizeInBytes: {self.vertex_buffer_views[0]['size']}, StrideInBytes: {vb_stride_0}}}, "
                f"{{BufferLocation: {self.vertex_buffer_views[1]['buffer']}, SizeInBytes: {self.vertex_buffer_views[1]['size']}, StrideInBytes: {vb_stride_1}}}])"
            )
            
            # Index Buffer - 仅 Indexed
            if is_indexed:
                calls.append(
                    f"IASetIndexBuffer(pView: {{BufferLocation: {self.index_buffer_view['buffer']}, "
                    f"SizeInBytes: {self.index_buffer_view['size']}, Format: DXGI_FORMAT_R32_UINT}})"
                )
            
            # Descriptor Tables - Indirect 需要更多
            if is_indirect:
                calls.append(
                    f"SetGraphicsRootDescriptorTable(RootParameterIndex: 0, BaseDescriptor: {self.descriptor_heaps[0]})"
                )
                calls.append(
                    f"SetGraphicsRootDescriptorTable(RootParameterIndex: 1, BaseDescriptor: {self.descriptor_heaps[1]})"
                )
            else:
                calls.append(
                    f"SetGraphicsRootDescriptorTable(RootParameterIndex: 0, BaseDescriptor: {self.descriptor_heaps[0]})"
                )
            
            # Indirect 特有
            if is_indirect:
                calls.append(
                    f"RSSetViewports(NumViewports: 1, pViewports: [{{TopLeftX: 0, TopLeftY: 0, Width: 1920, Height: 1080, MinDepth: 0, MaxDepth: 1}}])"
                )
            
            return calls
            
        elif self.api_type == "D3D11":
            calls = [
                f"VSSetShader(pVertexShader: {self.vertex_shader}, ppClassInstances: NULL, NumClassInstances: 0)",
                f"PSSetShader(pPixelShader: {self.pixel_shader}, ppClassInstances: NULL, NumClassInstances: 0)",
                f"IASetInputLayout(pInputLayout: {self.input_layout})",
                f"IASetPrimitiveTopology(Topology: D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST)",
            ]
            
            # Vertex Buffers - 详细参数
            calls.append(
                f"IASetVertexBuffers(StartSlot: 0, NumBuffers: 2, "
                f"ppVertexBuffers: [{self.vertex_buffers[0]}, {self.vertex_buffers[1]}], "
                f"pStrides: [{vb_stride_0}, {vb_stride_1}], pOffsets: [{vb_offset_0}, {vb_offset_1}])"
            )
            
            # Index Buffer - 仅 Indexed
            if is_indexed:
                calls.append(
                    f"IASetIndexBuffer(pIndexBuffer: {self.index_buffer}, Format: DXGI_FORMAT_R32_UINT, Offset: {ib_offset})"
                )
            
            # Constant Buffers
            calls.append(
                f"VSSetConstantBuffers(StartSlot: 0, NumBuffers: 2, "
                f"ppConstantBuffers: [{self.constant_buffers[0]}, {self.constant_buffers[1]}])"
            )
            
            # Instanced 需要额外的 instance buffer
            if is_instanced:
                calls.append(
                    f"VSSetShaderResources(StartSlot: 0, NumViews: 1, ppShaderResourceViews: [{self.shader_resources[0]}])"
                )
            
            # Indirect 特有 - 通常涉及 UAV
            if is_indirect:
                calls.append(
                    f"CSSetUnorderedAccessViews(StartSlot: 0, NumUAVs: 1, "
                    f"ppUnorderedAccessViews: [{self.shader_resources[4]}], pUAVInitialCounts: [0])"
                )
            
            return calls
            
        elif self.api_type == "OpenGL":
            calls = [
                f"glUseProgram(program: {self.program})",
                f"glBindVertexArray(array: {self.vao})",
            ]
            
            # Vertex Buffers
            for i, vb in enumerate(self.vertex_buffers[:2]):
                offset = vb_offset_0 if i == 0 else vb_offset_1
                stride = vb_stride_0 if i == 0 else vb_stride_1
                calls.append(f"glBindVertexBuffer(bindingindex: {i}, buffer: {vb}, offset: {offset}, stride: {stride})")
            
            # Index Buffer - 仅 Indexed
            if is_indexed:
                calls.append(f"glBindBuffer(target: GL_ELEMENT_ARRAY_BUFFER, buffer: {self.index_buffer})")
            
            # Textures
            for i in range(min(2, len(self.textures))):
                calls.append(f"glBindTextureUnit(unit: {i}, texture: {self.textures[i]})")
            
            # Indirect - 绑定 indirect buffer
            if is_indirect:
                calls.append(f"glBindBuffer(target: GL_DRAW_INDIRECT_BUFFER, buffer: {self.pass_index * 1000 + 700})")
            
            return calls
        
        return []
    
    def get_dispatch_related_calls(self) -> list:
        """生成 Dispatch 调用的关联状态调用列表"""
        if self.api_type == "Vulkan":
            return [
                f"vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, {self.pipeline})",
                f"vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, {self.pipeline_layout}, 0, 1, &{self.descriptor_sets[0]}, 0, NULL)",
            ]
        elif self.api_type == "D3D12":
            return [
                f"SetPipelineState(pPipelineState: {self.pipeline_state})",
                f"SetComputeRootSignature(pRootSignature: {self.root_signature})",
            ]
        elif self.api_type == "D3D11":
            return [
                f"CSSetShader(pComputeShader: CS_{self.pass_index:04X}, NULL, 0)",
            ]
        elif self.api_type == "OpenGL":
            return [
                f"glUseProgram(program: {self.program})",
            ]
        return []


def generate_api_call(api_type, call_type, params, binding_state=None):
    """
    生成 API 调用指令字符串
    
    Args:
        api_type: "D3D11", "D3D12", "Vulkan", "OpenGL"
        call_type: "draw", "dispatch", "clear"
        params: 调用参数字典
        binding_state: PassBindingState 对象，提供一致的句柄（可选，向后兼容）
    
    Returns:
        dict: {
            "signature": 完整的函数签名,
            "params": 参数列表 [{name, value, type}],
            "returnType": 返回值类型,
            "relatedCalls": 相关的前置调用列表
        }
    """
    
    if api_type == "Vulkan":
        if call_type == "draw":
            # 优先使用传入的调用名称，确保 name 和 apiCall 一致
            call_name = params.get("callName", "")
            is_indexed = params.get("numIndices", 0) > 0 or "Indexed" in call_name
            is_instanced = params.get("numInstances", 1) > 1
            is_indirect = "Indirect" in call_name
            
            # 使用 binding_state 获取一致的句柄，否则回退到随机生成（向后兼容）
            if binding_state:
                cmd_buffer = binding_state.command_buffer
                indirect_buffer = binding_state.indirect_buffer
                related_calls = binding_state.get_draw_related_calls(is_indexed, is_indirect, is_instanced)
            else:
                # 向后兼容：无 binding_state 时使用随机句柄
                cmd_buffer = f"0x{random.randint(0x7F000000, 0x7FFFFFFF):08X}"
                indirect_buffer = f"0x{random.randint(0x7F500000, 0x7F5FFFFF):08X}"
                pipeline_handle = f"0x{random.randint(0x7F100000, 0x7F1FFFFF):08X}"
                desc_set_handle = f"0x{random.randint(0x7F200000, 0x7F2FFFFF):08X}"
                vb_handle = f"0x{random.randint(0x7F300000, 0x7F3FFFFF):08X}"
                ib_handle = f"0x{random.randint(0x7F400000, 0x7F4FFFFF):08X}"
                related_calls = [
                    f"vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, {pipeline_handle})",
                    f"vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, layout, 0, 1, &{desc_set_handle}, 0, NULL)",
                    f"vkCmdBindVertexBuffers(commandBuffer, 0, 1, &{vb_handle}, offsets)",
                ]
                if is_indexed:
                    related_calls.append(f"vkCmdBindIndexBuffer(commandBuffer, {ib_handle}, 0, VK_INDEX_TYPE_UINT32)")
            
            if is_indirect:
                # Indirect 调用：使用 VkBuffer 和 offset 代替直接参数
                # 参考: https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/vkCmdDrawIndexedIndirect.html
                if is_indexed:
                    func_name = "vkCmdDrawIndexedIndirect"
                else:
                    func_name = "vkCmdDrawIndirect"
                
                draw_count = random.randint(1, 16)  # 模拟批量绘制
                stride = 20 if is_indexed else 16  # VkDrawIndexedIndirectCommand=20, VkDrawIndirectCommand=16
                
                call_params = [
                    {"name": "commandBuffer", "value": cmd_buffer, "type": "VkCommandBuffer"},
                    {"name": "buffer", "value": indirect_buffer, "type": "VkBuffer"},
                    {"name": "offset", "value": "0", "type": "VkDeviceSize"},
                    {"name": "drawCount", "value": str(draw_count), "type": "uint32_t"},
                    {"name": "stride", "value": str(stride), "type": "uint32_t"},
                ]
                
            elif is_indexed:
                func_name = "vkCmdDrawIndexed"
                call_params = [
                    {"name": "commandBuffer", "value": cmd_buffer, "type": "VkCommandBuffer"},
                    {"name": "indexCount", "value": str(params.get("numIndices", 0)), "type": "uint32_t"},
                    {"name": "instanceCount", "value": str(params.get("numInstances", 1)), "type": "uint32_t"},
                    {"name": "firstIndex", "value": str(params.get("indexOffset", 0)), "type": "uint32_t"},
                    {"name": "vertexOffset", "value": str(params.get("baseVertex", 0)), "type": "int32_t"},
                    {"name": "firstInstance", "value": str(params.get("instanceOffset", 0)), "type": "uint32_t"},
                ]
                
            else:
                func_name = "vkCmdDraw"
                call_params = [
                    {"name": "commandBuffer", "value": cmd_buffer, "type": "VkCommandBuffer"},
                    {"name": "vertexCount", "value": str(params.get("numVertices", 0)), "type": "uint32_t"},
                    {"name": "instanceCount", "value": str(params.get("numInstances", 1)), "type": "uint32_t"},
                    {"name": "firstVertex", "value": "0", "type": "uint32_t"},
                    {"name": "firstInstance", "value": str(params.get("instanceOffset", 0)), "type": "uint32_t"},
                ]
            
            return {
                "signature": func_name,
                "params": call_params,
                "returnType": "void",
                "relatedCalls": related_calls,
            }
        
        elif call_type == "dispatch":
            # 使用 binding_state 获取一致的句柄
            if binding_state:
                cmd_buffer = binding_state.command_buffer
                related_calls = binding_state.get_dispatch_related_calls()
            else:
                cmd_buffer = f"0x{random.randint(0x7F000000, 0x7FFFFFFF):08X}"
                related_calls = [
                    f"vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, 0x{random.randint(0x7F100000, 0x7F1FFFFF):08X})",
                    f"vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, 1, &descSet, 0, NULL)",
                ]
            
            return {
                "signature": "vkCmdDispatch",
                "params": [
                    {"name": "commandBuffer", "value": cmd_buffer, "type": "VkCommandBuffer"},
                    {"name": "groupCountX", "value": str(params.get("groupCountX", 1)), "type": "uint32_t"},
                    {"name": "groupCountY", "value": str(params.get("groupCountY", 1)), "type": "uint32_t"},
                    {"name": "groupCountZ", "value": str(params.get("groupCountZ", 1)), "type": "uint32_t"},
                ],
                "returnType": "void",
                "relatedCalls": related_calls,
            }
        
        elif call_type == "clear":
            return {
                "signature": "vkCmdClearColorImage",
                "params": [
                    {"name": "commandBuffer", "value": f"0x{random.randint(0x7F000000, 0x7FFFFFFF):08X}", "type": "VkCommandBuffer"},
                    {"name": "image", "value": f"0x{random.randint(0x7F500000, 0x7F5FFFFF):08X}", "type": "VkImage"},
                    {"name": "imageLayout", "value": "VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL", "type": "VkImageLayout"},
                    {"name": "pColor", "value": "{0.0, 0.0, 0.0, 1.0}", "type": "VkClearColorValue*"},
                    {"name": "rangeCount", "value": "1", "type": "uint32_t"},
                    {"name": "pRanges", "value": "&subresourceRange", "type": "VkImageSubresourceRange*"},
                ],
                "returnType": "void",
                "relatedCalls": [],
            }
    
    elif api_type == "D3D12":
        if call_type == "draw":
            is_indexed = params.get("numIndices", 0) > 0
            
            if is_indexed:
                func_name = "DrawIndexedInstanced"
                call_params = [
                    {"name": "IndexCountPerInstance", "value": str(params.get("numIndices", 0)), "type": "UINT"},
                    {"name": "InstanceCount", "value": str(params.get("numInstances", 1)), "type": "UINT"},
                    {"name": "StartIndexLocation", "value": str(params.get("indexOffset", 0)), "type": "UINT"},
                    {"name": "BaseVertexLocation", "value": str(params.get("baseVertex", 0)), "type": "INT"},
                    {"name": "StartInstanceLocation", "value": str(params.get("instanceOffset", 0)), "type": "UINT"},
                ]
            else:
                func_name = "DrawInstanced"
                call_params = [
                    {"name": "VertexCountPerInstance", "value": str(params.get("numVertices", 0)), "type": "UINT"},
                    {"name": "InstanceCount", "value": str(params.get("numInstances", 1)), "type": "UINT"},
                    {"name": "StartVertexLocation", "value": "0", "type": "UINT"},
                    {"name": "StartInstanceLocation", "value": str(params.get("instanceOffset", 0)), "type": "UINT"},
                ]
            
            pso_handle = f"0x{random.randint(0x000001, 0x0000FF):08X}"
            root_sig = f"0x{random.randint(0x000100, 0x0001FF):08X}"
            
            return {
                "signature": f"ID3D12GraphicsCommandList::{func_name}",
                "params": call_params,
                "returnType": "void",
                "relatedCalls": [
                    f"SetPipelineState(pPipelineState: {pso_handle})",
                    f"SetGraphicsRootSignature(pRootSignature: {root_sig})",
                    f"IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST)",
                    f"IASetVertexBuffers(StartSlot: 0, NumViews: 1, pViews: &vbView)",
                    f"IASetIndexBuffer(pView: &ibView)" if is_indexed else None,
                ],
            }
        
        elif call_type == "dispatch":
            return {
                "signature": "ID3D12GraphicsCommandList::Dispatch",
                "params": [
                    {"name": "ThreadGroupCountX", "value": str(params.get("groupCountX", 1)), "type": "UINT"},
                    {"name": "ThreadGroupCountY", "value": str(params.get("groupCountY", 1)), "type": "UINT"},
                    {"name": "ThreadGroupCountZ", "value": str(params.get("groupCountZ", 1)), "type": "UINT"},
                ],
                "returnType": "void",
                "relatedCalls": [
                    f"SetComputeRootSignature(pRootSignature: 0x{random.randint(0x000100, 0x0001FF):08X})",
                    f"SetPipelineState(pPipelineState: 0x{random.randint(0x000001, 0x0000FF):08X})",
                ],
            }
    
    elif api_type == "D3D11":
        if call_type == "draw":
            is_indexed = params.get("numIndices", 0) > 0
            is_instanced = params.get("numInstances", 1) > 1
            
            if is_indexed and is_instanced:
                func_name = "DrawIndexedInstanced"
                call_params = [
                    {"name": "IndexCountPerInstance", "value": str(params.get("numIndices", 0)), "type": "UINT"},
                    {"name": "InstanceCount", "value": str(params.get("numInstances", 1)), "type": "UINT"},
                    {"name": "StartIndexLocation", "value": str(params.get("indexOffset", 0)), "type": "UINT"},
                    {"name": "BaseVertexLocation", "value": str(params.get("baseVertex", 0)), "type": "INT"},
                    {"name": "StartInstanceLocation", "value": str(params.get("instanceOffset", 0)), "type": "UINT"},
                ]
            elif is_indexed:
                func_name = "DrawIndexed"
                call_params = [
                    {"name": "IndexCount", "value": str(params.get("numIndices", 0)), "type": "UINT"},
                    {"name": "StartIndexLocation", "value": str(params.get("indexOffset", 0)), "type": "UINT"},
                    {"name": "BaseVertexLocation", "value": str(params.get("baseVertex", 0)), "type": "INT"},
                ]
            else:
                func_name = "Draw"
                call_params = [
                    {"name": "VertexCount", "value": str(params.get("numVertices", 0)), "type": "UINT"},
                    {"name": "StartVertexLocation", "value": "0", "type": "UINT"},
                ]
            
            return {
                "signature": f"ID3D11DeviceContext::{func_name}",
                "params": call_params,
                "returnType": "void",
                "relatedCalls": [
                    f"VSSetShader(pVertexShader: 0x{random.randint(0x7F000000, 0x7FFFFFFF):08X}, NULL, 0)",
                    f"PSSetShader(pPixelShader: 0x{random.randint(0x7F000000, 0x7FFFFFFF):08X}, NULL, 0)",
                    f"IASetInputLayout(pInputLayout: 0x{random.randint(0x7F000000, 0x7FFFFFFF):08X})",
                    f"IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST)",
                    f"IASetVertexBuffers(0, 1, &pVB, &stride, &offset)",
                    f"IASetIndexBuffer(pIB, DXGI_FORMAT_R32_UINT, 0)" if is_indexed else None,
                ],
            }
        
        elif call_type == "dispatch":
            return {
                "signature": "ID3D11DeviceContext::Dispatch",
                "params": [
                    {"name": "ThreadGroupCountX", "value": str(params.get("groupCountX", 1)), "type": "UINT"},
                    {"name": "ThreadGroupCountY", "value": str(params.get("groupCountY", 1)), "type": "UINT"},
                    {"name": "ThreadGroupCountZ", "value": str(params.get("groupCountZ", 1)), "type": "UINT"},
                ],
                "returnType": "void",
                "relatedCalls": [
                    f"CSSetShader(pComputeShader: 0x{random.randint(0x7F000000, 0x7FFFFFFF):08X}, NULL, 0)",
                ],
            }
    
    elif api_type == "OpenGL":
        if call_type == "draw":
            is_indexed = params.get("numIndices", 0) > 0
            is_instanced = params.get("numInstances", 1) > 1
            
            if is_indexed and is_instanced:
                func_name = "glDrawElementsInstanced"
                call_params = [
                    {"name": "mode", "value": "GL_TRIANGLES", "type": "GLenum"},
                    {"name": "count", "value": str(params.get("numIndices", 0)), "type": "GLsizei"},
                    {"name": "type", "value": "GL_UNSIGNED_INT", "type": "GLenum"},
                    {"name": "indices", "value": "(void*)0", "type": "void*"},
                    {"name": "instancecount", "value": str(params.get("numInstances", 1)), "type": "GLsizei"},
                ]
            elif is_indexed:
                func_name = "glDrawElements"
                call_params = [
                    {"name": "mode", "value": "GL_TRIANGLES", "type": "GLenum"},
                    {"name": "count", "value": str(params.get("numIndices", 0)), "type": "GLsizei"},
                    {"name": "type", "value": "GL_UNSIGNED_INT", "type": "GLenum"},
                    {"name": "indices", "value": "(void*)0", "type": "void*"},
                ]
            else:
                func_name = "glDrawArrays"
                call_params = [
                    {"name": "mode", "value": "GL_TRIANGLES", "type": "GLenum"},
                    {"name": "first", "value": "0", "type": "GLint"},
                    {"name": "count", "value": str(params.get("numVertices", 0)), "type": "GLsizei"},
                ]
            
            return {
                "signature": func_name,
                "params": call_params,
                "returnType": "void",
                "relatedCalls": [
                    f"glUseProgram(program: {random.randint(1, 100)})",
                    f"glBindVertexArray(array: {random.randint(1, 50)})",
                    f"glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, {random.randint(1, 50)})" if is_indexed else None,
                ],
            }
        
        elif call_type == "dispatch":
            return {
                "signature": "glDispatchCompute",
                "params": [
                    {"name": "num_groups_x", "value": str(params.get("groupCountX", 1)), "type": "GLuint"},
                    {"name": "num_groups_y", "value": str(params.get("groupCountY", 1)), "type": "GLuint"},
                    {"name": "num_groups_z", "value": str(params.get("groupCountZ", 1)), "type": "GLuint"},
                ],
                "returnType": "void",
                "relatedCalls": [
                    f"glUseProgram(program: {random.randint(100, 150)})",
                ],
            }
    
    # 默认返回
    return {
        "signature": "UnknownCall",
        "params": [],
        "returnType": "void",
        "relatedCalls": [],
    }


def generate_mesh_data(eid, num_indices, is_indexed, topology="TriangleList"):
    """
    生成网格数据，包含：
    - Input Layout 详情
    - 顶点统计信息
    - 包围盒 (Bounding Box)
    - 采样的法线/UV 数据用于预览
    
    基于 RenderDoc 的 MeshViewer 和 BufferViewer 功能设计
    """
    import math
    import random
    
    # 根据 EID 生成稳定的随机种子
    random.seed(eid * 12345)
    
    # ========== Input Layout ==========
    # 模拟常见的顶点格式
    input_layouts = [
        # 格式 1: 标准 PBR 顶点 (Position + Normal + Tangent + UV)
        [
            {"semantic": "POSITION", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 0, "size": 12},
            {"semantic": "NORMAL", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 12, "size": 12},
            {"semantic": "TANGENT", "semanticIndex": 0, "format": "R32G32B32A32_FLOAT", "inputSlot": 0, "offset": 24, "size": 16},
            {"semantic": "TEXCOORD", "semanticIndex": 0, "format": "R32G32_FLOAT", "inputSlot": 0, "offset": 40, "size": 8},
        ],
        # 格式 2: 骨骼动画顶点 (Position + Normal + UV + BoneWeights + BoneIndices)
        [
            {"semantic": "POSITION", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 0, "size": 12},
            {"semantic": "NORMAL", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 12, "size": 12},
            {"semantic": "TEXCOORD", "semanticIndex": 0, "format": "R32G32_FLOAT", "inputSlot": 0, "offset": 24, "size": 8},
            {"semantic": "BLENDWEIGHTS", "semanticIndex": 0, "format": "R32G32B32A32_FLOAT", "inputSlot": 1, "offset": 0, "size": 16},
            {"semantic": "BLENDINDICES", "semanticIndex": 0, "format": "R8G8B8A8_UINT", "inputSlot": 1, "offset": 16, "size": 4},
        ],
        # 格式 3: 简单顶点 (Position + Color + UV)
        [
            {"semantic": "POSITION", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 0, "size": 12},
            {"semantic": "COLOR", "semanticIndex": 0, "format": "R8G8B8A8_UNORM", "inputSlot": 0, "offset": 12, "size": 4},
            {"semantic": "TEXCOORD", "semanticIndex": 0, "format": "R32G32_FLOAT", "inputSlot": 0, "offset": 16, "size": 8},
        ],
        # 格式 4: 地形顶点 (Position + Normal + UV0 + UV1)
        [
            {"semantic": "POSITION", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 0, "size": 12},
            {"semantic": "NORMAL", "semanticIndex": 0, "format": "R32G32B32_FLOAT", "inputSlot": 0, "offset": 12, "size": 12},
            {"semantic": "TEXCOORD", "semanticIndex": 0, "format": "R32G32_FLOAT", "inputSlot": 0, "offset": 24, "size": 8},
            {"semantic": "TEXCOORD", "semanticIndex": 1, "format": "R32G32_FLOAT", "inputSlot": 0, "offset": 32, "size": 8},
        ],
    ]
    
    layout_idx = eid % len(input_layouts)
    input_layout = input_layouts[layout_idx]
    
    # 计算每个顶点的总大小 (stride)
    strides_by_slot = {}
    for attr in input_layout:
        slot = attr["inputSlot"]
        end_offset = attr["offset"] + attr["size"]
        strides_by_slot[slot] = max(strides_by_slot.get(slot, 0), end_offset)
    
    # ========== 顶点统计 ==========
    if topology == "TriangleList":
        num_triangles = num_indices // 3
        # 模拟顶点复用率 (通常 0.5 - 0.8)
        reuse_ratio = 0.5 + random.random() * 0.3
        num_vertices = int(num_indices * (1 - reuse_ratio * 0.5))
    elif topology == "TriangleStrip":
        num_triangles = num_indices - 2
        num_vertices = num_indices
        reuse_ratio = (num_triangles * 3 - num_indices) / (num_triangles * 3) if num_triangles > 0 else 0
    else:
        num_triangles = num_indices // 3
        num_vertices = num_indices
        reuse_ratio = 0
    
    # 计算 Buffer 大小
    vb_sizes = {slot: stride * num_vertices for slot, stride in strides_by_slot.items()}
    ib_size = num_indices * 4 if is_indexed else 0  # R32_UINT = 4 bytes
    total_mesh_size = sum(vb_sizes.values()) + ib_size
    
    # ========== 包围盒 (Bounding Box) ==========
    # 基于 EID 生成不同位置和大小的物体
    base_x = (eid % 10 - 5) * 2.0
    base_y = ((eid // 10) % 5) * 1.5
    base_z = (eid % 7 - 3) * 3.0
    
    # 物体大小变化
    scale = 0.5 + (eid % 20) * 0.1
    
    bbox = {
        "min": {
            "x": round(base_x - scale, 3),
            "y": round(base_y - scale * 0.5, 3),
            "z": round(base_z - scale, 3),
        },
        "max": {
            "x": round(base_x + scale, 3),
            "y": round(base_y + scale * 1.5, 3),
            "z": round(base_z + scale, 3),
        },
        "center": {
            "x": round(base_x, 3),
            "y": round(base_y + scale * 0.5, 3),
            "z": round(base_z, 3),
        },
        "extents": {
            "x": round(scale, 3),
            "y": round(scale, 3),
            "z": round(scale, 3),
        },
    }
    
    # ========== 采样法线数据 (用于颜色预览) ==========
    # 生成 16 个采样法线，用于生成 4x4 的颜色预览
    sampled_normals = []
    for i in range(16):
        # 生成随机但合理的法线方向
        theta = random.random() * math.pi * 2
        phi = random.random() * math.pi * 0.5  # 半球
        nx = math.sin(phi) * math.cos(theta)
        ny = math.cos(phi)  # Y-up
        nz = math.sin(phi) * math.sin(theta)
        sampled_normals.append({
            "x": round(nx, 4),
            "y": round(ny, 4),
            "z": round(nz, 4),
        })
    
    # UV 采样数据已移除 - 随机 UV 三角形可视化无实际价值
    
    return {
        "inputLayout": input_layout,
        "statistics": {
            "vertexCount": num_vertices,
            "indexCount": num_indices if is_indexed else 0,
            "triangleCount": num_triangles,
            "topology": topology,
            "vertexReuseRatio": round(reuse_ratio, 3),
            "vertexBufferSizes": vb_sizes,
            "indexBufferSize": ib_size,
            "totalMeshSize": total_mesh_size,
        },
        "boundingBox": bbox,
        "sampledNormals": sampled_normals,
        "strides": strides_by_slot,
    }


def generate_vs_cb_bindings(eid):
    """
    生成 Vertex Shader 阶段的 Constant Buffer 绑定数据
    
    VS 阶段通常需要：
    - 变换矩阵 (World, View, Proj, WVP)
    - 骨骼动画矩阵
    - 顶点动画参数
    """
    import math
    
    # 基于 EID 生成有变化的数值（模拟动画/移动）
    time_offset = eid * 0.016  # 假设每 EID 约 16ms
    
    # 模拟世界矩阵（带平移）
    world_matrix = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        (eid % 100) * 0.5, 0.0, (eid % 50) * 0.2, 1.0  # 平移
    ]
    
    # 模拟视图矩阵（相机位置）
    cam_angle = (eid % 360) * 0.01
    view_matrix = [
        math.cos(cam_angle), 0.0, -math.sin(cam_angle), 0.0,
        0.0, 1.0, 0.0, 0.0,
        math.sin(cam_angle), 0.0, math.cos(cam_angle), 0.0,
        0.0, 1.5, -5.0, 1.0  # 相机位置
    ]
    
    # 模拟投影矩阵（透视投影，固定值）
    proj_matrix = [
        1.299, 0.0, 0.0, 0.0,
        0.0, 2.414, 0.0, 0.0,
        0.0, 0.0, -1.0002, -1.0,
        0.0, 0.0, -0.20002, 0.0
    ]
    
    # WorldViewProj = World * View * Proj（这里简化，直接生成）
    wvp_matrix = [
        1.0 + cam_angle * 0.1, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, -1.0,
        (eid % 100) * 0.05, 0.0, -5.0, 1.0
    ]
    
    return [
        {
            "slot": 0, 
            "name": "cbTransforms", 
            "resourceId": f"Buffer_0x{0x1A00 + eid % 256:04X}",
            "size": 256,
            "offset": 0,
            "bindFlags": "ConstantBuffer",
            "members": [
                {
                    "name": "WorldMatrix", 
                    "type": "float4x4", 
                    "offset": 0, 
                    "size": 64,
                    "rows": 4,
                    "columns": 4,
                    "value": format_matrix_value(4, 4, world_matrix)
                },
                {
                    "name": "ViewMatrix", 
                    "type": "float4x4", 
                    "offset": 64, 
                    "size": 64,
                    "rows": 4,
                    "columns": 4,
                    "value": format_matrix_value(4, 4, view_matrix)
                },
                {
                    "name": "ProjMatrix", 
                    "type": "float4x4", 
                    "offset": 128, 
                    "size": 64,
                    "rows": 4,
                    "columns": 4,
                    "value": format_matrix_value(4, 4, proj_matrix)
                },
                {
                    "name": "WorldViewProj", 
                    "type": "float4x4", 
                    "offset": 192, 
                    "size": 64,
                    "rows": 4,
                    "columns": 4,
                    "value": format_matrix_value(4, 4, wvp_matrix)
                },
            ]
        },
        {
            "slot": 1, 
            "name": "cbSkinning", 
            "resourceId": f"Buffer_0x{0x5000 + eid % 32:04X}",
            "size": 1024,
            "offset": 0,
            "bindFlags": "ConstantBuffer",
            "members": [
                {
                    "name": "BoneCount", 
                    "type": "uint", 
                    "offset": 0, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "64"
                },
                {
                    "name": "Padding", 
                    "type": "float3", 
                    "offset": 4, 
                    "size": 12,
                    "rows": 1,
                    "columns": 3,
                    "value": "(0, 0, 0)"
                },
                {
                    "name": "BoneMatrices[0]", 
                    "type": "float4x4", 
                    "offset": 16, 
                    "size": 64,
                    "rows": 4,
                    "columns": 4,
                    "value": format_matrix_value(4, 4)  # 单位矩阵
                },
                {
                    "name": "BoneMatrices[1]", 
                    "type": "float4x4", 
                    "offset": 80, 
                    "size": 64,
                    "rows": 4,
                    "columns": 4,
                    "value": format_matrix_value(4, 4)  # 单位矩阵
                },
            ]
        },
    ]


def generate_ps_cb_bindings(eid):
    """
    生成 Pixel/Fragment Shader 阶段的 Constant Buffer 绑定数据
    
    PS 阶段通常需要：
    - 材质参数 (颜色、粗糙度、金属度)
    - 光照参数 (太阳方向、环境光)
    - 帧级别参数 (时间、曝光)
    """
    time_offset = eid * 0.016
    
    return [
        {
            "slot": 0, 
            "name": "cbPerMaterial", 
            "resourceId": f"Buffer_0x{0x2B00 + eid % 64:04X}",
            "size": 128,
            "offset": 0,
            "bindFlags": "ConstantBuffer",
            "members": [
                {
                    "name": "DiffuseColor", 
                    "type": "float4", 
                    "offset": 0, 
                    "size": 16,
                    "rows": 1,
                    "columns": 4,
                    "value": format_vector_value(4, [0.8, 0.6, 0.4, 1.0])
                },
                {
                    "name": "SpecularColor", 
                    "type": "float4", 
                    "offset": 16, 
                    "size": 16,
                    "rows": 1,
                    "columns": 4,
                    "value": format_vector_value(4, [1.0, 1.0, 1.0, 32.0])  # w = shininess
                },
                {
                    "name": "EmissiveColor", 
                    "type": "float4", 
                    "offset": 32, 
                    "size": 16,
                    "rows": 1,
                    "columns": 4,
                    "value": format_vector_value(4, [0.0, 0.0, 0.0, 0.0])
                },
                {
                    "name": "Roughness", 
                    "type": "float", 
                    "offset": 48, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0.35"
                },
                {
                    "name": "Metallic", 
                    "type": "float", 
                    "offset": 52, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0.0"
                },
                {
                    "name": "AO", 
                    "type": "float", 
                    "offset": 56, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "1.0"
                },
                {
                    "name": "Padding", 
                    "type": "float", 
                    "offset": 60, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0"
                },
                {
                    "name": "UVScale", 
                    "type": "float2", 
                    "offset": 64, 
                    "size": 8,
                    "rows": 1,
                    "columns": 2,
                    "value": format_vector_value(2, [1.0, 1.0])
                },
                {
                    "name": "UVOffset", 
                    "type": "float2", 
                    "offset": 72, 
                    "size": 8,
                    "rows": 1,
                    "columns": 2,
                    "value": format_vector_value(2, [0.0, 0.0])
                },
            ]
        },
        {
            "slot": 1, 
            "name": "cbLighting", 
            "resourceId": "Buffer_0x0F00",  # 帧级别缓冲区，ID 固定
            "size": 64,
            "offset": 0,
            "bindFlags": "ConstantBuffer",
            "members": [
                {
                    "name": "SunDirection", 
                    "type": "float3", 
                    "offset": 0, 
                    "size": 12,
                    "rows": 1,
                    "columns": 3,
                    "value": format_vector_value(3, [0.577, 0.577, -0.577])
                },
                {
                    "name": "SunIntensity", 
                    "type": "float", 
                    "offset": 12, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "1.0"
                },
                {
                    "name": "SunColor", 
                    "type": "float3", 
                    "offset": 16, 
                    "size": 12,
                    "rows": 1,
                    "columns": 3,
                    "value": format_vector_value(3, [1.0, 0.98, 0.95])
                },
                {
                    "name": "Padding1", 
                    "type": "float", 
                    "offset": 28, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0"
                },
                {
                    "name": "AmbientColor", 
                    "type": "float3", 
                    "offset": 32, 
                    "size": 12,
                    "rows": 1,
                    "columns": 3,
                    "value": format_vector_value(3, [0.15, 0.18, 0.22])
                },
                {
                    "name": "AmbientIntensity", 
                    "type": "float", 
                    "offset": 44, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0.5"
                },
            ]
        },
        {
            "slot": 2, 
            "name": "cbPerFrame", 
            "resourceId": "Buffer_0x0F10",
            "size": 32,
            "offset": 0,
            "bindFlags": "ConstantBuffer",
            "members": [
                {
                    "name": "Time", 
                    "type": "float", 
                    "offset": 0, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": f"{time_offset:.3f}"
                },
                {
                    "name": "DeltaTime", 
                    "type": "float", 
                    "offset": 4, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0.0167"  # 60fps
                },
                {
                    "name": "FrameIndex", 
                    "type": "uint", 
                    "offset": 8, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": str(eid // 10)  # 模拟帧号
                },
                {
                    "name": "ExposureValue", 
                    "type": "float", 
                    "offset": 12, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "1.2"
                },
                {
                    "name": "CameraPosition", 
                    "type": "float3", 
                    "offset": 16, 
                    "size": 12,
                    "rows": 1,
                    "columns": 3,
                    "value": format_vector_value(3, [0.0, 1.5, -5.0])
                },
                {
                    "name": "Padding", 
                    "type": "float", 
                    "offset": 28, 
                    "size": 4,
                    "rows": 1,
                    "columns": 1,
                    "value": "0"
                },
            ]
        },
    ]


def generate_event_pass_data(textures, usage_analysis):
    """
    生成模拟的 Event/Pass 数据
    
    基于调研的 RenderDoc 数据结构:
    - ActionDescription: EID, actionId, name, flags, draw params, outputs
    - PipeState: 统一抽象层，跨 D3D11/D3D12/Vulkan/OpenGL
    """
    events = []
    passes = []
    
    # 随机选择 API 类型
    api_type = random.choice(["D3D11", "D3D12", "Vulkan", "OpenGL"])
    
    # API 特定的调用名称映射
    api_calls = {
        "D3D11": {
            "draw": ["DrawIndexed", "Draw", "DrawIndexedInstanced", "DrawInstanced"],
            "dispatch": ["Dispatch"],
            "clear": ["ClearRenderTargetView", "ClearDepthStencilView"],
            "copy": ["CopyResource", "CopySubresourceRegion"],
            "present": ["Present"],
        },
        "D3D12": {
            "draw": ["DrawIndexedInstanced", "DrawInstanced", "ExecuteIndirect"],
            "dispatch": ["Dispatch"],
            "clear": ["ClearRenderTargetView", "ClearDepthStencilView"],
            "copy": ["CopyResource", "CopyBufferRegion", "CopyTextureRegion"],
            "present": ["Present"],
        },
        "Vulkan": {
            "draw": ["vkCmdDrawIndexed", "vkCmdDraw", "vkCmdDrawIndexedIndirect"],
            "dispatch": ["vkCmdDispatch"],
            "clear": ["vkCmdClearColorImage", "vkCmdClearDepthStencilImage"],
            "copy": ["vkCmdCopyImage", "vkCmdCopyBuffer", "vkCmdBlitImage"],
            "present": ["vkQueuePresentKHR"],
        },
        "OpenGL": {
            "draw": ["glDrawElements", "glDrawArrays", "glDrawElementsInstanced"],
            "dispatch": ["glDispatchCompute"],
            "clear": ["glClear"],
            "copy": ["glCopyTexSubImage2D", "glBlitFramebuffer"],
            "present": ["SwapBuffers"],
        },
    }
    
    calls = api_calls[api_type]
    
    # Shader 阶段名称映射
    shader_stages = {
        "D3D11": ["VS", "PS", "GS", "HS", "DS", "CS"],
        "D3D12": ["VS", "PS", "GS", "HS", "DS", "CS", "MS", "AS"],
        "Vulkan": ["Vert", "Frag", "Geom", "TessCtrl", "TessEval", "Comp"],
        "OpenGL": ["Vertex", "Fragment", "Geometry", "TessControl", "TessEval", "Compute"],
    }
    
    stages = shader_stages[api_type]
    
    # 定义渲染 Pass 结构
    pass_definitions = [
        {"name": "Shadow Pass", "type": "shadow", "draws": random.randint(10, 30)},
        {"name": "GBuffer Pass", "type": "gbuffer", "draws": random.randint(50, 100)},
        {"name": "SSAO Pass", "type": "postprocess", "draws": random.randint(2, 5)},
        {"name": "Lighting Pass", "type": "lighting", "draws": random.randint(5, 15)},
        {"name": "Transparent Pass", "type": "transparent", "draws": random.randint(10, 25)},
        {"name": "Post Process", "type": "postprocess", "draws": random.randint(8, 15)},
        {"name": "UI Pass", "type": "ui", "draws": random.randint(15, 40)},
    ]
    
    # 创建一些模拟的渲染目标
    render_targets = [
        {"id": "rt_gbuffer_albedo", "name": "GBuffer_Albedo", "format": "R8G8B8A8_UNORM", "width": 1920, "height": 1080},
        {"id": "rt_gbuffer_normal", "name": "GBuffer_Normal", "format": "R16G16B16A16_FLOAT", "width": 1920, "height": 1080},
        {"id": "rt_gbuffer_orm", "name": "GBuffer_ORM", "format": "R8G8B8A8_UNORM", "width": 1920, "height": 1080},
        {"id": "rt_depth", "name": "DepthBuffer", "format": "D24_UNORM_S8_UINT", "width": 1920, "height": 1080},
        {"id": "rt_shadow", "name": "ShadowMap", "format": "D32_FLOAT", "width": 2048, "height": 2048},
        {"id": "rt_ssao", "name": "SSAO_Result", "format": "R8_UNORM", "width": 1920, "height": 1080},
        {"id": "rt_lighting", "name": "LightingResult", "format": "R16G16B16A16_FLOAT", "width": 1920, "height": 1080},
        {"id": "rt_backbuffer", "name": "BackBuffer", "format": "R8G8B8A8_UNORM_SRGB", "width": 1920, "height": 1080},
    ]
    
    # 创建一些模拟的 Shader
    shaders = [
        {"id": "shader_shadow_vs", "name": "ShadowVS", "stage": stages[0]},
        {"id": "shader_shadow_ps", "name": "ShadowPS", "stage": stages[1]},
        {"id": "shader_gbuffer_vs", "name": "GBufferVS", "stage": stages[0]},
        {"id": "shader_gbuffer_ps", "name": "GBufferPS", "stage": stages[1]},
        {"id": "shader_fullscreen_vs", "name": "FullscreenVS", "stage": stages[0]},
        {"id": "shader_ssao_ps", "name": "SSAO_PS", "stage": stages[1]},
        {"id": "shader_lighting_ps", "name": "LightingPS", "stage": stages[1]},
        {"id": "shader_tonemap_ps", "name": "TonemapPS", "stage": stages[1]},
        {"id": "shader_ui_vs", "name": "UI_VS", "stage": stages[0]},
        {"id": "shader_ui_ps", "name": "UI_PS", "stage": stages[1]},
    ]
    
    # 根据使用分析获取纹理使用信息
    usage_by_id = {}
    if usage_analysis and "all_usage_list" in usage_analysis:
        for u in usage_analysis["all_usage_list"]:
            usage_by_id[u["resource_id"]] = u
    
    # 选择一些纹理用于绑定
    available_textures = textures[:50] if len(textures) >= 50 else textures
    
    # ========== 关键配置：是否有 Symbol/Marker ==========
    # 如果 has_markers=False，使用兜底命名方案
    has_markers = False  # 设为 False 以演示兜底方案
    
    # RT 格式到推测类型的映射（启发式）
    def infer_pass_type_from_rt(rt_format):
        """基于渲染目标格式推测 Pass 类型"""
        fmt = rt_format.upper()
        if "D32" in fmt or "D24" in fmt or "D16" in fmt:
            return "depth/shadow"
        elif "R32G32B32A32_FLOAT" in fmt or "R16G16B16A16_FLOAT" in fmt:
            return "HDR/GBuffer"
        elif "R10G10B10A2" in fmt:
            return "HDR"
        elif "R8G8B8A8" in fmt or "B8G8R8A8" in fmt:
            return "color"
        elif "R16G16_FLOAT" in fmt or "R16G16_SNORM" in fmt:
            return "normal/velocity"
        elif "R8_UNORM" in fmt or "R16_FLOAT" in fmt:
            return "AO/mask"
        else:
            return "unknown"
    
    eid = 1
    action_id = 1
    
    # 帧开始
    events.append({
        "eid": eid,
        "actionId": action_id,
        "name": "BeginFrame",
        "displayName": "Frame Start",
        "type": "Marker",
        "flags": ["PushMarker"],
        "parent": None,
        "children": [],
        "duration": 0,
    })
    frame_start_eid = eid
    eid += 1
    action_id += 1
    
    # 生成每个 Pass
    pass_index = 0  # Pass 序号（用于兜底命名）
    for pass_def in pass_definitions:
        pass_index += 1
        pass_start_eid = eid
        pass_event_eids = []
        
        # ========== 根据 Pass 类型选择渲染目标（先确定 outputs）==========
        if pass_def["type"] == "shadow":
            pass_outputs = [render_targets[4]]  # ShadowMap
            pass_depth = render_targets[4]
            pass_shaders = [shaders[0], shaders[1]]
        elif pass_def["type"] == "gbuffer":
            pass_outputs = render_targets[0:3]  # GBuffer MRT
            pass_depth = render_targets[3]
            pass_shaders = [shaders[2], shaders[3]]
        elif pass_def["type"] == "lighting":
            pass_outputs = [render_targets[6]]  # Lighting result
            pass_depth = None
            pass_shaders = [shaders[4], shaders[6]]
        elif pass_def["type"] == "postprocess":
            pass_outputs = [render_targets[5] if "SSAO" in pass_def["name"] else render_targets[7]]
            pass_depth = None
            pass_shaders = [shaders[4], shaders[5] if "SSAO" in pass_def["name"] else shaders[7]]
        elif pass_def["type"] == "ui":
            pass_outputs = [render_targets[7]]  # BackBuffer
            pass_depth = None
            pass_shaders = [shaders[8], shaders[9]]
        else:
            pass_outputs = [render_targets[7]]
            pass_depth = render_targets[3]
            pass_shaders = [shaders[2], shaders[3]]
        
        # ========== Pass 命名策略 ==========
        if has_markers:
            # 有 Symbol/Marker：使用原始名称
            pass_display_name = pass_def["name"]
            pass_inferred_type = pass_def["type"]
            is_inferred = False
        else:
            # 无 Symbol/Marker：兜底方案
            # 命名格式：Pass #N (Output: [主要RT格式])
            primary_rt_format = pass_outputs[0]["format"] if pass_outputs else "Unknown"
            pass_display_name = f"Pass #{pass_index} (Output: {primary_rt_format})"
            pass_inferred_type = infer_pass_type_from_rt(primary_rt_format)
            is_inferred = True
        
        # Pass 开始标记
        events.append({
            "eid": eid,
            "actionId": action_id,
            "name": f"BeginPass: {pass_display_name}",
            "displayName": pass_display_name,
            "type": "Marker",
            "flags": ["PushMarker", "PassBoundary", "BeginPass"],
            "parent": frame_start_eid,
            "children": [],
            "duration": 0,
            "isInferred": is_inferred,  # 标记是否为推测
        })
        pass_marker_eid = eid
        eid += 1
        action_id += 1
        
        # ========== 创建 Pass 绑定状态（确保句柄一致性）==========
        pass_binding_state = PassBindingState(api_type, pass_index, pass_shaders, pass_outputs)
        
        # 绑定纹理（需要在这里初始化，供后续使用）
        bound_textures = random.sample(available_textures, min(4, len(available_textures)))
        
        # 生成 Clear 操作（部分 Pass）
        if pass_def["type"] in ["shadow", "gbuffer"]:
            events.append({
                "eid": eid,
                "actionId": action_id,
                "name": random.choice(calls["clear"]),
                "displayName": f"Clear {pass_outputs[0]['name']}",
                "type": "Clear",
                "flags": ["Clear"],
                "parent": pass_marker_eid,
                "children": [],
                "duration": round(random.uniform(0.01, 0.05), 3),
                "outputs": [{"id": rt["id"], "name": rt["name"]} for rt in pass_outputs],
                "depthOutput": {"id": pass_depth["id"], "name": pass_depth["name"]} if pass_depth else None,
            })
            pass_event_eids.append(eid)
            eid += 1
            action_id += 1
        
        # 生成 Draw/Dispatch 调用
        for i in range(pass_def["draws"]):
            is_dispatch = pass_def["type"] == "postprocess" and random.random() < 0.3
            
            if is_dispatch:
                # Dispatch 调用
                dispatch_x = random.choice([8, 16, 32, 64])
                dispatch_y = random.choice([8, 16, 32, 64])
                dispatch_z = 1
                
                dispatch_params = {
                    "groupCountX": dispatch_x,
                    "groupCountY": dispatch_y,
                    "groupCountZ": dispatch_z,
                }
                
                event = {
                    "eid": eid,
                    "actionId": action_id,
                    "name": random.choice(calls["dispatch"]),
                    "displayName": f"Dispatch ({dispatch_x}×{dispatch_y}×{dispatch_z})",
                    "type": "Dispatch",
                    "flags": ["Dispatch"],
                    "parent": pass_marker_eid,
                    "children": [],
                    "duration": round(random.uniform(0.1, 0.5), 3),
                    "dispatchParams": dispatch_params,
                    "apiCall": generate_api_call(api_type, "dispatch", dispatch_params, pass_binding_state),
                }
            else:
                # Draw 调用
                is_indexed = random.random() < 0.8
                is_instanced = random.random() < 0.3
                
                num_indices = random.choice([36, 72, 144, 360, 720, 1440, 3600, 7200, 14400])
                num_instances = random.randint(1, 100) if is_instanced else 1
                topology = random.choice(["TriangleList", "TriangleStrip"])
                
                flags = ["Drawcall"]
                if is_indexed:
                    flags.append("Indexed")
                if is_instanced:
                    flags.append("Instanced")
                
                # 选择绑定的纹理
                bound_textures = random.sample(available_textures, min(4, len(available_textures)))
                
                # 生成网格数据 (Input Layout, 统计, 包围盒等)
                mesh_data = generate_mesh_data(eid, num_indices, is_indexed, topology)
                
                # 先选择 API 调用名称，确保 name 和 apiCall 一致
                draw_call_name = random.choice(calls["draw"])
                
                event = {
                    "eid": eid,
                    "actionId": action_id,
                    "name": draw_call_name,
                    "displayName": f"Draw #{i+1}" + (f" (×{num_instances})" if is_instanced else ""),
                    "type": "Draw",
                    "flags": flags,
                    "parent": pass_marker_eid,
                    "children": [],
                    "duration": round(random.uniform(0.01, 0.3), 3),
                    "drawParams": {
                        "numIndices": num_indices if is_indexed else 0,
                        "numVertices": num_indices // 3 if not is_indexed else 0,
                        "numInstances": num_instances,
                        "baseVertex": 0,
                        "indexOffset": 0,
                        "instanceOffset": 0,
                        "topology": topology,
                        "indexed": is_indexed,
                        "instanced": is_instanced,
                    },
                    "apiCall": generate_api_call(api_type, "draw", {
                        "numIndices": num_indices if is_indexed else 0,
                        "numVertices": num_indices // 3 if not is_indexed else 0,
                        "numInstances": num_instances,
                        "indexed": is_indexed,
                        "instanced": is_instanced,
                        "callName": draw_call_name,  # 传入实际调用名
                    }, pass_binding_state),
                    "meshData": mesh_data,  # 网格数据：Input Layout, 统计, 包围盒
                    "outputs": [
                        {
                            "id": rt["id"], 
                            "name": rt["name"],
                            "format": rt["format"],
                            "size": f"{rt['width']}x{rt['height']}",
                            "thumbnail": generate_placeholder_thumbnail(rt["name"], rt["width"], rt["height"]),
                        } 
                        for rt in pass_outputs
                    ],
                    "inputs": [
                        {
                            "id": tex["id"],
                            "name": tex["name"],
                            "slot": idx,
                            "format": tex.get("format", "RGBA8"),
                            "thumbnail": tex.get("thumbnail", ""),  # 从全局纹理继承
                        }
                        for idx, tex in enumerate(bound_textures)
                    ],
                    "depthOutput": {
                        "id": pass_depth["id"], 
                        "name": pass_depth["name"],
                        "format": pass_depth.get("format", "D32_FLOAT"),
                        "thumbnail": generate_placeholder_thumbnail(pass_depth["name"], 1920, 1080),
                    } if pass_depth else None,
                    "pipelineState": {
                        "shaders": {
                            pass_shaders[0]["stage"]: {"id": pass_shaders[0]["id"], "name": pass_shaders[0]["name"]},
                            pass_shaders[1]["stage"]: {"id": pass_shaders[1]["id"], "name": pass_shaders[1]["name"]},
                        },
                        "viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                        "scissor": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                        "bindings": {
                            # VS 阶段绑定
                            pass_shaders[0]["stage"]: {
                                "vertexBuffers": [
                                    {"slot": 0, "id": f"VB_0x{0x3000 + eid % 128:04X}", "stride": 32, "offset": 0},
                                    {"slot": 1, "id": f"VB_0x{0x3100 + eid % 128:04X}", "stride": 16, "offset": 0},
                                ],
                                "indexBuffer": {
                                    "id": f"IB_0x{0x4000 + eid % 64:04X}",
                                    "format": "R32_UINT" if is_indexed else None,
                                    "offset": 0,
                                },
                                "constantBuffers": generate_vs_cb_bindings(eid),
                            },
                            # PS 阶段绑定
                            pass_shaders[1]["stage"]: {
                                "textures": [
                                    {"slot": idx, "id": tex["id"], "name": tex["name"]}
                                    for idx, tex in enumerate(bound_textures)
                                ],
                                "samplers": [
                                    {"slot": 0, "filter": "Linear", "addressU": "Wrap", "addressV": "Wrap"},
                                ],
                                "constantBuffers": generate_ps_cb_bindings(eid),
                            },
                        },
                    },
                }
            
            events.append(event)
            pass_event_eids.append(eid)
            eid += 1
            action_id += 1
        
        # Pass 结束标记
        events.append({
            "eid": eid,
            "actionId": action_id,
            "name": f"EndPass: {pass_def['name']}",
            "displayName": f"End {pass_def['name']}",
            "type": "Marker",
            "flags": ["PopMarker", "PassBoundary", "EndPass"],
            "parent": pass_marker_eid,
            "children": [],
            "duration": 0,
        })
        eid += 1
        action_id += 1
        
        # 计算 Pass 总时长
        pass_duration = sum(e.get("duration", 0) for e in events if e["eid"] in pass_event_eids)
        
        # 添加 Pass 摘要（使用兜底命名或原始名称）
        passes.append({
            "eid": pass_marker_eid,
            "name": pass_display_name,  # 使用处理后的显示名称
            "originalName": pass_def["name"],  # 保留原始名称供参考
            "type": pass_inferred_type,  # 使用推测或实际类型
            "isInferred": is_inferred,  # 是否为推测
            "eventCount": len(pass_event_eids),
            "drawCount": pass_def["draws"],
            "duration": round(pass_duration, 3),
            "events": pass_event_eids,
            "inputs": [tex["name"] for tex in bound_textures[:2]] if bound_textures else [],
            "outputs": [rt["name"] for rt in pass_outputs],
            # 添加完整的 RT 信息（含缩略图占位符）
            "outputDetails": [
                {
                    "id": rt["id"],
                    "name": rt["name"],
                    "format": rt["format"],
                    "width": rt["width"],
                    "height": rt["height"],
                    "thumbnail": generate_placeholder_thumbnail(rt["name"], rt["width"], rt["height"]),
                }
                for rt in pass_outputs
            ],
        })
    
    # Present
    events.append({
        "eid": eid,
        "actionId": action_id,
        "name": random.choice(calls["present"]),
        "displayName": "Present",
        "type": "Present",
        "flags": ["Present"],
        "parent": frame_start_eid,
        "children": [],
        "duration": round(random.uniform(0.5, 2.0), 3),
    })
    eid += 1
    action_id += 1
    
    # 帧结束
    events.append({
        "eid": eid,
        "actionId": action_id,
        "name": "EndFrame",
        "displayName": "Frame End",
        "type": "Marker",
        "flags": ["PopMarker"],
        "parent": frame_start_eid,
        "children": [],
        "duration": 0,
    })
    
    # 计算总帧时间
    total_duration = sum(e.get("duration", 0) for e in events)
    
    return {
        "apiType": api_type,
        "events": events,
        "passes": passes,
        "renderTargets": render_targets,
        "shaders": shaders,
        "totalEvents": len(events),
        "totalDraws": sum(1 for e in events if e["type"] == "Draw"),
        "totalDispatches": sum(1 for e in events if e["type"] == "Dispatch"),
        "frameDuration": round(total_duration, 3),
    }


def generate_optimization_report(textures, dup_analysis, usage_analysis):
    """生成优化建议报告"""
    lines = [
        "# 🎯 纹理优化建议报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**纹理总数**: {len(textures)}",
        "",
        "---",
        "",
        "## 📊 问题摘要",
        "",
        f"| 问题类型 | 数量 | 严重程度 |",
        f"|----------|------|----------|",
    ]
    
    # 统计问题
    issues = []
    
    # 重复纹理
    if dup_analysis["total_duplicate_count"] > 0:
        wasted_mb = dup_analysis["total_wasted_bytes"] / (1024 * 1024)
        issues.append(("🔁 重复纹理", dup_analysis["total_duplicate_count"], "高", f"浪费 {wasted_mb:.1f} MB"))
    
    # 未使用纹理
    if usage_analysis["unused_textures"] > 0:
        unused_mb = usage_analysis["unused_vram_bytes"] / (1024 * 1024)
        issues.append(("💤 未使用纹理", usage_analysis["unused_textures"], "高", f"浪费 {unused_mb:.1f} MB"))
    
    # 缺少Mipmap
    no_mip = [t for t in textures if t["mips"] == 1 and t["width"] > 256]
    if no_mip:
        issues.append(("⚠️ 无Mipmap", len(no_mip), "中", "可能导致采样问题"))
    
    # 过大纹理
    huge = [t for t in textures if t["width"] >= 4096 or t["height"] >= 4096]
    if huge:
        issues.append(("📐 超大纹理(4K+)", len(huge), "低", "考虑降低分辨率"))
    
    for issue_type, count, severity, note in issues:
        lines.append(f"| {issue_type} | {count} | {severity} | {note} |")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## ✅ 优化检查清单")
    lines.append("")
    
    # 生成检查项
    lines.append("### 高优先级")
    lines.append("")
    
    if dup_analysis["total_duplicate_count"] > 0:
        lines.append("- [ ] **合并重复纹理**: 以下纹理内容完全相同，可合并为单一资源")
        for g in dup_analysis["duplicate_groups"][:3]:
            names = [t["name"] for t in g["textures"][:3]]
            lines.append(f"  - 组: {', '.join(names)}")
        lines.append("")
    
    if usage_analysis["unused_textures"] > 0:
        lines.append("- [ ] **移除未使用纹理**: 以下纹理在整个帧中从未被引用")
        for u in usage_analysis["cold_list"][:5]:
            mb = u["vram_bytes"] / (1024 * 1024)
            lines.append(f"  - `{u['name']}` ({mb:.2f} MB)")
        lines.append("")
    
    lines.append("### 中优先级")
    lines.append("")
    
    if no_mip:
        lines.append("- [ ] **添加Mipmap**: 以下纹理缺少Mipmap链")
        for t in no_mip[:5]:
            lines.append(f"  - `{t['name']}` ({t['width']}×{t['height']})")
        lines.append("")
    
    lines.append("### 低优先级")
    lines.append("")
    
    if huge:
        lines.append("- [ ] **评估4K纹理必要性**: 以下纹理分辨率较高")
        for t in huge[:3]:
            lines.append(f"  - `{t['name']}` ({t['width']}×{t['height']})")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## 📈 预期收益")
    lines.append("")
    
    total_save = (dup_analysis.get("total_wasted_bytes", 0) + 
                  usage_analysis.get("unused_vram_bytes", 0))
    lines.append(f"执行以上优化后，预计可节省 **{total_save / (1024*1024):.1f} MB** VRAM")
    lines.append("")
    
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("生成 145 纹理演示报告 (含 Event/Pass 数据)")
    print("=" * 60)
    
    # 设置随机种子保证可复现
    random.seed(42)
    
    # 1. 生成模拟纹理数据
    print("\n[1/6] Generating 145 textures...")
    textures = generate_145_textures()
    print(f"  [OK] Generated {len(textures)} textures")
    
    # 2. 生成去重分析
    print("\n[2/6] Generating duplicate analysis...")
    dup_analysis = generate_duplicate_groups(textures)
    print(f"  [OK] Found {len(dup_analysis['duplicate_groups'])} duplicate groups")
    print(f"  [OK] Wasted VRAM: {dup_analysis['total_wasted_bytes'] / (1024*1024):.1f} MB")
    
    # 3. 生成热度分析
    print("\n[3/6] Generating usage analysis...")
    usage_analysis = generate_usage_analysis(textures)
    print(f"  [OK] Used: {usage_analysis['used_textures']}")
    print(f"  [OK] Unused: {usage_analysis['unused_textures']}")
    
    # 4. 生成 Event/Pass 数据
    print("\n[4/6] Generating Event/Pass data...")
    event_pass_data = generate_event_pass_data(textures, usage_analysis)
    print(f"  [OK] API Type: {event_pass_data['apiType']}")
    print(f"  [OK] Total Events: {event_pass_data['totalEvents']}")
    print(f"  [OK] Total Draws: {event_pass_data['totalDraws']}")
    print(f"  [OK] Total Dispatches: {event_pass_data['totalDispatches']}")
    print(f"  [OK] Passes: {len(event_pass_data['passes'])}")
    print(f"  [OK] Frame Duration: {event_pass_data['frameDuration']} ms")
    
    # 5. 生成优化报告
    print("\n[5/6] Generating optimization report...")
    opt_report = generate_optimization_report(textures, dup_analysis, usage_analysis)
    
    # 保存 Markdown 报告
    md_path = os.path.join(os.path.dirname(__file__), "optimization_report_145.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(opt_report)
    print(f"  [OK] Optimization report: {md_path}")
    
    # 6. 生成 HTML 报告
    print("\n[6/6] Generating HTML report...")
    
    output_path = os.path.join(os.path.dirname(__file__), "full_145_texture_report.html")
    
    generate_offline_html(
        textures=textures,
        rdc_name="Game_x64h_Capture_2026.01.18_15.30.45.rdc",
        output_path=output_path,
        duplicate_analysis=dup_analysis,
        usage_analysis=usage_analysis,
        event_pass_data=event_pass_data,
    )
    
    print(f"\n{'=' * 60}")
    print(f"[DONE] Report generation complete!")
    print(f"   HTML: {output_path}")
    print(f"   MD:   {md_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
