#!/bin/bash
# WiFi Connect Script for PaperDrop
# Based on balena's wifi-connect approach
# 
# This script manages WiFi setup using a simple AP -> Connect -> AP fallback pattern
# It does NOT use concurrent AP+STA mode (which is unreliable on single-radio devices)

set -e

PORTAL_SSID="${PORTAL_SSID:-PaperDrop_Setup}"
PORTAL_GATEWAY="${PORTAL_GATEWAY:-192.168.4.1}"
PORTAL_DHCP_RANGE="${PORTAL_DHCP_RANGE:-192.168.4.2,192.168.4.254}"
PORTAL_INTERFACE="${PORTAL_INTERFACE:-wlan0}"
PORTAL_CHANNEL="${PORTAL_CHANNEL:-6}"

HOSTAPD_CONF="/tmp/paperdrop_hostapd.conf"
DNSMASQ_CONF="/tmp/paperdrop_dnsmasq.conf"
DNSMASQ_HOSTS="/tmp/paperdrop_hosts"

log() {
    echo "[WiFi-Connect] $1"
}

generate_hostapd_conf() {
    cat > "$HOSTAPD_CONF" << EOF
interface=$PORTAL_INTERFACE
driver=nl80211
ssid=$PORTAL_SSID
hw_mode=g
channel=$PORTAL_CHANNEL
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
EOF
}

generate_dnsmasq_conf() {
    # Create hosts file that redirects everything to us
    echo "$PORTAL_GATEWAY setup.paperdrop.local" > "$DNSMASQ_HOSTS"
    
    cat > "$DNSMASQ_CONF" << EOF
interface=$PORTAL_INTERFACE
bind-interfaces
dhcp-range=$PORTAL_DHCP_RANGE,255.255.255.0,24h

# Captive portal DNS hijacking
address=/#/$PORTAL_GATEWAY

# Don't forward unknown domains
bogus-priv
domain-needed

# Read local hosts
addn-hosts=$DNSMASQ_HOSTS
EOF
}

start_ap() {
    log "Starting Access Point..."
    
    # Stop any existing processes
    stop_ap 2>/dev/null || true
    
    # Disable NetworkManager control of wlan0
    nmcli device set $PORTAL_INTERFACE managed no 2>/dev/null || true
    
    # Bring up interface
    ip link set $PORTAL_INTERFACE up
    
    # Set IP address
    ip addr flush dev $PORTAL_INTERFACE
    ip addr add $PORTAL_GATEWAY/24 dev $PORTAL_INTERFACE
    
    # Generate configs
    generate_hostapd_conf
    generate_dnsmasq_conf
    
    # Start hostapd
    log "Starting hostapd..."
    hostapd -B "$HOSTAPD_CONF"
    
    # Wait for hostapd to bring interface up
    sleep 2
    
    # Start dnsmasq
    log "Starting dnsmasq..."
    dnsmasq -C "$DNSMASQ_CONF"
    
    # Enable IP forwarding and set up iptables
    sysctl -w net.ipv4.ip_forward=1 > /dev/null
    
    # Redirect port 80 to our web server on 8080
    iptables -t nat -A PREROUTING -i $PORTAL_INTERFACE -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || true
    
    log "Access Point started! SSID: $PORTAL_SSID"
}

stop_ap() {
    log "Stopping Access Point..."
    
    # Kill processes
    killall hostapd 2>/dev/null || true
    killall dnsmasq 2>/dev/null || true
    
    # Clean up iptables
    iptables -t nat -D PREROUTING -i $PORTAL_INTERFACE -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || true
    
    # Flush IP
    ip addr flush dev $PORTAL_INTERFACE 2>/dev/null || true
    
    # Re-enable NetworkManager control
    nmcli device set $PORTAL_INTERFACE managed yes 2>/dev/null || true
    
    log "Access Point stopped."
}

connect_wifi() {
    local ssid="$1"
    local password="$2"
    
    log "Attempting to connect to WiFi: $ssid"
    
    # Stop AP mode first
    stop_ap
    
    # Wait a moment
    sleep 2
    
    # Try to connect using NetworkManager
    # First, check if we already have this connection
    if nmcli connection show "$ssid" > /dev/null 2>&1; then
        # Update existing connection
        nmcli connection modify "$ssid" wifi-sec.psk "$password"
        nmcli connection up "$ssid"
    else
        # Create new connection
        nmcli device wifi connect "$ssid" password "$password"
    fi
    
    # Wait for connection
    for i in {1..30}; do
        if ip addr show $PORTAL_INTERFACE | grep -q "inet "; then
            # Check if we actually have internet
            if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
                log "Connected to $ssid!"
                return 0
            fi
        fi
        sleep 1
    done
    
    log "Failed to connect to $ssid"
    return 1
}

# Main command handler
case "$1" in
    start)
        start_ap
        ;;
    stop)
        stop_ap
        ;;
    connect)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Usage: $0 connect <ssid> <password>"
            exit 1
        fi
        connect_wifi "$2" "$3"
        ;;
    *)
        echo "Usage: $0 {start|stop|connect <ssid> <password>}"
        exit 1
        ;;
esac
