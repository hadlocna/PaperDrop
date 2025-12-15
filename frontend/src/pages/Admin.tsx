import { useEffect, useRef, useState } from 'react';
import { Layout } from '../components/Layout';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { Terminal as TerminalIcon, Power, Wifi, WifiOff } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || '';
const WS_BASE = API_BASE.replace('http', 'ws');

interface Device {
    id: string;
    code: string;
    status: string;
    name: string;
    lastSeen: string;
    owner: string | null;
}

export function Admin() {
    const [password, setPassword] = useState('');
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [devices, setDevices] = useState<Device[]>([]);
    const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
    const [error, setError] = useState('');

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

    const verifyPassword = async (pass: string) => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/devices`, {
                headers: { 'x-admin-password': pass }
            });
            if (res.ok) {
                const data = await res.json();
                setDevices(data);
                setIsAuthenticated(true);
                setPassword(pass);
                localStorage.setItem('admin_pass', pass);
            } else {
                setError('Invalid password');
                localStorage.removeItem('admin_pass');
            }
        } catch (e) {
            setError('Connection error');
        }
    };

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault();
        verifyPassword(password);
    };

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

    return (
        <Layout>
            <div className="max-w-6xl mx-auto mt-10 p-6">
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-3xl font-bold text-slate-800">Device Monitor</h1>
                    <button
                        onClick={() => { localStorage.removeItem('admin_pass'); setIsAuthenticated(false); }}
                        className="text-red-500 hover:text-red-700 font-medium"
                    >
                        Logout
                    </button>
                </div>

                <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
                    <table className="w-full">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="p-4 text-left text-sm font-semibold text-slate-500">Status</th>
                                <th className="p-4 text-left text-sm font-semibold text-slate-500">Device</th>
                                <th className="p-4 text-left text-sm font-semibold text-slate-500">Owner</th>
                                <th className="p-4 text-left text-sm font-semibold text-slate-500">Last Seen</th>
                                <th className="p-4 text-left text-sm font-semibold text-slate-500">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {devices.map(device => (
                                <tr key={device.id} className="border-b hover:bg-slate-50">
                                    <td className="p-4">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${device.status === 'online' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                            }`}>
                                            {device.status === 'online' ? <Wifi size={14} className="mr-1" /> : <WifiOff size={14} className="mr-1" />}
                                            {device.status}
                                        </span>
                                    </td>
                                    <td className="p-4">
                                        <div className="font-medium">{device.name}</div>
                                        <div className="text-xs text-gray-500 font-mono">{device.code}</div>
                                    </td>
                                    <td className="p-4 text-sm text-gray-600">
                                        {device.owner || <span className="text-orange-400 italic">Unclaimed</span>}
                                    </td>
                                    <td className="p-4 text-sm text-gray-500">
                                        {new Date(device.lastSeen).toLocaleString()}
                                    </td>
                                    <td className="p-4">
                                        <button
                                            onClick={() => setSelectedDevice(device)}
                                            className="bg-slate-800 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2"
                                        >
                                            <TerminalIcon size={16} />
                                            Terminal
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Terminal Modal */}
            {selectedDevice && (
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
            )}
        </Layout>
    );
}
