#!/usr/bin/env python3
"""Generate cryptographically secure access token for the application."""

import secrets
import string
import sys
import tomli
import tomli_w
from pathlib import Path


def generate_secure_token(length: int = 8) -> str:
    """Generate cryptographically secure random token."""
    alphabet = string.ascii_letters + string.digits + "-_!$*+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def update_config_token(token: str):
    """Update access_token in config.toml."""
    config_path = Path(__file__).parent.parent / "config.toml"

    if not config_path.exists():
        print(f"Error: config.toml not found at {config_path}")
        return False

    with open(config_path, "rb") as f:
        config = tomli.load(f)

    if "app" not in config:
        config["app"] = {}

    config["app"]["access_token"] = token

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    return True


def main():
    import sys

    length = int(sys.argv[1]) if len(sys.argv) > 1 else 8

    # Generate secure token
    token = generate_secure_token(length=length)

    # Update config.toml
    if not update_config_token(token):
        print("Error: Failed to update config.toml")
        return 1

    # Display usage
    app_config = {}
    try:
        config_path = Path(__file__).parent.parent / "config.toml"
        with open(config_path, "rb") as f:
            config = tomli.load(f)
            app_config = config.get("app", {})
    except Exception:
        pass

    port = app_config.get("port", 8080)
    host = app_config.get("host", "0.0.0.0")

    if host == "0.0.0.0":
        host = "localhost"

    print(f"Token: {token}")
    print(f"URL: http://{host}:{port}/?token={token}")


if __name__ == "__main__":
    sys.exit(main())
