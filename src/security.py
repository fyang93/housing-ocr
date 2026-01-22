"""
Security middleware for FastAPI application.

This module provides comprehensive security features including:
- Path traversal attack prevention
- IP blacklist/whitelist management
- Security headers
- Rate limiting
- Request logging
"""

import ipaddress
import re
import time
from collections import defaultdict
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        enable_csp: bool = True,
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        if self.enable_csp:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
            response.headers["Content-Security-Policy"] = csp

        # HSTS (HTTP Strict Transport Security)
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


class PathTraversalMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and block path traversal attacks.

    This middleware:
    - Checks for path traversal patterns in URL path
    - Blocks requests with suspicious path components
    - Logs suspicious requests for potential blacklisting
    """

    # Common path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # ../
        r"\.\.\\",  # ..\
        r"%2e%2e/",  # URL encoded ../
        r"%252e%252e/",  # Double URL encoded ../
        r"\.\.%2f",  # Mixed ../
        r"\.\.%5c",  # Mixed ..\
        r"~/",  # Unix home directory
        r"%2fetc%2f",  # /etc/
        r"%5cetc%5c",  # \etc\
        r"\.\.[\\/]",  # ..\ or ../
        r"%2e%2e%2f",  # ../ (encoded)
        r"%2e%2e%5c",  # ..\ (encoded)
        r"\.\.[%]2f",  # ../ (partial encoding)
        r"\.\.[%]5c",  # ..\ (partial encoding)
    ]

    # Allowed path patterns (whitelist)
    ALLOWED_PATHS = [
        r"^/$",  # root
        r"^/api/",  # API endpoints
        r"^/assets/",  # Static files
    ]

    def __init__(
        self, app: ASGIApp, enable_logging: bool = True, blacklist_manager=None
    ):
        super().__init__(app)
        self.enable_logging = enable_logging
        self.blacklist_manager = blacklist_manager
        self.traversal_pattern = re.compile(
            "|".join(self.PATH_TRAVERSAL_PATTERNS), re.IGNORECASE
        )
        self.allowed_pattern = re.compile("|".join(self.ALLOWED_PATHS))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Check if path is in allowed patterns first
        if not self.allowed_pattern.match(path):
            # Check for path traversal patterns
            if self.traversal_pattern.search(path):
                client_ip = self._get_client_ip(request)
                if self.enable_logging:
                    print(
                        f"[SECURITY] Path traversal attempt blocked: "
                        f"IP={client_ip}, Path={path}, Method={request.method}"
                    )

                # Report suspicious activity to blacklist manager
                if self.blacklist_manager:
                    self.blacklist_manager.report_suspicious(client_ip)

                return JSONResponse(
                    content={"detail": "Access denied"},
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check for forwarded headers (reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"


class IPBlacklistManager:
    """
    Manages IP blacklist with automatic suspicious activity detection.

    Features:
    - Manual blacklisting
    - Automatic blacklisting based on suspicious patterns
    - Temporary bans with expiry
    - Persistent storage (in-memory for now, can be extended)
    """

    def __init__(self, auto_ban_threshold: int = 3):
        """
        Initialize the IP blacklist manager.

        Args:
            auto_ban_threshold: Number of suspicious requests before auto-banning
        """
        self.blacklist: dict[str, float] = {}  # IP -> expiry timestamp
        self.suspicious_counts: defaultdict[str, int] = defaultdict(int)
        self.auto_ban_threshold = auto_ban_threshold
        self.ban_duration = 24 * 60 * 60  # 24 hours in seconds

    def is_blacklisted(self, ip: str) -> bool:
        """Check if an IP is blacklisted."""
        if ip not in self.blacklist:
            return False

        # Check if ban has expired
        if time.time() > self.blacklist[ip]:
            del self.blacklist[ip]
            return False

        return True

    def blacklist_ip(self, ip: str, duration: Optional[int] = None) -> None:
        """Manually blacklist an IP."""
        ban_duration = duration or self.ban_duration
        expiry = time.time() + ban_duration
        self.blacklist[ip] = expiry
        print(f"[SECURITY] IP blacklisted: {ip}, Duration: {ban_duration}s")

    def report_suspicious(self, ip: str) -> None:
        """Report suspicious activity from an IP."""
        self.suspicious_counts[ip] += 1

        # Auto-ban if threshold exceeded
        if self.suspicious_counts[ip] >= self.auto_ban_threshold:
            self.blacklist_ip(ip)
            print(f"[SECURITY] IP auto-blacklisted due to suspicious activity: {ip}")

    def whitelist_ip(self, ip: str) -> None:
        """Remove IP from blacklist."""
        if ip in self.blacklist:
            del self.blacklist[ip]
            print(f"[SECURITY] IP whitelisted: {ip}")

        if ip in self.suspicious_counts:
            del self.suspicious_counts[ip]


class IPBlacklistMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce IP blacklist."""

    def __init__(self, app: ASGIApp, blacklist_manager: IPBlacklistManager):
        super().__init__(app)
        self.blacklist_manager = blacklist_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)

        if self.blacklist_manager.is_blacklisted(client_ip):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

        return "unknown"


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Limits requests per IP within a time window.
    """

    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per IP
        """
        self.requests_per_minute = requests_per_minute
        self.requests: defaultdict[str, list[float]] = defaultdict(list)
        self.window = 60  # 60 seconds

    def is_allowed(self, ip: str) -> bool:
        """Check if request from IP is allowed."""
        now = time.time()
        # Clean up old requests
        self.requests[ip] = [
            timestamp
            for timestamp in self.requests[ip]
            if now - timestamp < self.window
        ]

        # Check if under limit
        if len(self.requests[ip]) >= self.requests_per_minute:
            return False

        # Add current request
        self.requests[ip].append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting."""

    def __init__(self, app: ASGIApp, rate_limiter: RateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)

        if not self.rate_limiter.is_allowed(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

        return "unknown"


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, handling proxies.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address as string
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


def is_valid_ip(ip: str) -> bool:
    """
    Validate if string is a valid IP address.

    Args:
        ip: IP address string

    Returns:
        True if valid IP, False otherwise
    """
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False
