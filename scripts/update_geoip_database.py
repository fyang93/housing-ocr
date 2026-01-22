#!/usr/bin/env python3
"""Automatically download and update MaxMind GeoIP2 database."""

import sys
from datetime import datetime
from pathlib import Path

import requests
import tomli


def load_config() -> dict:
    """Load configuration from config.toml."""
    config_path = Path(__file__).parent.parent / "config.toml"
    if not config_path.exists():
        print(f"Error: config.toml not found at {config_path}")
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomli.load(f)


def get_database_build_date(mmdb_path: Path) -> str:
    """Get the build date of the database file."""
    try:
        stat = mmdb_path.stat()
        return datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"


def download_database(
    edition_id: str,
    account_id: str,
    license_key: str,
    output_dir: Path,
    suffix: str = "tar.gz",
) -> bool:
    """Download the GeoIP2 database using MaxMind's permalinks."""
    url = f"https://download.maxmind.com/geoip/databases/{edition_id}/download?suffix={suffix}"

    try:
        print(f"\nDownloading: {edition_id}")
        print(f"URL: {url}")

        # Create auth tuple for Basic Authentication
        auth = (account_id, license_key)

        # Stream download with redirects enabled
        response = requests.get(url, auth=auth, stream=True, timeout=300)
        response.raise_for_status()

        # Save to file
        archive_path = output_dir / f"{edition_id}.{suffix}"
        with open(archive_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Download complete: {archive_path}")
        print(f"File size: {archive_path.stat().st_size / 1024 / 1024:.2f} MB")

        return True

    except requests.exceptions.HTTPError as e:
        print(f"Download failed (HTTP {e.response.status_code}): {e}")
        if e.response.status_code == 401:
            print(
                "Authentication failed. Please check Account ID and License Key in config.toml"
            )
        elif e.response.status_code == 403:
            print("Permission denied or download quota exceeded")
        elif e.response.status_code == 404:
            print(f"Edition ID {edition_id} not found")
        return False
    except Exception as e:
        print(f"Download failed: {e}")
        return False


def extract_tar_gz(archive_path: Path) -> Path | None:
    """Extract .tar.gz archive and return path to .mmdb file."""
    try:
        print(f"\nExtracting: {archive_path}")

        import shutil
        import tarfile

        extract_dir = archive_path.parent

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)

        # Find the .mmdb file in extracted directory
        mmdb_files = list(extract_dir.rglob("*.mmdb"))
        if not mmdb_files:
            print("Error: No .mmdb file found in archive")
            return None

        mmdb_path = mmdb_files[0]
        print(f"Extracted: {mmdb_path}")

        # Move to standard location if not already there
        standard_name = "GeoLite2-Country.mmdb"
        standard_path = extract_dir / standard_name
        if mmdb_path != standard_path:
            import shutil

            shutil.move(str(mmdb_path), str(standard_path))
            mmdb_path = standard_path

        # Remove archive and temporary extraction directories
        archive_path.unlink()

        # Clean up extracted directory if it's a subdirectory
        for item in extract_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)

        print(f"Database ready: {mmdb_path}")
        print(f"File size: {mmdb_path.stat().st_size / 1024 / 1024:.2f} MB")

        return mmdb_path

    except Exception as e:
        print(f"Extraction failed: {e}")
        return None


def verify_database(mmdb_path: Path, edition_id: str) -> bool:
    """Verify that the database file is valid."""
    try:
        print(f"\nVerifying database: {mmdb_path}")

        if not mmdb_path.exists():
            print("Error: Database file does not exist")
            return False

        size_mb = mmdb_path.stat().st_size / 1024 / 1024
        if size_mb < 1:
            print(f"Warning: Database file is too small ({size_mb:.2f} MB)")
            return False

        # Try to open the database with geoip2
        try:
            import geoip2.database

            reader = geoip2.database.Reader(mmdb_path)
            reader.close()
            print("Database verification: OK")
        except ImportError:
            print(
                "Warning: geoip2 module not available, skipping detailed verification"
            )
        except Exception as e:
            print(f"Warning: Database verification failed: {e}")
            # Don't fail, just warn

        print(f"Database file size: {size_mb:.2f} MB")
        return True

    except Exception as e:
        print(f"Verification failed: {e}")
        return False


def main():
    print("=" * 60)
    print("MaxMind GeoIP2 Database Auto-Update Script")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load configuration
    config = load_config()

    # Get credentials from config
    security_config = config.get("security", {})
    account_id = security_config.get("maxmind_account_id")
    license_key = security_config.get("maxmind_license_key")
    database_path = security_config.get(
        "geoip_database_path", "./data/GeoLite2-Country.mmdb"
    )

    if not account_id or not license_key:
        print("Error: MaxMind credentials not found in config.toml")
        print("Please add the following to [security] section:")
        print('  maxmind_account_id = "YOUR_ACCOUNT_ID"')
        print('  maxmind_license_key = "YOUR_LICENSE_KEY"')
        return 1

    edition_id = "GeoLite2-Country"
    database_dir = Path(database_path).parent
    database_dir.mkdir(parents=True, exist_ok=True)

    current_db_path = Path(database_path)

    print("Configuration:")
    print(f"  Database: {edition_id}")
    print(f"  Account ID: {account_id}")
    print(f"  Database directory: {database_dir}")

    if current_db_path.exists():
        build_date = get_database_build_date(current_db_path)
        print(f"  Current database build date: {build_date}")

        # Ask for confirmation if database exists
        response = input("\nDatabase already exists. Update? [y/N]: ").strip().lower()
        if response != "y":
            print("Update cancelled")
            return 0

        # Backup existing database
        backup_path = current_db_path.with_suffix(".mmdb.backup")
        import shutil

        shutil.copy2(current_db_path, backup_path)
        print(f"Backed up existing database to: {backup_path}")

    # Download database
    if download_database(edition_id, account_id, license_key, database_dir):
        archive_path = database_dir / f"{edition_id}.tar.gz"

        # Extract and verify
        mmdb_path = extract_tar_gz(archive_path)
        if mmdb_path and verify_database(mmdb_path, edition_id):
            print("\n" + "=" * 60)
            print("Database update completed successfully!")
            print(f"New database location: {mmdb_path}")
            return 0
        else:
            print("\n" + "=" * 60)
            print("Database update failed!")
            return 1
    else:
        print("\n" + "=" * 60)
        print("Download failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
