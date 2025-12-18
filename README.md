# PaperDrop

PaperDrop is a plug-and-play thermal printer that allows family members to send physical printed messages to loved ones at home.

## 🌟 Features

- **Instant Messaging**: Send text and images from your phone to a thermal printer
- **BLE Provisioning**: Easy WiFi setup via Bluetooth from your mobile device
- **Multi-User Access**: Share your printer with family members via invite links
- **Message Queue**: Messages are queued and delivered even when the printer is offline
- **Admin Dashboard**: Manage devices, firmware updates, and monitor fleet status

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Cloud                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Frontend   │    │   Backend   │    │  Database   │     │
│  │   (React)   │◄──►│  (Express)  │◄──►│ (PostgreSQL)│     │
│  └─────────────┘    └──────┬──────┘    └─────────────┘     │
│                            │ WebSocket                      │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Raspberry Pi                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   BLE       │    │  WS Agent   │    │   Thermal   │     │
│  │Provisioning │    │  (Python)   │───►│   Printer   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Node.js (Express) | REST API & WebSocket server |
| **Frontend** | React + Vite | Web dashboard for users |
| **Agent** | Python | Device-side software on Raspberry Pi |
| **Database** | PostgreSQL | User/device/message storage |

## 📁 Directory Structure

```
paperdrop/
├── backend/           # Cloud API and WebSocket server
│   ├── src/
│   │   ├── controllers/   # Request handlers
│   │   ├── routes/        # API routes
│   │   ├── websocket/     # WebSocket handlers
│   │   └── server.ts      # Main entry point
│   └── prisma/            # Database schema
├── frontend/          # React web application
│   └── src/
│       ├── components/    # UI components
│       ├── pages/         # Page components
│       └── api/           # API client
├── agent/             # Raspberry Pi software
│   └── src/
│       ├── ws_agent.py            # WebSocket client
│       ├── ble_provisioning.py    # BLE GATT server
│       ├── config.py              # Device configuration
│       └── device_interface.py    # Printer interface
└── docs/              # Additional documentation
```

## 🖨️ Hardware Requirements

- **Raspberry Pi 5** (recommended) or Pi 4
- **Epson TM-T20III** thermal printer (USB)
- **MicroSD Card** (16GB+ recommended)
- **Power supply** for both Pi and printer

## 💾 Creating Your Own Device

### Option 1: Clone an Existing SD Card

If you have a working PaperDrop device and want to create another:

**On macOS:**
```bash
# 1. Insert the SD card and find its disk identifier
diskutil list

# 2. Unmount the disk (replace diskX with your disk)
diskutil unmountDisk /dev/diskX

# 3. Create an image (this may take 10-20 minutes)
sudo dd if=/dev/rdiskX of=~/paperdrop-image.img bs=1m status=progress

# 4. Insert your new SD card and find its identifier
diskutil list

# 5. Unmount the new card
diskutil unmountDisk /dev/diskX

# 6. Write the image to the new card
sudo dd if=~/paperdrop-image.img of=/dev/rdiskX bs=1m status=progress

# 7. Eject the card
diskutil eject /dev/diskX
```

**On Linux:**
```bash
# 1. Find the SD card device
lsblk

# 2. Create an image
sudo dd if=/dev/sdX of=~/paperdrop-image.img bs=4M status=progress

# 3. Write to new card
sudo dd if=~/paperdrop-image.img of=/dev/sdX bs=4M status=progress
```

