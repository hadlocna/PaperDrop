# PI-side follow-up for fleet insights

The UI now highlights connectivity risks (offline/stale heartbeat), weak Wi-Fi, and firmware lag. To keep those signals accurate and actionable when connected to the devices, apply the following on each PI/agent build:

1. **Heartbeat freshness**
   - Emit a heartbeat at least once per minute that updates the `lastSeen` timestamp in the backend API.
   - Include a monotonic clock or boot ID to avoid time skew issues after reboots.
2. **Wi-Fi diagnostics**
   - Attach current RSSI (e.g., `iwconfig`/`iw` output) to each heartbeat payload as `wifiSignal` in dBm.
   - Optionally send SSID/BSSID so support can spot roaming or mismatched networks.
3. **Firmware version reporting**
   - Ensure the agent reports its running firmware/app version string (`firmwareVersion`) on every heartbeat.
   - After an update, send an immediate heartbeat so the dashboard clears the "Update to <latest>" issue quickly.
4. **Optional deep-health metrics** (nice-to-have for future UI badges)
   - CPU temp/load and free disk space to preempt thermal or storage issues.
   - Recent error codes from printer/USB subsystems that could block jobs.
5. **Connectivity recovery hooks**
   - Add a lightweight connectivity self-check (ping gateway/DNS) and report failures so support can see whether offline devices are power vs. network related.

Document any new payload fields in the admin API so the dashboard can surface them consistently.
