# Device Provisioning Guide

This document describes the complete provisioning process for a PaperDrop device.

## Overview

PaperDrop uses Bluetooth Low Energy (BLE) for initial device setup, allowing users to configure WiFi credentials without needing to connect to the device directly.

## Prerequisites

- PaperDrop device (Raspberry Pi + thermal printer)
- Smartphone with Bluetooth enabled
- WiFi network credentials

## Provisioning Steps

### 1. Physical Setup

1. Connect the thermal printer to the Raspberry Pi via USB
2. Power on the Raspberry Pi
3. Wait ~30 seconds for the device to boot

### 2. Device Initialization

On first boot, the device automatically:
- Generates a unique device ID (format: `PD-XXXXXXXX`)
- Creates a device secret for authentication
- Starts the BLE provisioning service
- Begins advertising as "PaperDrop-XXXX"

### 3. BLE Connection

1. Open the PaperDrop web app on your mobile device
2. Navigate to the device list and click **"Add New Device"**
3. The app scans for nearby BLE devices with the PaperDrop service UUID
4. Select your device from the list

### 4. WiFi Configuration

1. The app reads the device ID via BLE
2. The app requests a WiFi network scan from the device
3. Select your network from the list
4. Enter your WiFi password
5. The device attempts to connect

### 5. Connection Status

The device reports its connection status via BLE notifications:
- `idle` - Initial state
- `connecting` - Attempting to connect to WiFi
- `connected` - Successfully connected
- `failed` - Connection failed

### 6. Cloud Registration

Once WiFi is connected:
1. The device establishes a WebSocket connection to the backend
2. The backend creates a new device record (if first time)
3. The device appears in the "unclaimed" state

### 7. Device Claiming

1. In the web app, you'll see the new device
2. Click **"Claim Device"**
3. Enter a friendly name (e.g., "Mom's Printer")
4. The device is now linked to your account

## BLE Service Details

### Service UUID
`12345678-1234-5678-1234-56789abcdef0`

### Characteristics

| UUID | Name | Properties | Description |
|------|------|------------|-------------|
| `...def1` | Device ID | Read | Returns device code |
| `...def2` | WiFi Config | Write | Accepts JSON: `{ssid, password}` |
| `...def3` | WiFi Networks | Read | Returns JSON array of networks |
| `...def4` | WiFi Status | Read, Notify | Returns connection status |

## Troubleshooting

### Device not appearing in scan
- Ensure Bluetooth is enabled on your phone
- Move closer to the device
- Restart the BLE service on the device

### WiFi connection fails
- Check password is correct
- Ensure the network is 2.4GHz (5GHz may not work)
- Check signal strength

### Device shows offline after claiming
- Verify WiFi credentials are correct
- Check device logs: `journalctl -u paperdrop-ws-agent -f`
- Ensure backend is accessible from the network

## Re-Provisioning

To set up a device again:
1. Admin can "unprovision" the device from the admin panel
2. This removes it from the database
3. Device automatically reconnects and appears as new
4. User can claim it again

## Device Files

| Path | Purpose |
|------|---------|
| `/etc/paperdrop/device.json` | Device ID and secret |
| `/etc/paperdrop/wifi.json` | Saved WiFi credentials |
| `/etc/paperdrop/device-id` | Plain text device ID |
| `/etc/paperdrop/wifi-provisioned` | Flag file indicating WiFi was set up |
