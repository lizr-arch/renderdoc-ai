"""
二进制解析器
============

直接解析 RDC 文件的二进制格式。
不依赖 RenderDoc 模块，但功能有限。
"""

import os
import struct
from typing import Dict, List, Any, Optional
from .base import BaseParser
from ..core.context import ParsedData
from ..utils.lz4_utils import decompress_lz4_blocks, decompress_with_lz4_lib


# RDC 文件魔数
RDC_MAGIC = b'RDOC'

# =============================================================================
# D3D11 Chunk 类型 ID 映射
# 
# 基于 RenderDoc 源码:
#   - renderdoc/core/core.h: SystemChunk::FirstDriverChunk = 1000
#   - renderdoc/driver/d3d11/d3d11_common.h: D3D11Chunk enum
#
# 计算公式: actual_id = FirstDriverChunk (1000) + enum_value
# =============================================================================

FIRST_DRIVER_CHUNK = 1000

D3D11_CHUNK_TYPES = {
    # =========================================================================
    # 系统 Chunks (0-999, 来自 SystemChunk)
    # =========================================================================
    1: "SystemChunk::DriverInit",
    2: "SystemChunk::InitialContentsList",
    3: "SystemChunk::InitialContents",
    4: "SystemChunk::CaptureBegin",
    5: "SystemChunk::CaptureScope",
    6: "SystemChunk::CaptureEnd",
    
    # =========================================================================
    # D3D11 Driver Chunks (1000+)
    # 来自 d3d11_common.h D3D11Chunk enum
    # =========================================================================
    
    # --- 设备初始化 (1000-1009) ---
    1000: "DeviceInitialisation",
    1001: "SetResourceName",
    1002: "CreateSwapBuffer",
    
    # --- 资源创建 (1010-1039) ---
    1010: "CreateTexture1D",
    1011: "CreateTexture2D",
    1012: "CreateTexture3D",
    1013: "CreateBuffer",
    1014: "CreateVertexShader",
    1015: "CreateHullShader",
    1016: "CreateDomainShader",
    1017: "CreateGeometryShader",
    1018: "CreateGeometryShaderWithStreamOutput",
    1019: "CreatePixelShader",
    1020: "CreateComputeShader",
    1021: "GetClassInstance",
    1022: "CreateClassInstance",
    1023: "CreateClassLinkage",
    1024: "CreateShaderResourceView",
    1025: "CreateRenderTargetView",
    1026: "CreateDepthStencilView",
    1027: "CreateUnorderedAccessView",
    1028: "CreateInputLayout",
    1029: "CreateBlendState",
    1030: "CreateDepthStencilState",
    1031: "CreateRasterizerState",
    1032: "CreateSamplerState",
    1033: "CreateQuery",
    1034: "CreatePredicate",
    1035: "CreateCounter",
    1036: "CreateDeferredContext",
    1037: "SetExceptionMode",
    1038: "OpenSharedResource",
    1039: "OpenSharedResourceByName",
    1040: "OpenSharedResource1",
    
    # --- IA 输入装配 (1041-1049) ---
    1041: "IASetInputLayout",
    1042: "IASetVertexBuffers",
    1043: "IASetIndexBuffer",
    1044: "IASetPrimitiveTopology",
    
    # --- VS 顶点着色器 (1050-1054) ---
    1050: "VSSetConstantBuffers",
    1051: "VSSetShaderResources",
    1052: "VSSetSamplers",
    1053: "VSSetShader",
    
    # --- HS 曲面细分着色器 (1054-1058) ---
    1054: "HSSetConstantBuffers",
    1055: "HSSetShaderResources",
    1056: "HSSetSamplers",
    1057: "HSSetShader",
    
    # --- DS 域着色器 (1058-1062) ---
    1058: "DSSetConstantBuffers",
    1059: "DSSetShaderResources",
    1060: "DSSetSamplers",
    1061: "DSSetShader",
    
    # --- GS 几何着色器 (1062-1066) ---
    1062: "GSSetConstantBuffers",
    1063: "GSSetShaderResources",
    1064: "GSSetSamplers",
    1065: "GSSetShader",
    
    # --- SO 流输出 (1066-1067) ---
    1066: "SOSetTargets",
    
    # --- PS 像素着色器 (1067-1071) ---
    1067: "PSSetConstantBuffers",
    1068: "PSSetShaderResources",
    1069: "PSSetSamplers",
    1070: "PSSetShader",
    
    # --- CS 计算着色器 (1071-1075) ---
    1071: "CSSetConstantBuffers",
    1072: "CSSetShaderResources",
    1073: "CSSetSamplers",
    1074: "CSSetShader",
    1075: "CSSetUnorderedAccessViews",
    
    # --- RS 光栅化 (1076-1078) ---
    1076: "RSSetState",
    1077: "RSSetViewports",
    1078: "RSSetScissorRects",
    
    # --- OM 输出合并 (1079-1083) ---
    1079: "OMSetRenderTargets",
    1080: "OMSetRenderTargetsAndUnorderedAccessViews",
    1081: "OMSetBlendState",
    1082: "OMSetDepthStencilState",
    
    # --- 清除操作 (1083-1090) ---
    1083: "ClearState",
    1084: "ClearRenderTargetView",
    1085: "ClearUnorderedAccessViewUint",
    1086: "ClearUnorderedAccessViewFloat",
    1087: "ClearDepthStencilView",
    
    # --- 执行命令列表 (1088) ---
    1088: "ExecuteCommandList",
    1089: "FinishCommandList",
    
    # --- Dispatch (1090-1091) ---
    1090: "Dispatch",
    1091: "DispatchIndirect",
    
    # --- 绘制命令 (1092-1099) --- [关键!]
    1092: "Draw",
    1093: "DrawAuto",
    1094: "DrawIndexed",
    1095: "DrawInstanced",
    1096: "DrawIndexedInstanced",
    1097: "DrawInstancedIndirect",
    1098: "DrawIndexedInstancedIndirect",
    
    # --- 资源操作 (1099-1110) ---
    1099: "Map",
    1100: "Unmap",
    1101: "CopySubresourceRegion",
    1102: "CopyResource",
    1103: "UpdateSubresource",
    1104: "CopyStructureCount",
    1105: "ResolveSubresource",
    1106: "GenerateMips",
    1107: "SetResourceMinLOD",
    
    # --- Query 操作 (1108-1112) ---
    1108: "Begin",
    1109: "End",
    1110: "SetPredication",
    1111: "GetData",
    
    # --- Debug 标记 (1112-1115) ---
    1112: "PushEvent",      # PushMarker
    1113: "SetMarker",
    1114: "PopEvent",       # PopMarker
    
    # --- Present (1115+) ---
    1115: "Present",
    1116: "SwapchainPresent",
    
    # --- 扩展 D3D11.1+ ---
    1117: "DiscardResource",
    1118: "DiscardView",
    1119: "VSSetConstantBuffers1",
    1120: "HSSetConstantBuffers1",
    1121: "DSSetConstantBuffers1",
    1122: "GSSetConstantBuffers1",
    1123: "PSSetConstantBuffers1",
    1124: "CSSetConstantBuffers1",
    1125: "CopySubresourceRegion1",
    1126: "UpdateSubresource1",
    1127: "ClearView",
    1128: "VSGetConstantBuffers1",
    1129: "HSGetConstantBuffers1",
    1130: "DSGetConstantBuffers1",
    1131: "GSGetConstantBuffers1",
    1132: "PSGetConstantBuffers1",
    1133: "CSGetConstantBuffers1",
    1134: "SwapDeviceContextState",
    
    # --- D3D11.3+ ---
    1135: "CreateRasterizerState1",
    1136: "CreateRasterizerState2",
    1137: "CreateTexture2D1",
    1138: "CreateTexture3D1",
    1139: "CreateShaderResourceView1",
    1140: "CreateRenderTargetView1",
    1141: "CreateUnorderedAccessView1",
    1142: "CreateQuery1",
    1143: "SetShaderDebugPath",
    
    # --- Video ---
    1144: "CreateVideoDecoder",
    1145: "CreateVideoDecoderOutputView",
    1146: "CreateVideoProcessor",
    1147: "CreateVideoProcessorInputView",
    1148: "CreateVideoProcessorOutputView",
    
    # --- 11on12 ---
    1150: "CreateWrappedResource",
    1151: "AcquireWrappedResources",
    1152: "ReleaseWrappedResources",
    
    # --- DX11.4 + Multithread ---
    1153: "CreateFence",
    1154: "Signal",
    1155: "Wait",
    1156: "WriteToSubresource",
    1157: "ReadFromSubresource",
}

