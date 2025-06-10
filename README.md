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
│ │    .conf    │ │     │ VIP: 10.0.0.12      │
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
python generate_forward_zones.py devices.csv /etc/unbound/forward_zones.conf 10.0.0.12,10.0.0.13 --domain corp.local

# Verbose output for troubleshooting
python generate_forward_zones.py devices.csv /etc/unbound/forward_zones.conf 10.0.0.12 --domain corp.local --verbose
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
python generate_forward_zones.py zscaler_devices_20250610_143022.csv /etc/unbound/forward_zones.conf 10.0.0.12 --domain corp.local

# Step 3: Reload Unbound
sudo unbound-control reload

# Step 4: Test resolution
# Client hostname should resolve through Branch Connector
dig @localhost client001.corp.local

# Server hostname should resolve through corporate DNS
dig @localhost server001.corp.local
```

## 🔄 High Availability Setup with Synchronization Scripts

For production environments requiring high availability, this project includes synchronization scripts to maintain multiple Unbound servers with identical forward zone configurations.

### Architecture Overview

```
┌─────────────────────┐                    ┌─────────────────────┐
│  Primary Server     │                    │  Secondary Server   │
│                     │                    │                     │
│ • Downloads from API│      SSH/SCP       │ • No API access     │
│ • Generates zones   │ ◄────────────────►│ • Syncs from primary│
│ • Unbound (active)  │   pdl.csv transfer │ • Unbound (standby) │
│                     │                    │                     │
│ API Rate Limits: ✓  │                    │ API Rate Limits: ✗  │
└─────────────────────┘                    └─────────────────────┘
```

**Note:** The secondary server does not require Zscaler API credentials. It relies entirely on the CSV file synchronized from the primary server, helping to avoid API rate limits.

### Primary Server Script Setup

1. **Copy Python scripts and synchronization script:**

    ```bash
    # Copy Python scripts to root directory
    sudo cp download_devices_csv.py /root/
    sudo cp generate_forward_zones.py /root/

    # Copy synchronization script
    sudo cp sync_unbound_primary.sh /root/
    sudo chmod +x /root/sync_unbound_primary.sh

    # Copy .env file with API credentials
    sudo cp .env /root/
    sudo chmod 600 /root/.env
    ```

2. **Create the zonesync user for secure file transfer:**

    ```bash
    # Create user
    sudo useradd -m -s /bin/bash zonesync

    # Set password (optional if using only SSH keys)
    sudo passwd zonesync

    # Create .ssh directory
    sudo mkdir -p /home/zonesync/.ssh
    sudo chmod 700 /home/zonesync/.ssh
    sudo chown zonesync:zonesync /home/zonesync/.ssh
    ```

3. **Configure cron for nightly execution:**

    ```bash
    # Add to root's crontab - runs at 2:00 AM daily
    echo "0 2 * * * /root/sync_unbound_primary.sh >/dev/null 2>&1" | sudo crontab -

    # Verify crontab entry
    sudo crontab -l
    ```

### Secondary Server Script Setup

1. **Copy Python script and synchronization script:**

    ```bash
    # Only need the generate script (no download script needed)
    sudo cp generate_forward_zones.py /root/

    # Copy synchronization script
    sudo cp sync_unbound_secondary.sh /root/
    sudo chmod +x /root/sync_unbound_secondary.sh
    ```

2. **Configure the primary server IP:**

    ```bash
    # Replace with your actual primary server IP
    sudo sed -i 's/IP_SERVER_PRIMARIO/10.1.1.100/g' /root/sync_unbound_secondary.sh
    ```

3. **Setup SSH key authentication:**

    ```bash
    # Generate SSH key pair (as root)
    sudo ssh-keygen -t rsa -b 4096 -f /root/.ssh/id_rsa -N ""

    # Copy public key to primary server
    sudo ssh-copy-id zonesync@10.1.1.100

    # Test SSH connection
    sudo ssh zonesync@10.1.1.100 "echo 'SSH connection successful'"
    ```

4. **Configure cron for nightly execution (30 minutes after primary):**

    ```bash
    # Add to root's crontab - runs at 2:30 AM daily
    echo "30 2 * * * /root/sync_unbound_secondary.sh >/dev/null 2>&1" | sudo crontab -

    # Verify crontab entry
    sudo crontab -l
    ```

### Script Features

-   **Automatic error handling**: Scripts exit on any failure to prevent partial updates
-   **Comprehensive logging**: All operations logged with timestamps
    -   Primary: `/var/log/unbound_sync.log`
    -   Secondary: `/var/log/unbound_sync_secondary.log`
-   **Permission management**: Automatic permission setting for synchronized files
-   **Service management**: Automatic Unbound restart after configuration changes
-   **API rate limit protection**: Only primary server accesses Zscaler API

### Monitoring the Synchronization

#### Check Synchronization Status

```bash
# On primary server - check last sync
sudo tail -20 /var/log/unbound_sync.log

