#!/usr/bin/env python3
"""
RDC Analysis MCP Server - 桥接架构
让 AI（如 Claude/CodeMaker）能够分析 RenderDoc 截帧文件

架构说明:
- MCP Server (本文件): Python 3.8+ 运行，处理 MCP 协议
- RDC Worker (rdc_worker.py): Python 3.6 运行，访问 renderdoc.pyd

使用方式:
  配置 VS Code CodeMaker:
  {
    "mcpServers": {
      "renderdochelper": {
        "command": "py",
        "args": ["-3", "path/to/rdc_mcp.py"]
      }
    }
  }
"""

import os
import sys
import json
import subprocess
from typing import Optional

from mcp.server.fastmcp import FastMCP

# 脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_SCRIPT = os.path.join(SCRIPT_DIR, "rdc_worker.py")

# 创建 MCP 服务器
mcp = FastMCP(
    "RDC Analyzer",
    instructions="RenderDoc 截帧分析工具 - 让 AI 能够打开和分析 .rdc 文件"
)


# ============================================================================
# 桥接层 - 调用 Python 3.6 Worker
# ============================================================================

def _call_worker(command: str, **kwargs) -> dict:
    """
    调用 Python 3.6 的 RDC Worker
    
    Args:
        command: 命令名称
        **kwargs: 命令参数
        
    Returns:
        Worker 返回的 JSON 结果
        
    Raises:
        RuntimeError: Worker 执行失败
    """
    request = {"command": command, **kwargs}
    request_json = json.dumps(request, ensure_ascii=False)
    
    try:
        result = subprocess.run(
            ["py", "-3.6", WORKER_SCRIPT, request_json],
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
        )
        
        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(f"Worker 执行失败: {result.stderr}")
        
        return json.loads(result.stdout)
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Worker 执行超时 (5分钟)")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Worker 返回无效 JSON: {e}")


# ============================================================================
# MCP 工具
# ============================================================================

@mcp.tool()
def rdc_ping() -> str:
    """
    测试 RenderDoc 模块是否可用
    
    Returns:
        包含 Python 版本和状态的 JSON
    """
    try:
        result = _call_worker("ping")
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "suggestion": "检查 Python 3.6 是否安装，或设置 RENDERDOC_PATH 环境变量"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def rdc_open_capture(rdc_path: str) -> str:
    """
    打开 RenderDoc 截帧文件 (.rdc)
    
    Args:
        rdc_path: RDC 文件的完整路径
        
    Returns:
        包含会话 ID 和截帧基本信息的 JSON
    """
    try:
        result = _call_worker("open", rdc_path=rdc_path)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def rdc_get_actions(rdc_path: str, max_count: int = 100) -> str:
    """
    获取 RDC 文件中的绘制调用列表
    
    Args:
        rdc_path: RDC 文件路径
        max_count: 最大返回数量
        
    Returns:
        绘制调用列表 JSON
    """
    try:
        # Worker 会自动打开 rdc_path
        result = _call_worker("get_actions", rdc_path=rdc_path, max_count=max_count)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def rdc_get_textures(rdc_path: str, max_count: int = 50) -> str:
    """
    获取 RDC 文件中的纹理列表
    
    Args:
        rdc_path: RDC 文件路径
        max_count: 最大返回数量
        
    Returns:
        纹理列表 JSON
    """
    try:
        result = _call_worker("get_textures", rdc_path=rdc_path, max_count=max_count)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def rdc_get_buffers(rdc_path: str, max_count: int = 50) -> str:
    """
    获取 RDC 文件中的缓冲区列表
    
    Args:
        rdc_path: RDC 文件路径
        max_count: 最大返回数量
        
    Returns:
        缓冲区列表 JSON
    """
    try:
        result = _call_worker("get_buffers", rdc_path=rdc_path, max_count=max_count)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def rdc_analyze(
    rdc_path: str,
    output_dir: str = "",
    platform: str = "android"
) -> str:
    """
    对 RDC 执行完整分析，生成 HTML 报告
    
    分析内容包括：
    - 性能问题检测（过大纹理、未压缩纹理、冗余渲染等）
    - 资源使用统计（Draw Call、纹理、Buffer）
    - 优化建议生成
    
    Args:
        rdc_path: RDC 文件路径
        output_dir: 输出目录（留空则在 RDC 同目录创建 analysis_output/）
        platform: 目标平台，影响性能阈值 ("pc" 或 "android")
        
    Returns:
        分析摘要 JSON，包含问题统计和输出文件路径
    """
    try:
        result = _call_worker(
            "analyze",
            rdc_path=rdc_path,
            output_dir=output_dir,
            platform=platform
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


# ============================================================================
# 主入口
# ============================================================================

def main():
    """启动 MCP 服务器"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RDC Analysis MCP Server")
    parser.add_argument("--http", action="store_true", help="使用 HTTP 模式")
    parser.add_argument("--port", type=int, default=8000, help="HTTP 端口")
    args = parser.parse_args()
    
    if args.http:
        # HTTP 模式 (团队共享)
        mcp.run(transport="sse", host="0.0.0.0", port=args.port)
    else:
        # stdio 模式 (本地)
        mcp.run()


if __name__ == "__main__":
    main()