**On Windows:**
- Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) or [Win32 Disk Imager](https://sourceforge.net/projects/win32diskimager/)

### Option 2: Fresh Install

1. Flash Raspberry Pi OS Lite (64-bit) to an SD card
2. Enable SSH and configure WiFi in Raspberry Pi Imager
3. Boot the Pi and SSH in
4. Clone this repository and run the installer:
```bash
git clone https://github.com/hadlocna/PaperDrop.git
cd PaperDrop
sudo ./install_paperdrop.sh
```

### Important: Reset Device Identity

After cloning an SD card, **you must reset the device identity** so it gets a new unique ID:

```bash
# SSH into the new device
ssh pi@<new-device-ip>

# Remove the old device identity
sudo rm -f /etc/paperdrop/device.json
sudo rm -f /etc/paperdrop/device-id
sudo rm -f /etc/paperdrop/wifi.json
sudo rm -f /etc/paperdrop/wifi-provisioned

# Restart services to generate new identity
sudo systemctl restart paperdrop-ble
sudo systemctl restart paperdrop-ws-agent
```

The device will now generate a new unique ID and be ready for provisioning.

## 🚀 User Provisioning Flow

This is the complete flow for a user setting up a new PaperDrop device:

### Step 1: Power On Device
1. Plug in the Raspberry Pi and printer
2. The device boots and starts advertising via Bluetooth
3. A unique device ID is generated (e.g., `PD-780420ea`)

### Step 2: Connect via Mobile App
1. Navigate to the PaperDrop web app on your phone
2. Click **"Add New Device"**
3. The app scans for nearby PaperDrop devices via Bluetooth

### Step 3: WiFi Provisioning (BLE)
1. Select your PaperDrop device from the list
2. Choose your WiFi network from the scan results
3. Enter your WiFi password
4. The device connects to WiFi and reports status back via BLE

### Step 4: Device Claims to Cloud
1. Once WiFi is connected, the device establishes a WebSocket connection to the backend
2. If this is a new device, it registers itself in the database
3. The user is prompted to **claim** the device

### Step 5: Claim Device
1. The device appears as "unclaimed" in the user's dashboard
2. User clicks **"Claim Device"** and gives it a friendly name
3. The device is now linked to the user's account

### Step 6: Send Messages!
1. Use the web app to compose text or image messages
2. Messages are sent to the backend and queued
3. The device receives messages via WebSocket and prints them instantly

## 🔧 Technical Setup

### Backend Deployment (Render)

The backend is deployed on Render with:
- **Build Command**: `npm install --include=dev && npm run build`
- **Start Command**: `npx prisma db push --accept-data-loss && npx ts-node prisma/seed.ts && npm start`

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string

### Frontend Deployment (Render)

The frontend is deployed as a static site:
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`

Environment variables:
- `VITE_API_URL`: Backend API URL

### Device Setup

The Raspberry Pi runs three main services:

| Service | Purpose |
|---------|---------|
| `paperdrop-ble.service` | BLE GATT server for WiFi provisioning |
| `paperdrop-ws-agent.service` | WebSocket client for cloud communication |
| `paperdrop-wifi.service` | WiFi management helper |

Key files on the device:
- `/etc/paperdrop/device.json` - Device ID and secret
- `/etc/paperdrop/wifi.json` - Saved WiFi credentials
- `/opt/paperdrop/` - Application code

## 🔐 Security

- **Device Authentication**: Each device has a unique `deviceCode` and `deviceSecret`
- **User Authentication**: Users log in via email/password
- **Device Access**: Owners can share access with other users via invite links
- **API Security**: Backend uses CORS and Helmet for protection

## 🐛 Troubleshooting

### Device Shows Offline
1. Check WiFi connection on the device
2. Verify the device secret matches the database
3. Check WebSocket agent logs: `journalctl -u paperdrop-ws-agent -f`

### Print Jobs Fail
1. Ensure CUPS is disabled: `sudo systemctl stop cups cups-browsed`
2. Check USB printer connection: `lsusb | grep Epson`
3. Verify no other process is using the printer

### BLE Provisioning Fails
1. Restart BLE service: `sudo systemctl restart paperdrop-ble`
2. Check BLE logs: `journalctl -u paperdrop-ble -f`
3. Ensure Bluetooth is enabled: `bluetoothctl show`

## 📝 Admin Features

Access the admin panel at `/admin` with password authentication:
- View all devices and their status
- Unprovision devices (complete removal)
- Deploy firmware updates
- Monitor device connections

## 🏷️ Version History

| Version | Date | Notes |
|---------|------|-------|
| v1.0.0-working | 2025-12-18 | Stable release with full provisioning flow |

---

## Development

### Running Locally

**Backend:**
```bash
cd backend
npm install
npm run dev
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Deploying to Device

Use the deployment script:
```bash
./agent/venv/bin/python3 deploy_refactor.py
```

This uploads `ble_provisioning.py`, `ws_agent.py`, and `paperdrop-wifi.sh` to the device and restarts services.

---

Built with ❤️ for keeping families connected.
