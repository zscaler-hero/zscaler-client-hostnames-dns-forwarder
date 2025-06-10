#!/usr/bin/env python3
"""
Zscaler Forward Zones Generator

This script reads a Zscaler devices CSV file and generates an Unbound DNS forward zones
configuration file for all Windows devices.

PERFORMANCE: Optimized for large datasets (up to 30,000+ hostnames)
- Efficient CSV reading and parsing
- O(1) hostname deduplication using sets
- Memory-optimized configuration generation
- Minimal console output for large datasets

For each Windows device hostname, it creates a forward zone entry like:
forward-zone:
    name: "[hostname].domain.local"
    forward-addr: [DNS_IP_1]
    forward-addr: [DNS_IP_2]  # If multiple DNS servers specified

Usage:
    python generate_forward_zones.py [INPUT_CSV_FILE] [OUTPUT_CONF_FILE] [DNS_IPS]
    python generate_forward_zones.py devices.csv forward_zones.conf 10.213.182.62
    python generate_forward_zones.py devices.csv zones.conf 10.213.182.62,192.168.1.1
    python generate_forward_zones.py devices.csv custom_zones.conf 192.168.1.1 --domain custom.local

Copyright (c) 2025 ZHERO srl, Italy
Website: https://zhero.ai

MIT License - see LICENSE file for details
"""

import csv
import sys
import argparse
from typing import List, Dict, Set
from datetime import datetime
import os


def read_devices_csv(csv_file: str) -> List[Dict[str, str]]:
    """
    Read the Zscaler devices CSV file and return a list of device records.

    Optimized for large files (30k+ records):
    - Uses efficient CSV reading with DictReader
    - Minimal memory overhead during parsing
    - Early detection of file format issues

    Args:
        csv_file (str): Path to the CSV file

    Returns:
        List[Dict[str, str]]: List of device records as dictionaries

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV file is invalid or empty
    """
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    print(f"Reading CSV file: {csv_file}")
    devices = []

    try:
        with open(csv_file, "r", encoding="utf-8") as file:
            # Try to detect if this is a CSV downloaded from the API
            first_line = file.readline().strip()
            file.seek(0)  # Reset to beginning

            # Check if it looks like a CSV header
            if "," in first_line and (
                "hostname" in first_line.lower() or "device" in first_line.lower()
            ):
                reader = csv.DictReader(file)
                devices = list(reader)
            else:
                # If no header detected, try to read as raw CSV and create our own headers
                reader = csv.reader(file)
                rows = list(reader)

                if not rows:
                    raise ValueError("CSV file is empty")

                # Try to detect common Zscaler CSV patterns
                # Look for hostname and device type columns
                header_row = rows[0] if rows else []

                # Common Zscaler CSV headers (case insensitive)
                hostname_keywords = [
                    "hostname",
                    "machine hostname",
                    "machinehostname",
                    "device name",
                ]
                device_type_keywords = [
                    "device type",
                    "devicetype",
                    "type",
                    "os",
                    "platform",
                ]

                hostname_col = None
                device_type_col = None

                for i, header in enumerate(header_row):
                    header_lower = header.lower().strip()
                    if any(keyword in header_lower for keyword in hostname_keywords):
                        hostname_col = i
                    if any(keyword in header_lower for keyword in device_type_keywords):
                        device_type_col = i

                if hostname_col is None:
                    print(
                        "Warning: Could not detect hostname column. Using column names as provided."
                    )
                    # Fall back to DictReader
                    file.seek(0)
                    reader = csv.DictReader(file)
                    devices = list(reader)
                else:
                    # Create dictionaries with detected columns
                    headers = header_row
                    for row in rows[1:]:  # Skip header row
                        if len(row) >= len(headers):
                            device = {headers[i]: row[i] for i in range(len(headers))}
                            devices.append(device)

    except csv.Error as e:
        raise ValueError(f"Error reading CSV file: {e}")
    except UnicodeDecodeError:
        # Try with different encoding
        try:
            with open(csv_file, "r", encoding="latin-1") as file:
                reader = csv.DictReader(file)
                devices = list(reader)
        except Exception as e:
            raise ValueError(f"Error reading CSV file with encoding issues: {e}")

    if not devices:
        raise ValueError("No device records found in CSV file")

    print(f"Successfully read {len(devices)} device records from {csv_file}")
    return devices


