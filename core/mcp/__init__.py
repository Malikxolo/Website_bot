"""
MCP (Model Context Protocol) Integration Module
================================================

Provides integration with Zapier MCP to enable access to 8000+ 
application integrations through a single client.

Main Components:
    - MCPClient: Base MCP client for protocol communication
    - ZapierMCPClient: Zapier-specific high-level client
    - ZapierToolManager: Bridge to existing tool_manager pattern
    - MCPSecurityManager: Secure credential management

Quick Start:
    from core.mcp import ZapierToolManager, MCPSecurityManager
    
    # Initialize
    security = MCPSecurityManager()
    zapier_tools = ZapierToolManager(security)
    await zapier_tools.initialize()
    
    # Check available tools
    tools = zapier_tools.get_tool_names()
    print(f"Available Zapier tools: {len(tools)}")
    
    # Execute
    result = await zapier_tools.execute(
        tool_name="zapier_gmail_send_email",
        params={"to": "user@example.com", "subject": "Hi", "body": "Hello"}
    )

For full documentation, see core/mcp/IMPLEMENTATION_PLAN.md
"""

# Exceptions
from .exceptions import (
    MCPError,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    MCPRateLimitError,
    MCPValidationError,
    MCPServerError
)

# Security
from .security import (
    MCPSecurityManager,
    MCPCredentials
)

# Transport
from .transport import (
    MCPTransport,
    StreamableHTTPTransport,
    MCPRequest,
    MCPResponse,
    MCPMethod,
    RateLimiter,
    ConnectionPool,
    JSONRPCErrorCode
)

# Client
from .client import (
    MCPClient,
    MCPTool,
    MCPToolResult
)

# Zapier Integration
from .zapier_integration import (
    ZapierMCPClient,
    ZapierToolManager,
    ZapierTool,
    ZapierToolCategory,
    get_zapier_tools_prompt
)

__all__ = [
    # Exceptions
    "MCPError",
    "MCPAuthenticationError",
    "MCPConnectionError",
    "MCPToolExecutionError",
    "MCPRateLimitError",
    "MCPValidationError",
    "MCPServerError",
    
    # Security
    "MCPSecurityManager",
    "MCPCredentials",
    
    # Transport
    "MCPTransport",
    "StreamableHTTPTransport",
    "MCPRequest",
    "MCPResponse",
    "MCPMethod",
    "RateLimiter",
    "ConnectionPool",
    "JSONRPCErrorCode",
    
    # Client
    "MCPClient",
    "MCPTool",
    "MCPToolResult",
    
    # Zapier
    "ZapierMCPClient",
    "ZapierToolManager",
    "ZapierTool",
    "ZapierToolCategory",
    "get_zapier_tools_prompt"
]

# Version
__version__ = "1.0.0"
