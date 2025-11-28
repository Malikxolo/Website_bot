"""
MCP Client Base Class
=====================

Base client implementation for Model Context Protocol.
Handles tool discovery, execution, and response parsing.

MCP Operations:
    - tools/list: Discover available tools
    - tools/call: Execute a specific tool
    - resources/list: List available resources
    - resources/read: Read a specific resource

Usage:
    client = MCPClient(transport)
    await client.connect()
    
    # Discover tools
    tools = await client.list_tools()
    
    # Execute tool
    result = await client.call_tool("gmail_send_email", {
        "to": "user@example.com",
        "subject": "Hello",
        "body": "Test message"
    })

"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .transport import MCPTransport, MCPRequest, MCPResponse, MCPMethod, JSONRPCErrorCode
from .exceptions import (
    MCPError,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    MCPValidationError,
    MCPServerError,
    MCPRateLimitError
)

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """
    Represents an MCP tool definition.
    
    Attributes:
        name: Unique tool identifier (e.g., "gmail_send_email")
        description: Human-readable description
        input_schema: JSON Schema for tool parameters
        provider: Optional provider name (e.g., "zapier")
        category: Optional category (e.g., "email", "crm")
    """
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    provider: Optional[str] = None
    category: Optional[str] = None
    
    @property
    def required_params(self) -> List[str]:
        """Get list of required parameter names"""
        schema = self.input_schema
        if "properties" in schema:
            return schema.get("required", [])
        return []
    
    @property
    def optional_params(self) -> List[str]:
        """Get list of optional parameter names"""
        schema = self.input_schema
        if "properties" in schema:
            all_params = list(schema["properties"].keys())
            required = set(self.required_params)
            return [p for p in all_params if p not in required]
        return []
    
    @property
    def all_params(self) -> List[str]:
        """Get all parameter names"""
        schema = self.input_schema
        if "properties" in schema:
            return list(schema["properties"].keys())
        return []
    
    def get_param_info(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Get schema information for a specific parameter"""
        schema = self.input_schema
        if "properties" in schema:
            return schema["properties"].get(param_name)
        return None
    
    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """
        Validate parameters against schema.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required params
        for required in self.required_params:
            if required not in params:
                errors.append(f"Missing required parameter: {required}")
            elif params[required] is None:
                errors.append(f"Required parameter cannot be null: {required}")
        
        # Check for unknown params (warning only)
        known_params = set(self.all_params)
        for param in params:
            if param not in known_params and known_params:
                logger.warning(f"Unknown parameter for tool {self.name}: {param}")
        
        # Type validation could be added here using JSON Schema validators
        
        return errors
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPTool":
        """Create MCPTool from dictionary"""
        return cls(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {})),
            provider=data.get("provider"),
            category=data.get("category")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "provider": self.provider,
            "category": self.category,
            "required_params": self.required_params,
            "optional_params": self.optional_params
        }


@dataclass
class MCPToolResult:
    """
    Result from tool execution.
    
    Attributes:
        success: Whether execution succeeded
        tool_name: Name of executed tool
        result: Tool output data
        error: Error details if failed
        execution_time_ms: How long the execution took
    """
    success: bool
    tool_name: str
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[int] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_retriable(self) -> bool:
        """Check if the error is retriable"""
        if self.success:
            return False
        # Rate limit and server errors are retriable
        retriable_codes = [
            JSONRPCErrorCode.SERVER_ERROR,
            JSONRPCErrorCode.RATE_LIMITED
        ]
        return self.error_code in retriable_codes
    
    @classmethod
    def from_response(cls, tool_name: str, response: MCPResponse) -> "MCPToolResult":
        """Create from MCP response"""
        if response.is_success:
            return cls(
                success=True,
                tool_name=tool_name,
                result=response.result,
                execution_time_ms=response.latency_ms
            )
        else:
            return cls(
                success=False,
                tool_name=tool_name,
                error=response.error_message,
                error_code=response.error_code,
                execution_time_ms=response.latency_ms
            )
    
    @classmethod
    def from_error(cls, tool_name: str, error: str, error_code: int = None) -> "MCPToolResult":
        """Create error result"""
        return cls(
            success=False,
            tool_name=tool_name,
            error=error,
            error_code=error_code
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": self.result,
            "error": self.error,
            "error_code": self.error_code,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata
        }


class MCPClient:
    """
    MCP client implementation.
    
    Provides high-level interface for MCP operations:
        - Tool discovery and caching
        - Tool execution with validation
        - Error handling and exception mapping
        - Response parsing
    """
    
    def __init__(
        self,
        transport: MCPTransport,
        cache_tools: bool = True,
        tool_cache_ttl: int = 300,  # 5 minutes
        validate_params: bool = True
    ):
        """
        Initialize MCP client.
        
        Args:
            transport: MCP transport implementation
            cache_tools: Whether to cache tool definitions
            tool_cache_ttl: Tool cache TTL in seconds
            validate_params: Whether to validate params before sending
        """
        self.transport = transport
        self.cache_tools = cache_tools
        self.tool_cache_ttl = tool_cache_ttl
        self.validate_params = validate_params
        
        # Tool cache
        self._tools_cache: Dict[str, MCPTool] = {}
        self._tools_cache_time: Optional[datetime] = None
        
        # Connection state
        self._connected = False
        self._server_info: Optional[Dict[str, Any]] = None
        
        # Stats
        self._call_count = 0
        self._error_count = 0
        
        logger.info("✅ MCPClient initialized")
    
    async def connect(self) -> bool:
        """
        Connect to MCP server.
        
        Establishes transport connection and optionally fetches
        initial tool list for caching.
        
        Returns:
            True if connection successful
            
        Raises:
            MCPConnectionError: If connection fails
        """
        try:
            # Connect transport
            connected = await self.transport.connect()
            
            if not connected:
                raise MCPConnectionError("Transport failed to connect")
            
            self._connected = True
            logger.info("✅ MCP client connected")
            
            # Optionally send initialize request (MCP protocol handshake)
            try:
                init_request = MCPRequest(
                    method=MCPMethod.INITIALIZE,
                    params={
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {}
                        },
                        "clientInfo": {
                            "name": "CS-Agent-MCP-Client",
                            "version": "1.0.0"
                        }
                    }
                )
                
                response = await self.transport.send_request(init_request)
                
                if response.is_success:
                    self._server_info = response.result
                    logger.info(f"✅ MCP handshake successful")
                    if self._server_info:
                        server_name = self._server_info.get("serverInfo", {}).get("name", "Unknown")
                        logger.info(f"   Server: {server_name}")
                else:
                    # Some servers don't support initialize, that's OK
                    logger.debug(f"Initialize not supported or failed: {response.error_message}")
                    
            except Exception as e:
                # Initialize is optional, continue without it
                logger.debug(f"Initialize request failed (continuing): {e}")
            
            # Pre-fetch tools if caching enabled
            if self.cache_tools:
                try:
                    await self.list_tools()
                except Exception as e:
                    logger.warning(f"Failed to pre-fetch tools: {e}")
            
            return True
            
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise MCPConnectionError(f"Failed to connect: {e}")
    
    async def disconnect(self) -> None:
        """
        Disconnect from MCP server.
        """
        await self.transport.disconnect()
        self._connected = False
        self._tools_cache.clear()
        self._tools_cache_time = None
        self._server_info = None
        
        logger.info(f"✅ MCP client disconnected (calls: {self._call_count}, errors: {self._error_count})")
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected and self.transport.is_connected
    
    async def list_tools(self, force_refresh: bool = False) -> List[MCPTool]:
        """
        Get list of available tools.
        
        Args:
            force_refresh: Skip cache and fetch fresh list
            
        Returns:
            List of available tools
            
        Raises:
            MCPConnectionError: If not connected
            MCPServerError: If server returns error
        """
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")
        
        # Check cache
        if not force_refresh and self._is_cache_valid():
            logger.debug(f"Using cached tools ({len(self._tools_cache)} tools)")
            return list(self._tools_cache.values())
        
        # Send tools/list request
        request = MCPRequest(method=MCPMethod.TOOLS_LIST)
        response = await self.transport.send_request(request)
        
        # Handle response
        if not response.is_success:
            self._handle_error_response(response, "list_tools")
        
        # Parse tools
        tools = []
        if response.result:
            tools_data = response.result.get("tools", [])
            for tool_data in tools_data:
                tool = MCPTool.from_dict(tool_data)
                tools.append(tool)
                self._tools_cache[tool.name] = tool
        
        self._tools_cache_time = datetime.now(timezone.utc)
        
        logger.info(f"✅ Loaded {len(tools)} tools from MCP server")
        return tools
    
    async def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """
        Get specific tool by name.
        
        Args:
            tool_name: Tool name to find
            
        Returns:
            MCPTool if found, None otherwise
        """
        # Ensure tools are loaded
        if not self._tools_cache:
            await self.list_tools()
        
        return self._tools_cache.get(tool_name)
    
    async def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        validate: bool = None
    ) -> MCPToolResult:
        """
        Execute a tool.
        
        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            validate: Override default validation setting
            
        Returns:
            Tool execution result
            
        Raises:
            MCPConnectionError: If not connected
            MCPToolExecutionError: If tool execution fails
            MCPValidationError: If parameter validation fails
        """
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")
        
        self._call_count += 1
        should_validate = validate if validate is not None else self.validate_params
        
        logger.info(f"📤 Calling tool: {tool_name}")
        logger.debug(f"   Params: {list(params.keys())}")
        
        # Get tool definition for validation
        tool = await self.get_tool(tool_name)
        
        # Validate parameters
        if should_validate and tool:
            errors = tool.validate_params(params)
            if errors:
                error_msg = "; ".join(errors)
                logger.error(f"❌ Validation failed for {tool_name}: {error_msg}")
                raise MCPValidationError(
                    message=f"Invalid parameters for {tool_name}: {error_msg}",
                    field_errors={tool_name: errors}
                )
        
        # Send tools/call request
        request = MCPRequest(
            method=MCPMethod.TOOLS_CALL,
            params={
                "name": tool_name,
                "arguments": params
            }
        )
        
        response = await self.transport.send_request(request)
        result = MCPToolResult.from_response(tool_name, response)
        
        # Log result
        if result.success:
            logger.info(f"✅ Tool {tool_name} executed successfully ({result.execution_time_ms:.1f}ms)")
        else:
            self._error_count += 1
            logger.error(f"❌ Tool {tool_name} failed: {result.error}")
            
            # Map to appropriate exception if needed
            if response.is_rate_limited:
                raise MCPRateLimitError(
                    message=f"Rate limited while executing {tool_name}",
                    retry_after=60  # Default, should come from response headers
                )
            elif response.is_auth_error:
                raise MCPAuthenticationError(
                    message=f"Authentication failed for {tool_name}"
                )
        
        return result
    
    async def call_tool_safe(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> MCPToolResult:
        """
        Execute tool with error handling (never raises).
        
        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            
        Returns:
            Tool result (check success field)
        """
        try:
            return await self.call_tool(tool_name, params)
        except MCPValidationError as e:
            logger.error(f"❌ Validation error: {e}")
            return MCPToolResult.from_error(
                tool_name=tool_name,
                error=str(e),
                error_code=JSONRPCErrorCode.INVALID_PARAMS
            )
        except MCPRateLimitError as e:
            logger.error(f"❌ Rate limited: {e}")
            return MCPToolResult.from_error(
                tool_name=tool_name,
                error=str(e),
                error_code=JSONRPCErrorCode.RATE_LIMITED
            )
        except MCPError as e:
            logger.error(f"❌ MCP error: {e}")
            return MCPToolResult.from_error(
                tool_name=tool_name,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error in safe call: {e}")
            return MCPToolResult.from_error(
                tool_name=tool_name,
                error=f"Unexpected error: {e}"
            )
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources from MCP server.
        
        Returns:
            List of resource definitions
        """
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")
        
        request = MCPRequest(method=MCPMethod.RESOURCES_LIST)
        response = await self.transport.send_request(request)
        
        if not response.is_success:
            self._handle_error_response(response, "list_resources")
        
        resources = response.result.get("resources", []) if response.result else []
        logger.info(f"✅ Loaded {len(resources)} resources")
        return resources
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        Read a specific resource.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content
        """
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")
        
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ,
            params={"uri": uri}
        )
        response = await self.transport.send_request(request)
        
        if not response.is_success:
            self._handle_error_response(response, "read_resource")
        
        return response.result or {}
    
    async def ping(self) -> bool:
        """
        Ping MCP server to check health.
        
        Returns:
            True if server is responding
        """
        if not self.is_connected:
            return False
        
        try:
            request = MCPRequest(method=MCPMethod.PING)
            response = await self.transport.send_request(request)
            return response.is_success or response.error_code == JSONRPCErrorCode.METHOD_NOT_FOUND
        except Exception:
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check.
        
        Returns:
            Health status dictionary
        """
        ping_ok = await self.ping() if self.is_connected else False
        
        return {
            "connected": self.is_connected,
            "ping_ok": ping_ok,
            "tools_cached": len(self._tools_cache),
            "cache_valid": self._is_cache_valid(),
            "transport_connected": self.transport.is_connected,
            "server_info": self._server_info,
            "stats": {
                "call_count": self._call_count,
                "error_count": self._error_count,
                "error_rate": self._error_count / max(self._call_count, 1) * 100
            }
        }
    
    def _is_cache_valid(self) -> bool:
        """Check if tool cache is still valid"""
        if not self.cache_tools:
            return False
        
        if not self._tools_cache or not self._tools_cache_time:
            return False
        
        age = (datetime.now(timezone.utc) - self._tools_cache_time).total_seconds()
        return age < self.tool_cache_ttl
    
    def _handle_error_response(self, response: MCPResponse, operation: str):
        """Map MCP error response to appropriate exception"""
        error_code = response.error_code
        error_message = response.error_message or "Unknown error"
        
        if response.is_auth_error:
            raise MCPAuthenticationError(
                message=f"Authentication failed during {operation}: {error_message}",
                is_token_expired=error_code == JSONRPCErrorCode.AUTHENTICATION_FAILED
            )
        
        if response.is_rate_limited:
            raise MCPRateLimitError(
                message=f"Rate limited during {operation}: {error_message}",
                retry_after=60
            )
        
        if error_code == JSONRPCErrorCode.METHOD_NOT_FOUND:
            raise MCPToolExecutionError(
                message=f"Method not found: {operation}",
                tool_name=operation
            )
        
        if error_code == JSONRPCErrorCode.INVALID_PARAMS:
            raise MCPValidationError(
                message=f"Invalid parameters for {operation}: {error_message}"
            )
        
        # Default to server error
        raise MCPServerError(
            message=f"Server error during {operation}: {error_message}",
            status_code=response.http_status
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "connected": self.is_connected,
            "tools_cached": len(self._tools_cache),
            "cache_valid": self._is_cache_valid(),
            "call_count": self._call_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._call_count, 1) * 100
        }
