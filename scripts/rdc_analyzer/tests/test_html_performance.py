"""
HTML Performance Tab 测试
=========================

测试 HTML 导出器的性能分析标签页功能
"""

import pytest
from ..exporters.html_exporter import HTMLExporter, HTMLExportConfig
from ..core.pipeline_state import DrawCallDetail, DrawType


class TestPerformanceHTML:
    """测试性能 HTML 生成"""
    
    def test_no_performance_report(self):
        """测试无性能报告时显示空状态"""
        exporter = HTMLExporter()
        html = exporter._generate_performance_html(None)
        
        assert 'No performance analysis data available' in html
        assert 'empty-state' in html
    
    def test_empty_performance_report(self):
        """测试空性能报告"""
        exporter = HTMLExporter()
        report = {
            'overall_score': 100,
            'issues': [],
            'metrics': {},
            'recommendations': []
        }
        html = exporter._generate_performance_html(report)
        
        assert 'perf-dashboard' in html
        assert '100' in html  # score
        assert 'Excellent' in html  # label
    
    def test_performance_score_colors(self):
        """测试不同分数显示不同颜色"""
        exporter = HTMLExporter()
        
        # Excellent (>= 90)
        html = exporter._generate_performance_html({'overall_score': 95, 'issues': [], 'metrics': {}, 'recommendations': []})
        assert 'perf-score-excellent' in html
        assert 'Excellent' in html
        
        # Good (>= 70)
        html = exporter._generate_performance_html({'overall_score': 75, 'issues': [], 'metrics': {}, 'recommendations': []})
        assert 'perf-score-good' in html
        assert 'Good' in html
        
        # Fair (>= 50)
        html = exporter._generate_performance_html({'overall_score': 55, 'issues': [], 'metrics': {}, 'recommendations': []})
        assert 'perf-score-fair' in html
        assert 'Fair' in html
        
        # Poor (< 50)
        html = exporter._generate_performance_html({'overall_score': 30, 'issues': [], 'metrics': {}, 'recommendations': []})
        assert 'perf-score-poor' in html
        assert 'Needs Improvement' in html
    
    def test_performance_issues_display(self):
        """测试性能问题显示"""
        exporter = HTMLExporter()
        report = {
            'overall_score': 60,
            'issues': [
                {
                    'rule_id': 'PERF001',
                    'message': 'Overdraw detected on render target',
                    'impact_score': 8,
                    'event_id': 100
                },
                {
                    'rule_id': 'PERF003',
                    'message': 'Small batch with only 10 vertices',
                    'impact_score': 3,
                    'event_id': 150
                }
            ],
            'metrics': {'total_draw_calls': 50, 'total_textures': 10},
            'recommendations': []
        }
        html = exporter._generate_performance_html(report)
        
        # 检查问题显示
        assert 'PERF001' in html
        assert 'PERF003' in html
        assert 'Overdraw detected' in html
        assert 'Small batch' in html
        
        # 检查分类卡片
        assert 'perf-category-card' in html
        assert '过度绘制' in html or 'Overdraw' in html
    
    def test_performance_metrics_display(self):
        """测试指标显示"""
        exporter = HTMLExporter()
        report = {
            'overall_score': 80,
            'issues': [],
            'metrics': {
                'total_draw_calls': 123,
                'total_textures': 45
            },
            'recommendations': []
        }
        html = exporter._generate_performance_html(report)
        
        assert '123' in html  # draw calls
        assert '45' in html   # textures
        assert 'Draw Calls Analyzed' in html
        assert 'Textures Analyzed' in html
    
    def test_recommendations_display(self):
        """测试建议显示"""
        exporter = HTMLExporter()
        report = {
            'overall_score': 70,
            'issues': [],
            'metrics': {},
            'recommendations': [
                {'text': 'Consider using texture compression', 'priority': 'high'},
                {'text': 'Batch small draw calls together', 'priority': 'medium'},
                'Simple string recommendation'  # 也支持简单字符串
            ]
        }
        html = exporter._generate_performance_html(report)
        
        assert 'Optimization Recommendations' in html
        assert 'texture compression' in html
        assert 'Batch small draw calls' in html
        assert 'Simple string recommendation' in html
        assert 'HIGH' in html
        assert 'MEDIUM' in html
    
    def test_issue_severity_classification(self):
        """测试问题严重程度分类"""
        exporter = HTMLExporter()
        report = {
            'overall_score': 50,
            'issues': [
                {'rule_id': 'PERF001', 'message': 'Critical issue', 'impact_score': 15},  # >= 10 -> critical
                {'rule_id': 'PERF002', 'message': 'Warning issue', 'impact_score': 7},    # >= 5 -> warning
                {'rule_id': 'PERF003', 'message': 'Info issue', 'impact_score': 2},       # < 5 -> info
            ],
            'metrics': {},
            'recommendations': []
        }
        html = exporter._generate_performance_html(report)
        
        assert 'data-severity="critical"' in html
        assert 'data-severity="warning"' in html
        assert 'data-severity="info"' in html
    
    def test_filter_javascript_included(self):
        """测试包含筛选 JavaScript"""
        exporter = HTMLExporter()
        report = {
            'overall_score': 60,
            'issues': [{'rule_id': 'PERF001', 'message': 'Test', 'impact_score': 5}],
            'metrics': {},
            'recommendations': []
        }
        html = exporter._generate_performance_html(report)
        
        assert 'filterPerfIssues' in html
        assert '<script>' in html


class TestHTMLExporterPerformanceIntegration:
    """测试 HTMLExporter 性能集成"""
    
    def test_export_with_performance_report(self):
        """测试带性能报告的导出"""
        exporter = HTMLExporter()
        
        # 创建最小的 DrawCallDetail
        draws = [
            DrawCallDetail(
                event_id=1,
                name="DrawIndexed",
                draw_type=DrawType.DRAW_INDEXED,
                vertex_count=100,
                instance_count=1
            )
        ]
        
        perf_report = {
            'overall_score': 85,
            'issues': [
                {'rule_id': 'PERF001', 'message': 'Minor overdraw', 'impact_score': 3}
            ],
            'metrics': {'total_draw_calls': 1, 'total_textures': 0},
            'recommendations': [{'text': 'Consider batching', 'priority': 'low'}]
        }
        
        html = exporter.export(
            draws=draws,
            performance_report=perf_report
        )
        
        # 验证性能标签页存在
        assert 'data-tab="performance"' in html
        assert 'tab-performance' in html
        
        # 验证性能数据显示
        assert '85' in html  # score
        assert 'PERF001' in html
        assert 'Minor overdraw' in html
    
    def test_export_without_performance_report(self):
        """测试无性能报告时导出"""
        exporter = HTMLExporter()
        
        draws = [
            DrawCallDetail(
                event_id=1,
                name="DrawIndexed",
                draw_type=DrawType.DRAW_INDEXED,
                vertex_count=100,
                instance_count=1
            )
        ]
        
        html = exporter.export(draws=draws)
        
        # 验证性能标签页存在（但显示空状态）
        assert 'data-tab="performance"' in html
        assert 'No performance analysis data available' in html
