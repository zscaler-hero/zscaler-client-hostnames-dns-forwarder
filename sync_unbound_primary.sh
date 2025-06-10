#!/bin/bash
# sync_unbound_primary.sh
# Main script to be executed via cron as root on the primary server

# Configuration
PYTHON_DOWNLOAD_SCRIPT="/root/download_devices_csv.py"
CSV_OUTPUT="/root/pdl.csv"
ZONESYNC_DIR="/home/zonesync"
ZONESYNC_USER="zonesync"
PYTHON_GENERATE_SCRIPT="/root/generate_forward_zones.py"
UNBOUND_CONF="/etc/unbound/forward_zones.conf"
DNS_SERVERS="10.0.0.1,10.0.0.2"
DOMAIN="domain.com"
LOG_FILE="/var/log/unbound_sync.log"

# Logging function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Start execution
log_message "Starting primary Unbound synchronization"

# Execute download script
log_message "Executing devices CSV download"
if python "$PYTHON_DOWNLOAD_SCRIPT" "$CSV_OUTPUT"; then
    log_message "Download completed successfully"
else
    log_message "ERROR: Download failed with code $?"
    exit 1
fi

# Verify the file was created
if [ ! -f "$CSV_OUTPUT" ]; then
    log_message "ERROR: File $CSV_OUTPUT not found after download"
    exit 1
fi

# Create destination directory if it doesn't exist
if [ ! -d "$ZONESYNC_DIR" ]; then
    log_message "Creating directory $ZONESYNC_DIR"
    mkdir -p "$ZONESYNC_DIR"
fi

# Copy file to zonesync folder
log_message "Copying CSV file to $ZONESYNC_DIR"
if cp "$CSV_OUTPUT" "$ZONESYNC_DIR/pdl.csv"; then
    # Set correct permissions
    chown "$ZONESYNC_USER":"$ZONESYNC_USER" "$ZONESYNC_DIR/pdl.csv"
    chmod 644 "$ZONESYNC_DIR/pdl.csv"
    log_message "File copied and permissions set correctly"
else
    log_message "ERROR: Unable to copy file"
    exit 1
fi

# Generate forward zones
log_message "Generating forward zones"
if python "$PYTHON_GENERATE_SCRIPT" "$CSV_OUTPUT" "$UNBOUND_CONF" "$DNS_SERVERS" --domain "$DOMAIN"; then
    log_message "Forward zones generated successfully"
else
    log_message "ERROR: Forward zones generation failed with code $?"
    exit 1
fi

# Restart unbound service
log_message "Restarting unbound service"
if systemctl restart unbound; then
    log_message "Unbound service restarted successfully"
else
    log_message "ERROR: Unable to restart unbound"
    exit 1
fi

log_message "Synchronization completed successfully"
log_message "----------------------------------------"

exit 0

