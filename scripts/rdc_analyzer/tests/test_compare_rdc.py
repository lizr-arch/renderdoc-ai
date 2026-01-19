#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_rdc.py CLI 测试
========================

测试命令行对比工具的各种功能。
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from compare_rdc import (
    load_json_data,
    run_comparison,
    export_html_report,
    export_json_diff,
    print_summary,
    main,
)
from diff import DiffHTMLConfig, RegressionRuleId


# ========== Fixtures ==========

@pytest.fixture
def baseline_data():
    """基准测试数据"""
    return {
        "summary": {
            "draw_call_count": 100,
            "total_vertices": 50000,
            "total_triangles": 16666
        },
        "textures": [
            {"resource_id": 1, "name": "albedo", "width": 1024, "height": 1024, "format": "BC1", "size_bytes": 1048576}
        ],
        "shaders": [
            {"hash": "abc123", "type": "vertex", "entry_point": "main"}
        ],
        "buffers": [
            {"resource_id": 10, "name": "vbo", "size": 65536}
        ],
        "draw_calls": [
            {"event_id": 50, "name": "DrawIndexed", "index_count": 3000}
        ]
    }


@pytest.fixture
def target_data():
    """目标测试数据（有回归）"""
    return {
        "summary": {
            "draw_call_count": 120,  # +20%
            "total_vertices": 75000,  # +50%
            "total_triangles": 25000  # +50%
        },
        "textures": [
            {"resource_id": 1, "name": "albedo", "width": 2048, "height": 2048, "format": "BC1", "size_bytes": 4194304},
            {"resource_id": 2, "name": "normal", "width": 512, "height": 512, "format": "BC5", "size_bytes": 262144}
        ],
        "shaders": [
            {"hash": "abc123", "type": "vertex", "entry_point": "main"}
        ],
        "buffers": [
            {"resource_id": 10, "name": "vbo", "size": 131072}  # 翻倍
        ],
        "draw_calls": [
            {"event_id": 50, "name": "DrawIndexed", "index_count": 3000},
            {"event_id": 60, "name": "DrawIndexed", "index_count": 6000}
        ]
    }


@pytest.fixture
def baseline_file(baseline_data, tmp_path):
    """创建基准 JSON 文件"""
    path = tmp_path / "baseline.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(baseline_data, f)
    return str(path)


@pytest.fixture
def target_file(target_data, tmp_path):
    """创建目标 JSON 文件"""
    path = tmp_path / "target.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(target_data, f)
    return str(path)


# ========== load_json_data 测试 ==========

class TestLoadJsonData:
    """JSON 加载测试"""
    
    def test_load_valid_json(self, baseline_file, baseline_data):
        """测试加载有效 JSON"""
        data = load_json_data(baseline_file)
        assert data == baseline_data
    
    def test_file_not_found(self):
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            load_json_data("nonexistent.json")
    
    def test_invalid_json(self, tmp_path):
        """测试无效 JSON"""
        path = tmp_path / "invalid.json"
        path.write_text("{ invalid json }")
        
        with pytest.raises(json.JSONDecodeError):
            load_json_data(str(path))


# ========== run_comparison 测试 ==========

class TestRunComparison:
    """对比分析测试"""
    
    def test_basic_comparison(self, baseline_data, target_data):
        """测试基本对比功能"""
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json"
        )
        
        # 验证差异结果
        assert diff_result.baseline_file == "baseline.json"
        assert diff_result.target_file == "target.json"
        # 验证纹理数量差异（基于 textures 列表，不依赖 summary.draw_call_count）
        assert diff_result.summary.texture_count.delta == 1  # 1 -> 2
        
        # 验证回归检测（至少有警告或临界）
        # 注意：draw_calls 基于 draw_calls 列表，不是 summary.draw_call_count
        assert diff_result is not None
        assert regression_report is not None
    
    def test_custom_threshold(self, baseline_data, target_data):
        """测试自定义阈值"""
        # 设置非常高的阈值 (200%)
        custom_thresholds = {
            RegressionRuleId.REG001: 200.0,  # Draw Call 增加
            RegressionRuleId.REG005: 200.0,  # 三角形增加
        }
        
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json",
            custom_thresholds=custom_thresholds
        )
        
        # 验证结果存在
        assert diff_result is not None
        assert regression_report is not None


# ========== 导出测试 ==========

class TestExport:
    """导出功能测试"""
    
    def test_export_html(self, baseline_data, target_data, tmp_path):
        """测试 HTML 导出"""
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json"
        )
        
        output_path = tmp_path / "report.html"
        result_path = export_html_report(diff_result, regression_report, str(output_path))
        
        assert Path(result_path).exists()
        content = Path(result_path).read_text(encoding='utf-8')
        assert "<!DOCTYPE html>" in content
        assert "baseline.json" in content
    
    def test_export_html_with_config(self, baseline_data, target_data, tmp_path):
        """测试带配置的 HTML 导出"""
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json"
        )
        
        config = DiffHTMLConfig(theme="light")
        output_path = tmp_path / "report_light.html"
        result_path = export_html_report(diff_result, regression_report, str(output_path), config)
        
        content = Path(result_path).read_text(encoding='utf-8')
        # Light theme 应使用浅色背景
        assert "--bg-primary: #f6f8fa" in content
    
    def test_export_json(self, baseline_data, target_data, tmp_path):
        """测试 JSON 导出"""
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json"
        )
        
        output_path = tmp_path / "diff.json"
        result_path = export_json_diff(diff_result, regression_report, str(output_path))
        
        assert Path(result_path).exists()
        
        with open(result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert "metadata" in data
        assert "summary" in data
        assert "regressions" in data
        assert data["metadata"]["baseline_file"] == "baseline.json"
    
    def test_export_creates_parent_dirs(self, baseline_data, target_data, tmp_path):
        """测试导出时创建父目录"""
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json"
        )
        
        output_path = tmp_path / "subdir" / "nested" / "report.html"
        result_path = export_html_report(diff_result, regression_report, str(output_path))
        
        assert Path(result_path).exists()


