#!/bin/bash
set -e

# CONSTANTS
PHY_IFACE="wlan0"
AP_IFACE="uap0"
IP_ADDR="192.168.4.1/24"
HOSTAPD_CONF="/etc/paperdrop/hostapd_apsta.conf"
DNSMASQ_CONF="/etc/paperdrop/dnsmasq_apsta.conf"

function start() {
    echo "[APSTA] Enabling Mode..."
    
    # 1. Create uap0 if not exists
    if ! iw dev $AP_IFACE info >/dev/null 2>&1; then
        echo "[APSTA] Creating virtual interface $AP_IFACE..."
        iw dev $PHY_IFACE interface add $AP_IFACE type __ap
        
        # 1.5 Assign unique MAC (BSSID)
        # Flip the 7th bit of the first byte (Typical Local Admin bit)
        # Or just hardcode a slight variation if we know the OUI. 
        # Easier: Let's just retrieve wlan0 MAC and set uap0 to +1 or something.
        # Actually, let's just retry setting a random local MAC.
        ip link set dev $AP_IFACE address 02:00:00:00:01:00
    fi

    # 2. Config IP
    echo "[APSTA] Setting IP for $AP_IFACE..."
    ip link set $AP_IFACE up
    ip addr flush dev $AP_IFACE
    ip addr add $IP_ADDR dev $AP_IFACE

    # 3. Config Firewall (NAT + Redirect)
    echo "[APSTA] Configuring firewall (NAT + Redirect)..."
    
    # Enable IP Forwarding
    sysctl -w net.ipv4.ip_forward=1 > /dev/null
    
    # Flush existing NAT rules to be safe
    # iptables -t nat -F  <-- Dangerous if other things use it, but for this device likely fine. 
    # Let's just append our needed rules.
    
    # 3a. Captive Portal Redirect (Port 80 -> 8080)
    # Only redirect traffic destined to the Gateway IP (192.168.4.1) OR if we want to catch ALL HTTP.
    # Since we are doing "Targeted DNS Poisoning", the client will resolve CP domains to 192.168.4.1.
    # So valid traffic to 192.168.4.1:80 will be caught here.
    iptables -t nat -A PREROUTING -i $AP_IFACE -d $IP_ADDR -p tcp --dport 80 -j REDIRECT --to-port 8080
    
    # 3b. Enable NAT (Masquerade) for Internet Access
    # Allow traffic from uap0 to go out via wlan0
    iptables -t nat -A POSTROUTING -o $PHY_IFACE -j MASQUERADE
    
    # Allow forwarding
    iptables -A FORWARD -i $PHY_IFACE -o $AP_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i $AP_IFACE -o $PHY_IFACE -j ACCEPT

    # 4. Start Services
    echo "[APSTA] Starting dnsmasq..."
    # We kill any system dnsmasq to avoid port 53 conflicts, or we can run on alternate port/bind-interface
    # Assuming we want full control:
    killall dnsmasq || true
    dnsmasq -C $DNSMASQ_CONF

    echo "[APSTA] Starting hostapd..."
    killall hostapd || true
    hostapd -B $HOSTAPD_CONF
    
    echo "[APSTA] Enabled."
}

function stop() {
    echo "[APSTA] Disabling Mode..."
    killall hostapd || true
    killall dnsmasq || true
    
    # Clean up firewall
    iptables -t nat -F PREROUTING
    
    if iw dev $AP_IFACE info >/dev/null 2>&1; then
        echo "[APSTA] Removing $AP_IFACE..."
        iw dev $AP_IFACE del
    fi
    echo "[APSTA] Disabled."
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac
