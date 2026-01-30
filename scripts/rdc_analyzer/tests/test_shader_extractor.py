"""
Shader 提取器测试
=================

测试 ShaderExtractor 和相关数据模型的功能。

分为两类：
1. 独立测试 (Standalone) - 不需要 RenderDoc，验证数据模型和逻辑
2. 集成测试 (Integration) - 需要 RenderDoc 环境，验证实际提取功能
"""

import unittest
import sys
from pathlib import Path
from dataclasses import asdict

# 添加项目路径 - 包含 rdc_analyzer 父目录 (scripts/)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestShaderDataModels(unittest.TestCase):
    """测试 Shader 数据模型"""
    
    def test_shader_info_import(self):
        """验证 ShaderInfo 可以正确导入"""
        from rdc_analyzer.core.types import ShaderInfo
        self.assertTrue(hasattr(ShaderInfo, '__dataclass_fields__'))
    
    def test_shader_info_fields(self):
        """验证 ShaderInfo 包含所有必需字段"""
        from rdc_analyzer.core.types import ShaderInfo
        
        required_fields = [
            'resource_id', 'type', 'name', 'stage', 'entry_point',
            'source_hlsl', 'source_asm', 'encoding', 'has_debug_info',
            'input_signature', 'output_signature', 'constant_blocks',
            'read_only_resources', 'read_write_resources', 'samplers'
        ]
        
        for field in required_fields:
            self.assertIn(field, ShaderInfo.__dataclass_fields__)
    
    def test_shader_info_creation(self):
        """验证 ShaderInfo 实例化"""
        from rdc_analyzer.core.types import ShaderInfo
        
        shader = ShaderInfo(
            resource_id="0x12345678",
            type="VS",
            name="main",
            stage="Vertex",
            entry_point="VSMain",
            source_asm="mov r0, v0\nret",
            encoding="DXBC"
        )
        
        self.assertEqual(shader.resource_id, "0x12345678")
        self.assertEqual(shader.type, "VS")
        self.assertEqual(shader.stage, "Vertex")
        self.assertEqual(shader.encoding, "DXBC")
        # 默认值
        self.assertEqual(shader.source_hlsl, "")
        self.assertFalse(shader.has_debug_info)
        self.assertEqual(shader.input_signature, [])
    
    def test_shader_signature_creation(self):
        """验证 ShaderSignature 实例化"""
        from rdc_analyzer.core.types import ShaderSignature
        
        sig = ShaderSignature(
            semantic_name="POSITION",
            semantic_index=0,
            register=0,
            component_type="float",
            component_count=4
        )
        
        self.assertEqual(sig.semantic_name, "POSITION")
        self.assertEqual(sig.component_count, 4)
    
    def test_shader_constant_block(self):
        """验证 ShaderConstantBlock 实例化"""
        from rdc_analyzer.core.types import ShaderConstantBlock, ShaderConstant
        
        var = ShaderConstant(
            name="worldMatrix",
            type_name="float4x4",
            byte_offset=0,
            byte_size=64
        )
        
        cb = ShaderConstantBlock(
            name="cbPerObject",
            slot=0,
            byte_size=64,
            variables=[var]
        )
        
        self.assertEqual(cb.name, "cbPerObject")
        self.assertEqual(len(cb.variables), 1)
        self.assertEqual(cb.variables[0].name, "worldMatrix")
    
    def test_shader_resource(self):
        """验证 ShaderResource 实例化"""
        from rdc_analyzer.core.types import ShaderResource
        
        res = ShaderResource(
            name="diffuseTexture",
            slot=0,
            resource_type="Texture2D",
            is_read_only=True
        )
        
        self.assertEqual(res.name, "diffuseTexture")
        self.assertTrue(res.is_read_only)


