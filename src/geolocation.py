"""
IP Geolocation module for country-based filtering.

Uses MaxMind GeoIP2 database to identify the country of origin for IP addresses.
"""

import ipaddress
from pathlib import Path
from typing import Optional, Callable

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

try:
    import geoip2.database
    import geoip2.errors

    GEOIP2_AVAILABLE = True
except ImportError:
    GEOIP2_AVAILABLE = False


class GeoIPManager:
    """
    Manages IP geolocation using GeoIP2 database.

    Features:
    - Load GeoIP2 database (MaxMind)
    - Query country for IP address
    - Check if IP is from allowed countries
    - Handle errors gracefully when database not available
    - Configurable country whitelist
    """

    def __init__(
        self,
        database_path: Optional[str] = None,
        allowed_countries: Optional[list[str]] = None,
    ):
        """
        Initialize GeoIP manager.

        Args:
            database_path: Path to GeoIP2 Country database (.mmdb file)
                          If None, uses default path: data/GeoLite2-Country.mmdb
            allowed_countries: List of allowed country codes (ISO 3166-1 alpha-2)
                           Examples: ["JP"] for Japan only
                                     ["JP", "US", "CN"] for multiple countries
                                     ["*"] or None to allow all countries
        """
        self.db_path = database_path
        self.reader = None
        self.database_loaded = False

        self.allowed_countries = (
            allowed_countries
            if allowed_countries and allowed_countries != ["*"]
            else None
        )

        if GEOIP2_AVAILABLE:
            self._load_database()

    def _load_database(self) -> None:
        """Load GeoIP2 database."""
        if self.db_path is None:
            # Default path
            self.db_path = str(
                Path(__file__).parent.parent / "data" / "GeoLite2-Country.mmdb"
            )

        db_file = Path(self.db_path)
        if not db_file.exists():
            print(
                f"[GEOIP] GeoIP2 database not found at: {self.db_path}\n"
                f"[GEOIP] To enable geolocation filtering:\n"
                f"  1. Download GeoLite2-Country.mmdb from: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data\n"
                f"  2. Place it in: {db_file.parent}/\n"
                f"  3. Or set custom path in config.toml: [security] geoip_database_path = '/path/to/GeoLite2-Country.mmdb'\n"
                f"[GEOIP] IP geolocation filtering will be DISABLED."
            )
            return

        try:
            self.reader = geoip2.database.Reader(self.db_path)
            self.database_loaded = True
            print(f"[GEOIP] GeoIP2 database loaded successfully: {self.db_path}")
        except (OSError, ValueError, geoip2.errors.GeoIP2Error) as e:
            print(f"[GEOIP] Failed to load GeoIP2 database: {e}")

    def get_country_code(self, ip: str) -> Optional[str]:
        """
        Get country code for an IP address.

        Args:
            ip: IP address string

        Returns:
            Two-letter country code (e.g., 'JP', 'US') or None if not found
        """
        if not self.database_loaded or self.reader is None:
            return None

        try:
            # Validate IP address
            ip_obj = ipaddress.ip_address(ip.strip())

            # Query database
            response = self.reader.country(ip_obj)
            return response.country.iso_code

        except (
            ValueError,
            geoip2.errors.AddressNotFoundError,
            geoip2.errors.GeoIP2Error,
        ):
            return None

    def is_allowed_ip(self, ip: str) -> bool:
        """
        Check if IP address is from an allowed country.

        Args:
            ip: IP address string

        Returns:
            True if IP is from an allowed country, False otherwise
        """
        country_code = self.get_country_code(ip)

        if country_code is None:
            # If geolocation is not available, allow the request
            # This is a safe fallback - better to allow than block legitimate users
            return True

        # If no country restrictions, allow all
        if self.allowed_countries is None:
            return True

        return country_code in self.allowed_countries

    def is_available(self) -> bool:
        """Check if GeoIP database is available and loaded."""
        return self.database_loaded and self.reader is not None

    def close(self) -> None:
        """Close the GeoIP database reader."""
        if self.reader is not None:
            self.reader.close()
            self.reader = None
            self.database_loaded = False


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce IP whitelist based on geolocation.

    Allows only IP addresses from configured countries to access the application.
    """

    def __init__(
        self, app: ASGIApp, geoip_manager: GeoIPManager, enable_geolocation: bool = True
    ):
        """
        Initialize IP whitelist middleware.

        Args:
            app: ASGI application
            geoip_manager: GeoIPManager instance
            enable_geolocation: If False, bypasses geolocation check (useful for testing)
        """
        super().__init__(app)
        self.geoip_manager = geoip_manager
        self.enable_geolocation = enable_geolocation

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and enforce IP whitelist.

        Args:
            request: FastAPI Request object
            call_next: Next middleware/handler in chain

        Returns:
            Response or raises HTTPException
        """
        from fastapi import HTTPException, status
        from src.security import get_client_ip

        # Skip geolocation if disabled
        if not self.enable_geolocation:
            return await call_next(request)

        # Check if GeoIP is available
        if not self.geoip_manager.is_available():
            # GeoIP not available, allow request (safe fallback)
            return await call_next(request)

        # Get client IP
        client_ip = get_client_ip(request)

        # Check if IP is from allowed countries
        if not self.geoip_manager.is_allowed_ip(client_ip):
            # Log blocked IP
            country_code = self.geoip_manager.get_country_code(client_ip)
            allowed = self.geoip_manager.allowed_countries or ["all"]
            print(
                f"[GEOIP] Blocked IP: {client_ip} (Country: {country_code}, Allowed: {allowed})"
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Your location is not allowed.",
            )

        return await call_next(request)
