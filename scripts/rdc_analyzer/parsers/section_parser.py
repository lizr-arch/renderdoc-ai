#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Section Parser - Parse RDC file headers and sections.

This module handles the binary parsing of RDC file structure:
- File Header (magic, version, prog_version)
- Thumbnail
- CaptureMetaData (driver info)
- TimeBase (v1.2+)
- Section Headers and Data

Extracted from rdc_parser.py for better modularity.
"""

import json
import struct
from typing import BinaryIO, Dict, List, Optional

from .constants import RDC_VERSION_1_2
from .enums import RDCDriver, SectionFlags, SectionType
from .io_utils import BinaryReader
from .models import (
    CaptureMetaData,
    FileHeader,
    RDCFileInfo,
    SectionInfo,
    Thumbnail,
    TimeBase,
)


class SectionParser:
    """
    RDC 文件头和 Section 解析器。
    
    负责解析 RDC 文件的顶层结构，包括：
    - FileHeader (28 bytes)
    - BinaryThumbnail (variable)
    - CaptureMetaData (variable)
    - TimeBase (16 bytes, v1.2+)
    - Section 列表
    
    Usage:
        with open("capture.rdc", "rb") as f:
            parser = SectionParser(f)
            info = parser.parse()
            
            # 读取特定 section
            fc_section = info.frame_capture_section
            data = parser.read_section_data(fc_section)
    """
    
    def __init__(self, file: BinaryIO, filepath: str = ""):
        """
        初始化 SectionParser。
        
        Args:
            file: 已打开的二进制文件对象
            filepath: 文件路径（用于记录）
        """
        self._reader = BinaryReader(file)
        self._filepath = filepath
        
        # 获取文件大小
        current_pos = self._reader.tell()
        self._reader.seek(0, 2)  # 跳到文件末尾
        self._file_size = self._reader.tell()
        self._reader.seek(current_pos)  # 恢复位置
        
        # 缓存
        self._rdc_info: Optional[RDCFileInfo] = None
        self._frame_capture_data: Optional[bytes] = None
    
    @property
    def file_size(self) -> int:
        """文件大小（字节）"""
        return self._file_size
    
    @property
    def rdc_info(self) -> Optional[RDCFileInfo]:
        """解析后的 RDC 文件信息"""
        return self._rdc_info
    
    def parse(self) -> RDCFileInfo:
        """
        解析 RDC 文件头和元数据。
        
        Returns:
            RDCFileInfo: 包含所有解析结果的数据结构
            
        Raises:
            ValueError: 如果文件格式无效
        """
        self._reader.seek(0)
        
        # 1. FileHeader
        magic = self._reader.read(4)
        magic_padding = self._reader.read(4)  # 填充字节
        version = self._reader.read_u32()
        header_length = self._reader.read_u32()
        prog_version = self._reader.read_string(16)
        
        file_header = FileHeader(
            magic=magic,
            version=version,
            header_length=header_length,
            prog_version=prog_version
        )
        
        if not file_header.is_valid:
            raise ValueError(f"Invalid RDC magic: {magic.hex()}, expected 'RDOC'")
        
        # 2. BinaryThumbnail
        thumb_width = self._reader.read_u16()
        thumb_height = self._reader.read_u16()
        thumb_length = self._reader.read_u32()
        thumb_data = self._reader.read(thumb_length) if thumb_length > 0 else b''
        
        thumbnail = Thumbnail(
            width=thumb_width,
            height=thumb_height,
            data=thumb_data
        )
        
        # 3. CaptureMetaData
        machine_ident = self._reader.read_u64()
        driver_id_raw = self._reader.read_u32()
        driver_name_length = self._reader.read_u8()
        driver_name = self._reader.read_string(driver_name_length)
        
        try:
            driver_id = RDCDriver(driver_id_raw)
        except ValueError:
            driver_id = RDCDriver.Unknown
        
        metadata = CaptureMetaData(
            machine_ident=machine_ident,
            driver_id=driver_id,
            driver_name=driver_name
        )
        
        # 4. TimeBase (v1.2+)
        time_base = None
        if version >= RDC_VERSION_1_2:
            tb = self._reader.read_u64()
            tf = self._reader.read_f64()
            time_base = TimeBase(time_base=tb, time_freq=tf)
        
        # 跳过到 header 结束
        current_pos = self._reader.tell()
        if current_pos < header_length:
            self._reader.seek(header_length)
        
        # 5. 解析 Sections
        sections = self._parse_all_sections()
        
        self._rdc_info = RDCFileInfo(
            file_path=self._filepath,
            file_size=self._file_size,
            header=file_header,
            thumbnail=thumbnail,
            capture_meta=metadata,
            time_base=time_base,
            sections=sections
        )
        
        return self._rdc_info
    
    def _parse_all_sections(self) -> List[SectionInfo]:
        """解析所有 Section Header"""
        sections = []
        while self._reader.tell() < self._file_size:
            section = self._parse_section_header()
            if section is None:
                break
            sections.append(section)
            # 跳过 section 数据
            self._reader.seek(section.data_offset + section.compressed_size)
        return sections
    
    def _parse_section_header(self) -> Optional[SectionInfo]:
        """
        解析单个 Section Header。
        
        Returns:
            SectionInfo: Section 元信息，或 None（到达文件末尾）
            
        Raises:
            NotImplementedError: ASCII section 格式
            ValueError: 无效的 section 标记
        """
        header_offset = self._reader.tell()
        
        if header_offset >= self._file_size:
            return None
        
        # 读取第一个字节判断是 ASCII 还是 Binary
        is_ascii = self._reader.read_u8()
        
        if is_ascii == ord('A'):
            # ASCII Section (不常用，简化处理)
            raise NotImplementedError("ASCII sections not supported")
        elif is_ascii != 0:
            raise ValueError(f"Invalid section marker: 0x{is_ascii:02x}")
        
        # Binary Section
        zero = self._reader.read(3)  # 保留字节
        section_type_raw = self._reader.read_u32()
        compressed_length = self._reader.read_u64()
        uncompressed_length = self._reader.read_u64()
        section_version = self._reader.read_u64()
        section_flags_raw = self._reader.read_u32()
        name_length = self._reader.read_u32()
        
        if name_length == 0 or name_length > 2048:
            raise ValueError(f"Invalid section name length: {name_length}")
        
        name = self._reader.read_string(name_length)
        
        try:
            section_type = SectionType(section_type_raw)
        except ValueError:
            section_type = SectionType.Unknown
        
        try:
            section_flags = SectionFlags(section_flags_raw)
        except ValueError:
            section_flags = SectionFlags.NoFlags
        
        data_offset = self._reader.tell()
        
        return SectionInfo(
            section_type=section_type,
            name=name,
            compressed_size=compressed_length,
            uncompressed_size=uncompressed_length,
            version=section_version,
            flags=section_flags,
            data_offset=data_offset,
            header_offset=header_offset
        )
    
    def read_section_data(self, section: SectionInfo) -> bytes:
        """
        读取并解压 Section 数据。
        
        Args:
            section: Section 元信息
            
        Returns:
            bytes: 解压后的数据
            
        Raises:
            ImportError: 缺少压缩库
        """
        self._reader.seek(section.data_offset)
        compressed_data = self._reader.read(section.compressed_size)
        
        if not section.is_compressed:
            return compressed_data
        
        # 解压
        if section.flags & SectionFlags.LZ4Compressed:
            return self._decompress_lz4_blocks(compressed_data, section.uncompressed_size)
        
        elif section.flags & SectionFlags.ZstdCompressed:
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                return dctx.decompress(compressed_data, max_output_size=section.uncompressed_size)
            except ImportError:
                raise ImportError("需要安装 zstandard 库: pip install zstandard")
        
        return compressed_data
    
    def _decompress_lz4_blocks(self, compressed_data: bytes, uncompressed_size: int) -> bytes:
        """
        解压 RenderDoc 的 LZ4 块格式。
        
        格式说明 (来自 renderdoc/serialise/lz4io.cpp):
        - 数据被分成多个 1MB (lz4BlockSize = 1024*1024) 的块
        - 每个块: [int32 压缩大小] [压缩数据]
        - 使用 LZ4 streaming 模式压缩，需要保持字典上下文
        
        Args:
            compressed_data: 压缩数据
            uncompressed_size: 预期解压后大小
            
        Returns:
            bytes: 解压后的数据
        """
        try:
            import lz4.block
        except ImportError:
            raise ImportError("需要安装 lz4 库: pip install lz4")
        
        LZ4_BLOCK_SIZE = 1024 * 1024  # 1MB
        
        result = bytearray()
        offset = 0
        prev_block = b''  # 用于字典模式
        
        while offset < len(compressed_data):
            # 读取压缩块大小 (int32, little-endian)
            if offset + 4 > len(compressed_data):
                break
            
            comp_size = struct.unpack_from('<i', compressed_data, offset)[0]
            offset += 4
            
            if comp_size <= 0 or comp_size > len(compressed_data) - offset:
                break
            
            # 读取压缩数据
            comp_block = compressed_data[offset:offset + comp_size]
            offset += comp_size
            
            # 解压块（使用前一个块作为字典）
            try:
                if prev_block:
                    # LZ4 streaming 模式需要前一个解压块作为字典
                    decompressed = lz4.block.decompress(
                        comp_block,
                        uncompressed_size=LZ4_BLOCK_SIZE,
                        dict=prev_block
                    )
                else:
                    decompressed = lz4.block.decompress(
                        comp_block,
                        uncompressed_size=LZ4_BLOCK_SIZE
                    )
            except lz4.block.LZ4BlockError as e:
                # 可能是最后一个小块
                try:
                    decompressed = lz4.block.decompress(comp_block)
                except Exception:
                    print(f"Warning: LZ4 decompression failed at offset {offset}: {e}")
                    break
            
            result.extend(decompressed)
            prev_block = bytes(decompressed)  # 保存用于下一个块的字典
            
            # 检查是否已达到预期大小
            if len(result) >= uncompressed_size:
                break
        
        return bytes(result[:uncompressed_size])
    
    def get_frame_capture_data(self) -> bytes:
        """
        获取解压后的 FrameCapture 数据。
        
        Returns:
            bytes: FrameCapture section 的解压数据
            
        Raises:
            ValueError: 找不到 FrameCapture section
        """
        if self._frame_capture_data is not None:
            return self._frame_capture_data
        
        if self._rdc_info is None:
            self.parse()
        
        fc_section = self._rdc_info.frame_capture_section
        if fc_section is None:
            raise ValueError("No FrameCapture section found")
        
        self._frame_capture_data = self.read_section_data(fc_section)
        return self._frame_capture_data
    
    def parse_resource_renames(self) -> Dict[int, str]:
        """
        解析 ResourceRenames Section，返回 ResourceID -> 用户自定义名称 的映射。
        
        RenderDoc UI 允许用户为资源设置自定义名称（右键 -> Set Custom Name）。
        这些名称存储在 RDC 文件的 ResourceRenames section 中，格式为 JSON：
        
        {
            "1234": "MyTexture",
            "5678": "MainBuffer"
        }
        
        Returns:
            Dict[int, str]: ResourceID 到自定义名称的映射
        """
        if self._rdc_info is None:
            self.parse()
        
        # 查找 ResourceRenames section
        renames_section = None
        for section in self._rdc_info.sections:
            if section.section_type == SectionType.ResourceRenames:
                renames_section = section
                break
        
        if renames_section is None:
            return {}
        
        # 读取并解析 JSON
        try:
            data = self.read_section_data(renames_section)
            json_str = data.decode('utf-8')
            raw_dict = json.loads(json_str)
            
            # 转换键为 int
            return {int(k): v for k, v in raw_dict.items()}
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            print(f"Warning: Failed to parse ResourceRenames: {e}")
            return {}


def parse_rdc_file(filepath: str) -> RDCFileInfo:
    """
    便捷函数：解析 RDC 文件并返回结构化信息。
    
    Args:
        filepath: RDC 文件路径
        
    Returns:
        RDCFileInfo: 解析结果
    """
    with open(filepath, 'rb') as f:
        parser = SectionParser(f, filepath)
        return parser.parse()
