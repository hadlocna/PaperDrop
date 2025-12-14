#!/bin/bash
set -e

# CONSTANTS
PHY_IFACE="wlan0"
AP_IFACE="uap0"
IP_ADDR="192.168.4.1/24"
HOSTAPD_CONF="/etc/paperdrop/hostapd_apsta.conf"
DNSMASQ_CONF="/etc/paperdrop/dnsmasq_apsta.conf"

    # 0. Harden NetworkManager (Prevent interference)
    if command -v nmcli >/dev/null 2>&1; then
        echo "[APSTA] Configuring NetworkManager to ignore $AP_IFACE..."
        # We try to set it unmanaged. might need 'dev set' or config file.
        # 'nmcli dev set' is runtime only, which is perfect.
        nmcli dev set $AP_IFACE managed no || true
    fi

    # 1. Create uap0 if not exists
    if ! iw dev $AP_IFACE info >/dev/null 2>&1; then
        echo "[APSTA] Creating virtual interface $AP_IFACE..."
        iw dev $PHY_IFACE interface add $AP_IFACE type __ap
        ip link set dev $AP_IFACE address 02:00:00:00:01:00
    fi

    # 2. Config IP
    echo "[APSTA] Setting IP for $AP_IFACE..."
    ip link set $AP_IFACE up
    ip addr flush dev $AP_IFACE
    ip addr add $IP_ADDR dev $AP_IFACE

    # 3. Config Firewall (NAT + Redirect)
    echo "[APSTA] Configuring firewall (NAT + Redirect)..."
    sysctl -w net.ipv4.ip_forward=1 > /dev/null
    
    # Cleanups
    iptables -t nat -D PREROUTING -i $AP_IFACE -d $IP_ADDR -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || true
    iptables -t nat -D POSTROUTING -o $PHY_IFACE -j MASQUERADE 2>/dev/null || true

    iptables -t nat -A PREROUTING -i $AP_IFACE -d $IP_ADDR -p tcp --dport 80 -j REDIRECT --to-port 8080
    iptables -t nat -A POSTROUTING -o $PHY_IFACE -j MASQUERADE
    
    iptables -D FORWARD -i $PHY_IFACE -o $AP_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i $AP_IFACE -o $PHY_IFACE -j ACCEPT 2>/dev/null || true
    
    iptables -A FORWARD -i $PHY_IFACE -o $AP_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i $AP_IFACE -o $PHY_IFACE -j ACCEPT

    # 4. Channel Sync (Avoid Single-Radio Conflict)
    CURRENT_CHANNEL=$(iw dev $PHY_IFACE info 2>/dev/null | grep channel | awk '{print $2}')
    if [ ! -z "$CURRENT_CHANNEL" ]; then
        echo "[APSTA] Detected wlan0 on channel $CURRENT_CHANNEL. Syncing hostapd..."
        sed -i "s/channel=.*/channel=$CURRENT_CHANNEL/" $HOSTAPD_CONF
    fi

    # 5. Start Services
    echo "[APSTA] Starting dnsmasq..."
    killall dnsmasq || true
    # Provide a longer timeout/retry if port 53 is stubborn
    dnsmasq -C $DNSMASQ_CONF || { echo "[APSTA] dnsmasq failed to start!"; exit 1; }

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
