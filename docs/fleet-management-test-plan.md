# Fleet management UI tests

Use these manual checks in the browser after running the frontend locally (e.g., `npm run dev`):

1. **Authentication**
   - Enter a valid admin password and confirm devices + firmware data loads.
   - Enter an invalid password and confirm an error displays and the session is not persisted.
2. **Refresh cycle**
   - Click **Refresh devices** and verify the table reloads without navigating away.
   - Temporarily revoke access/stop the API to ensure the refresh shows the transient failure banner.
3. **Search and filter**
   - Type part of a device name and part of a device code; table rows should filter in real time.
   - Toggle **Show at-risk only** to hide healthy devices and then return to all devices.
4. **Health badges**
   - Provide fixture data with: an offline device, a device with `lastSeen` older than 10 minutes, RSSI ≤ -70 dBm, and an outdated firmware version; ensure each shows the correct issue badge.
   - Confirm healthy devices show the green **Healthy** badge.
5. **Last-seen timing**
   - Confirm the relative time (e.g., `5m ago`) matches the absolute timestamp when hovered/compared.
6. **Terminal launch**
   - Open the terminal for a device and confirm the modal appears and the websocket connects.
7. **Firmware awareness**
   - Upload a firmware release and check that the "Update to <latest>" badge clears when a device reports the new version.

Automate as feasible with component tests by mocking device arrays and asserting rendered badges and filters.
