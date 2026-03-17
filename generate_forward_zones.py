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
    python generate_forward_zones.py devices.csv forward_zones.conf 10.0.0.12
    python generate_forward_zones.py devices.csv zones.conf 10.0.0.12,192.168.1.1
    python generate_forward_zones.py devices.csv custom_zones.conf 192.168.1.1 --domain custom.local

Copyright (c) 2025 ZHERO srl, Italy
Website: https://zhero.ai

MIT License - see LICENSE file for details
"""

import csv
import sys
import argparse
from typing import List, Dict, Set, Optional
from datetime import datetime
import os


def get_version() -> str:
    """Read version from VERSION file."""
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"


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
    user_key = None

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
    user_fields = {"user", "email", "username", "useremail"}

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
        elif not user_key and normalized_key in user_fields:
            user_key = key

    if not device_type_key or not hostname_key:
        print(f"Warning: Could not find device type or hostname fields")
        print(
            f"Available fields: {list(first_device.keys())[:5]}..."
        )  # Show only first 5
        return []

    if not device_state_key:
        print(
            f"Warning: Could not find device state field - proceeding without state filtering"
        )
        print(f"Available fields: {list(first_device.keys())[:10]}...")

    print(
        f"Using fields - Device type: '{device_type_key}', Hostname: '{hostname_key}'"
    )
    if device_state_key:
        print(f"Device state field: '{device_state_key}'")
    if user_key:
        print(f"User field: '{user_key}'")

    # Filter devices efficiently
    windows_devices = []
    windows_keywords = ("windows", "win")
    valid_states = ("registered", "unregistered")

    for device in devices:
        device_type = device.get(device_type_key, "").lower()
        hostname = device.get(hostname_key, "").strip()
        device_state = (
            device.get(device_state_key, "").lower()
            if device_state_key
            else "registered"
        )

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
            device_copy["_user"] = device.get(user_key, "") if user_key else ""
            windows_devices.append(device_copy)

    print(
        f"Found {len(windows_devices)} Windows devices with valid hostnames and registered/unregistered state"
    )
    return windows_devices


def deduplicate_hostnames_with_domains(
    windows_devices: List[Dict[str, str]],
) -> Dict[str, Set[str]]:
    """
    Extract and deduplicate hostnames, preserving email domain associations.

    For each unique hostname, collects the set of email domains from
    all users associated with that hostname.

    Optimized for large datasets (up to 30k+ hostnames):
    1. Uses dicts and sets for O(1) operations
    2. Single pass through devices
    3. Efficient hostname normalization

    Args:
        windows_devices (List[Dict[str, str]]): List of Windows device records

    Returns:
        Dict[str, Set[str]]: Mapping of normalized hostname to set of email domains
    """
    print("Performing hostname deduplication...")

    hostname_domains: Dict[str, Set[str]] = {}

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
                if normalized not in hostname_domains:
                    hostname_domains[normalized] = set()

                # Extract email domain from user field
                user_email = device.get("_user", "").strip()
                if "@" in user_email:
                    email_domain = user_email.split("@", 1)[1].lower().strip()
                    if email_domain:
                        hostname_domains[normalized].add(email_domain)
            else:
                invalid_count += 1

    duplicates_removed = original_count - len(hostname_domains) - invalid_count

    # Report deduplication results (no long lists)
    print(f"Hostname deduplication results:")
    print(f"  - Original hostnames processed: {original_count}")
    print(f"  - Unique hostnames after deduplication: {len(hostname_domains)}")
    print(f"  - Duplicates removed: {duplicates_removed}")
    print(f"  - Invalid hostnames filtered: {invalid_count}")

    return hostname_domains


def deduplicate_hostnames(windows_devices: List[Dict[str, str]]) -> List[str]:
    """
    Extract and deduplicate hostnames from Windows devices.
    Legacy wrapper for backward compatibility.

    Args:
        windows_devices (List[Dict[str, str]]): List of Windows device records

    Returns:
        List[str]: List of unique, normalized hostnames sorted alphabetically
    """
    hostname_domains = deduplicate_hostnames_with_domains(windows_devices)
    return sorted(hostname_domains.keys())


def generate_forward_zones_config(
    windows_devices: List[Dict[str, str]],
    dns_ips: str = "10.0.0.12",
    domain: str = "domain.local",
    domain_mappings: Optional[Dict[str, str]] = None,
) -> str:
    """
    Generate Unbound forward zones configuration for Windows devices.

    Optimized for large datasets (30k+ hostnames):
    - Efficient string building using list concatenation
    - Memory-efficient hostname deduplication
    - Minimal intermediate string operations
    - Support for multiple DNS servers (comma-separated)
    - Optional secondary domain generation via domain mappings

    Args:
        windows_devices (List[Dict[str, str]]): List of Windows device records
        dns_ips (str): DNS server IP addresses to forward to (comma-separated)
        domain (str): Domain suffix for forward zones
        domain_mappings (Optional[Dict[str, str]]): Email domain to secondary DNS domain mappings

    Returns:
        str: Unbound configuration content
    """
    # Step 1: Deduplicate hostnames (preserving email domain associations)
    hostname_domains = deduplicate_hostnames_with_domains(windows_devices)

    if not hostname_domains:
        print("Warning: No valid hostnames found after deduplication")
        return "# No valid hostnames found\n"

    unique_hostnames = sorted(hostname_domains.keys())
    hostname_count = len(unique_hostnames)

    # Parse and validate DNS IPs
    dns_ip_list = [ip.strip() for ip in dns_ips.split(",") if ip.strip()]
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

    # Pre-compute secondary zone count for the header
    secondary_zone_count = 0
    if domain_mappings:
        for hostname in unique_hostnames:
            email_domains = hostname_domains.get(hostname, set())
            seen_secondary = set()
            for ed in email_domains:
                if ed in domain_mappings:
                    sd = domain_mappings[ed]
                    if sd != domain and sd not in seen_secondary:
                        secondary_zone_count += 1
                        seen_secondary.add(sd)

    total_zone_count = hostname_count + secondary_zone_count

    print(f"Generating configuration for {hostname_count} unique hostnames...")
    if domain_mappings and secondary_zone_count > 0:
        print(f"Secondary domain zones to generate: {secondary_zone_count}")
        print(f"Total forward zones: {total_zone_count}")
    print(f"Using DNS servers: {', '.join(valid_dns_ips)}")

    # Pre-allocate list for better performance with large datasets
    lines_per_hostname = (
        2 + len(valid_dns_ips) + 1
    )  # forward-zone, name, N*forward-addr, empty
    estimated_lines = (total_zone_count * lines_per_hostname) + 12
    config_lines = []
    if total_zone_count > 1000:
        config_lines.extend([None] * estimated_lines)
        config_lines.clear()  # Clear but keep allocated memory

    # Add header comment
    dns_servers_str = ", ".join(valid_dns_ips)
    config_lines.extend(
        [
            "# Unbound Forward Zones Configuration",
            f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Total forward zones: {total_zone_count}",
            f"# Primary domain zones: {hostname_count}",
            f"# DNS servers: {dns_servers_str}",
            f"# Primary domain: {domain}",
        ]
    )
    if domain_mappings and secondary_zone_count > 0:
        config_lines.append(f"# Secondary domain zones: {secondary_zone_count}")
        config_lines.append(f"# Domain mappings ({len(domain_mappings)} configured):")
        for email_dom, dns_dom in domain_mappings.items():
            config_lines.append(f"#   @{email_dom} -> {dns_dom}")
    config_lines.extend(
        [
            "# Note: Hostnames have been deduplicated to prevent conflicts",
            "",
        ]
    )

    # Generate forward zones efficiently
    for hostname in unique_hostnames:
        # Always generate primary domain zone
        config_lines.append("forward-zone:")
        config_lines.append(f'    name: "{hostname}.{domain}"')
        for dns_ip in valid_dns_ips:
            config_lines.append(f"    forward-addr: {dns_ip}")
        config_lines.append("")

        # Generate secondary domain zones if mappings are configured
        if domain_mappings:
            email_domains = hostname_domains.get(hostname, set())
            added_secondary = set()
            for email_domain in sorted(email_domains):
                if email_domain in domain_mappings:
                    secondary_dns_domain = domain_mappings[email_domain]
                    if secondary_dns_domain != domain and secondary_dns_domain not in added_secondary:
                        config_lines.append("forward-zone:")
                        config_lines.append(f'    name: "{hostname}.{secondary_dns_domain}"')
                        for dns_ip in valid_dns_ips:
                            config_lines.append(f"    forward-addr: {dns_ip}")
                        config_lines.append("")
                        added_secondary.add(secondary_dns_domain)

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


def load_domain_mappings(mappings_file: str) -> Dict[str, str]:
    """
    Load email-domain to DNS-domain mappings from a configuration file.

    File format: one mapping per line, 'email_domain:dns_domain'
    Lines starting with '#' are comments. Empty lines are ignored.

    Args:
        mappings_file (str): Path to the domain mappings configuration file

    Returns:
        Dict[str, str]: Mapping of email domain (lowercase) to secondary DNS domain

    Raises:
        FileNotFoundError: If mappings file doesn't exist
        ValueError: If mappings file contains invalid format
    """
    if not os.path.exists(mappings_file):
        raise FileNotFoundError(f"Domain mappings file not found: {mappings_file}")

    mappings = {}
    print(f"Loading domain mappings from: {mappings_file}")

    with open(mappings_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(
                    f"Invalid mapping format at line {line_num}: '{line}' "
                    f"(expected 'email_domain:dns_domain')"
                )
            parts = line.split(":", 1)
            email_domain = parts[0].strip().lower()
            dns_domain = parts[1].strip()
            if not email_domain or not dns_domain:
                raise ValueError(
                    f"Empty domain at line {line_num}: '{line}'"
                )
            mappings[email_domain] = dns_domain

    print(f"Loaded {len(mappings)} domain mapping(s):")
    for email_dom, dns_dom in mappings.items():
        print(f"  {email_dom} -> {dns_dom}")

    return mappings


def main():
    """Main function to handle command line arguments and orchestrate the process."""

    parser = argparse.ArgumentParser(
        description="Generate Unbound forward zones configuration from Zscaler devices CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s devices.csv forward_zones.conf 10.0.0.12
  %(prog)s devices.csv zones.conf 10.0.0.12,192.168.1.1
  %(prog)s devices.csv custom_zones.conf 10.0.0.12,192.168.1.1,8.8.8.8 --domain internal.local
  %(prog)s devices.csv my_zones.conf 10.0.0.12 --verbose
  %(prog)s devices.csv zones.conf 10.0.0.12 --domain corp.local --domain-mappings /root/domain_mappings.conf
        """,
    )

    parser.add_argument("input_csv_file", help="Path to the Zscaler devices CSV file")
    parser.add_argument("output_conf_file", help="Output configuration file path")
    parser.add_argument(
        "dns_ips",
        help="DNS server IP addresses to forward queries to (comma-separated for multiple servers)",
    )
    parser.add_argument(
        "--domain",
        "-d",
        default="domain.local",
        help="Domain suffix for forward zones (default: domain.local)",
    )
    parser.add_argument(
        "--domain-mappings",
        "-m",
        default=None,
        help="Path to domain mappings configuration file for secondary DNS domain generation",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    args = parser.parse_args()

    # Validate arguments - parse and validate all DNS IPs
    dns_ip_list = [ip.strip() for ip in args.dns_ips.split(",") if ip.strip()]
    if not dns_ip_list:
        print(f"✗ Error: No DNS IP addresses provided")
        print("Please provide at least one valid IPv4 address (e.g., 10.0.0.12)")
        sys.exit(1)

    # Check if all IPs are valid
    invalid_ips = [ip for ip in dns_ip_list if not validate_dns_ip(ip)]
    if invalid_ips:
        print(f"✗ Error: Invalid DNS IP address(es): {', '.join(invalid_ips)}")
        print("Please provide valid IPv4 addresses (e.g., 10.0.0.12,192.168.1.1)")
        sys.exit(1)

    version = get_version()
    print(f"Zscaler Forward Zones Generator v{version}")
    print("=" * 40)
    print(f"Input CSV: {args.input_csv_file}")
    print(f"Output file: {args.output_conf_file}")
    print(f"DNS IPs: {args.dns_ips}")
    print(f"Domain: {args.domain}")
    if args.domain_mappings:
        print(f"Domain mappings: {args.domain_mappings}")
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

        # Step 3: Load domain mappings (optional)
        domain_mappings = None
        if args.domain_mappings:
            print("\nStep 3: Loading domain mappings...")
            domain_mappings = load_domain_mappings(args.domain_mappings)

        # Step 4: Generate configuration
        step_num = 4 if args.domain_mappings else 3
        print(f"\nStep {step_num}: Generating forward zones configuration...")
        config_content = generate_forward_zones_config(
            windows_devices, args.dns_ips, args.domain, domain_mappings
        )

        # Save configuration file
        step_num += 1
        print(f"\nStep {step_num}: Saving configuration file...")
        save_config_file(config_content, args.output_conf_file)

        print(f"\n✓ Successfully generated forward zones configuration!")
        print(f"Configuration file: {args.output_conf_file}")

        # Count zones from the generated config
        config_lines = config_content.split("\n")
        zone_count = len(
            [line for line in config_lines if line.strip().startswith("name:")]
        )
        # Count primary vs secondary zones
        primary_zone_count = len(
            [line for line in config_lines if line.strip().startswith(f'name:') and f'.{args.domain}"' in line]
        )
        secondary_zone_count = zone_count - primary_zone_count

        print(f"Total forward zones created: {zone_count}")
        if secondary_zone_count > 0:
            print(f"  - Primary domain zones: {primary_zone_count}")
            print(f"  - Secondary domain zones: {secondary_zone_count}")
        print(f"Windows devices processed: {len(windows_devices)}")

        if primary_zone_count < len(windows_devices):
            print(
                f"Note: {len(windows_devices) - primary_zone_count} duplicate hostnames were removed during deduplication"
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