class TestShaderExtractorModule(unittest.TestCase):
    """测试 ShaderExtractor 模块导入和基础功能"""
    
    def test_extractor_import(self):
        """验证 ShaderExtractor 可以正确导入"""
        from rdc_analyzer.extractors.shader_extractor import ShaderExtractor
        self.assertTrue(callable(ShaderExtractor))
    
    def test_extractor_result_import(self):
        """验证 ShaderExtractorResult 可以正确导入"""
        from rdc_analyzer.extractors.shader_extractor import ShaderExtractorResult
        self.assertTrue(hasattr(ShaderExtractorResult, '__dataclass_fields__'))
    
    def test_factory_function(self):
        """验证工厂函数可以正确导入"""
        from rdc_analyzer.extractors.shader_extractor import create_shader_extractor
        self.assertTrue(callable(create_shader_extractor))
    
    def test_stage_constants(self):
        """验证阶段常量定义正确"""
        from rdc_analyzer.extractors.shader_extractor import SHADER_STAGE_NAMES, SHADER_TYPE_ABBREV
        
        # 验证主要阶段都有定义
        self.assertIn(0, SHADER_STAGE_NAMES)  # Vertex
        self.assertIn(4, SHADER_STAGE_NAMES)  # Pixel
        self.assertIn(5, SHADER_STAGE_NAMES)  # Compute
        
        # 验证缩写映射
        self.assertEqual(SHADER_TYPE_ABBREV["Vertex"], "VS")
        self.assertEqual(SHADER_TYPE_ABBREV["Pixel"], "PS")
        self.assertEqual(SHADER_TYPE_ABBREV["Compute"], "CS")
    
    def test_encoding_constants(self):
        """验证编码常量定义正确"""
        from rdc_analyzer.extractors.shader_extractor import SHADER_ENCODING_NAMES
        
        self.assertIn(1, SHADER_ENCODING_NAMES)  # DXBC
        self.assertIn(5, SHADER_ENCODING_NAMES)  # HLSL
        self.assertIn(6, SHADER_ENCODING_NAMES)  # DXIL


class TestShaderExtractorBasicLogic(unittest.TestCase):
    """测试 ShaderExtractor 的基础逻辑（不需要 RenderDoc）"""
    
    def test_extractor_init_without_controller(self):
        """验证 Extractor 可以在没有 controller 的情况下初始化"""
        from rdc_analyzer.extractors.shader_extractor import ShaderExtractor
        
        extractor = ShaderExtractor(controller=None, rd_module=None)
        self.assertIsNone(extractor.controller)
        self.assertIsNone(extractor.rd)
    
    def test_cache_management(self):
        """验证缓存管理功能"""
        from rdc_analyzer.extractors.shader_extractor import ShaderExtractor
        
        extractor = ShaderExtractor(controller=None)
        
        # 初始缓存应为空
        self.assertEqual(len(extractor._shader_cache), 0)
        
        # 测试清除缓存
        extractor._shader_cache["test"] = "value"
        extractor.clear_cache()
        self.assertEqual(len(extractor._shader_cache), 0)
    
    def test_disassembly_targets_empty(self):
        """验证无 controller 时反汇编目标返回空列表"""
        from rdc_analyzer.extractors.shader_extractor import ShaderExtractor
        
        extractor = ShaderExtractor(controller=None)
        targets = extractor.get_disassembly_targets()
        
        self.assertEqual(targets, [])


class TestShaderInfoSerialization(unittest.TestCase):
    """测试 ShaderInfo 序列化"""
    
    def test_to_dict(self):
        """验证 ShaderInfo 可以转换为字典"""
        from rdc_analyzer.core.types import ShaderInfo, ShaderSignature
        
        shader = ShaderInfo(
            resource_id="0x1234",
            type="PS",
            stage="Pixel",
            input_signature=[
                ShaderSignature(semantic_name="TEXCOORD", semantic_index=0)
            ]
        )
        
        data = asdict(shader)
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['resource_id'], "0x1234")
        self.assertEqual(data['type'], "PS")
        self.assertEqual(len(data['input_signature']), 1)
    
    def test_json_serializable(self):
        """验证 ShaderInfo 可以 JSON 序列化"""
        import json
        from rdc_analyzer.core.types import ShaderInfo
        
        shader = ShaderInfo(
            resource_id="0x1234",
            type="VS",
            source_asm="dcl_position v0\nmov o0, v0\nret"
        )
        
        # raw_bytes 不应该影响 JSON 序列化（使用 asdict 时）
        data = asdict(shader)
        # raw_bytes 默认是空 bytes，asdict 会把它转成 bytes 对象
        # 我们需要手动处理
        data['raw_bytes'] = None  # 或者移除
        
        json_str = json.dumps(data)
        self.assertIn('"resource_id": "0x1234"', json_str)


