# Zscaler Forward Zones Generator

Tools to download devices from Zscaler One API and generate DNS forward zone configurations for Unbound.

---

**Copyright (c) 2025 ZHERO srl, Italy**  
**Website:** [https://zhero.ai](https://zhero.ai)

This project is released under the MIT License. See the LICENSE file for full details.

---

## Installation

### Prerequisites

-   Python 3.6 or higher

### Dependencies

Install the required dependencies:

```bash
pip install requests python-dotenv
```

### Configuration

1. Create a `.env` file in the project directory:

```env
ZSCALER_IDENTITY_BASE_URL=https://[YOUR-ID].zslogin.net
ZSCALER_CLIENT_ID=your_client_id
ZSCALER_CLIENT_SECRET=your_client_secret
```

2. Replace the values with your OAuth credentials obtained from the Zscaler admin portal.

## Usage

### 1. Download devices from Zscaler

```bash
# With custom filename
python download_devices_csv.py devices.csv

# Auto-generated filename with timestamp
python download_devices_csv.py
```

The script will download all devices in CSV format from your Zscaler environment.

### 2. Generate DNS forward zones

```bash
# Basic usage with default domain (domain.local)
python generate_forward_zones.py devices.csv forward_zones.conf 10.213.182.62

# With multiple DNS servers (comma-separated)
python generate_forward_zones.py devices.csv zones.conf 10.213.182.62,192.168.1.100

# With custom domain and multiple DNS servers
python generate_forward_zones.py devices.csv zones.conf 10.213.182.62,192.168.1.100,8.8.8.8 --domain company.local

# Verbose output
python generate_forward_zones.py devices.csv zones.conf 10.213.182.62 --verbose
```

### Complete example

```bash
# Step 1: Download devices
python download_devices_csv.py

# Step 2: Generate DNS zones (use the file created in step 1)
python generate_forward_zones.py zscaler_devices_20250610_143022.csv forward_zones.conf 10.213.182.62
```

## Parameters

### download_devices_csv.py

```
python download_devices_csv.py [OUTPUT_FILENAME]
```

-   `OUTPUT_FILENAME` (optional): Name of the CSV file to create

### generate_forward_zones.py

```
python generate_forward_zones.py INPUT_CSV OUTPUT_CONF DNS_IP [--domain DOMAIN] [--verbose]
```

-   `INPUT_CSV`: Zscaler devices CSV file
-   `OUTPUT_CONF`: Unbound configuration file to create
-   `DNS_IP`: DNS server IP address (e.g. 10.213.182.62)
-   `--domain`: Domain suffix for zones (default: domain.local)
-   `--verbose`: Detailed output

## Generated output

The generated configuration file contains forward zones for Unbound DNS:

```
# Unbound Forward Zones Configuration
# Generated on: 2025-06-10 14:30:22
# Total forward zones: 156
# DNS server: 10.213.182.62
# Domain: domain.local

forward-zone:
    name: "pc001234.domain.local"
    forward-addr: 10.213.182.62

forward-zone:
    name: "laptop5678.domain.local"
    forward-addr: 10.213.182.62
```

## Features

-   **Automatic filtering**: Processes only Windows devices with "Registered" or "Unregistered" status
-   **Deduplication**: Automatically removes duplicate hostnames
-   **Performance**: Optimized for large datasets (up to 30,000+ devices)
-   **Error handling**: Clear and informative error messages
-   **OAuth authentication**: Secure integration with Zscaler One API
-   **Multiple DNS servers**: Supports configuration with multiple DNS servers

## Troubleshooting

### Authentication error

Verify that the credentials in the `.env` file are correct and that the OAuth application has the necessary permissions for the Client Connector API.

### API limit reached

If you receive rate limiting errors (429), wait before retrying. The download script has low API limits.

### No Windows devices found

Ensure the CSV contains devices with:
- "WINDOWS" in the device type field
- Device state "Registered" or "Unregistered" 
- Valid hostnames

## License

MIT License

Copyright (c) 2025 ZHERO srl, Italy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

**Developed by ZHERO srl - [https://zhero.ai](https://zhero.ai)**
