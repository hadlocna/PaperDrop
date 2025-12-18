# Device Architecture

This document describes the software architecture running on the PaperDrop Raspberry Pi device.

## System Services

The device runs three main systemd services:

### 1. paperdrop-ble.service

**Purpose**: BLE GATT server for WiFi provisioning

**File**: `/opt/paperdrop/ble_provisioning.py`

**Responsibilities**:
- Advertise as a BLE peripheral
- Provide device ID via BLE characteristic
- Scan for WiFi networks on request
- Accept WiFi credentials and connect
- Report connection status via notifications

**Dependencies**: `bluez`, `python3-dbus`, `python3-gi`

### 2. paperdrop-ws-agent.service

**Purpose**: WebSocket client for cloud communication

**File**: `/opt/paperdrop/ws_agent.py`

**Responsibilities**:
- Maintain persistent WebSocket connection to backend
- Authenticate using device code and secret
- Receive print jobs from the cloud
- Send print status updates
- Handle heartbeat/keepalive messages
- Auto-reconnect on disconnection

**Dependencies**: `websockets`, `python-escpos`, `Pillow`

### 3. paperdrop-wifi.service

**Purpose**: WiFi management helper

**File**: `/usr/local/bin/paperdrop-wifi.sh`

**Responsibilities**:
- Auto-connect to saved WiFi on boot
- Manage NetworkManager connections

## File Locations

```
/etc/paperdrop/
├── device.json          # Device credentials
├── wifi.json            # Saved WiFi credentials
├── device-id            # Plain text device ID
└── wifi-provisioned     # Flag file

/opt/paperdrop/
├── ble_provisioning.py  # BLE service
├── ws_agent.py          # WebSocket agent
├── config.py            # Configuration management
├── device_interface.py  # Printer interface
└── venv/                # Python virtual environment

/usr/local/bin/
└── paperdrop-wifi.sh    # WiFi management script
```

## Authentication Flow

```
Device Boot
    │
    ▼
Load device.json
    │
    ├─── Device ID exists? ─── No ──► Generate new ID
    │                                      │
    ▼                                      ▼
Connect to WebSocket with credentials
    │
    ▼
Backend validates device
    │
    ├─── Device in DB? ─── No ──► Create new device record
    │                                    │
    ├─── Secret matches? ─── No ──► If unclaimed, update secret
    │                                    │
    ▼                                    ▼
Connection established ◄────────────────┘
```

## Print Job Flow

```
Backend receives message
    │
    ▼
Send via WebSocket: {type: "new_message", message: {...}}
    │
    ▼
Agent receives message
    │
    ▼
Parse content type (text/image)
    │
    ▼
Open USB printer connection
    │
    ▼
Print content
    │
    ▼
Close printer connection
    │
    ▼
Send status update: {type: "print_status", status: "printed"}
```

## USB Printer Configuration

The Epson TM-T20III is accessed via `python-escpos`:

```python
from escpos.printer import Usb
printer = Usb(0x04b8, 0x0e28, profile="TM-T20II", auto_detach_kernel_driver=True)
```

**Important**: CUPS must be disabled to prevent USB conflicts:
```bash
sudo systemctl disable cups cups-browsed
sudo systemctl stop cups cups-browsed
```

## Network Configuration

The device uses NetworkManager for WiFi management:

```bash
# Connect to a network
nmcli connection add type wifi con-name "SSID" ssid "SSID" \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "password"
nmcli connection up "SSID"

# List connections
nmcli connection show

# Delete a connection
nmcli connection delete "SSID"
```

## Logging

View service logs with journalctl:

```bash
# BLE provisioning logs
journalctl -u paperdrop-ble -f

# WebSocket agent logs
journalctl -u paperdrop-ws-agent -f

# WiFi service logs
journalctl -u paperdrop-wifi -f
```

## Deployment

To update device software:

```python
# From development machine
python3 deploy_refactor.py
```

This script:
1. Connects to the device via SSH
2. Uploads updated Python files
3. Restarts all services