class TestHTMLShaderIntegration(unittest.TestCase):
    """测试 HTML 导出器中的 Shader 相关功能"""
    
    def test_html_template_has_shader_tab(self):
        """验证 HTML 模板包含 Shaders 标签页"""
        from rdc_analyzer.exporters.html_exporter import HTML_TEMPLATE
        
        self.assertIn('data-tab="shaders"', HTML_TEMPLATE)
        self.assertIn('id="tab-shaders"', HTML_TEMPLATE)
        self.assertIn('shaders-content', HTML_TEMPLATE)
    
    def test_html_template_has_shader_modal(self):
        """验证 HTML 模板包含 Shader 代码模态框"""
        from rdc_analyzer.exporters.html_exporter import HTML_TEMPLATE
        
        self.assertIn('shader-modal', HTML_TEMPLATE)
        self.assertIn('shader-code-content', HTML_TEMPLATE)
        self.assertIn('shader-code-tab', HTML_TEMPLATE)
    
    def test_html_template_has_shader_styles(self):
        """验证 HTML 模板包含 Shader 样式"""
        from rdc_analyzer.exporters.html_exporter import HTML_TEMPLATE
        
        self.assertIn('.shader-card', HTML_TEMPLATE)
        self.assertIn('.shader-stage-badge', HTML_TEMPLATE)
        self.assertIn('.shader-code', HTML_TEMPLATE)
    
    def test_html_template_has_shader_js_functions(self):
        """验证 HTML 模板包含 Shader JavaScript 函数"""
        from rdc_analyzer.exporters.html_exporter import HTML_TEMPLATE
        
        self.assertIn('updateShadersContent', HTML_TEMPLATE)
        self.assertIn('openShaderModal', HTML_TEMPLATE)
        self.assertIn('highlightShaderCode', HTML_TEMPLATE)
        self.assertIn('copyShaderCode', HTML_TEMPLATE)


class TestPackageExports(unittest.TestCase):
    """测试包导出"""
    
    def test_extractors_package_exports(self):
        """验证 extractors 包正确导出 Shader 相关模块"""
        from rdc_analyzer.extractors import (
            ShaderExtractor,
            ShaderExtractorResult,
            create_shader_extractor,
            SHADER_STAGE_NAMES,
            SHADER_TYPE_ABBREV,
            SHADER_ENCODING_NAMES
        )
        
        self.assertTrue(callable(ShaderExtractor))
        self.assertTrue(callable(create_shader_extractor))


# ============================================================================
# 集成测试（需要 RenderDoc 环境）
# ============================================================================

class TestRealShaderExtraction(unittest.TestCase):
    """
    实际 Shader 提取测试（需要 RenderDoc 环境）
    
    这些测试需要在 RenderDoc GUI 的 Python Shell 中运行，
    或者在有 renderdoc 模块可用的环境中运行。
    """
    
    @classmethod
    def setUpClass(cls):
        """检查 RenderDoc 是否可用"""
        try:
            import renderdoc as rd
            cls.rd_available = True
            cls.rd = rd
        except ImportError:
            cls.rd_available = False
            cls.rd = None
    
    @unittest.skipUnless(
        hasattr(sys.modules.get('__main__', None), 'rd_available') or False,
        "需要 RenderDoc 环境"
    )
    def test_extract_from_real_capture(self):
        """从真实捕获中提取 Shader"""
        # 此测试需要在 RenderDoc GUI 中运行
        pass


def run_standalone_tests():
    """运行不需要 RenderDoc 的独立测试"""
    suite = unittest.TestSuite()
    
    # 添加所有独立测试类
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestShaderDataModels))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestShaderExtractorModule))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestShaderExtractorBasicLogic))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestShaderInfoSerialization))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHTMLShaderIntegration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPackageExports))
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == '__main__':
    print("=" * 70)
    print("Shader 提取器测试 (方向 B)")
    print("=" * 70)
    print()
    
    result = run_standalone_tests()
    
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print(f"✅ 所有独立测试通过! ({result.testsRun} tests)")
    else:
        print(f"❌ 测试失败: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 70)
    
    # 如果在 RenderDoc 环境中，提示可以运行集成测试
    try:
        import renderdoc
        print()
        print("检测到 RenderDoc 环境，可以运行集成测试:")
        print("  unittest.main(module='test_shader_extractor', verbosity=2)")
    except ImportError:
        print()
        print("提示: 集成测试需要在 RenderDoc GUI Python Shell 中运行")
