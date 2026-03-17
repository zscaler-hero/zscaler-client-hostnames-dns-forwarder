# Changelog

All notable changes to the Zscaler Forward Zones Generator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-03-17

### Added
- Multi-domain support via `--domain-mappings` configuration file
- Secondary DNS domain generation based on user email domain mappings
- `domain_mappings.conf.example` template with self-documented instructions
- `VERSION` file for explicit version tracking
- This `CHANGELOG.md` for change documentation

### Changed
- `deduplicate_hostnames()` redesigned to preserve hostname-to-email-domain associations
- `generate_forward_zones_config()` now accepts optional domain mappings for secondary zone generation
- `filter_windows_devices()` now detects and preserves the User email field
- Shell scripts (`sync_unbound_primary.sh`, `sync_unbound_secondary.sh`) updated to support `--domain-mappings` argument
- Primary sync script now copies `domain_mappings.conf` to zonesync directory for secondary server
- Secondary sync script retrieves `domain_mappings.conf` from primary via SCP
- README updated with multi-domain documentation and migration guide

### Backward Compatibility
- Without `--domain-mappings`, behavior is identical to v1.0.0
- All existing CLI arguments and shell script invocations continue to work unchanged

## [1.0.0] - 2025-06-10

### Added
- Initial release
- Device CSV download from Zscaler One API (`download_devices_csv.py`)
- Unbound forward zones generation for Windows devices (`generate_forward_zones.py`)
- Hostname deduplication with O(1) set-based performance
- High availability synchronization scripts (primary/secondary)
- Support for multiple DNS servers (comma-separated)
- Comprehensive error handling and logging
