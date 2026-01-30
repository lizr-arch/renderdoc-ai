"""
Binary Parser 模块测试
=====================

测试二进制 RDC 文件解析。
"""

import pytest
import struct
from rdc_analyzer.parsers.binary_parser import (
    BinaryParser, D3D11_CHUNK_TYPES, RDC_MAGIC,
    DRAW_CHUNK_IDS, DISPATCH_CHUNK_IDS, CLEAR_CHUNK_IDS,
    STATE_CHANGE_CHUNK_IDS, MARKER_CHUNK_IDS, FIRST_DRIVER_CHUNK
)


class TestChunkConstants:
    """测试 Chunk 常量"""
    
    def test_first_driver_chunk_value(self):
        """验证 FirstDriverChunk 值"""
        assert FIRST_DRIVER_CHUNK == 1000
    
    def test_draw_chunk_ids(self):
        """验证 Draw Chunk ID 集合"""
        assert 1092 in DRAW_CHUNK_IDS  # Draw
        assert 1094 in DRAW_CHUNK_IDS  # DrawIndexed
        assert 1096 in DRAW_CHUNK_IDS  # DrawIndexedInstanced
        assert len(DRAW_CHUNK_IDS) == 7
    
    def test_dispatch_chunk_ids(self):
        """验证 Dispatch Chunk ID 集合"""
        assert 1090 in DISPATCH_CHUNK_IDS  # Dispatch
        assert 1091 in DISPATCH_CHUNK_IDS  # DispatchIndirect
    
    def test_clear_chunk_ids(self):
        """验证 Clear Chunk ID 集合"""
        assert 1084 in CLEAR_CHUNK_IDS  # ClearRenderTargetView
        assert 1087 in CLEAR_CHUNK_IDS  # ClearDepthStencilView
    
    def test_marker_chunk_ids(self):
        """验证 Marker Chunk ID 集合"""
        assert 1112 in MARKER_CHUNK_IDS  # PushEvent
        assert 1113 in MARKER_CHUNK_IDS  # SetMarker
        assert 1114 in MARKER_CHUNK_IDS  # PopEvent


class TestD3D11ChunkTypes:
    """测试 D3D11 Chunk 类型映射"""
    
    def test_device_initialization(self):
        """验证设备初始化 Chunk"""
        assert D3D11_CHUNK_TYPES[1000] == "DeviceInitialisation"
    
    def test_resource_creation(self):
        """验证资源创建 Chunk"""
        assert D3D11_CHUNK_TYPES[1011] == "CreateTexture2D"
        assert D3D11_CHUNK_TYPES[1013] == "CreateBuffer"
        assert D3D11_CHUNK_TYPES[1014] == "CreateVertexShader"
        assert D3D11_CHUNK_TYPES[1019] == "CreatePixelShader"
    
    def test_draw_commands(self):
        """验证绘制命令 Chunk"""
        assert D3D11_CHUNK_TYPES[1092] == "Draw"
        assert D3D11_CHUNK_TYPES[1094] == "DrawIndexed"
        assert D3D11_CHUNK_TYPES[1095] == "DrawInstanced"
        assert D3D11_CHUNK_TYPES[1096] == "DrawIndexedInstanced"
    
    def test_dispatch_commands(self):
        """验证 Dispatch 命令 Chunk"""
        assert D3D11_CHUNK_TYPES[1090] == "Dispatch"
        assert D3D11_CHUNK_TYPES[1091] == "DispatchIndirect"
    
    def test_state_commands(self):
        """验证状态设置 Chunk"""
        assert D3D11_CHUNK_TYPES[1041] == "IASetInputLayout"
        assert D3D11_CHUNK_TYPES[1053] == "VSSetShader"
        assert D3D11_CHUNK_TYPES[1070] == "PSSetShader"
        assert D3D11_CHUNK_TYPES[1079] == "OMSetRenderTargets"
    
    def test_present(self):
        """验证 Present Chunk"""
        assert D3D11_CHUNK_TYPES[1115] == "Present"


class TestBinaryParserValidation:
    """测试二进制解析器验证"""
    
    def test_rdc_magic(self):
        """验证 RDC 魔数"""
        assert RDC_MAGIC == b'RDOC'
    
    def test_invalid_magic_raises(self):
        """验证无效魔数抛出异常"""
        import tempfile
        import os
        
        # 创建无效文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.rdc') as f:
            f.write(b'INVALID')
            temp_path = f.name
        
        try:
            parser = BinaryParser(temp_path)
            with pytest.raises(ValueError, match="magic mismatch"):
                parser.parse()
        finally:
            os.unlink(temp_path)


class TestBinaryParserHeader:
    """测试文件头解析"""
    
    def create_minimal_rdc(self, version=104):
        """创建最小 RDC 文件数据"""
        import io
        buf = io.BytesIO()
        
        # Magic
        buf.write(RDC_MAGIC)
        # Version
        buf.write(struct.pack('<I', version))
        # Header length (placeholder)
        buf.write(struct.pack('<I', 64))
        # Thumbnail: width, height, data_length
        buf.write(struct.pack('<H', 0))  # width
        buf.write(struct.pack('<H', 0))  # height
        buf.write(struct.pack('<I', 0))  # data_length
        
        # Pad to 64 bytes
        while buf.tell() < 64:
            buf.write(b'\x00')
        
        return buf.getvalue()
    
    def test_header_parsing(self):
        """测试头部解析"""
        import tempfile
        import os
        
        data = self.create_minimal_rdc(version=104)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.rdc') as f:
            f.write(data)
            temp_path = f.name
        
        try:
            parser = BinaryParser(temp_path)
            parser._raw_data = data
            header = parser._parse_header()
            
            assert header["version"] == 104
            assert header["thumbnail"]["width"] == 0
            assert header["thumbnail"]["height"] == 0
        finally:
            os.unlink(temp_path)


class TestStateChangeChunks:
    """测试状态变更 Chunk"""
    
    def test_ia_chunks(self):
        """验证 IA 阶段 Chunk"""
        assert 1041 in STATE_CHANGE_CHUNK_IDS  # IASetInputLayout
        assert 1042 in STATE_CHANGE_CHUNK_IDS  # IASetVertexBuffers
        assert 1043 in STATE_CHANGE_CHUNK_IDS  # IASetIndexBuffer
        assert 1044 in STATE_CHANGE_CHUNK_IDS  # IASetPrimitiveTopology
    
    def test_vs_chunks(self):
        """验证 VS 阶段 Chunk"""
        assert 1050 in STATE_CHANGE_CHUNK_IDS  # VSSetConstantBuffers
        assert 1053 in STATE_CHANGE_CHUNK_IDS  # VSSetShader
    
    def test_ps_chunks(self):
        """验证 PS 阶段 Chunk"""
        assert 1067 in STATE_CHANGE_CHUNK_IDS  # PSSetConstantBuffers
        assert 1070 in STATE_CHANGE_CHUNK_IDS  # PSSetShader
    
    def test_cs_chunks(self):
        """验证 CS 阶段 Chunk"""
        assert 1074 in STATE_CHANGE_CHUNK_IDS  # CSSetShader
        assert 1075 in STATE_CHANGE_CHUNK_IDS  # CSSetUnorderedAccessViews
    
    def test_om_chunks(self):
        """验证 OM 阶段 Chunk"""
        assert 1079 in STATE_CHANGE_CHUNK_IDS  # OMSetRenderTargets
        assert 1081 in STATE_CHANGE_CHUNK_IDS  # OMSetBlendState
