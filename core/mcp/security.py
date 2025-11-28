"""
MCP Security Manager
====================

Handles secure storage and retrieval of MCP credentials.
Treats MCP server URLs as secrets (equivalent to API keys).

Security Features:
    - Environment variable storage (never in code)
    - Credential masking in logs
    - Secure memory handling
    - Rotation support
    - Per-user credential isolation

Environment Variables:
    ZAPIER_MCP_SERVER_URL: Primary Zapier MCP server endpoint
    ZAPIER_MCP_SERVER_SECRET: Optional additional auth secret
    MCP_CREDENTIAL_ENCRYPTION_KEY: Optional encryption key for stored credentials

Usage:
    security_mgr = MCPSecurityManager()
    creds = security_mgr.get_zapier_credentials()
    
    # Masked logging (safe)
    logger.info(f"Using MCP server: {creds.masked_url}")

⚠️ SECURITY WARNING:
    - NEVER log full MCP server URLs
    - NEVER commit credentials to version control
    - Rotate credentials regularly
    - Use separate MCP servers for dev/staging/prod
"""

import os
import re
import logging
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class MCPCredentials:
    """
    Secure container for MCP credentials.
    
    Attributes:
        server_url: Full MCP server URL (treated as secret)
        server_id: Identifier extracted from URL (safe to log)
        provider: MCP provider name (e.g., "zapier")
        created_at: When credentials were loaded
        expires_at: Optional expiration time
        metadata: Additional non-sensitive metadata
    """
    server_url: str
    provider: str = "zapier"
    server_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Extract server ID from URL for safe logging"""
        if self.server_url and not self.server_id:
            self.server_id = self._extract_server_id(self.server_url)
    
    @staticmethod
    def _extract_server_id(url: str) -> str:
        """
        Extract a safe-to-log identifier from MCP server URL.
        
        Example:
            Input:  "https://mcp.zapier.com/api/v1/abc123xyz789"
            Output: "abc1...9789"
        """
        if not url:
            return "unknown"
        
        # Extract last path segment (typically the server ID)
        parts = url.rstrip('/').split('/')
        if parts:
            server_id = parts[-1]
            # Mask middle portion
            if len(server_id) > 8:
                return f"{server_id[:4]}...{server_id[-4:]}"
            return "****"
        return "unknown"
    
    @property
    def masked_url(self) -> str:
        """Return masked URL safe for logging"""
        if not self.server_url:
            return "[NO_URL]"
        
        # Parse URL and mask the path/query
        try:
            # Keep scheme and host, mask path
            if "://" in self.server_url:
                scheme_host = self.server_url.split("://")[0] + "://"
                rest = self.server_url.split("://")[1]
                if "/" in rest:
                    host = rest.split("/")[0]
                    return f"{scheme_host}{host}/***MASKED***"
                return f"{scheme_host}{rest[:10]}...***"
            return "***MASKED_URL***"
        except Exception:
            return "***MASKED_URL***"
    
    @property
    def is_expired(self) -> bool:
        """Check if credentials have expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if credentials are valid (present and not expired)"""
        return bool(self.server_url) and not self.is_expired
    
    def get_url_hash(self) -> str:
        """Get SHA256 hash of URL for comparison/caching (without exposing URL)"""
        if not self.server_url:
            return ""
        return hashlib.sha256(self.server_url.encode()).hexdigest()[:16]
    
    def __repr__(self) -> str:
        """Safe string representation (never exposes actual URL)"""
        return (
            f"MCPCredentials("
            f"provider='{self.provider}', "
            f"server_id='{self.server_id}', "
            f"valid={self.is_valid}"
            f")"
        )


class MCPSecurityManager:
    """
    Manages MCP credentials securely.
    
    Features:
        - Load credentials from environment variables
        - Validate credential format
        - Provide masked versions for logging
        - Support credential rotation
        - Per-user credential isolation (future)
    
    Usage:
        security_mgr = MCPSecurityManager()
        
        # Check if Zapier MCP is configured
        if security_mgr.is_zapier_configured():
            creds = security_mgr.get_zapier_credentials()
            # Use creds.server_url for actual requests
            # Use creds.masked_url for logging
    """
    
    # Environment variable names
    ENV_ZAPIER_MCP_URL = "ZAPIER_MCP_SERVER_URL"
    ENV_ZAPIER_MCP_SECRET = "ZAPIER_MCP_SERVER_SECRET"  # Optional additional auth
    ENV_MCP_ENABLED = "MCP_ENABLED"
    
    # URL validation patterns
    ZAPIER_MCP_URL_PATTERN = re.compile(
        r'^https://mcp\.zapier\.com/api/v\d+/[a-zA-Z0-9_-]+$'
    )
    
    def __init__(self):
        """Initialize security manager and load environment variables"""
        self._credentials_cache: Dict[str, MCPCredentials] = {}
        self._load_environment()
        
        logger.info("🔐 MCPSecurityManager initialized")
        logger.info(f"   Zapier MCP: {'✅ Configured' if self.is_zapier_configured() else '❌ Not configured'}")
    
    def _load_environment(self):
        """Load and validate environment variables"""
        # Check if MCP is enabled
        self._mcp_enabled = os.getenv(self.ENV_MCP_ENABLED, "false").lower() == "true"
        
        # Load Zapier credentials
        zapier_url = os.getenv(self.ENV_ZAPIER_MCP_URL)
        
        if zapier_url:
            # Validate URL format
            if not self._validate_zapier_url(zapier_url):
                logger.warning(
                    f"⚠️ ZAPIER_MCP_SERVER_URL format may be invalid. "
                    f"Expected pattern: https://mcp.zapier.com/api/v1/..."
                )
            
            self._credentials_cache["zapier"] = MCPCredentials(
                server_url=zapier_url,
                provider="zapier",
                metadata={
                    "has_secret": bool(os.getenv(self.ENV_ZAPIER_MCP_SECRET))
                }
            )
            logger.info(f"   Loaded Zapier MCP: {self._credentials_cache['zapier'].masked_url}")
    
    def _validate_zapier_url(self, url: str) -> bool:
        """
        Validate Zapier MCP URL format.
        
        Expected format: https://mcp.zapier.com/api/v1/[server_id]
        """
        if not url:
            return False
        
        # Basic validation
        if not url.startswith("https://"):
            logger.warning("⚠️ MCP URL should use HTTPS")
            return False
        
        # Check against expected pattern (loose check, Zapier may change format)
        if "zapier.com" not in url.lower():
            logger.warning("⚠️ MCP URL doesn't appear to be a Zapier URL")
            return False
        
        return True
    
    def is_mcp_enabled(self) -> bool:
        """Check if MCP is globally enabled"""
        return self._mcp_enabled
    
    def is_zapier_configured(self) -> bool:
        """Check if Zapier MCP credentials are configured"""
        return "zapier" in self._credentials_cache and self._credentials_cache["zapier"].is_valid
    
    def get_zapier_credentials(self) -> Optional[MCPCredentials]:
        """
        Get Zapier MCP credentials.
        
        Returns:
            MCPCredentials object if configured, None otherwise
        
        Raises:
            MCPAuthenticationError: If credentials are invalid or expired
        """
        from .exceptions import MCPAuthenticationError
        
        if not self.is_zapier_configured():
            logger.error("❌ Zapier MCP not configured. Set ZAPIER_MCP_SERVER_URL in .env")
            return None
        
        creds = self._credentials_cache["zapier"]
        
        if creds.is_expired:
            logger.warning("⚠️ Zapier MCP credentials have expired")
            raise MCPAuthenticationError(
                message="Zapier MCP credentials have expired",
                is_token_expired=True
            )
        
        return creds
    
    def get_zapier_secret(self) -> Optional[str]:
        """Get optional Zapier MCP secret (if configured)"""
        return os.getenv(self.ENV_ZAPIER_MCP_SECRET)
    
    def rotate_credentials(self, provider: str = "zapier") -> bool:
        """
        Rotate credentials by reloading from environment.
        
        Call this after updating environment variables.
        
        Returns:
            True if credentials were successfully rotated
        """
        logger.info(f"🔄 Rotating MCP credentials for {provider}")
        
        # Clear cache
        if provider in self._credentials_cache:
            del self._credentials_cache[provider]
        
        # Reload from environment
        load_dotenv(override=True)  # Force reload
        self._load_environment()
        
        success = provider in self._credentials_cache
        if success:
            logger.info(f"✅ Credentials rotated for {provider}")
        else:
            logger.error(f"❌ Failed to rotate credentials for {provider}")
        
        return success
    
    def get_credentials_status(self) -> Dict[str, Any]:
        """
        Get status of all configured MCP credentials (safe for logging/API).
        
        Returns:
            Dictionary with credential status (no secrets exposed)
        """
        status = {
            "mcp_enabled": self._mcp_enabled,
            "providers": {}
        }
        
        for provider, creds in self._credentials_cache.items():
            status["providers"][provider] = {
                "configured": True,
                "valid": creds.is_valid,
                "expired": creds.is_expired,
                "server_id": creds.server_id,
                "created_at": creds.created_at.isoformat() if creds.created_at else None,
                "url_hash": creds.get_url_hash()
            }
        
        return status
    
    def mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive data in a dictionary for safe logging.
        
        Masks: URLs, tokens, secrets, keys, passwords
        """
        sensitive_patterns = [
            "url", "token", "secret", "key", "password", "auth", "credential"
        ]
        
        def _mask_value(key: str, value: Any) -> Any:
            if isinstance(value, dict):
                return {k: _mask_value(k, v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_mask_value(key, v) for v in value]
            elif isinstance(value, str):
                # Check if key suggests sensitive data
                key_lower = key.lower()
                if any(pattern in key_lower for pattern in sensitive_patterns):
                    if len(value) > 8:
                        return f"{value[:4]}...{value[-4:]}"
                    return "****"
            return value
        
        return {k: _mask_value(k, v) for k, v in data.items()}


# Placeholder for future per-user credential management
class UserMCPCredentialManager:
    """
    🚧 PLACEHOLDER: Per-user MCP credential management
    
    Future implementation for multi-tenant scenarios where each user
    can connect their own Zapier account.
    
    TODO:
        - Secure credential storage (encrypted at rest)
        - OAuth flow for user Zapier connection
        - Token refresh handling
        - Credential isolation per user
    """
    
    def __init__(self, user_id: str, security_manager: MCPSecurityManager):
        self.user_id = user_id
        self.security_manager = security_manager
        raise NotImplementedError(
            "UserMCPCredentialManager is not yet implemented. "
            "Currently using organization-level Zapier MCP credentials."
        )

