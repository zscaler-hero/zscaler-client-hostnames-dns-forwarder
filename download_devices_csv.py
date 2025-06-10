#!/usr/bin/env python3
"""
Zscaler Devices CSV Downloader

This script connects to the Zscaler One API and downloads only the devices CSV file
using the downloadDevices endpoint. It's a simplified version focused on just
getting the CSV data efficiently.

Usage:
    python download_devices_csv.py [OUTPUT_FILENAME]
    python download_devices_csv.py devices.csv
    python download_devices_csv.py  # Uses auto-generated timestamped filename

Configuration is read from .env file with OAuth credentials.

Copyright (c) 2025 ZHERO srl, Italy
Website: https://zhero.ai

MIT License - see LICENSE file for details
"""

import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional


class ZscalerCSVDownloader:
    """
    Simplified Zscaler One API client for downloading device CSV files.
    """

    def __init__(self, identity_base_url: str, client_id: str, client_secret: str):
        """
        Initialize the CSV downloader.

        Args:
            identity_base_url (str): Zscaler Identity base URL
            client_id (str): OAuth Client ID
            client_secret (str): OAuth Client Secret
        """
        self.identity_base_url = identity_base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret

        # OAuth and API URLs
        self.token_url = f"{self.identity_base_url}/oauth2/v1/token"
        self.api_base_url = "https://api.zsapi.net"

        # Authentication token
        self.access_token: Optional[str] = None

    def authenticate(self) -> bool:
        """
        Authenticate with Zscaler Identity OAuth and obtain access token.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        print("Authenticating with Zscaler One API...")

        # OAuth 2.0 Client Credentials with audience parameter
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": "https://api.zscaler.com",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(
                self.token_url, headers=headers, data=auth_data, timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")

                if self.access_token:
                    expires_in = token_data.get("expires_in", "Unknown")
                    print(
                        f"✓ Authentication successful (expires in {expires_in} seconds)"
                    )
                    return True
                else:
                    print("✗ Authentication failed: No access token received")
                    return False
            else:
                print(f"✗ Authentication failed: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"✗ Authentication failed: Network error - {e}")
            return False

    def download_devices_csv(self, filename: str) -> bool:
        """
        Download devices CSV file from Zscaler.

        Args:
            filename (str): Output filename for the CSV

        Returns:
            bool: True if download successful, False otherwise
        """
        if not self.access_token:
            print("✗ Not authenticated - call authenticate() first")
            return False

        print(f"Downloading devices CSV to: {filename}")

        # Prepare request
        url = f"{self.api_base_url}/zcc/papi/public/v1/downloadDevices"
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "*/*"}

        try:
            # Make download request
            response = requests.get(url, headers=headers, timeout=120)  # 2 min timeout

            if response.status_code == 200:
                # Check content type
                content_type = response.headers.get("Content-Type", "")

                if (
                    "application/octet-stream" in content_type
                    or "text/csv" in content_type
                ):
                    # Save CSV content
                    with open(filename, "wb") as file:
                        file.write(response.content)

                    file_size = len(response.content)
                    print(
                        f"✓ Successfully downloaded {file_size:,} bytes to {filename}"
                    )

                    # Show basic file info
                    lines = response.content.decode("utf-8", errors="ignore").count(
                        "\n"
                    )
                    print(f"  - Estimated records: ~{lines:,} (including header)")

                    return True
                else:
                    print(f"✗ Unexpected content type: {content_type}")
                    print(f"Response preview: {response.text[:200]}")
                    return False

            elif response.status_code == 401:
                print("✗ Download failed: Unauthorized (401)")
                print("Token may have expired or lack necessary permissions")
                return False

            elif response.status_code == 429:
                print("✗ Download failed: Rate limited (429)")
                print("Too many API requests - please wait before retrying")
                return False

            else:
                print(f"✗ Download failed: HTTP {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False

        except requests.exceptions.Timeout:
            print("✗ Download failed: Request timeout")
            print("The download took too long - try again later")
            return False

        except requests.exceptions.RequestException as e:
            print(f"✗ Download failed: Network error - {e}")
            return False

        except IOError as e:
            print(f"✗ Download failed: File write error - {e}")
            return False


def load_environment_config() -> dict:
    """
    Load OAuth configuration from environment variables.

    Returns:
        dict: Configuration dictionary

    Raises:
        SystemExit: If required environment variables are missing
    """
    load_dotenv()

    config = {
        "identity_base_url": os.getenv("ZSCALER_IDENTITY_BASE_URL"),
        "client_id": os.getenv("ZSCALER_CLIENT_ID"),
        "client_secret": os.getenv("ZSCALER_CLIENT_SECRET"),
    }

    missing_vars = [key for key, value in config.items() if not value]

    if missing_vars:
        print("✗ Missing required environment variables:")
        for var in missing_vars:
            env_var = f"ZSCALER_{var.upper()}"
            print(f"  - {env_var}")
        print("\nPlease set these in your .env file")
        print("Example .env file:")
        print("ZSCALER_IDENTITY_BASE_URL=https://[YOUR-ID].zslogin.net")
        print("ZSCALER_CLIENT_ID=your_client_id")
        print("ZSCALER_CLIENT_SECRET=your_client_secret")
        sys.exit(1)

    return config


def generate_default_filename() -> str:
    """
    Generate a default filename with timestamp.

    Returns:
        str: Timestamped filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"zscaler_devices_{timestamp}.csv"


def main():
    """Main function"""

    print("Zscaler Devices CSV Downloader")
    print("=" * 40)

    # Parse command line arguments
    if len(sys.argv) > 2:
        print("Usage: python download_devices_csv.py [OUTPUT_FILENAME]")
        sys.exit(1)

    # Determine output filename
    if len(sys.argv) == 2:
        output_filename = sys.argv[1]
        print(f"Output file: {output_filename}")
    else:
        output_filename = generate_default_filename()
        print(f"Output file: {output_filename} (auto-generated)")

    print()

    # Load configuration
    try:
        config = load_environment_config()
        print(f"Identity URL: {config['identity_base_url']}")
        print(f"Client ID: {config['client_id']}")
        print()
    except SystemExit:
        return

    # Create downloader and authenticate
    downloader = ZscalerCSVDownloader(
        identity_base_url=config["identity_base_url"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
    )

    if not downloader.authenticate():
        print("\n✗ Failed to authenticate with Zscaler One API")
        sys.exit(1)

    # Download CSV file
    print()
    if downloader.download_devices_csv(output_filename):
        print(f"\n✓ CSV download completed successfully!")
        print(f"File saved as: {output_filename}")
        print(f"\nYou can now use this file with:")
        print(
            f"python generate_forward_zones.py {output_filename} zones.conf 10.0.0.12,10.0.0.13 --domain yourdomain.local"
        )
    else:
        print(f"\n✗ CSV download failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