def filter_windows_devices(devices: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Filter devices to only include Windows devices with valid hostnames and registered/unregistered state.

    Optimized for large datasets:
    - Efficient field matching with pre-computed normalized keys
    - Early exit conditions to avoid unnecessary processing
    - Minimal memory overhead during filtering

    Args:
        devices (List[Dict[str, str]]): List of all device records

    Returns:
        List[Dict[str, str]]: List of Windows device records that are registered or unregistered
    """
    print("Filtering Windows devices (registered/unregistered only)...")

    if not devices:
        return []

    # Pre-compute normalized field mappings for efficiency
    first_device = devices[0]
    device_type_key = None
    hostname_key = None
    device_state_key = None

    # Find the correct field names once (more efficient for large datasets)
    device_type_fields = {"devicetype", "type", "osversion", "os", "platform"}
    hostname_fields = {
        "machinehostname",
        "hostname",
        "machinehostname",
        "devicename",
        "name",
    }
    device_state_fields = {"devicestate", "state", "status", "connectionstatus"}

    for key in first_device.keys():
        normalized_key = key.lower().replace(" ", "").replace("_", "")
        # Special case for "Device State" field
        if not device_state_key and key.lower() == "device state":
            device_state_key = key
        elif not device_type_key and normalized_key in device_type_fields:
            device_type_key = key
        elif not hostname_key and normalized_key in hostname_fields:
            hostname_key = key
        elif not device_state_key and normalized_key in device_state_fields:
            device_state_key = key
        if device_type_key and hostname_key and device_state_key:
            break

    if not device_type_key or not hostname_key:
        print(f"Warning: Could not find device type or hostname fields")
        print(
            f"Available fields: {list(first_device.keys())[:5]}..."
        )  # Show only first 5
        return []
    
    if not device_state_key:
        print(f"Warning: Could not find device state field - proceeding without state filtering")
        print(f"Available fields: {list(first_device.keys())[:10]}...")

    print(
        f"Using fields - Device type: '{device_type_key}', Hostname: '{hostname_key}'"
    )
    if device_state_key:
        print(f"Device state field: '{device_state_key}'")

    # Filter devices efficiently
    windows_devices = []
    windows_keywords = ("windows", "win")
    valid_states = ("registered", "unregistered")

    for device in devices:
        device_type = device.get(device_type_key, "").lower()
        hostname = device.get(hostname_key, "").strip()
        device_state = device.get(device_state_key, "").lower() if device_state_key else "registered"

        # Quick checks with early exit
        if (
            hostname
            and len(hostname) > 0
            and hostname.lower() not in ("unknown", "n/a", "null", "")
            and any(keyword in device_type for keyword in windows_keywords)
            and device_state in valid_states
        ):

            # Add normalized fields to device record (minimal copy)
            device_copy = device.copy()
            device_copy["_hostname"] = hostname
            device_copy["_device_type"] = device_type
            device_copy["_device_state"] = device_state
            windows_devices.append(device_copy)

    print(f"Found {len(windows_devices)} Windows devices with valid hostnames and registered/unregistered state")
    return windows_devices


def deduplicate_hostnames(windows_devices: List[Dict[str, str]]) -> List[str]:
    """
    Extract and deduplicate hostnames from Windows devices.

    Optimized for large datasets (up to 30k+ hostnames):
    1. Uses sets for O(1) lookup performance
    2. Minimizes memory usage during processing
    3. Avoids storing large duplicate lists
    4. Efficient hostname normalization

    Args:
        windows_devices (List[Dict[str, str]]): List of Windows device records

    Returns:
        List[str]: List of unique, normalized hostnames sorted alphabetically
    """
    print("Performing hostname deduplication...")

    # Use sets for efficient O(1) operations
    normalized_hostnames: Set[str] = set()

    # Track counts without storing full lists (memory efficient)
    original_count = 0
    invalid_count = 0

    # Process devices efficiently
    for device in windows_devices:
        original_hostname = device.get("_hostname", "").strip()
        if original_hostname:
            original_count += 1

            # Normalize hostname efficiently
            normalized = original_hostname.lower().strip()

            # Remove existing domain suffix if present
            dot_index = normalized.find(".")
            if dot_index != -1:
                normalized = normalized[:dot_index]

            # Validate hostname (efficient checks)
            if (
                normalized
                and len(normalized) > 0
                and normalized not in ("unknown", "n/a", "null", "localhost", "")
            ):
                normalized_hostnames.add(normalized)
            else:
                invalid_count += 1

    # Convert to sorted list (single operation)
    unique_hostnames = sorted(normalized_hostnames)
    duplicates_removed = original_count - len(unique_hostnames) - invalid_count

    # Report deduplication results (no long lists)
    print(f"Hostname deduplication results:")
    print(f"  - Original hostnames processed: {original_count}")
    print(f"  - Unique hostnames after deduplication: {len(unique_hostnames)}")
    print(f"  - Duplicates removed: {duplicates_removed}")
    print(f"  - Invalid hostnames filtered: {invalid_count}")

    return unique_hostnames


def generate_forward_zones_config(
    windows_devices: List[Dict[str, str]],
    dns_ips: str = "10.213.182.62",
    domain: str = "domain.local",
) -> str:
    """
    Generate Unbound forward zones configuration for Windows devices.

    Optimized for large datasets (30k+ hostnames):
    - Efficient string building using list concatenation
    - Memory-efficient hostname deduplication
    - Minimal intermediate string operations
    - Support for multiple DNS servers (comma-separated)

    Args:
        windows_devices (List[Dict[str, str]]): List of Windows device records
        dns_ips (str): DNS server IP addresses to forward to (comma-separated)
        domain (str): Domain suffix for forward zones

    Returns:
        str: Unbound configuration content
    """
    # Step 1: Deduplicate hostnames
    unique_hostnames = deduplicate_hostnames(windows_devices)

    if not unique_hostnames:
        print("Warning: No valid hostnames found after deduplication")
        return "# No valid hostnames found\n"

    hostname_count = len(unique_hostnames)
    
    # Parse and validate DNS IPs
    dns_ip_list = [ip.strip() for ip in dns_ips.split(',') if ip.strip()]
    if not dns_ip_list:
        print("Warning: No valid DNS IPs provided")
        return "# No valid DNS IPs found\n"
    
    # Validate each IP
    valid_dns_ips = []
    for ip in dns_ip_list:
        if validate_dns_ip(ip):
            valid_dns_ips.append(ip)
        else:
            print(f"Warning: Invalid DNS IP skipped: {ip}")
    
    if not valid_dns_ips:
        print("Error: No valid DNS IPs found after validation")
        return "# No valid DNS IPs found\n"
    
    print(f"Generating configuration for {hostname_count} unique hostnames...")
    print(f"Using DNS servers: {', '.join(valid_dns_ips)}")

    # Pre-allocate list for better performance with large datasets
    # Each hostname generates (2 + len(dns_ips)) lines, plus header (7 lines)
    lines_per_hostname = 2 + len(valid_dns_ips) + 1  # forward-zone, name, N*forward-addr, empty
    estimated_lines = (hostname_count * lines_per_hostname) + 8
    config_lines = []
    # Note: Python lists don't have reserve(), but pre-extending helps with large datasets
    if hostname_count > 1000:
        config_lines.extend([None] * estimated_lines)
        config_lines.clear()  # Clear but keep allocated memory

    # Add header comment
    dns_servers_str = ', '.join(valid_dns_ips)
    config_lines.extend(
        [
            "# Unbound Forward Zones Configuration",
            f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Total forward zones: {hostname_count}",
            f"# DNS servers: {dns_servers_str}",
            f"# Domain: {domain}",
            "# Note: Hostnames have been deduplicated to prevent conflicts",
            "",
        ]
    )

    # Generate forward zones efficiently
    for hostname in unique_hostnames:
        config_lines.append("forward-zone:")
        config_lines.append(f'    name: "{hostname}.{domain}"')
        # Add all DNS servers
        for dns_ip in valid_dns_ips:
            config_lines.append(f"    forward-addr: {dns_ip}")
        config_lines.append("")

    print(f"Configuration generation completed ({len(config_lines)} lines)")

    # Use join for efficient string concatenation
    return "\n".join(config_lines)


def save_config_file(config_content: str, output_file: str) -> None:
    """
    Save the configuration content to a file.

    Optimized for large files:
    - Uses buffered writing for better performance
    - Explicit file flushing for reliability

    Args:
        config_content (str): Configuration file content
        output_file (str): Output file path
    """
    try:
        file_size = len(config_content)
        print(f"Saving configuration ({file_size:,} characters) to: {output_file}")

        with open(output_file, "w", encoding="utf-8", buffering=8192) as file:
            file.write(config_content)
            file.flush()  # Ensure data is written

        print(f"✓ Configuration saved successfully")
    except IOError as e:
        raise IOError(f"Failed to save configuration file: {e}")


def validate_dns_ip(dns_ip: str) -> bool:
    """
    Validate that the DNS IP address is in a valid format.

    Args:
        dns_ip (str): DNS IP address to validate

    Returns:
        bool: True if valid, False otherwise
    """
    import re

    # Basic IPv4 validation
    ipv4_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    match = re.match(ipv4_pattern, dns_ip)

    if not match:
        return False

    # Check each octet is 0-255
    for octet in match.groups():
        if int(octet) > 255:
            return False

    return True


def main():
    """Main function to handle command line arguments and orchestrate the process."""

    parser = argparse.ArgumentParser(
        description="Generate Unbound forward zones configuration from Zscaler devices CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s devices.csv forward_zones.conf 10.213.182.62
  %(prog)s devices.csv zones.conf 10.213.182.62,192.168.1.1
  %(prog)s devices.csv custom_zones.conf 10.213.182.62,192.168.1.1,8.8.8.8 --domain internal.local
  %(prog)s devices.csv my_zones.conf 10.213.182.62 --verbose
        """,
    )

    parser.add_argument("input_csv_file", help="Path to the Zscaler devices CSV file")
    parser.add_argument("output_conf_file", help="Output configuration file path")
    parser.add_argument("dns_ips", help="DNS server IP addresses to forward queries to (comma-separated for multiple servers)")
    parser.add_argument(
        "--domain",
        "-d",
        default="domain.local",
        help="Domain suffix for forward zones (default: domain.local)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    args = parser.parse_args()

    # Validate arguments - parse and validate all DNS IPs
    dns_ip_list = [ip.strip() for ip in args.dns_ips.split(',') if ip.strip()]
    if not dns_ip_list:
        print(f"✗ Error: No DNS IP addresses provided")
        print("Please provide at least one valid IPv4 address (e.g., 10.213.182.62)")
        sys.exit(1)
    
    # Check if all IPs are valid
    invalid_ips = [ip for ip in dns_ip_list if not validate_dns_ip(ip)]
    if invalid_ips:
        print(f"✗ Error: Invalid DNS IP address(es): {', '.join(invalid_ips)}")
        print("Please provide valid IPv4 addresses (e.g., 10.213.182.62,192.168.1.1)")
        sys.exit(1)

    print("Zscaler Forward Zones Generator")
    print("=" * 40)
    print(f"Input CSV: {args.input_csv_file}")
    print(f"Output file: {args.output_conf_file}")
    print(f"DNS IPs: {args.dns_ips}")
    print(f"Domain: {args.domain}")
    print()

    try:
        # Step 1: Read CSV file
        print("Step 1: Reading CSV file...")
        devices = read_devices_csv(args.input_csv_file)

        if args.verbose:
            # Show available columns (limit to prevent long output)
            if devices:
                columns = list(devices[0].keys())
                if len(columns) > 10:
                    print(
                        f"Available columns ({len(columns)} total): {columns[:10]}..."
                    )
                else:
                    print(f"Available columns: {columns}")

        # Step 2: Filter Windows devices
        print("\nStep 2: Filtering Windows devices...")
        windows_devices = filter_windows_devices(devices)

        if not windows_devices:
            print("✗ No Windows devices found in the CSV file")
            print(
                "Make sure the CSV contains devices with 'WINDOWS' in the device type field"
            )
            sys.exit(1)

        if args.verbose and len(windows_devices) <= 10:
            # Only show samples for small datasets to avoid long output
            print("Sample Windows devices found:")
            for i, device in enumerate(windows_devices[:3]):
                hostname = device.get("_hostname", "Unknown")
                device_type = device.get("_device_type", "Unknown")
                print(f"  {i+1}. {hostname} ({device_type})")
            if len(windows_devices) > 3:
                print(f"  ... and {len(windows_devices) - 3} more")
        elif args.verbose:
            # For large datasets, just show summary
            print(
                f"Large dataset detected ({len(windows_devices)} devices) - skipping sample output"
            )

        # Step 3: Generate configuration
        print("\nStep 3: Generating forward zones configuration...")
        config_content = generate_forward_zones_config(
            windows_devices, args.dns_ips, args.domain
        )

        # Step 4: Save configuration file
        print("\nStep 4: Saving configuration file...")
        save_config_file(config_content, args.output_conf_file)

        print(f"\n✓ Successfully generated forward zones configuration!")
        print(f"Configuration file: {args.output_conf_file}")

        # Count unique hostnames from the generated config
        config_lines = config_content.split("\n")
        zone_count = len(
            [line for line in config_lines if line.strip().startswith("name:")]
        )
        print(f"Total forward zones created: {zone_count}")
        print(f"Windows devices processed: {len(windows_devices)}")

        if zone_count < len(windows_devices):
            print(
                f"Note: {len(windows_devices) - zone_count} duplicate hostnames were removed during deduplication"
            )

        # Show a preview of the generated config (limited for large files)
        if zone_count <= 100:
            # Show preview for small configurations
            print(f"\nPreview of {args.output_conf_file}:")
            print("-" * 40)
            lines = config_content.split("\n")
            for line in lines[:15]:  # Show first 15 lines
                print(line)
            if len(lines) > 15:
                print("...")
                print(f"[{len(lines) - 15} more lines]")
        else:
            # For large configurations, just show header
            print(f"\n✓ Large configuration file generated ({zone_count} zones)")
            print(f"File size: ~{len(config_content):,} characters")
            lines = config_content.split("\n")
            print("Header preview:")
            print("-" * 20)
            for line in lines[:7]:  # Show just the header
                print(line)

    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except IOError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n✗ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
