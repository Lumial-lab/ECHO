"""Клієнт офіційного MCP «Сільпо» для прототипу «Пані Одарка».

Публічна поверхня пакета:

    from silpo_mcp import SilpoMCP, TraceLog

    with SilpoMCP() as mcp:
        for tool in mcp.list_tools():
            print(tool["name"])
        print(mcp.text_of(mcp.call("silpo_get_my_profile")))
"""
from .client import McpError, SilpoMCP
from .oauth import AuthError
from .trace import TraceLog, receipt, verify_chain

__all__ = ["SilpoMCP", "McpError", "AuthError", "TraceLog",
           "verify_chain", "receipt"]
__version__ = "0.1.0"
