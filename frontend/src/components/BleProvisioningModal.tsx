import { useState } from 'react';
import { X, Bluetooth, Wifi, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

// Fresh UUIDs matching the Pi BLE server
const SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0';
const DEVICE_ID_UUID = '12345678-1234-5678-1234-56789abcdef1';
const WIFI_CONFIG_UUID = '12345678-1234-5678-1234-56789abcdef2';

type Step = 'scan' | 'connect' | 'wifi' | 'success' | 'error';

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

    const reset = () => {
        setStep('scan');
        setDevice(null);
        setDeviceId('');
        setSsid('');
        setPassword('');
        setError('');
        setLoading(false);
        setWifiConfigChar(null);
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

        try {
            const config = JSON.stringify({ ssid, password });
            const encoder = new TextEncoder();
            await wifiConfigChar.writeValue(encoder.encode(config));

            // Wait for device to connect
            await new Promise(r => setTimeout(r, 3000));

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

                    {/* Step: Connecting */}
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
                                    <p className="text-sm font-medium text-green-800">Connected!</p>
                                    <p className="text-sm text-green-600 font-mono">{deviceId}</p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 mb-4">
                                <Wifi className="w-5 h-5 text-gray-600" />
                                <h3 className="font-medium text-gray-900">WiFi Configuration</h3>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Network Name (SSID)
                                    </label>
                                    <input
                                        type="text"
                                        value={ssid}
                                        onChange={(e) => setSsid(e.target.value)}
                                        placeholder="Enter WiFi name"
                                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                                    />
                                </div>
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
                                {loading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        Connecting...
                                    </>
                                ) : (
                                    'Connect to WiFi'
                                )}
                            </button>
                        </div>
                    )}

                    {/* Step: Success */}
                    {step === 'success' && (
                        <div className="text-center py-8">
                            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                                <CheckCircle className="w-10 h-10 text-green-600" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Setup Complete!
                            </h3>
                            <p className="text-gray-600 mb-2">
                                Your device is now connected to WiFi.
                            </p>
                            <p className="text-sm font-mono text-blue-600 mb-6">{deviceId}</p>
                            <button
                                onClick={handleClose}
                                className="w-full py-3 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl font-medium hover:from-green-600 hover:to-green-700 transition"
                            >
                                Done
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
                                Something went wrong
                            </h3>
                            <p className="text-gray-600 mb-6">
                                {error || 'Failed to connect to device'}
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
        </div>
    );
}
