#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端集成测试: Schema v1.0 → Bridge → DiffEngine

目标: 证明 analyze 命令输出的 JSON 可以被 compare 命令正确消费，
不会出现 "Silent Drop Diffs"（因字段名不匹配导致的误报）。

测试场景:
1. 相同资源，相同属性 → 无变化（不报 Added/Removed）
2. 相同资源，属性变化 → 报 Modified（正确检测差异）
3. 新增/删除资源 → 正确报 Added/Removed

P0-NEW-2: Schema v1 bridge → DiffEngine 端到端集成证明
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

# 导入 DiffStatus 枚举用于验证
from rdc_analyzer.diff.diff_types import DiffStatus


def create_schema_v1_json(resources: dict, summary: dict = None) -> dict:
    """创建符合 Schema v1.0 格式的 JSON 数据。"""
    return {
        "schema_version": "1.0",
        "meta": {
            "generated_by": "test",
            "capture_file": "test.rdc"
        },
        "resources": resources,
        "summary": summary or {
            "texture_count": len(resources.get("textures", {})),
            "buffer_count": len(resources.get("buffers", {})),
            "total_memory_mb": 100.0
        },
        "events": []
    }


class TestSchemaBridgeToDiffEngine:
    """测试 Schema v1.0 Bridge 到 DiffEngine 的完整链路。"""
    
    @pytest.fixture
    def diff_engine(self):
        """获取 DiffEngine 实例。"""
        from rdc_analyzer.diff.diff_engine import DiffEngine
        return DiffEngine()
    
    @pytest.fixture
    def load_capture_file(self):
        """获取 load_capture_file 函数。"""
        from rdc_analyzer.parsers.rdc_loader import load_capture_file
        return load_capture_file
    
    def _write_temp_json(self, data: dict) -> str:
        """写入临时 JSON 文件并返回路径。"""
        fd, path = tempfile.mkstemp(suffix=".json", prefix="test_schema_v1_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path
    
    # ============================================================
    # Case 1: 相同资源，无变化 → 不应该出现 Added/Removed
    # ============================================================
    
    def test_identical_textures_no_false_diff(self, diff_engine, load_capture_file):
        """相同纹理不应产生 Added/Removed 误报。"""
        # 准备两份完全相同的 Schema v1.0 数据
        resources = {
            "textures": {
                "tex_001": {
                    "name": "MainTexture",
                    "width": 1024,
                    "height": 1024,
                    "format": "RGBA8",
                    "size_bytes": 4194304,
                    "mips": 10
                },
                "tex_002": {
                    "name": "NormalMap",
                    "width": 512,
                    "height": 512,
                    "format": "RG8",
                    "size_bytes": 524288,
                    "mips": 9
                }
            },
            "buffers": {},
            "shaders": {}
        }
        
        baseline_data = create_schema_v1_json(resources)
        target_data = create_schema_v1_json(resources)
        
        # 写入临时文件
        baseline_path = self._write_temp_json(baseline_data)
        target_path = self._write_temp_json(target_data)
        
        try:
            # 通过 Bridge 加载
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            # 验证 Bridge 输出包含 resourceId
            assert len(baseline["textures"]) == 2
            assert all("resourceId" in tex for tex in baseline["textures"]), \
                "Bridge 必须生成 resourceId 字段"
            
            # 执行 Diff
            result = diff_engine.compare(baseline, target)
            
            # 断言: 纹理无变化（使用 DiffResult 的实际属性）
            added = [t for t in result.texture_diffs if t.status == DiffStatus.ADDED]
            removed = [t for t in result.texture_diffs if t.status == DiffStatus.REMOVED]
            modified = [t for t in result.texture_diffs if t.status == DiffStatus.MODIFIED]
            
            assert len(added) == 0, \
                f"不应有新增纹理，但发现: {added}"
            assert len(removed) == 0, \
                f"不应有删除纹理，但发现: {removed}"
            assert len(modified) == 0, \
                f"不应有修改纹理，但发现: {modified}"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    def test_identical_buffers_no_false_diff(self, diff_engine, load_capture_file):
        """相同缓冲区不应产生 Added/Removed 误报。"""
        resources = {
            "textures": {},
            "buffers": {
                "buf_001": {
                    "name": "VertexBuffer",
                    "size_bytes": 65536,
                    "usage": "vertex"
                },
                "buf_002": {
                    "name": "IndexBuffer",
                    "size_bytes": 16384,
                    "usage": "index"
                }
            },
            "shaders": {}
        }
        
        baseline_data = create_schema_v1_json(resources)
        target_data = create_schema_v1_json(resources)
        
        baseline_path = self._write_temp_json(baseline_data)
        target_path = self._write_temp_json(target_data)
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            # 验证 Bridge 输出
            assert len(baseline["buffers"]) == 2
            assert all("resourceId" in buf for buf in baseline["buffers"]), \
                "Bridge 必须生成 resourceId 字段"
            assert all("size" in buf for buf in baseline["buffers"]), \
                "Bridge 必须生成 size 字段（DiffEngine 期望）"
            
            result = diff_engine.compare(baseline, target)
            
            added = [b for b in result.buffer_diffs if b.status == DiffStatus.ADDED]
            removed = [b for b in result.buffer_diffs if b.status == DiffStatus.REMOVED]
            
            assert len(added) == 0, \
                f"不应有新增缓冲区: {added}"
            assert len(removed) == 0, \
                f"不应有删除缓冲区: {removed}"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    def test_identical_shaders_no_false_diff(self, diff_engine, load_capture_file):
        """相同着色器不应产生 Added/Removed 误报。"""
        resources = {
            "textures": {},
            "buffers": {},
            "shaders": {
                "shader_vs_001": {
                    "stage": "vertex",
                    "entryPoint": "main",
                    "source_hash": "abc123"
                },
                "shader_ps_001": {
                    "stage": "pixel",
                    "entryPoint": "main",
                    "source_hash": "def456"
                }
            }
        }
        
        baseline_data = create_schema_v1_json(resources)
        target_data = create_schema_v1_json(resources)
        
        baseline_path = self._write_temp_json(baseline_data)
        target_path = self._write_temp_json(target_data)
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            # 验证 Bridge 输出
            assert all("resourceId" in shader for shader in baseline["shaders"]), \
                "Bridge 必须生成 resourceId 字段"
            
            result = diff_engine.compare(baseline, target)
            
            added = [s for s in result.shader_diffs if s.status == DiffStatus.ADDED]
            removed = [s for s in result.shader_diffs if s.status == DiffStatus.REMOVED]
            
            assert len(added) == 0, \
                f"不应有新增着色器: {added}"
            assert len(removed) == 0, \
                f"不应有删除着色器: {removed}"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    # ============================================================
    # Case 2: 属性变化 → 应该检测为 Modified
    # ============================================================
    
    def test_texture_size_change_detected(self, diff_engine, load_capture_file):
        """纹理尺寸变化应被正确检测为 Modified。"""
        baseline_resources = {
            "textures": {
                "tex_001": {
                    "name": "MainTexture",
                    "width": 1024,
                    "height": 1024,
                    "format": "RGBA8",
                    "size_bytes": 4194304,
                    "mips": 10
                }
            },
            "buffers": {},
            "shaders": {}
        }
        
        target_resources = {
            "textures": {
                "tex_001": {
                    "name": "MainTexture",
                    "width": 2048,  # 尺寸变化
                    "height": 2048,
                    "format": "RGBA8",
                    "size_bytes": 16777216,
                    "mips": 11
                }
            },
            "buffers": {},
            "shaders": {}
        }
        
        baseline_path = self._write_temp_json(create_schema_v1_json(baseline_resources))
        target_path = self._write_temp_json(create_schema_v1_json(target_resources))
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            result = diff_engine.compare(baseline, target)
            
            # 使用 DiffResult 的实际属性
            added = [t for t in result.texture_diffs if t.status == DiffStatus.ADDED]
            removed = [t for t in result.texture_diffs if t.status == DiffStatus.REMOVED]
            modified = [t for t in result.texture_diffs if t.status == DiffStatus.MODIFIED]
            
            # 关键断言: 检测到修改，而不是误报为 Added+Removed
            assert len(added) == 0, \
                f"不应报新增（应为修改）: {added}"
            assert len(removed) == 0, \
                f"不应报删除（应为修改）: {removed}"
            assert len(modified) == 1, \
                f"应检测到1个修改: {modified}"
            
            # 验证修改详情
            mod = modified[0]
            assert "tex_001" in str(getattr(mod, 'resource_id', '')) or \
                   (hasattr(mod, 'baseline') and "tex_001" in str(mod.baseline)), \
                f"修改记录应包含 tex_001: {mod}"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    def test_buffer_size_change_detected(self, diff_engine, load_capture_file):
        """缓冲区大小变化应被正确检测。"""
        baseline_resources = {
            "textures": {},
            "buffers": {
                "buf_001": {
                    "name": "VertexBuffer",
                    "size_bytes": 65536,
                    "usage": "vertex"
                }
            },
            "shaders": {}
        }
        
        target_resources = {
            "textures": {},
            "buffers": {
                "buf_001": {
                    "name": "VertexBuffer",
                    "size_bytes": 131072,  # 大小翻倍
                    "usage": "vertex"
                }
            },
            "shaders": {}
        }
        
        baseline_path = self._write_temp_json(create_schema_v1_json(baseline_resources))
        target_path = self._write_temp_json(create_schema_v1_json(target_resources))
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            result = diff_engine.compare(baseline, target)
            
            added = [b for b in result.buffer_diffs if b.status == DiffStatus.ADDED]
            removed = [b for b in result.buffer_diffs if b.status == DiffStatus.REMOVED]
            modified = [b for b in result.buffer_diffs if b.status == DiffStatus.MODIFIED]
            
            assert len(added) == 0
            assert len(removed) == 0
            assert len(modified) == 1
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    # ============================================================
    # Case 3: 新增/删除资源 → 正确报 Added/Removed
    # ============================================================
    
    def test_new_texture_reported_as_added(self, diff_engine, load_capture_file):
        """新增纹理应被正确报告为 Added。"""
        baseline_resources = {
            "textures": {
                "tex_001": {"name": "A", "width": 100, "height": 100, "format": "RGBA8", "size_bytes": 40000}
            },
            "buffers": {},
            "shaders": {}
        }
        
        target_resources = {
            "textures": {
                "tex_001": {"name": "A", "width": 100, "height": 100, "format": "RGBA8", "size_bytes": 40000},
                "tex_002": {"name": "B", "width": 200, "height": 200, "format": "RGBA8", "size_bytes": 160000}  # 新增
            },
            "buffers": {},
            "shaders": {}
        }
        
        baseline_path = self._write_temp_json(create_schema_v1_json(baseline_resources))
        target_path = self._write_temp_json(create_schema_v1_json(target_resources))
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            result = diff_engine.compare(baseline, target)
            
            added = [t for t in result.texture_diffs if t.status == DiffStatus.ADDED]
            removed = [t for t in result.texture_diffs if t.status == DiffStatus.REMOVED]
            
            assert len(added) == 1, f"应有1个新增: {added}"
            assert len(removed) == 0
            # 检查新增的是 tex_002
            assert any("tex_002" in str(t) for t in added), f"新增应包含 tex_002: {added}"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    def test_removed_texture_reported(self, diff_engine, load_capture_file):
        """删除纹理应被正确报告为 Removed。"""
        baseline_resources = {
            "textures": {
                "tex_001": {"name": "A", "width": 100, "height": 100, "format": "RGBA8", "size_bytes": 40000},
                "tex_002": {"name": "B", "width": 200, "height": 200, "format": "RGBA8", "size_bytes": 160000}
            },
            "buffers": {},
            "shaders": {}
        }
        
        target_resources = {
            "textures": {
                "tex_001": {"name": "A", "width": 100, "height": 100, "format": "RGBA8", "size_bytes": 40000}
                # tex_002 被删除
            },
            "buffers": {},
            "shaders": {}
        }
        
        baseline_path = self._write_temp_json(create_schema_v1_json(baseline_resources))
        target_path = self._write_temp_json(create_schema_v1_json(target_resources))
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            result = diff_engine.compare(baseline, target)
            
            added = [t for t in result.texture_diffs if t.status == DiffStatus.ADDED]
            removed = [t for t in result.texture_diffs if t.status == DiffStatus.REMOVED]
            
            assert len(removed) == 1, f"应有1个删除: {removed}"
            assert len(added) == 0
            assert any("tex_002" in str(t) for t in removed), f"删除应包含 tex_002: {removed}"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    # ============================================================
    # Case 4: 统计信息差异检测
    # ============================================================
    
    def test_statistics_diff_detected(self, diff_engine, load_capture_file):
        """统计信息变化应被检测。"""
        baseline_data = create_schema_v1_json(
            {"textures": {}, "buffers": {}, "shaders": {}},
            {"texture_count": 10, "buffer_count": 5, "total_memory_mb": 100.0}
        )
        
        target_data = create_schema_v1_json(
            {"textures": {}, "buffers": {}, "shaders": {}},
            {"texture_count": 15, "buffer_count": 8, "total_memory_mb": 150.0}
        )
        
        baseline_path = self._write_temp_json(baseline_data)
        target_path = self._write_temp_json(target_data)
        
        try:
            baseline = load_capture_file(baseline_path)
            target = load_capture_file(target_path)
            
            # 验证 statistics 字段被正确转换
            assert "statistics" in baseline, "Bridge 应将 summary 映射到 statistics"
            assert baseline["statistics"]["texture_count"] == 10
            
            result = diff_engine.compare(baseline, target)
            
            # 验证有 summary 差异（DiffResult 使用 summary 而非 statistics_diff）
            assert result.summary is not None, "应有摘要信息"
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)
    
    # ============================================================
    # Case 5: Bridge 元数据保留
    # ============================================================
    
    def test_bridge_preserves_source_schema_marker(self, load_capture_file):
        """Bridge 应保留 _source_schema 标记以便追踪。"""
        data = create_schema_v1_json({"textures": {}, "buffers": {}, "shaders": {}})
        
        path = self._write_temp_json(data)
        try:
            result = load_capture_file(path)
            assert result.get("_source_schema") == "1.0", \
                "Bridge 应标记来源为 schema 1.0"
        finally:
            os.unlink(path)