# On secondary server - check last sync
sudo tail -20 /var/log/unbound_sync_secondary.log

# Verify file timestamps
ls -la /home/zonesync/pdl.csv  # On primary
ls -la /root/pdl.csv            # On secondary
```

#### Create a Monitoring Script

```bash
cat > /usr/local/bin/check-unbound-sync.sh << 'EOF'
#!/bin/bash

echo "=== Unbound Sync Status ==="
echo

# Check if sync ran today
if grep -q "$(date +%Y-%m-%d)" /var/log/unbound_sync*.log; then
    echo "✓ Sync ran today"
    grep "$(date +%Y-%m-%d)" /var/log/unbound_sync*.log | tail -5
else
    echo "✗ No sync today"
fi

# Check forward zones count
ZONE_COUNT=$(grep -c "forward-zone:" /etc/unbound/forward_zones.conf 2>/dev/null || echo "0")
echo
echo "Active forward zones: $ZONE_COUNT"

# Check Unbound status
echo
systemctl is-active --quiet unbound && echo "✓ Unbound is running" || echo "✗ Unbound is NOT running"
EOF

chmod +x /usr/local/bin/check-unbound-sync.sh
```

### Failover Configuration

For automatic failover, configure your clients to use both servers:

#### Option 1: Client DNS Configuration

```yaml
# /etc/resolv.conf or DHCP configuration
nameserver 10.1.1.100  # Primary Unbound
nameserver 10.1.1.101  # Secondary Unbound
```

#### Option 2: Load Balancer VIP

For seamless failover, consider using a load balancer or keepalived to provide a single VIP that automatically fails over between servers.

### Troubleshooting Synchronization

| Issue                     | Check            | Solution                                              |
| ------------------------- | ---------------- | ----------------------------------------------------- |
| No CSV on secondary       | SSH connectivity | Test with `ssh zonesync@primary "ls /home/zonesync/"` |
| Permission denied         | File permissions | Ensure zonesync owns `/home/zonesync/pdl.csv`         |
| Old data                  | Cron execution   | Check cron logs: `grep CRON /var/log/syslog`          |
| API errors (primary only) | API credentials  | Verify `.env` file in `/root/`                        |

## 🤖 Manual Automation (Without HA Scripts)

For single-server deployments, create a simple cron job:

```bash
# Create update script
cat > /usr/local/bin/update-zscaler-zones.sh << 'EOF'
#!/bin/bash
cd /opt/zscaler-forward-zones-generator
python download_devices_csv.py /tmp/devices.csv
python generate_forward_zones.py /tmp/devices.csv /etc/unbound/forward_zones.conf 10.0.0.12 --domain corp.local
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
# DNS server: 10.0.0.12
# Domain: corp.local
# Note: Hostnames have been deduplicated to prevent conflicts

forward-zone:
    name: "laptop-jsmith.corp.local"
    forward-addr: 10.0.0.12

forward-zone:
    name: "desktop-doe001.corp.local"
    forward-addr: 10.0.0.12

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
-   Secure SSH access between primary and secondary servers
-   Use SSH key authentication instead of passwords

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
