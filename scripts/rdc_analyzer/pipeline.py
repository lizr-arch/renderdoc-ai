"""
分析管线
========

协调解析器、分析器、规则和报告生成器的主流程。
"""

from typing import Optional, List
from .core.context import AnalysisContext
from .config import get_thresholds
from .core.result import AnalysisResult
from .core.types import ParsedData
from .parsers import APIParser, BinaryParser
from .analyzers import (
    FrameAnalyzer,
    ResourceAnalyzer,
    PassAnalyzer,
    StateAnalyzer,
)
from .rules import RuleRegistry, RuleRunner, register_all_rules
from .reporters import JSONReporter, HTMLReporter, CSVReporter, ConsoleReporter, ReportData


class AnalysisPipeline:
    """
    分析管线
    
    协调整个分析流程:
    1. 解析 RDC 文件
    2. 运行分析器
    3. 运行规则检测
    4. 生成报告
    """
    
    def __init__(
        self,
        rdc_path: str,
        platform: str = "pc",
        use_api: bool = True,
    ):
        """
        初始化管线
        
        Args:
            rdc_path: RDC 文件路径
            platform: 平台 (pc/mobile)
            use_api: 是否使用 RenderDoc API (False 则使用二进制解析)
        """
        self.rdc_path = rdc_path
        self.platform = platform
        self.use_api = use_api
        
        # 注册所有规则
        register_all_rules()
    
    def run(self) -> AnalysisResult:
        """
        执行完整分析
        
        Returns:
            分析结果
        """
        # Step 1: 解析
        parsed = self._parse()
        
        # Step 2: 创建上下文
        context = AnalysisContext(
            parsed=parsed,
            platform=self.platform,
            thresholds=get_thresholds(self.platform),
        )
        
        # Step 3: 运行分析器
        self._analyze(context)
        
        # Step 4: 运行规则
        issues = self._check_rules(context)
        
        # Step 5: 生成结果
        return context.to_result(issues)
    
    def _parse(self) -> ParsedData:
        """解析 RDC 文件"""
        if self.use_api:
            parser = APIParser(self.rdc_path)
        else:
            parser = BinaryParser(self.rdc_path)
        
        return parser.parse()
    
    def _analyze(self, context: AnalysisContext):
        """运行所有分析器"""
        analyzers = [
            FrameAnalyzer(context),
            ResourceAnalyzer(context),
            PassAnalyzer(context),
            StateAnalyzer(context),
        ]
        
        for analyzer in analyzers:
            analyzer.analyze()
    
    def _check_rules(self, context: AnalysisContext) -> list:
        """运行规则检测"""
        runner = RuleRunner(context)
        return runner.run()


def analyze_rdc(
    rdc_path: str,
    platform: str = "pc",
    use_api: bool = True,
    output_format: str = "console",
    output_path: Optional[str] = None,
) -> AnalysisResult:
    """
    便捷分析函数
    
    Args:
        rdc_path: RDC 文件路径
        platform: 平台
        use_api: 使用 API 或二进制解析
        output_format: 输出格式 (json/csv/html/console)
        output_path: 输出文件路径
        
    Returns:
        分析结果
    """
    pipeline = AnalysisPipeline(
        rdc_path=rdc_path,
        platform=platform,
        use_api=use_api,
    )
    
    result = pipeline.run()
    
    # 创建报告数据
    report_data = ReportData(
        file_path=rdc_path,
        platform=platform,
        api=result.api if hasattr(result, 'api') else "D3D11",
        frame_summary=result.frame_summary if hasattr(result, 'frame_summary') else None,
        issues=result.issues if hasattr(result, 'issues') else [],
    )
    
    # 选择报告器
    reporters = {
        "json": JSONReporter,
        "csv": CSVReporter,
        "html": HTMLReporter,
        "console": ConsoleReporter,
    }
    
    reporter_cls = reporters.get(output_format, ConsoleReporter)
    reporter = reporter_cls(report_data)
    
    # 输出
    if output_path:
        reporter.save(output_path)
    else:
        reporter.print_to_console()
    
    return result
