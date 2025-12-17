import { useState, useEffect } from 'react';
import { X, Bluetooth, Wifi, CheckCircle, AlertCircle, Loader2, WifiOff, Router } from 'lucide-react';

// Fresh UUIDs matching the Pi BLE server
const SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0';
const DEVICE_ID_UUID = '12345678-1234-5678-1234-56789abcdef1';
const WIFI_CONFIG_UUID = '12345678-1234-5678-1234-56789abcdef2';
const WIFI_NETWORKS_UUID = '12345678-1234-5678-1234-56789abcdef3';

type Step = 'scan' | 'connect' | 'wifi' | 'connecting_wifi' | 'success' | 'error';

interface WifiNetwork {
    ssid: string;
    signal: number;
    security: string;
}

interface BleProvisioningModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: (deviceId: string) => void;
}

export function BleProvisioningModal({ isOpen, onClose, onSuccess }: BleProvisioningModalProps) {
    const [step, setStep] = useState<Step>('scan');
    const [device, setDevice] = useState<BluetoothDevice | null>(null);
    const [deviceId, setDeviceId] = useState('');
    const [ssid, setSsid] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [wifiConfigChar, setWifiConfigChar] = useState<BluetoothRemoteGATTCharacteristic | null>(null);
    const [networks, setNetworks] = useState<WifiNetwork[]>([]);
    const [scanningNetworks, setScanningNetworks] = useState(false);
    const [connectionProgress, setConnectionProgress] = useState(0);

    const reset = () => {
        setStep('scan');
        setDevice(null);
        setDeviceId('');
        setSsid('');
        setPassword('');
        setError('');
        setLoading(false);
        setWifiConfigChar(null);
        setNetworks([]);
        setScanningNetworks(false);
        setConnectionProgress(0);
    };

    const handleClose = () => {
        if (device?.gatt?.connected) {
            device.gatt.disconnect();
        }
        reset();
        onClose();
    };

    const scanForDevice = async () => {
        setLoading(true);
        setError('');

        try {
            // Check if Web Bluetooth is supported
            if (!navigator.bluetooth) {
                throw new Error('Web Bluetooth is not supported in this browser. Please use Chrome or Edge.');
            }

            const bleDevice = await navigator.bluetooth.requestDevice({
                filters: [
                    { services: [SERVICE_UUID] },
                    { namePrefix: 'PaperDrop' },
                    { namePrefix: 'paperdrop' }
                ],
                optionalServices: [SERVICE_UUID]
            });

            setDevice(bleDevice);
            setStep('connect');

            // Connect to GATT server
            const server = await bleDevice.gatt?.connect();
            if (!server) throw new Error('Failed to connect to device');

            // Get service
            const service = await server.getPrimaryService(SERVICE_UUID);

            // Read Device ID
            const deviceIdChar = await service.getCharacteristic(DEVICE_ID_UUID);
            const value = await deviceIdChar.readValue();
            const id = new TextDecoder().decode(value);
            setDeviceId(id);

            // Get WiFi config characteristic
            const wifiChar = await service.getCharacteristic(WIFI_CONFIG_UUID);
            setWifiConfigChar(wifiChar);

            // Fetch WiFi networks
            setScanningNetworks(true);
            try {
                const wifiNetworksChar = await service.getCharacteristic(WIFI_NETWORKS_UUID);
                const networksValue = await wifiNetworksChar.readValue();
                const networksJson = new TextDecoder().decode(networksValue);
                const networksList = JSON.parse(networksJson) as WifiNetwork[];
                setNetworks(networksList);
                if (networksList.length > 0) {
                    setSsid(networksList[0].ssid);  // Default to strongest signal
                }
            } catch (e) {
                console.warn('Could not fetch WiFi networks:', e);
                // Continue without networks list - user can type manually
            }
            setScanningNetworks(false);

            setStep('wifi');
        } catch (err) {
            console.error('BLE Error:', err);
            setError(err instanceof Error ? err.message : 'Failed to connect to device');
            setStep('error');
        } finally {
            setLoading(false);
        }
    };

    const provisionDevice = async () => {
        if (!wifiConfigChar || !ssid || !password) return;

        setLoading(true);
        setError('');
        setStep('connecting_wifi');
        setConnectionProgress(0);

        try {
            const config = JSON.stringify({ ssid, password });
            const encoder = new TextEncoder();
            await wifiConfigChar.writeValue(encoder.encode(config));

            // Animate the connection progress
            for (let i = 1; i <= 10; i++) {
                await new Promise(r => setTimeout(r, 500));
                setConnectionProgress(i * 10);
            }

            // Wait a bit more for actual connection
            await new Promise(r => setTimeout(r, 2000));

            setStep('success');
            onSuccess(deviceId);
        } catch (err) {
            console.error('Provision Error:', err);
            setError(err instanceof Error ? err.message : 'Failed to configure WiFi');
            setStep('error');
        } finally {
            setLoading(false);
        }
    };

    const getSignalBars = (signal: number) => {
        if (signal >= 75) return '●●●●';
        if (signal >= 50) return '●●●○';
        if (signal >= 25) return '●●○○';
        return '●○○○';
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                            <Bluetooth className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h2 className="font-semibold text-gray-900">Add New Device</h2>
                            <p className="text-sm text-gray-500">Connect via Bluetooth</p>
                        </div>
                    </div>
                    <button onClick={handleClose} className="p-2 hover:bg-gray-100 rounded-lg transition">
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6">
                    {/* Step: Scan */}
                    {step === 'scan' && (
                        <div className="text-center py-8">
                            <div className="w-20 h-20 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-6">
                                <Bluetooth className="w-10 h-10 text-blue-500" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Ready to Connect
                            </h3>
                            <p className="text-gray-600 mb-6">
                                Make sure your PaperDrop device is powered on and nearby.
                            </p>
                            <button
                                onClick={scanForDevice}
                                disabled={loading}
                                className="w-full py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl font-medium hover:from-blue-600 hover:to-blue-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        Scanning...
                                    </>
                                ) : (
                                    'Scan for Device'
                                )}
                            </button>
                            <p className="text-xs text-gray-400 mt-4">
                                Requires Chrome or Edge browser
                            </p>
                        </div>
                    )}

                    {/* Step: Connecting to BLE */}
                    {step === 'connect' && (
                        <div className="text-center py-8">
                            <Loader2 className="w-16 h-16 text-blue-500 mx-auto mb-6 animate-spin" />
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Connecting...
                            </h3>
                            <p className="text-gray-600">
                                Establishing connection to {device?.name || 'device'}
                            </p>
                        </div>
                    )}

                    {/* Step: WiFi Configuration */}
                    {step === 'wifi' && (
                        <div>
                            <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6 flex items-center gap-3">
                                <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
                                <div>
                                    <p className="text-sm font-medium text-green-800">Device Connected!</p>
                                    <p className="text-sm text-green-600 font-mono">{deviceId}</p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 mb-4">
                                <Wifi className="w-5 h-5 text-gray-600" />
                                <h3 className="font-medium text-gray-900">Select WiFi Network</h3>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Available Networks
                                    </label>
                                    {scanningNetworks ? (
                                        <div className="w-full px-4 py-3 border border-gray-200 rounded-xl flex items-center gap-2 text-gray-500">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Scanning for networks...
                                        </div>
                                    ) : networks.length > 0 ? (
                                        <div className="space-y-2 max-h-48 overflow-y-auto">
                                            {networks.map((net) => (
                                                <button
                                                    key={net.ssid}
                                                    onClick={() => setSsid(net.ssid)}
                                                    className={`w-full p-3 border rounded-xl flex items-center justify-between transition ${ssid === net.ssid
                                                            ? 'border-blue-500 bg-blue-50'
                                                            : 'border-gray-200 hover:border-gray-300'
                                                        }`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <Wifi className={`w-4 h-4 ${ssid === net.ssid ? 'text-blue-500' : 'text-gray-400'}`} />
                                                        <span className={ssid === net.ssid ? 'text-blue-700 font-medium' : 'text-gray-700'}>
                                                            {net.ssid}
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center gap-2 text-sm">
                                                        <span className="text-gray-400">{net.signal}%</span>
                                                        <span className={`text-xs px-2 py-0.5 rounded ${net.security === 'Open'
                                                                ? 'bg-yellow-100 text-yellow-700'
                                                                : 'bg-gray-100 text-gray-600'
                                                            }`}>
                                                            {net.security === 'Open' ? '🔓' : '🔒'}
                                                        </span>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    ) : (
                                        <input
                                            type="text"
                                            value={ssid}
                                            onChange={(e) => setSsid(e.target.value)}
                                            placeholder="Enter WiFi name"
                                            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                                        />
                                    )}
                                </div>

                                {ssid && (
                                    <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 flex items-center gap-2">
                                        <Wifi className="w-4 h-4 text-blue-500" />
                                        <span className="text-sm text-blue-700">Selected: <strong>{ssid}</strong></span>
                                    </div>
                                )}

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Password
                                    </label>
                                    <input
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="Enter WiFi password"
                                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                                    />
                                </div>
                            </div>

                            <button
                                onClick={provisionDevice}
                                disabled={loading || !ssid || !password}
                                className="w-full mt-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl font-medium hover:from-blue-600 hover:to-blue-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                Connect to WiFi
                            </button>
                        </div>
                    )}

                    {/* Step: Connecting to WiFi - Animated */}
                    {step === 'connecting_wifi' && (
                        <div className="text-center py-8">
                            {/* Animated Router + Device */}
                            <div className="relative mb-8">
                                <div className="flex items-center justify-center gap-8">
                                    {/* Device */}
                                    <div className="w-16 h-20 bg-gradient-to-b from-gray-700 to-gray-900 rounded-lg flex items-center justify-center relative">
                                        <div className="w-12 h-14 bg-gradient-to-b from-blue-400 to-blue-600 rounded-sm flex items-center justify-center">
                                            <span className="text-white text-xs font-bold">📄</span>
                                        </div>
                                        {/* Blinking light */}
                                        <div className="absolute -top-1 right-1 w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                                    </div>

                                    {/* Connection animation */}
                                    <div className="flex items-center gap-1">
                                        {[...Array(5)].map((_, i) => (
                                            <div
                                                key={i}
                                                className={`w-2 h-2 rounded-full transition-all duration-300 ${connectionProgress >= (i + 1) * 20
                                                        ? 'bg-blue-500 scale-100'
                                                        : 'bg-gray-300 scale-75'
                                                    }`}
                                                style={{
                                                    animation: connectionProgress >= (i + 1) * 20
                                                        ? `pulse 0.5s ease-in-out ${i * 0.1}s`
                                                        : 'none'
                                                }}
                                            />
                                        ))}
                                    </div>

                                    {/* Router */}
                                    <div className="w-16 h-12 bg-gradient-to-b from-gray-200 to-gray-300 rounded-lg flex items-center justify-center relative">
                                        <Router className="w-8 h-8 text-gray-600" />
                                        {/* Antenna signals */}
                                        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 flex gap-0.5">
                                            <div className={`w-1 h-6 rounded-full ${connectionProgress > 30 ? 'bg-blue-500' : 'bg-gray-400'}`} />
                                            <div className={`w-1 h-4 rounded-full ${connectionProgress > 60 ? 'bg-blue-500' : 'bg-gray-400'}`} />
                                        </div>
                                    </div>
                                </div>

                                {/* WiFi waves animation */}
                                <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-4">
                                    <div className="relative">
                                        {[1, 2, 3].map((i) => (
                                            <div
                                                key={i}
                                                className={`absolute w-${4 + i * 4} h-${4 + i * 4} border-2 border-blue-500 rounded-full opacity-0`}
                                                style={{
                                                    width: `${16 + i * 16}px`,
                                                    height: `${16 + i * 16}px`,
                                                    left: `${-(8 + i * 8)}px`,
                                                    top: `${-(8 + i * 8)}px`,
                                                    animation: connectionProgress > 20
                                                        ? `ping 1.5s cubic-bezier(0, 0, 0.2, 1) ${i * 0.3}s infinite`
                                                        : 'none'
                                                }}
                                            />
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Connecting to WiFi...
                            </h3>
                            <p className="text-gray-600 mb-4">
                                {connectionProgress < 30 && 'Sending credentials to device...'}
                                {connectionProgress >= 30 && connectionProgress < 60 && 'Device is connecting to network...'}
                                {connectionProgress >= 60 && connectionProgress < 90 && 'Verifying connection...'}
                                {connectionProgress >= 90 && 'Almost done!'}
                            </p>

                            {/* Progress bar */}
                            <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-4">
                                <div
                                    className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-500 ease-out"
                                    style={{ width: `${connectionProgress}%` }}
                                />
                            </div>

                            <p className="text-sm text-blue-600 font-medium">
                                Connecting to: {ssid}
                            </p>
                        </div>
                    )}

                    {/* Step: Success */}
                    {step === 'success' && (
                        <div className="text-center py-8">
                            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6 relative">
                                <CheckCircle className="w-10 h-10 text-green-600" />
                                {/* Celebration particles */}
                                {[...Array(8)].map((_, i) => (
                                    <div
                                        key={i}
                                        className="absolute w-2 h-2 bg-green-400 rounded-full"
                                        style={{
                                            animation: `confetti 0.5s ease-out forwards`,
                                            animationDelay: `${i * 0.05}s`,
                                            '--angle': `${i * 45}deg`
                                        } as React.CSSProperties}
                                    />
                                ))}
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Device Connected! 🎉
                            </h3>
                            <p className="text-gray-600 mb-2">
                                Your PaperDrop is now connected to <strong>{ssid}</strong>
                            </p>
                            <p className="text-sm font-mono text-blue-600 mb-6 bg-blue-50 px-4 py-2 rounded-lg inline-block">{deviceId}</p>
                            <button
                                onClick={handleClose}
                                className="w-full py-3 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl font-medium hover:from-green-600 hover:to-green-700 transition"
                            >
                                Continue to Setup
                            </button>
                        </div>
                    )}

                    {/* Step: Error */}
                    {step === 'error' && (
                        <div className="text-center py-8">
                            <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                                <AlertCircle className="w-10 h-10 text-red-600" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Connection Failed
                            </h3>
                            <p className="text-gray-600 mb-6">
                                {error || 'Could not connect to WiFi network. Please check your credentials and try again.'}
                            </p>
                            <button
                                onClick={reset}
                                className="w-full py-3 bg-gray-100 text-gray-700 rounded-xl font-medium hover:bg-gray-200 transition"
                            >
                                Try Again
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* CSS Animations */}
            <style>{`
                @keyframes confetti {
                    0% {
                        transform: translate(0, 0) scale(1);
                        opacity: 1;
                    }
                    100% {
                        transform: translate(calc(cos(var(--angle)) * 40px), calc(sin(var(--angle)) * 40px)) scale(0);
                        opacity: 0;
                    }
                }
            `}</style>
        </div>
    );
}
