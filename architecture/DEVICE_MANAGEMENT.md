# PaperDrop Device Management Architecture

## 1. Philosophy: "Resilience First"
Devices in the field are unreliable. Power cuts, WiFi drops, and router resets are normal. The system must assume the device is **offline** until proven otherwise and must **queue** actions to be performed when connectivity returns.

## 2. Communication Protocol
We will enhance the existing **WebSocket** connection to behave like a robust IoT protocol (similar to MQTT QoS 1).

### Why not switch to MQTT right now?
While MQTT is excellent, adding a Broker (Mosquitto/AWS IoT) introduces significant infrastructure complexity. We can achieve 90% of the benefits with our existing WebSocket connection by implementing:
1.  **Application-Level Acknowledgements (ACKs)**: The backend doesn't consider a job "Sent" until the device replies "Received".
2.  **Store-and-Forward**: If the WebSocket is down, the backend saves the job to the Database. On reconnection, the device requests "Pending Jobs".
3.  **Heartbeats**: The device sends a ping every 30s with telemetry (WiFi Signal, RAM, Version).

## 3. Key Components

### A. The "Fleet Manager" (Backend)
*   **Device Registry**: Database of all devices, their secrets, and current state.
*   **Job Queue**: A persistent queue (Postgres) for messages waiting to be printed.
*   **OTA Orchestrator**: Manages firmware versions and rollout.

### B. The "Agent" (Raspberry Pi)
*   **Connection Manager**: Aggressively tries to reconnect. Exponential backoff.
*   **Offline Buffer**: If the printer is jammed/offline, it buffers messages locally (optional, but good).
*   **Telemetry Reporter**: Sends vital stats to help debug "Why is this device offline?" (e.g., "RSSI: -85dBm" means bad WiFi).
*   **Updater**: A separate thread/process that can download a `.tar.gz` or `git pull`, install dependencies, and restart the main service.

## 4. Data Model Changes

**Device Table Enhancements:**
*   `firmwareVersion`: Track what's running.
*   `wifiSignal`: Last known RSSI (dBm).
*   `lastHeartbeat`: Timestamp of last ping.
*   `status`: ONLINE, OFFLINE, PRINTING, ERROR.
*   `config`: JSON blob for remote configuration (e.g., polling intervals, timezone).

**New: FirmwareRelease Table:**
*   `version`: e.g., "1.2.0"
*   `url`: S3/GitHub URL to the update package.
*   `critical`: Boolean (force update?).

**New: PrintJob Table:**
*   `status`: PENDING, SENT, ACKNOWLEDGED, PRINTED, FAILED.
*   `retryCount`: Number of attempts.

## 5. Provisioning Flow (At Scale)
1.  **Manufacturing**:
    *   SD Card is flashed with a "Base Image".
    *   Script generates a unique `device_code` and `device_secret` on first boot (or pre-flashed).
2.  **Field Setup**:
    *   User connects to `PaperDrop Setup` AP.
    *   Enters WiFi creds.
3.  **Claiming**:
    *   Device connects to Backend.
    *   User enters `device_code` in Web App.
    *   Backend links Device to User.

## 6. Software Updates (OTA)
**Strategy: "Pull & Restart"**
1.  Admin uploads a new version (or tags a release in Git).
2.  Admin clicks "Deploy to All" or "Deploy to Device X".
3.  Backend sends a `command: update` message via WebSocket.
4.  Device receives command:
    *   Downloads code.
    *   Runs `pip install`.
    *   Restarts systemd service.
5.  Device comes back online with new version.

## 7. Security
*   **Device Auth**: `x-device-code` + `x-device-secret` headers.
*   **Admin Auth**: Strong password (Environment Variable) protecting all Admin API routes.

## 8. Log Retrieval Contract
To support fleet debugging, the backend can request device logs via the existing WebSocket channel.

**Backend ➜ Device**
* Message type: `fetch_logs`
* Payload: `{ request_id, log_type: 'agent' | 'wifi' | 'system', lines: number }`
* The backend waits ~15 seconds for a response before timing out.

**Device ➜ Backend**
* Message type: `log_bundle`
* Payload: `{ request_id, logs: '<text payload>' }` (additional metadata optional)
* The backend streams the `logs` content to the requesting user as a downloadable text file.

If the device is offline, the HTTP request returns `503 Device offline`; if no response is received in time, it returns `504 Device did not respond with logs`.