# Draw Call Chunk ID 集合 (用于快速判断)
DRAW_CHUNK_IDS = {1092, 1093, 1094, 1095, 1096, 1097, 1098}

# Dispatch Chunk ID 集合
DISPATCH_CHUNK_IDS = {1090, 1091}

# Clear Chunk ID 集合
CLEAR_CHUNK_IDS = {1083, 1084, 1085, 1086, 1087, 1127}

# State Change Chunk ID 集合
STATE_CHANGE_CHUNK_IDS = {
    1041, 1042, 1043, 1044,  # IA
    1050, 1051, 1052, 1053,  # VS
    1054, 1055, 1056, 1057,  # HS
    1058, 1059, 1060, 1061,  # DS
    1062, 1063, 1064, 1065, 1066,  # GS, SO
    1067, 1068, 1069, 1070,  # PS
    1071, 1072, 1073, 1074, 1075,  # CS
    1076, 1077, 1078,  # RS
    1079, 1080, 1081, 1082,  # OM
}

# Marker Chunk ID 集合
MARKER_CHUNK_IDS = {1112, 1113, 1114}


class BinaryParser(BaseParser):
    """
    二进制 RDC 解析器
    
    直接解析 RDC 文件格式:
    - 验证文件头
    - 解压 LZ4 数据
    - 解析 Chunk 结构
    """
    
    def __init__(self, rdc_path: str):
        super().__init__(rdc_path)
        self._raw_data: Optional[bytes] = None
        self._decompressed: Optional[bytes] = None
    
    def is_available(self) -> bool:
        """二进制解析器始终可用"""
        return True
    
    def parse(self) -> ParsedData:
        """
        解析 RDC 文件
        
        Returns:
            解析后的数据
        """
        # 读取文件
        with open(self.rdc_path, 'rb') as f:
            self._raw_data = f.read()
        
        # 验证魔数
        if not self._raw_data.startswith(RDC_MAGIC):
            raise ValueError(f"Invalid RDC file: magic mismatch")
        
        # 解析文件头
        header = self._parse_header()
        
        # 解压数据
        self._decompress_data(header)
        
        # 解析 Chunks
        chunks = self._parse_chunks()
        
        # 统计 Chunk 类型
        chunk_stats = self._count_chunks(chunks)
        
        # 从 chunks 提取 draw/texture/buffer 信息
        draws = []
        textures = []
        buffers = []
        dispatches = []
        clears = []
        markers = []
        
        for chunk in chunks:
            type_name = chunk.get("type_name", "")
            if type_name.startswith("Draw"):
                draws.append({
                    "event_id": len(draws),
                    "type": type_name,
                    "vertex_count": chunk.get("vertex_count", 0),
                })
            elif type_name == "CreateTexture2D":
                textures.append({
                    "resource_id": f"tex_{len(textures)}",
                    "type": "Texture2D",
                })
            elif type_name == "CreateBuffer":
                buffers.append({
                    "resource_id": f"buf_{len(buffers)}",
                })
            elif type_name == "Dispatch" or type_name == "DispatchIndirect":
                dispatches.append({
                    "event_id": len(dispatches),
                    "type": type_name,
                })
            elif type_name.startswith("Clear"):
                clears.append({
                    "event_id": len(clears),
                    "type": type_name,
                })
            elif "Marker" in type_name:
                markers.append({
                    "name": chunk.get("marker_name", ""),
                    "type": type_name,
                })
        
        return ParsedData(
            api="D3D11",  # 从 header 推断
            file_path=self.rdc_path,
            draws=draws,
            dispatches=dispatches,
            clears=clears,
            textures=textures,
            buffers=buffers,
            markers=markers,
            chunks=chunks,  # 保留原始 chunks 供 StateAnalyzer 使用
            total_events=len(chunks),
        )
    
    def _parse_header(self) -> Dict[str, Any]:
        """
        解析 RDC 文件头
        
        RDC Header 结构 (参考 RenderDoc 源码):
        - 0x00: Magic "RDOC" (4 bytes)
        - 0x04: Version (4 bytes)
        - 0x08: Header Length (4 bytes)
        - 0x0C: Thumb Width (2 bytes)
        - 0x0E: Thumb Height (2 bytes)
        - 0x10: Thumb Data Length (4 bytes)
        - Variable: Thumbnail Data
        - 64-byte aligned: Section Index
        """
        data = self._raw_data
        
        version = struct.unpack_from('<I', data, 4)[0]
        header_len = struct.unpack_from('<I', data, 8)[0]
        
        thumb_width = struct.unpack_from('<H', data, 12)[0]
        thumb_height = struct.unpack_from('<H', data, 14)[0]
        thumb_data_len = struct.unpack_from('<I', data, 16)[0]
        
        # 计算 Section Index 起始位置 (64 字节对齐)
        thumb_end = 20 + thumb_data_len
        section_index_offset = (thumb_end + 63) & ~63
        
        return {
            "version": version,
            "header_length": header_len,
            "thumbnail": {
                "width": thumb_width,
                "height": thumb_height,
                "data_length": thumb_data_len,
            },
            "section_index_offset": section_index_offset,
        }
    
    def _decompress_data(self, header: Dict[str, Any]):
        """解压 LZ4 数据"""
        section_offset = header["section_index_offset"]
        data = self._raw_data
        
        # 扫描 Section Index 找到 Frame Capture 数据
        pos = section_offset
        frame_data_offset = 0
        frame_data_size = 0
        frame_compressed_size = 0
        
        # Section Index 格式:
        # - Section Type (4 bytes)
        # - Section Flags (4 bytes)
        # - Offset (8 bytes)
        # - Compressed Size (8 bytes)
        # - Uncompressed Size (8 bytes)
        
        while pos + 32 <= len(data):
            section_type = struct.unpack_from('<I', data, pos)[0]
            section_flags = struct.unpack_from('<I', data, pos + 4)[0]
            offset = struct.unpack_from('<Q', data, pos + 8)[0]
            compressed_size = struct.unpack_from('<Q', data, pos + 16)[0]
            uncompressed_size = struct.unpack_from('<Q', data, pos + 24)[0]
            
            # Section Type 1 = Frame Capture
            if section_type == 1:
                frame_data_offset = offset
                frame_data_size = uncompressed_size
                frame_compressed_size = compressed_size
                break
            
            # Section Type 0 = End
            if section_type == 0:
                break
            
            pos += 32
        
        if frame_data_offset == 0:
            # 没有找到 Section Index, 尝试老格式
            # 直接从 header 之后开始解压
            frame_data_offset = header["header_length"]
            frame_data_size = len(data) * 4  # 估计值
        
        # 检查是否压缩 (flags & 1 = compressed)
        is_compressed = True  # 假设压缩
        
        if is_compressed:
            try:
                self._decompressed = decompress_with_lz4_lib(
                    data, frame_data_offset, frame_data_size
                )
            except Exception as e:
                # 回退到纯 Python 实现
                self._decompressed = decompress_lz4_blocks(
                    data, frame_data_offset, frame_data_size
                )
        else:
            self._decompressed = data[frame_data_offset:frame_data_offset + frame_data_size]
    
    def _parse_chunks(self) -> List[Dict[str, Any]]:
        """
        解析 Chunk 结构
        
        Chunk 格式:
        - Chunk Header (64 bytes, aligned)
          - Type ID (4 bytes)
          - Length (4 bytes, 包含 header)
          - ... other metadata
        """
        chunks = []
        data = self._decompressed
        if not data:
            return chunks
        
        pos = 0
        CHUNK_ALIGN = 64
        
        while pos + 8 <= len(data):
            # 读取 Chunk 头
            chunk_type = struct.unpack_from('<I', data, pos)[0]
            chunk_length = struct.unpack_from('<I', data, pos + 4)[0]
            
            if chunk_length == 0 or chunk_length > len(data) - pos:
                break
            
            # 获取 Chunk 类型名
            chunk_name = D3D11_CHUNK_TYPES.get(chunk_type, f"Unknown_{chunk_type}")
            
            chunk = {
                "type_id": chunk_type,
                "type_name": chunk_name,
                "offset": pos,
                "length": chunk_length,
            }
            
            # 尝试解析特定 Chunk 的额外信息
            self._parse_chunk_details(chunk, data, pos)
            
            chunks.append(chunk)
            
            # 下一个 Chunk (64 字节对齐)
            pos += chunk_length
            pos = (pos + CHUNK_ALIGN - 1) & ~(CHUNK_ALIGN - 1)
        
        return chunks
    
    def _parse_chunk_details(self, chunk: Dict, data: bytes, pos: int):
        """解析特定 Chunk 的详细信息"""
        chunk_type = chunk["type_id"]
        
        # Draw 命令: 尝试提取顶点数 (使用新的 ID 集合)
        if chunk_type in DRAW_CHUNK_IDS:
            if pos + 16 <= len(data):
                # 顶点数通常在偏移 8 或 12 (取决于具体命令)
                vertex_count = struct.unpack_from('<I', data, pos + 8)[0]
                if vertex_count < 1000000:  # 合理范围
                    chunk["vertex_count"] = vertex_count
                # DrawIndexed 的索引数在不同位置
                if chunk_type in (1094, 1096):  # DrawIndexed, DrawIndexedInstanced
                    index_count = struct.unpack_from('<I', data, pos + 8)[0]
                    if index_count < 10000000:
                        chunk["index_count"] = index_count
        
        # Dispatch 命令: 尝试提取线程组数量
        elif chunk_type in DISPATCH_CHUNK_IDS:
            if pos + 20 <= len(data):
                # Dispatch(ThreadGroupCountX, Y, Z)
                thread_x = struct.unpack_from('<I', data, pos + 8)[0]
                thread_y = struct.unpack_from('<I', data, pos + 12)[0]
                thread_z = struct.unpack_from('<I', data, pos + 16)[0]
                if all(v < 65536 for v in [thread_x, thread_y, thread_z]):
                    chunk["thread_groups"] = (thread_x, thread_y, thread_z)
        
        # Marker: 尝试提取名称 (使用新的 ID 集合)
        elif chunk_type in MARKER_CHUNK_IDS:
            if pos + 64 <= len(data):
                # 尝试读取字符串
                name_start = pos + 8
                name_bytes = []
                for i in range(128):
                    if name_start + i >= len(data):
                        break
                    b = data[name_start + i]
                    if b == 0:
                        break
                    name_bytes.append(b)
                if name_bytes:
                    try:
                        chunk["marker_name"] = bytes(name_bytes).decode('utf-8', errors='ignore')
                    except Exception:
                        pass
        
        # Clear 命令: 标记清除类型
        elif chunk_type in CLEAR_CHUNK_IDS:
            chunk["is_clear"] = True
            if chunk_type == 1084:  # ClearRenderTargetView
                chunk["clear_type"] = "color"
            elif chunk_type == 1087:  # ClearDepthStencilView
                chunk["clear_type"] = "depth_stencil"
    
    def _count_chunks(self, chunks: List[Dict]) -> Dict[str, int]:
        """统计各类型 Chunk 数量"""
        stats = {}
        for chunk in chunks:
            name = chunk["type_name"]
            stats[name] = stats.get(name, 0) + 1
        return stats
