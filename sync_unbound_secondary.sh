#!/bin/bash
# sync_unbound_secondary.sh
# Secondary script to be executed on another server to retrieve and synchronize

# Configuration - MODIFY WITH CORRECT IP/HOSTNAME
REMOTE_HOST="IP_SERVER_PRIMARIO"  # <-- REPLACE WITH ACTUAL IP
REMOTE_USER="zonesync"
REMOTE_FILE="/home/zonesync/pdl.csv"
REMOTE_DOMAIN_MAPPINGS="/home/zonesync/domain_mappings.conf"
LOCAL_CSV="/root/pdl.csv"
PYTHON_GENERATE_SCRIPT="/root/generate_forward_zones.py"
UNBOUND_CONF="/etc/unbound/forward_zones.conf"
DNS_SERVERS="10.0.0.1,10.0.0.2"
DOMAIN="domain.com"
DOMAIN_MAPPINGS="/root/domain_mappings.conf"
LOG_FILE="/var/log/unbound_sync_secondary.log"

# Logging function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Start execution
log_message "Starting secondary Unbound synchronization"

# Retrieve file via SCP
log_message "Retrieving CSV file from $REMOTE_HOST"
if scp "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_FILE}" "$LOCAL_CSV"; then
    log_message "File retrieved successfully"
else
    log_message "ERROR: Unable to retrieve file via SCP (code $?)"
    exit 1
fi

# Verify the file was downloaded
if [ ! -f "$LOCAL_CSV" ]; then
    log_message "ERROR: File $LOCAL_CSV not found after SCP"
    exit 1
fi

# Retrieve domain mappings file via SCP (optional, not fatal if missing)
log_message "Retrieving domain mappings from $REMOTE_HOST"
if scp "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DOMAIN_MAPPINGS}" "$DOMAIN_MAPPINGS" 2>/dev/null; then
    log_message "Domain mappings retrieved successfully"
else
    log_message "WARNING: Domain mappings file not found on primary (multi-domain disabled)"
fi

# Generate forward zones
log_message "Generating forward zones"
GENERATE_ARGS=("$LOCAL_CSV" "$UNBOUND_CONF" "$DNS_SERVERS" --domain "$DOMAIN")
if [ -f "$DOMAIN_MAPPINGS" ]; then
    GENERATE_ARGS+=(--domain-mappings "$DOMAIN_MAPPINGS")
    log_message "Using domain mappings from $DOMAIN_MAPPINGS"
fi

if python "$PYTHON_GENERATE_SCRIPT" "${GENERATE_ARGS[@]}"; then
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

log_message "Secondary synchronization completed successfully"
log_message "----------------------------------------"

exit 0