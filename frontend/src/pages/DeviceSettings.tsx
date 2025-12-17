import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { client as api, updateDevice, unclaimDevice, createInviteLink, downloadDeviceLogs } from '../api/client';

export function DeviceSettings() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [device, setDevice] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [newName, setNewName] = useState('');
    const [saving, setSaving] = useState(false);
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteLink, setInviteLink] = useState('');
    const [inviteMessage, setInviteMessage] = useState('');
    const [inviteLoading, setInviteLoading] = useState(false);
    const [logType, setLogType] = useState('agent');
    const [logLines, setLogLines] = useState('500');
    const [logsLoading, setLogsLoading] = useState(false);
    const [logMessage, setLogMessage] = useState('');

    useEffect(() => {
        async function loadDevice() {
            try {
                const res = await api.get(`/devices/${id}`, {
                    params: { userId: user?.id }
                });
                setDevice(res.data);
                setNewName(res.data.friendlyName);
            } catch (err) {
                console.error(err);
                navigate('/');
            } finally {
                setLoading(false);
            }
        }
        if (user?.id) loadDevice();
    }, [id, user?.id, navigate]);

    const handleUpdateName = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await updateDevice(id!, { friendlyName: newName, userId: user?.id });
            setDevice({ ...device, friendlyName: newName });
            alert('Device updated');
        } catch (err) {
            alert('Failed to update device');
        } finally {
            setSaving(false);
        }
    };

    const handleUnclaim = async () => {
        if (!confirm('Are you sure you want to remove this device? You will need the code to claim it again.')) return;
        try {
            await unclaimDevice(id!, user?.id!);
            navigate('/');
        } catch (err) {
            alert('Failed to remove device');
        }
    };

    const handleInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!user?.id) return;
        setInviteLoading(true);
        setInviteMessage('');
        try {
            const data = await createInviteLink(id!, user.id, inviteEmail || undefined);
            const link = `${window.location.origin}/invite/${data.token}`;
            setInviteLink(link);
            setInviteMessage('Share this link with your friend.');
        } catch (err: any) {
            setInviteMessage(err.response?.data?.error || 'Failed to create invite');
        } finally {
            setInviteLoading(false);
        }
    };

    const handleDownloadLogs = async () => {
        if (!user?.id || !id) return;
        setLogsLoading(true);
        setLogMessage('');
        try {
            const res = await downloadDeviceLogs(id, user.id, logType, parseInt(logLines) || 500);
            const filename = `${device.friendlyName || 'device'}-${logType}-logs.txt`;
            const blob = new Blob([res.data], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            setLogMessage('Logs downloaded successfully.');
        } catch (err: any) {
            setLogMessage(err.response?.data?.error || 'Unable to download logs');
        } finally {
            setLogsLoading(false);
        }
    };

    if (loading) return <Layout><div>Loading...</div></Layout>;
    if (!device) return <Layout><div>Device not found</div></Layout>;

    return (
        <Layout>
            <div className="max-w-2xl mx-auto mt-8 px-4">
                <h1 className="text-xl font-semibold mb-6 text-charcoal-700">Settings</h1>

                <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                    <h2 className="text-lg font-medium mb-4">Device Info</h2>
                    <form onSubmit={handleUpdateName} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-500 mb-1">Friendly Name</label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    className="flex-1 px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none"
                                />
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="px-4 py-2 bg-charcoal-800 text-white rounded-xl hover:bg-charcoal-700 transition disabled:opacity-50"
                                >
                                    {saving ? 'Saving...' : 'Save'}
                                </button>
                            </div>
                        </div>
                    </form>
                    <div className="mt-6 pt-6 border-t border-gray-100">
                        <p className="text-sm text-gray-500 mb-2">Device Code</p>
                        <span className="font-mono bg-gray-100 px-3 py-1 rounded text-lg">{device.deviceCode}</span>
                        <p className="text-sm text-gray-400 mt-2">Status: <span className="capitalize text-gray-600">{device.status}</span></p>
                    </div>
                </div>

                <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                    <h2 className="text-lg font-medium mb-2">Invite a friend</h2>
                    <p className="text-sm text-gray-500 mb-4">Generate a link to share access to this printer.</p>
                    <form onSubmit={handleInvite} className="space-y-3">
                        <div>
                            <label className="block text-sm font-medium text-gray-500 mb-1">Friend's email (optional)</label>
                            <input
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="friend@example.com"
                                className="w-full px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={inviteLoading}
                            className="w-full bg-charcoal-800 text-white rounded-xl py-2 font-medium hover:bg-charcoal-700 transition disabled:opacity-50"
                        >
                            {inviteLoading ? 'Generating...' : 'Create invite link'}
                        </button>
                    </form>
                    {inviteMessage && (
                        <p className="text-sm text-gray-600 mt-3">{inviteMessage}</p>
                    )}
                    {inviteLink && (
                        <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-xl flex items-center gap-2">
                            <input
                                type="text"
                                readOnly
                                value={inviteLink}
                                className="flex-1 bg-transparent text-sm text-gray-700 outline-none"
                            />
                            <button
                                onClick={() => navigator.clipboard.writeText(inviteLink)}
                                className="text-coral-600 font-medium"
                            >
                                Copy
                            </button>
                        </div>
                    )}
                </div>

                <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                    <h2 className="text-lg font-medium mb-2">Download device logs</h2>
                    <p className="text-sm text-gray-500 mb-4">Fetch recent logs from the device to help with debugging.</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                        <div className="space-y-1">
                            <label className="block text-sm font-medium text-gray-500">Log type</label>
                            <select
                                value={logType}
                                onChange={(e) => setLogType(e.target.value)}
                                className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none"
                            >
                                <option value="agent">Agent</option>
                                <option value="wifi">WiFi</option>
                                <option value="system">System</option>
                            </select>
                        </div>
                        <div className="space-y-1">
                            <label className="block text-sm font-medium text-gray-500">Lines</label>
                            <input
                                type="number"
                                min={10}
                                max={5000}
                                value={logLines}
                                onChange={(e) => setLogLines(e.target.value)}
                                className="w-full px-3 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none"
                            />
                        </div>
                        <button
                            onClick={handleDownloadLogs}
                            disabled={logsLoading}
                            className="w-full md:w-auto px-4 py-2 bg-charcoal-800 text-white rounded-xl hover:bg-charcoal-700 transition disabled:opacity-50"
                        >
                            {logsLoading ? 'Fetching...' : 'Download logs'}
                        </button>
                    </div>
                    {logMessage && <p className="text-sm text-gray-600 mt-3">{logMessage}</p>}
                </div>

                <div className="bg-white rounded-2xl p-6 shadow-sm border border-red-100">
                    <h2 className="text-lg font-medium mb-2 text-red-600">Danger Zone</h2>
                    <p className="text-gray-500 mb-4 text-sm">Remove this device from your account.</p>
                    <button
                        onClick={handleUnclaim}
                        className="px-4 py-2 border border-red-200 text-red-600 rounded-xl hover:bg-red-50 transition"
                    >
                        Unclaim Device
                    </button>
                </div>
            </div>
        </Layout>
    );
}