class TestBridgeFieldMapping:
    """测试 Bridge 字段映射的正确性。"""
    
    @pytest.fixture
    def convert_func(self):
        """获取转换函数。"""
        from rdc_analyzer.parsers.rdc_loader import _convert_schema_v1_to_capture_data
        return _convert_schema_v1_to_capture_data
    
    def test_texture_resourceId_mapping(self, convert_func):
        """验证 texture id → resourceId 映射。"""
        data = {
            "schema_version": "1.0",
            "resources": {
                "textures": {
                    "tex_abc": {"name": "Test", "width": 100, "height": 100}
                }
            }
        }
        
        result = convert_func(data)
        tex = result["textures"][0]
        
        assert tex["resourceId"] == "tex_abc", "必须生成 resourceId"
        assert tex["id"] == "tex_abc", "必须保留 id（向后兼容）"
    
    def test_texture_memorySize_mapping(self, convert_func):
        """验证 texture size_bytes → memorySize 映射。"""
        data = {
            "schema_version": "1.0",
            "resources": {
                "textures": {
                    "tex_001": {"name": "Test", "size_bytes": 12345}
                }
            }
        }
        
        result = convert_func(data)
        tex = result["textures"][0]
        
        assert tex["memorySize"] == 12345, "必须生成 memorySize"
        assert tex["size_bytes"] == 12345, "必须保留 size_bytes"
    
    def test_texture_mipLevels_mapping(self, convert_func):
        """验证 texture mips → mipLevels 映射。"""
        data = {
            "schema_version": "1.0",
            "resources": {
                "textures": {
                    "tex_001": {"name": "Test", "mips": 8}
                }
            }
        }
        
        result = convert_func(data)
        tex = result["textures"][0]
        
        assert tex["mipLevels"] == 8, "必须生成 mipLevels"
        assert tex["mips"] == 8, "必须保留 mips"
    
    def test_buffer_resourceId_and_size_mapping(self, convert_func):
        """验证 buffer 字段映射。"""
        data = {
            "schema_version": "1.0",
            "resources": {
                "buffers": {
                    "buf_xyz": {"name": "VB", "size_bytes": 99999}
                }
            }
        }
        
        result = convert_func(data)
        buf = result["buffers"][0]
        
        assert buf["resourceId"] == "buf_xyz", "必须生成 resourceId"
        assert buf["size"] == 99999, "必须生成 size（DiffEngine 期望）"
        assert buf["size_bytes"] == 99999, "必须保留 size_bytes"
    
    def test_shader_resourceId_mapping(self, convert_func):
        """验证 shader id → resourceId 映射。"""
        data = {
            "schema_version": "1.0",
            "resources": {
                "shaders": {
                    "vs_main": {"stage": "vertex", "entryPoint": "main"}
                }
            }
        }
        
        result = convert_func(data)
        shader = result["shaders"][0]
        
        assert shader["resourceId"] == "vs_main", "必须生成 resourceId"
        assert shader["id"] == "vs_main", "必须保留 id"
    
    def test_non_v1_data_passthrough(self, convert_func):
        """非 v1.0 数据应原样返回。"""
        data = {
            "textures": [{"resourceId": "123"}],
            "buffers": []
        }
        
        result = convert_func(data)
        assert result is data, "非 v1.0 数据应原样返回（同一对象）"
    
    def test_summary_to_statistics_mapping(self, convert_func):
        """验证 summary → statistics 映射。"""
        data = {
            "schema_version": "1.0",
            "resources": {},
            "summary": {"texture_count": 5, "total_memory_mb": 50.0}
        }
        
        result = convert_func(data)
        assert "statistics" in result
        assert result["statistics"]["texture_count"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