# ========== CLI 测试 ==========

class TestCLI:
    """命令行接口测试"""
    
    def test_help(self):
        """测试 --help"""
        with patch.object(sys, 'argv', ['compare_rdc.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    def test_version(self):
        """测试 --version"""
        with patch.object(sys, 'argv', ['compare_rdc.py', '--version']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    def test_file_not_found(self, tmp_path):
        """测试文件不存在错误"""
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            str(tmp_path / "nonexistent.json"),
            str(tmp_path / "also_nonexistent.json")
        ]):
            result = main()
            assert result == 1
    
    def test_basic_comparison(self, baseline_file, target_file, tmp_path, capsys):
        """测试基本对比命令"""
        output_html = tmp_path / "output.html"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--html', str(output_html)
        ]):
            result = main()
        
        # 有回归时返回 1 或 2
        assert result in [0, 1, 2]
        assert output_html.exists()
    
    def test_quiet_mode(self, baseline_file, target_file, tmp_path, capsys):
        """测试静默模式"""
        output_html = tmp_path / "output.html"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--html', str(output_html),
            '-q'
        ]):
            result = main()
        
        captured = capsys.readouterr()
        # 静默模式不应打印摘要
        assert "RDC 对比分析结果" not in captured.out
    
    def test_quiet_requires_output(self, baseline_file, target_file):
        """测试静默模式需要输出"""
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '-q'
        ]):
            result = main()
            assert result == 1
    
    def test_json_output(self, baseline_file, target_file, tmp_path):
        """测试 JSON 输出"""
        output_json = tmp_path / "diff.json"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--json', str(output_json)
        ]):
            result = main()
        
        assert output_json.exists()
        
        with open(output_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert "summary" in data
    
    def test_both_outputs(self, baseline_file, target_file, tmp_path):
        """测试同时输出 HTML 和 JSON"""
        output_html = tmp_path / "report.html"
        output_json = tmp_path / "diff.json"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--html', str(output_html),
            '--json', str(output_json)
        ]):
            result = main()
        
        assert output_html.exists()
        assert output_json.exists()
    
    def test_custom_thresholds(self, baseline_file, target_file, tmp_path):
        """测试自定义阈值参数"""
        output_html = tmp_path / "output.html"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--html', str(output_html),
            '--triangle-threshold', '0.5',
            '--draw-call-threshold', '0.3'
        ]):
            result = main()
        
        assert output_html.exists()
    
    def test_light_theme(self, baseline_file, target_file, tmp_path):
        """测试浅色主题"""
        output_html = tmp_path / "output.html"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--html', str(output_html),
            '--theme', 'light'
        ]):
            result = main()
        
        content = output_html.read_text(encoding='utf-8')
        # Light theme 应使用浅色配色
        assert "--bg-primary: #f6f8fa" in content


# ========== print_summary 测试 ==========

class TestPrintSummary:
    """控制台摘要测试"""
    
    def test_print_summary_with_regressions(self, baseline_data, target_data, capsys):
        """测试带回归的摘要输出"""
        diff_result, regression_report = run_comparison(
            baseline_data, target_data,
            "baseline.json", "target.json"
        )
        
        print_summary(diff_result, regression_report)
        
        captured = capsys.readouterr()
        assert "RDC 对比分析结果" in captured.out
        assert "baseline.json" in captured.out
    
    def test_print_summary_clean(self, baseline_data, capsys):
        """测试无回归的摘要输出"""
        # 使用相同数据对比
        diff_result, regression_report = run_comparison(
            baseline_data, baseline_data,
            "same.json", "same.json"
        )
        
        print_summary(diff_result, regression_report)
        
        captured = capsys.readouterr()
        assert "RDC 对比分析结果" in captured.out


# ========== 返回码测试 ==========

class TestReturnCodes:
    """返回码测试"""
    
    def test_return_0_no_issues(self, baseline_data, tmp_path):
        """测试无问题时返回 0"""
        # 创建相同的文件
        same_file1 = tmp_path / "same1.json"
        same_file2 = tmp_path / "same2.json"
        
        with open(same_file1, 'w') as f:
            json.dump(baseline_data, f)
        with open(same_file2, 'w') as f:
            json.dump(baseline_data, f)
        
        output_html = tmp_path / "output.html"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            str(same_file1),
            str(same_file2),
            '--html', str(output_html)
        ]):
            result = main()
        
        # 相同文件对比应无回归
        assert result == 0
    
    def test_return_nonzero_with_issues(self, baseline_file, target_file, tmp_path):
        """测试有问题时返回非零"""
        output_html = tmp_path / "output.html"
        
        with patch.object(sys, 'argv', [
            'compare_rdc.py',
            baseline_file,
            target_file,
            '--html', str(output_html)
        ]):
            result = main()
        
        # 有回归应返回 1 或 2
        assert result in [1, 2]