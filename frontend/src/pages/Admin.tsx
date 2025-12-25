import { useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '../components/Layout';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { Terminal as TerminalIcon, Power, Wifi, WifiOff, Package, Upload, Rocket, Trash2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || '';
const WS_BASE = API_BASE.replace('http', 'ws');

interface Device {
    id: string;
    code: string;
    status: string;
    name: string;
    mac?: string;
    lastSeen: string;
    wifiSignal?: number;
    firmwareVersion?: string;
    owner: string | null;
}

interface FirmwareRelease {
    id: string;
    version: string;
    url: string;
    description?: string;
    isCritical: boolean;
    createdAt: string;
}

interface User {
    id: string;
    email: string;
    name: string;
    createdAt: string;
    _count: {
        devices: number;
        deviceAccess: number;
    }
}

export function Admin() {
    const [password, setPassword] = useState('');
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [devices, setDevices] = useState<Device[]>([]);
    const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
    const [error, setError] = useState('');
    const [activeTab, setActiveTab] = useState<'devices' | 'firmware' | 'users'>('devices');
    const [firmwareReleases, setFirmwareReleases] = useState<FirmwareRelease[]>([]);
    const [users, setUsers] = useState<User[]>([]);
    const [deployStatus, setDeployStatus] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [attentionOnly, setAttentionOnly] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [assigningTo, setAssigningTo] = useState<string | null>(null);

    const termRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const xtermRef = useRef<Terminal | null>(null);

    // Check localStorage for persisted session
    useEffect(() => {
        const savedPass = localStorage.getItem('admin_pass');
        if (savedPass) {
            verifyPassword(savedPass);
        }
    }, []);

    const loadDevices = async (pass: string, { quietError }: { quietError?: boolean } = {}) => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/devices`, {
                headers: { 'x-admin-password': pass }
            });
            if (res.ok) {
                const data = await res.json();
                setDevices(data);
                setError('');
                return true;
            } else {
                if (!quietError) {
                    setError('Invalid password');
                }
                localStorage.removeItem('admin_pass');
            }
        } catch (e) {
            if (!quietError) {
                setError('Connection error');
            }
        }
        return false;
    };

    const verifyPassword = async (pass: string) => {
        const ok = await loadDevices(pass);
        if (ok) {
            setIsAuthenticated(true);
            setPassword(pass);
            localStorage.setItem('admin_pass', pass);
            // Also load firmware and users
            loadFirmware(pass);
            loadUsers(pass);
        }
    };

    const loadUsers = async (pass: string) => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/users`, {
                headers: { 'x-admin-password': pass }
            });
            if (res.ok) {
                setUsers(await res.json());
            }
        } catch (e) {
            console.error('Failed to load users:', e);
        }
    };

    const loadFirmware = async (pass: string) => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/firmware`, {
                headers: { 'x-admin-password': pass }
            });
            if (res.ok) {
                setFirmwareReleases(await res.json());
            }
        } catch (e) {
            console.error('Failed to load firmware:', e);
        }
    };



    const deployFirmware = async (deviceId: string, version: string) => {
        try {
            setDeployStatus(`Deploying ${version} to ${deviceId}...`);
            const res = await fetch(`${API_BASE}/api/admin/firmware/deploy`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-admin-password': password
                },
                body: JSON.stringify({ deviceId, version })
            });
            const data = await res.json();
            setDeployStatus(data.message || 'Deploy sent');
            setTimeout(() => setDeployStatus(''), 3000);
        } catch (e) {
            setDeployStatus('Deploy failed');
        }
    };

    const unprovisionDevice = async (deviceId: string) => {
        if (!confirm('Are you sure you want to unprovision this device? It will be permanently deleted from the database.')) return;
        try {
            const res = await fetch(`${API_BASE}/api/admin/devices/${deviceId}`, {
                method: 'DELETE',
                headers: { 'x-admin-password': password }
            });
            if (res.ok) {
                setDeployStatus('Device unprovisioned');
                refreshDevices();
                setTimeout(() => setDeployStatus(''), 3000);
            } else {
                setDeployStatus('Failed to unprovision device');
            }
        } catch (e) {
            setDeployStatus('Error unprovisioning device');
        }
    };

    const assignDevice = async (deviceId: string, email: string, role: string) => {
        try {
            setDeployStatus(`Assigning device to ${email}...`);
            const res = await fetch(`${API_BASE}/api/admin/devices/${deviceId}/assign`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-admin-password': password
                },
                body: JSON.stringify({ email, role })
            });
            if (res.ok) {
                setDeployStatus('Device assigned successfully');
                refreshDevices();
                loadUsers(password);
                setAssigningTo(null);
                setTimeout(() => setDeployStatus(''), 3000);
            } else {
                const data = await res.json();
                setDeployStatus(data.error || 'Assignment failed');
            }
        } catch (e) {
            setDeployStatus('Assignment failed');
        }
    };

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault();
        verifyPassword(password);
    };

    const refreshDevices = async () => {
        if (!password) return;
        setIsRefreshing(true);
        const ok = await loadDevices(password, { quietError: true });
        if (!ok) {
            setDeployStatus('Refresh failed. Please re-authenticate.');
            setTimeout(() => setDeployStatus(''), 3000);
        }
        setIsRefreshing(false);
    };

    const getRelativeTime = (timestamp: string) => {
        const diff = Date.now() - new Date(timestamp).getTime();
        const minutes = Math.floor(diff / 60000);
        if (minutes < 1) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    };

    const latestFirmwareVersion = useMemo(() => {
        if (!firmwareReleases.length) return '';
        const newest = firmwareReleases.reduce((latest, current) => {
            return new Date(current.createdAt) > new Date(latest.createdAt) ? current : latest;
        }, firmwareReleases[0]);
        return newest.version;
    }, [firmwareReleases]);

    const getIssues = (device: Device) => {
        const issues: string[] = [];
        const lastSeenDate = new Date(device.lastSeen);
        const minutesSinceSeen = (Date.now() - lastSeenDate.getTime()) / 60000;

        if (device.status !== 'online') {
            issues.push('Offline');
        } else if (minutesSinceSeen > 10) {
            issues.push('Stale heartbeat (>10m)');
        }

        if (device.wifiSignal && device.wifiSignal <= -70) {
            issues.push('Weak Wi-Fi');
        }

        if (latestFirmwareVersion && device.firmwareVersion && device.firmwareVersion !== latestFirmwareVersion) {
            issues.push(`Update to ${latestFirmwareVersion}`);
        }

        return issues;
    };

    const filteredDevices = useMemo(() => {
        const bySearch = devices.filter(device =>
            device.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            device.code.toLowerCase().includes(searchTerm.toLowerCase())
        );

        const byAttention = attentionOnly
            ? bySearch.filter(device => getIssues(device).length > 0)
            : bySearch;

        return byAttention.sort((a, b) => getIssues(b).length - getIssues(a).length);
    }, [devices, searchTerm, attentionOnly, firmwareReleases]);

    // Terminal Logic
    useEffect(() => {
        if (!selectedDevice || !termRef.current) return;

        const term = new Terminal({
            cursorBlink: true,
            theme: {
                background: '#1e1e1e',
                foreground: '#ffffff'
            }
        });
        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);

        term.open(termRef.current);
        fitAddon.fit();
        xtermRef.current = term;

        // Connect WebSocket
        const ws = new WebSocket(`${WS_BASE}/api/admin/connect?password=${password}`);
        wsRef.current = ws;

        ws.onopen = () => {
            term.write('\r\n\x1b[32mConnected to Admin Relay...\x1b[0m\r\n');
            // Request Shell
            ws.send(JSON.stringify({
                type: 'start_shell',
                deviceId: selectedDevice.id
            }));

            // Send initial resize
            ws.send(JSON.stringify({
                type: 'resize_shell',
                deviceId: selectedDevice.id,
                payload: { cols: term.cols, rows: term.rows }
            }));
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'shell_output' && msg.deviceId === selectedDevice.id) {
                    term.write(msg.data);
                } else if (msg.type === 'error') {
                    term.write(`\r\n\x1b[31mError: ${msg.message}\x1b[0m\r\n`);
                }
            } catch (e) {
                console.error(e);
            }
        };

        ws.onclose = () => {
            term.write('\r\n\x1b[31mConnection Closed\x1b[0m\r\n');
        };

        term.onData(data => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'shell_input',
                    deviceId: selectedDevice.id,
                    payload: data
                }));
            }
        });

        // Handle Resize
        const handleResize = () => {
            fitAddon.fit();
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'resize_shell',
                    deviceId: selectedDevice.id,
                    payload: { cols: term.cols, rows: term.rows }
                }));
            }
        };
        window.addEventListener('resize', handleResize);

        return () => {
            ws.close();
            term.dispose();
            window.removeEventListener('resize', handleResize);
        };
    }, [selectedDevice]);

    if (!isAuthenticated) {
        return (
            <Layout>
                <div className="max-w-md mx-auto mt-20 p-8 bg-white rounded-2xl shadow-xl">
                    <h1 className="text-2xl font-bold mb-6 text-center">Admin Access</h1>
                    <form onSubmit={handleLogin}>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            className="w-full p-3 border rounded-xl mb-4"
                            placeholder="Enter Password"
                        />
                        {error && <p className="text-red-500 mb-4 text-sm">{error}</p>}
                        <button className="w-full bg-slate-800 text-white p-3 rounded-xl font-bold">
                            Login
                        </button>
                    </form>
                </div>
            </Layout>
        );
    }

    const getSignalColor = (rssi?: number) => {
        if (!rssi) return 'text-gray-400';
        if (rssi > -60) return 'text-green-500';
        if (rssi > -75) return 'text-yellow-500';
        return 'text-red-500';
    };

    return (
        <Layout>
            <div className="max-w-6xl mx-auto mt-10 p-6">
                <div className="flex justify-between items-center mb-8">
                    <div className="flex items-center gap-4">
                        <h1 className="text-3xl font-bold text-slate-800">Fleet Manager</h1>
                        <div className="flex bg-slate-100 rounded-lg p-1">
                            <button
                                onClick={() => setActiveTab('devices')}
                                className={`px-4 py-2 rounded-lg font-medium transition-colors ${activeTab === 'devices' ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
                            >
                                Devices
                            </button>
                            <button
                                onClick={() => setActiveTab('firmware')}
                                className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${activeTab === 'firmware' ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
                            >
                                <Package size={16} />
                                Firmware
                            </button>
                            <button
                                onClick={() => setActiveTab('users')}
                                className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${activeTab === 'users' ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
                            >
                                <TerminalIcon size={16} />
                                Users
                            </button>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={refreshDevices}
                            disabled={isRefreshing}
                            className={`px-4 py-2 rounded-lg font-medium border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 transition ${isRefreshing ? 'opacity-60 cursor-not-allowed' : ''}`}
                        >
                            {isRefreshing ? 'Refreshing...' : 'Refresh devices'}
                        </button>
                        <button
                            onClick={() => { localStorage.removeItem('admin_pass'); setIsAuthenticated(false); }}
                            className="text-red-500 hover:text-red-700 font-medium"
                        >
                            Logout
                        </button>
                    </div>
                </div>

                {activeTab === 'devices' && (
                    <div className="mb-6 space-y-3">
                        <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
                            <div className="flex items-center gap-2 w-full md:w-auto">
                                <input
                                    type="text"
                                    value={searchTerm}
                                    onChange={e => setSearchTerm(e.target.value)}
                                    placeholder="Search by name or code"
                                    className="w-full md:w-64 p-3 border rounded-xl"
                                />
                                <button
                                    onClick={() => setAttentionOnly(v => !v)}
                                    className={`px-4 py-2 rounded-xl font-medium border transition ${attentionOnly ? 'bg-amber-50 border-amber-200 text-amber-700' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}`}
                                >
                                    {attentionOnly ? 'Show all devices' : 'Show at-risk only'}
                                </button>
                            </div>
                            <div className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-xl p-3">
                                Flags devices that are offline, have heartbeats older than 10 minutes, Wi-Fi weaker than -70 dBm, or are behind the latest firmware{latestFirmwareVersion ? ` (v${latestFirmwareVersion})` : ''}.
                            </div>
                        </div>
                    </div>
                )}

                {deployStatus && (
                    <div className="mb-4 p-3 bg-blue-100 text-blue-800 rounded-lg flex items-center gap-2">
                        <Rocket size={16} /> {deployStatus}
                    </div>
                )}

                {activeTab === 'firmware' && (
                    <div className="space-y-6">
                        {/* New Firmware Form */}
                        <div className="bg-white rounded-2xl shadow-lg p-6">
                            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                                <Upload size={20} /> Upload Firmware Release
                            </h2>
                            <form onSubmit={async (e) => {
                                e.preventDefault();
                                const form = e.target as HTMLFormElement;
                                const formData = new FormData(form);
                                try {
                                    const res = await fetch(`${API_BASE}/api/admin/firmware/upload`, {
                                        method: 'POST',
                                        headers: { 'x-admin-password': password },
                                        body: formData
                                    });
                                    if (res.ok) {
                                        form.reset();
                                        loadFirmware(password);
                                        setDeployStatus('Firmware uploaded!');
                                        setTimeout(() => setDeployStatus(''), 3000);
                                    }
                                } catch (err) {
                                    setDeployStatus('Upload failed');
                                }
                            }} className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                <input
                                    type="text"
                                    name="version"
                                    placeholder="Version (e.g. 1.1.0)"
                                    className="p-3 border rounded-xl"
                                    required
                                />
                                <input
                                    type="file"
                                    name="file"
                                    accept=".tar.gz,.tgz"
                                    className="p-3 border rounded-xl"
                                    required
                                />
                                <input
                                    type="text"
                                    name="description"
                                    placeholder="Description"
                                    className="p-3 border rounded-xl"
                                />
                                <button
                                    type="submit"
                                    className="bg-slate-800 hover:bg-slate-700 text-white px-6 py-3 rounded-xl font-medium"
                                >
                                    Upload
                                </button>
                            </form>
                        </div>

                        {/* Firmware Releases List */}
                        <div className="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-x-auto">
                            <table className="w-full min-w-[700px]">
                                <thead className="bg-slate-50/50 border-b border-slate-100">
                                    <tr>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Version</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">URL</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Description</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Created</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {firmwareReleases.map(fw => (
                                        <tr key={fw.id} className="border-b hover:bg-slate-50">
                                            <td className="p-4 font-mono font-bold">{fw.version}</td>
                                            <td className="p-4 text-sm text-gray-500 truncate max-w-xs">{fw.url}</td>
                                            <td className="p-4 text-sm">{fw.description || '-'}</td>
                                            <td className="p-4 text-sm text-gray-500">{new Date(fw.createdAt).toLocaleDateString()}</td>
                                            <td className="p-4">
                                                <select
                                                    onChange={e => e.target.value && deployFirmware(e.target.value, fw.version)}
                                                    className="p-2 border rounded-lg text-sm"
                                                    defaultValue=""
                                                >
                                                    <option value="">Deploy to...</option>
                                                    {devices.filter(d => d.status === 'online').map(d => (
                                                        <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                                                    ))}
                                                </select>
                                            </td>
                                        </tr>
                                    ))}
                                    {firmwareReleases.length === 0 && (
                                        <tr><td colSpan={5} className="p-8 text-center text-gray-400">No firmware releases yet</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'users' && (
                    <div className="space-y-6">
                        <div className="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-x-auto">
                            <table className="w-full min-w-[800px]">
                                <thead className="bg-slate-50/50 border-b border-slate-100">
                                    <tr>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Name</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Email</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Devices Owned</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Shared Access</th>
                                        <th className="p-4 text-left text-sm font-semibold text-slate-500">Created</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr key={user.id} className="border-b hover:bg-slate-50">
                                            <td className="p-4 font-bold">{user.name}</td>
                                            <td className="p-4 text-sm text-gray-500">{user.email}</td>
                                            <td className="p-4 text-sm">{user._count.devices}</td>
                                            <td className="p-4 text-sm">{user._count.deviceAccess}</td>
                                            <td className="p-4 text-sm text-gray-500">{new Date(user.createdAt).toLocaleDateString()}</td>
                                        </tr>
                                    ))}
                                    {users.length === 0 && (
                                        <tr><td colSpan={5} className="p-8 text-center text-gray-400">No users found</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'devices' && (
                    <div className="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-x-auto">
                        <table className="w-full min-w-[1100px] border-collapse">
                            <thead className="bg-slate-50/50 border-b border-slate-100">
                                <tr>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider w-32">Status</th>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Device</th>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider w-32">Signal</th>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider w-24">Firmware</th>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Owner</th>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider w-40">Last Seen</th>
                                    <th className="p-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Issues</th>
                                    <th className="p-4 text-right text-xs font-bold text-slate-400 uppercase tracking-wider w-48 pr-6">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredDevices.map(device => {
                                    const issues = getIssues(device);
                                    return (
                                        <tr key={device.id} className="border-b hover:bg-slate-50">
                                            <td className="p-4">
                                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${device.status === 'online' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                                    }`}>
                                                    {device.status === 'online' ? <Wifi size={14} className="mr-1" /> : <WifiOff size={14} className="mr-1" />}
                                                    {device.status}
                                                </span>
                                            </td>
                                            <td className="p-4">
                                                <div className="font-medium flex items-center gap-2">
                                                    {device.name}
                                                    {device.code.startsWith('TEST') && (
                                                        <span className="bg-amber-100 text-amber-800 text-xs px-1.5 py-0.5 rounded border border-amber-200">
                                                            DUMMY
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="text-xs text-gray-500 font-mono">{device.code}</div>
                                            </td>
                                            <td className="p-4">
                                                <div className={`flex items-center gap-1 font-mono text-sm ${getSignalColor(device.wifiSignal)}`}>
                                                    <Wifi size={16} />
                                                    {device.wifiSignal ? `${device.wifiSignal} dBm` : '-'}
                                                </div>
                                            </td>
                                            <td className="p-4 text-sm font-mono text-gray-600">
                                                {device.firmwareVersion || 'v1.0.0'}
                                            </td>
                                            <td className="p-4 text-sm text-gray-600">
                                                {device.owner || <span className="text-orange-400 italic">Unclaimed</span>}
                                            </td>
                                            <td className="p-4 text-sm text-gray-500">
                                                <div className="font-medium text-slate-700">{getRelativeTime(device.lastSeen)}</div>
                                                <div className="text-xs text-gray-400">{new Date(device.lastSeen).toLocaleString()}</div>
                                            </td>
                                            <td className="p-4">
                                                <div className="flex flex-wrap gap-2">
                                                    {issues.length === 0 && (
                                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-100">
                                                            Healthy
                                                        </span>
                                                    )}
                                                    {issues.map(issue => (
                                                        <span key={issue} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-100">
                                                            {issue}
                                                        </span>
                                                    ))}
                                                </div>
                                            </td>
                                            <td className="p-4 pr-6">
                                                <div className="flex items-center justify-end gap-2">
                                                    <button
                                                        onClick={() => setSelectedDevice(device)}
                                                        className="bg-slate-800 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2"
                                                    >
                                                        <TerminalIcon size={16} />
                                                        Terminal
                                                    </button>
                                                    <div className="relative group">
                                                        <button
                                                            onClick={() => setAssigningTo(assigningTo === device.id ? null : device.id)}
                                                            className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2"
                                                        >
                                                            Assign
                                                        </button>
                                                        {assigningTo === device.id && (
                                                            <div className="absolute right-0 mt-2 w-72 bg-white border border-slate-200 rounded-xl shadow-2xl z-20 p-5 animate-in fade-in zoom-in-95 duration-200">
                                                                <h4 className="text-sm font-bold mb-3 text-slate-800">Assign Printer to User</h4>
                                                                <div className="space-y-4">
                                                                    <div>
                                                                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 block">User Email</label>
                                                                        <input
                                                                            type="email"
                                                                            id="assign-email"
                                                                            placeholder="user@example.com"
                                                                            className="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-slate-800 outline-none"
                                                                            onKeyDown={(e) => {
                                                                                if (e.key === 'Enter') {
                                                                                    const input = e.currentTarget as HTMLInputElement;
                                                                                    assignDevice(device.id, input.value, 'owner');
                                                                                }
                                                                            }}
                                                                        />
                                                                    </div>

                                                                    <div className="grid grid-cols-2 gap-2">
                                                                        <button
                                                                            onClick={() => {
                                                                                const email = (document.getElementById('assign-email') as HTMLInputElement).value;
                                                                                if (email) assignDevice(device.id, email, 'owner');
                                                                            }}
                                                                            className="bg-slate-800 text-white text-xs font-bold py-2.5 rounded-lg hover:bg-slate-700 transition shadow-sm"
                                                                        >
                                                                            Make Owner
                                                                        </button>
                                                                        <button
                                                                            onClick={() => {
                                                                                const email = (document.getElementById('assign-email') as HTMLInputElement).value;
                                                                                if (email) assignDevice(device.id, email, 'sender');
                                                                            }}
                                                                            className="bg-white border border-slate-200 text-slate-700 text-xs font-bold py-2.5 rounded-lg hover:bg-slate-50 transition shadow-sm"
                                                                        >
                                                                            Add as Sender
                                                                        </button>
                                                                    </div>

                                                                    <hr className="border-slate-100" />

                                                                    <div>
                                                                        <p className="text-[10px] text-slate-400 mb-2">Quick Pick From Recent Users:</p>
                                                                        <div className="max-h-32 overflow-y-auto space-y-1">
                                                                            {users.slice(0, 5).map(u => (
                                                                                <button
                                                                                    key={u.id}
                                                                                    onClick={() => assignDevice(device.id, u.email, 'sender')}
                                                                                    className="w-full text-left text-xs p-2 rounded-lg hover:bg-slate-50 text-slate-600 truncate transition border border-transparent hover:border-slate-100"
                                                                                    title={u.email}
                                                                                >
                                                                                    {u.name} ({u.email})
                                                                                </button>
                                                                            ))}
                                                                        </div>
                                                                    </div>

                                                                    <button
                                                                        onClick={() => setAssigningTo(null)}
                                                                        className="w-full text-xs text-slate-400 hover:text-slate-600 pt-1"
                                                                    >
                                                                        Cancel
                                                                        ```
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                    <button
                                                        onClick={() => unprovisionDevice(device.id)}
                                                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
                                                        title="Unprovision Device"
                                                    >
                                                        <Trash2 size={18} />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                                {filteredDevices.length === 0 && (
                                    <tr><td colSpan={8} className="p-8 text-center text-gray-400">No devices match your filters</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Terminal Modal */}
            {
                selectedDevice && (
                    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                        <div className="bg-slate-900 w-full max-w-4xl rounded-2xl overflow-hidden shadow-2xl border border-slate-700 flex flex-col h-[600px]">
                            <div className="bg-slate-800 p-4 flex justify-between items-center border-b border-slate-700">
                                <div className="flex items-center gap-2">
                                    <TerminalIcon className="text-green-400" size={20} />
                                    <span className="text-white font-mono font-bold">root@{selectedDevice.code} ~</span>
                                </div>
                                <button
                                    onClick={() => setSelectedDevice(null)}
                                    className="text-slate-400 hover:text-white transition-colors"
                                >
                                    <Power size={20} />
                                </button>
                            </div>
                            <div className="flex-1 p-4 bg-[#1e1e1e] overflow-hidden">
                                <div ref={termRef} className="h-full w-full" />
                            </div>
                        </div>
                    </div>
                )
            }
        </Layout >
    );
}
