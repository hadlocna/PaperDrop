import { CaptureStatus } from './publicNetwork';
import { latestDeviceActivity } from './deviceActivity';
type RelayDevice = {
    code: string;
    status?: string;
    lastSeen?: string | null;
    lastHeartbeat?: string | null;
    wifiSignal?: number | null;
    firmwareVersion?: string | null;
    publicNetwork?: unknown;
    publicNetworkDiagnostic?: { localCapture?: { status: CaptureStatus; observedAt: string } | null };
};

const relayBaseUrl = () => process.env.DEVICE_RELAY_URL?.replace(/\/$/, '');

const relayHeaders = () => ({
    'Content-Type': 'application/json',
    'x-admin-password': process.env.DEVICE_RELAY_ADMIN_PASSWORD || process.env.ADMIN_PASSWORD || 'nathan'
});

const withTimeout = async <T>(promise: Promise<T>, timeoutMs: number): Promise<T> => {
    let timer: NodeJS.Timeout | undefined;
    const timeout = new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error('Relay request timed out')), timeoutMs);
    });

    try {
        return await Promise.race([promise, timeout]);
    } finally {
        if (timer) clearTimeout(timer);
    }
};

export const relayEnabled = () => Boolean(relayBaseUrl());

export const relayMessageToDevice = async (deviceId: string, payload: any): Promise<boolean> => {
    const baseUrl = relayBaseUrl();
    if (!baseUrl) return false;

    try {
        const response = await withTimeout(
            fetch(`${baseUrl}/api/admin/relay-message`, {
                method: 'POST',
                headers: relayHeaders(),
                body: JSON.stringify({ deviceId, payload })
            }),
            5000
        );

        if (!response.ok) return false;
        const body = await response.json();
        return body.sent === true;
    } catch (error) {
        console.warn('Device relay message failed:', error);
        return false;
    }
};

export const fetchRelayDeviceStatuses = async (): Promise<Map<string, RelayDevice>> => {
    const baseUrl = relayBaseUrl();
    if (!baseUrl) return new Map();

    try {
        const response = await withTimeout(
            fetch(`${baseUrl}/api/admin/devices`, {
                headers: relayHeaders()
            }),
            5000
        );

        if (!response.ok) return new Map();

        const devices = await response.json() as RelayDevice[];
        return new Map(devices.map((device) => {
            const capture = device.publicNetworkDiagnostic?.localCapture;
            const allowed = ['observed', 'missing_peer', 'untrusted_non_public_peer', 'trusted_proxy_without_public_client'];
            const age = capture ? Date.now() - Date.parse(capture.observedAt) : NaN;
            if (device.publicNetworkDiagnostic) device.publicNetworkDiagnostic = {
                localCapture: capture && allowed.includes(capture.status) && age >= 0 && age < 15 * 60 * 1000
                    ? { status: capture.status, observedAt: new Date(capture.observedAt).toISOString() } : null
            };
            return [device.code, device];
        }));
    } catch (error) {
        console.warn('Device relay status fetch failed:', error);
        return new Map();
    }
};

export const relayLastActive = (device?: RelayDevice): Date | null => {
    return latestDeviceActivity(device?.lastHeartbeat, device?.lastSeen);
};

export const relayIsOnline = (device?: RelayDevice): boolean => {
    if (!device) return false;
    const lastActive = relayLastActive(device);
    return device.status === 'online' || Boolean(lastActive && Date.now() - lastActive.getTime() < 60000);
};
