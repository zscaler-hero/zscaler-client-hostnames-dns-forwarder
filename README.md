# Zscaler Forward Zones Generator

A comprehensive solution for integrating Unbound DNS with Zscaler ZPA to enable client-to-client connectivity through synthetic IP resolution. This project automatically generates DNS forward zone configurations from Zscaler-registered devices, allowing seamless resolution of client FQDNs through Branch Connectors.

---

**Copyright (c) 2025 ZHERO srl, Italy**  
**Website:** [https://zhero.ai](https://zhero.ai)

This project is released under the MIT License. See the LICENSE file for full details.

---

## 🎯 Purpose

This solution addresses a common challenge in Zscaler ZPA deployments: enabling client-to-client communication when client and server FQDNs share the same domain namespace. By leveraging Unbound DNS with dynamically generated forward zones, we can:

-   Route client hostname queries to Zscaler Branch Connectors for synthetic IP resolution
-   Maintain standard DNS resolution for server resources through corporate DNS
-   Enable ZPA client-to-client functionality without complex DNS restructuring
-   Support dynamic environments with automated configuration updates

## 🏗️ Architecture

```
┌─────────────────┐                  ┌─────────────────────┐
│   ZPA Client    │                  │  Corporate DNS      │
│ (hostname.corp) │                  │  (10.1.1.53)        │
└────────┬────────┘                  └──────────┬──────────┘
         │                                      │
         │ DNS Query                            │
         │ hostname.corp?                       │
         ▼                                      │
┌─────────────────┐                             │
│   Unbound DNS   │──── server.corp ────────────┘
│ (Local Resolver)│      (forward)
│                 │
│ ┌─────────────┐ │     ┌─────────────────────┐
│ │forward_zones│ │     │ Branch Connector    │
│ │    .conf    │ │     │ VIP: 10.213.182.62  │
│ └─────────────┘ │     │                     │
└────────┬────────┘     │ ┌─────────────────┐ │
         │              │ │ Synthetic IP    │ │
         └──client.corp─┤ │ Resolution      │ │
            (forward)   │ └─────────────────┘ │
                        └─────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ ZPA Client-to-Client│
                        │    Connectivity     │
                        └─────────────────────┘
```

## 📋 Prerequisites

### System Requirements

-   RHEL 9 / CentOS 9 / Rocky Linux 9 (for App Connector deployment)
-   Python 3.6 or higher
-   Unbound DNS server
-   Network access to Zscaler API endpoints
-   Network access to Branch Connector VIP

### Python Dependencies

```bash
pip install requests python-dotenv
```

## 🚀 Installation

### 1. Install Unbound on RHEL 9

```bash
# Install Unbound
sudo dnf install -y unbound

# Enable and start the service
sudo systemctl enable unbound
sudo systemctl start unbound

# Configure firewall (if needed)
sudo firewall-cmd --permanent --add-service=dns
sudo firewall-cmd --reload
```

### 2. Clone the Repository

```bash
git clone https://github.com/zhero-ai/zscaler-forward-zones-generator.git
cd zscaler-forward-zones-generator
```

### 3. Configure API Access

Create a `.env` file in the project directory:

```env
ZSCALER_IDENTITY_BASE_URL=https://[YOUR-ID].zslogin.net
ZSCALER_CLIENT_ID=your_client_id
ZSCALER_CLIENT_SECRET=your_client_secret
```

Replace the values with your OAuth credentials obtained from the Zscaler admin portal.

## ⚙️ Unbound Configuration

### Critical Configuration Changes

Edit `/etc/unbound/unbound.conf` and ensure these settings:

```yaml
server:
    # CRITICAL: Use only iterator module (no DNSSEC validation)
    module-config: "iterator"

    # Network interfaces
    interface: 0.0.0.0
    interface: ::0

    # Access control (adjust for your network)
    access-control: 10.0.0.0/8 allow
    access-control: 172.16.0.0/12 allow
    access-control: 192.168.0.0/16 allow

    # Logging (optional, for troubleshooting)
    verbosity: 1
    log-queries: yes

    # Performance tuning
    cache-min-ttl: 60
    cache-max-ttl: 86400

    # Include generated forward zones
    include: "/etc/unbound/forward_zones.conf"

# Default forward zone for corporate DNS
forward-zone:
    name: "."
    forward-addr: 10.1.1.53  # Your corporate DNS server(s)
    forward-first: no
```

**Important Notes:**

-   `module-config: "iterator"` is essential - it disables DNSSEC validation which can interfere with synthetic IP resolution
-   Place the `include` statement BEFORE the default forward-zone
-   More specific zones (from forward_zones.conf) take precedence over the default zone

### Verify Configuration

```bash
# Check configuration syntax
sudo unbound-checkconf

# Test DNS resolution
dig @localhost hostname.domain.local
```

## 📖 Usage

### 1. Download Devices from Zscaler

```bash
# With custom filename
python download_devices_csv.py devices.csv

# Auto-generated filename with timestamp
python download_devices_csv.py
```

This downloads all registered devices from your Zscaler environment in CSV format.

### 2. Generate Forward Zones Configuration

```bash
# Basic usage
python generate_forward_zones.py devices.csv /etc/unbound/forward_zones.conf BRANCH_CONNECTOR_VIP --domain yourdomain.local

# With multiple Branch Connector IPs (for redundancy)
python generate_forward_zones.py devices.csv /etc/unbound/forward_zones.conf 10.213.182.62,10.213.182.63 --domain corp.local

# Verbose output for troubleshooting
python generate_forward_zones.py devices.csv /etc/unbound/forward_zones.conf 10.213.182.62 --domain corp.local --verbose
```

### 3. Reload Unbound

```bash
# Reload configuration without dropping cache
sudo unbound-control reload

# Or restart the service
sudo systemctl restart unbound
```

## 🔄 Complete Example

```bash
# Step 1: Download current device list
python download_devices_csv.py

# Step 2: Generate forward zones (using the auto-generated filename)
python generate_forward_zones.py zscaler_devices_20250610_143022.csv /etc/unbound/forward_zones.conf 10.213.182.62 --domain corp.local

# Step 3: Reload Unbound
sudo unbound-control reload

# Step 4: Test resolution
# Client hostname should resolve through Branch Connector
dig @localhost client001.corp.local

# Server hostname should resolve through corporate DNS
dig @localhost server001.corp.local
```

## 🤖 Automation

Create a cron job for automatic updates:

```bash
# Create update script
cat > /usr/local/bin/update-zscaler-zones.sh << 'EOF'
#!/bin/bash
cd /opt/zscaler-forward-zones-generator
python download_devices_csv.py /tmp/devices.csv
python generate_forward_zones.py /tmp/devices.csv /etc/unbound/forward_zones.conf 10.213.182.62 --domain corp.local
unbound-control reload
EOF

chmod +x /usr/local/bin/update-zscaler-zones.sh

# Add to crontab (runs every 4 hours)
echo "0 */4 * * * root /usr/local/bin/update-zscaler-zones.sh" >> /etc/crontab
```

## 📊 Generated Output

The `forward_zones.conf` file contains:

```yaml
# Unbound Forward Zones Configuration
# Generated on: 2025-06-10 14:30:22
# Total forward zones: 1,847
# DNS server: 10.213.182.62
# Domain: corp.local
# Note: Hostnames have been deduplicated to prevent conflicts

forward-zone:
    name: "laptop-jsmith.corp.local"
    forward-addr: 10.213.182.62

forward-zone:
    name: "desktop-doe001.corp.local"
    forward-addr: 10.213.182.62

# ... additional zones ...
```

## 🔧 Troubleshooting

### DNS Resolution Issues

1. **Check Unbound is running:**

    ```bash
    sudo systemctl status unbound
    ```

2. **Verify forward zones are loaded:**

    ```bash
    sudo unbound-control list_forwards
    ```

3. **Test specific resolution:**

    ```bash
    # Should go to Branch Connector
    dig @localhost client-hostname.corp.local +short

    # Should go to corporate DNS
    dig @localhost server-hostname.corp.local +short
    ```

4. **Enable query logging:**
    ```yaml
    server:
        log-queries: yes
        verbosity: 2
    ```

### Common Issues

| Issue                 | Solution                                                    |
| --------------------- | ----------------------------------------------------------- |
| SERVFAIL responses    | Ensure `module-config: "iterator"` is set                   |
| Zones not loading     | Check file permissions on forward_zones.conf                |
| Authentication errors | Verify .env credentials and API permissions                 |
| No devices found      | Check CSV contains Windows devices with "Registered" status |

### Performance Optimization

For large deployments (10,000+ devices):

```yaml
server:
    # Increase cache size
    msg-cache-size: 100m
    rrset-cache-size: 200m

    # Increase number of threads
    num-threads: 4

    # Optimize for forward zones
    prefetch: yes
    prefetch-key: yes
```

## 🔒 Security Considerations

-   Limit Unbound access with appropriate `access-control` directives
-   Use firewall rules to restrict DNS access
-   Regularly rotate Zscaler API credentials
-   Monitor DNS query logs for anomalies
-   Consider implementing DNS over TLS for client connections

## 📈 Monitoring

Basic monitoring script:

```bash
#!/bin/bash
# Check zone count
ZONE_COUNT=$(unbound-control list_forwards | wc -l)
echo "Active forward zones: $ZONE_COUNT"

# Check cache hit rate
unbound-control stats_noreset | grep "total.num.cachehits"
unbound-control stats_noreset | grep "total.num.cachemiss"
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

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

---

**Developed by ZHERO srl - [https://zhero.ai](https://zhero.ai)**
