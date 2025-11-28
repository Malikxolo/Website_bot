"""
MCP Exception Hierarchy
=======================

Custom exceptions for MCP (Model Context Protocol) operations.
Provides granular error handling for authentication, connection,
tool execution, and rate limiting issues.

Usage:
    try:
        result = await mcp_client.execute_tool("gmail_send", params)
    except MCPAuthenticationError:
        # Re-authenticate or refresh tokens
    except MCPRateLimitError as e:
        # Wait and retry after e.retry_after seconds
    except MCPToolExecutionError as e:
        # Log tool-specific error, e.tool_name, e.details
    except MCPError:
        # Generic MCP error fallback
"""

from typing import Optional, Dict, Any


class MCPError(Exception):
    """
    Base exception for all MCP-related errors.
    
    Attributes:
        message: Human-readable error description
        error_code: Optional machine-readable error code
        details: Optional additional error context
    """
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class MCPAuthenticationError(MCPError):
    """
    Raised when MCP authentication fails.
    
    Causes:
        - Invalid or expired MCP server URL
        - Token refresh failure
        - Revoked access permissions
    
    Recovery:
        - Refresh MCP server URL from Zapier dashboard
        - Re-authenticate user
    """
    
    def __init__(
        self, 
        message: str = "MCP authentication failed",
        error_code: Optional[str] = "AUTH_FAILED",
        details: Optional[Dict[str, Any]] = None,
        is_token_expired: bool = False
    ):
        self.is_token_expired = is_token_expired
        super().__init__(message, error_code, details)


class MCPConnectionError(MCPError):
    """
    Raised when connection to MCP server fails.
    
    Causes:
        - Network timeout
        - MCP server unreachable
        - DNS resolution failure
        - SSL/TLS handshake failure
    
    Recovery:
        - Retry with exponential backoff
        - Check network connectivity
        - Verify MCP server URL
    """
    
    def __init__(
        self, 
        message: str = "Failed to connect to MCP server",
        error_code: Optional[str] = "CONNECTION_FAILED",
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        self.retry_after = retry_after  # Seconds to wait before retry
        super().__init__(message, error_code, details)


class MCPToolExecutionError(MCPError):
    """
    Raised when a tool execution fails on the MCP server.
    
    Causes:
        - Tool not found or not configured
        - Invalid tool parameters
        - Downstream service error (e.g., Gmail API failed)
        - Permission denied for tool action
    
    Recovery:
        - Verify tool is configured in Zapier MCP dashboard
        - Check parameter validation
        - Review tool-specific error details
    """
    
    def __init__(
        self, 
        message: str = "Tool execution failed",
        tool_name: Optional[str] = None,
        error_code: Optional[str] = "TOOL_EXECUTION_FAILED",
        details: Optional[Dict[str, Any]] = None,
        is_retriable: bool = False
    ):
        self.tool_name = tool_name
        self.is_retriable = is_retriable
        super().__init__(message, error_code, details)


class MCPRateLimitError(MCPError):
    """
    Raised when rate limit is exceeded.
    
    Causes:
        - Too many requests to MCP server
        - Zapier plan quota exceeded
        - Per-tool rate limit hit
    
    Recovery:
        - Wait for retry_after seconds
        - Implement request queuing
        - Consider upgrading Zapier plan
    """
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded",
        error_code: Optional[str] = "RATE_LIMITED",
        details: Optional[Dict[str, Any]] = None,
        retry_after: int = 60,
        limit_type: Optional[str] = None  # "per_minute", "per_hour", "daily", "plan_quota"
    ):
        self.retry_after = retry_after
        self.limit_type = limit_type
        super().__init__(message, error_code, details)


class MCPValidationError(MCPError):
    """
    Raised when request validation fails.
    
    Causes:
        - Invalid tool parameters
        - Missing required fields
        - Type mismatch in parameters
    
    Recovery:
        - Review tool schema
        - Validate parameters before sending
    """
    
    def __init__(
        self, 
        message: str = "Validation failed",
        error_code: Optional[str] = "VALIDATION_FAILED",
        details: Optional[Dict[str, Any]] = None,
        field_errors: Optional[Dict[str, str]] = None
    ):
        self.field_errors = field_errors or {}
        super().__init__(message, error_code, details)


class MCPServerError(MCPError):
    """
    Raised when MCP server returns an internal error.
    
    Causes:
        - Zapier MCP server internal error
        - Downstream service unavailable
        - Server maintenance
    
    Recovery:
        - Retry with exponential backoff
        - Check Zapier status page
    """
    
    def __init__(
        self, 
        message: str = "MCP server error",
        error_code: Optional[str] = "SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ):
        self.status_code = status_code
        super().__init__(message, error_code, details)

