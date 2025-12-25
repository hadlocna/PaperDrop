import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { CanvasComposer } from '../components/CanvasComposer';
import { ActivityFeed } from '../components/ActivityFeed';
import { BleProvisioningModal } from '../components/BleProvisioningModal';
import { useAuth } from '../context/AuthContext';
import { X, Activity, Printer, Bluetooth, Settings, Trash2, RefreshCw, Download, Share2, Copy, Check, MessageSquare, Rocket } from 'lucide-react';
import { client as api, updateDevice, unclaimDevice, clearMessageQueue, createInviteLink, downloadDeviceLogs } from '../api/client';

interface Device {
    id: string;
    friendlyName: string;
    status: string;
    deviceCode: string;
}

function DeviceSettingsModal({ deviceId, onClose, onUpdate }: { deviceId: string, onClose: () => void, onUpdate: () => void }) {
    const { user } = useAuth();
    const [device, setDevice] = useState<any>(null);
    const [accessList, setAccessList] = useState<any[]>([]);
    const [pendingInvites, setPendingInvites] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [newName, setNewName] = useState('');
    const [saving, setSaving] = useState(false);
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteLink, setInviteLink] = useState('');
    const [inviteLoading, setInviteLoading] = useState(false);
    const [logType, setLogType] = useState('agent');
    const [logLines, setLogLines] = useState('500');
    const [logsLoading, setLogsLoading] = useState(false);
    const [logMessage, setLogMessage] = useState('');
    const [copied, setCopied] = useState(false);
    const [testingConnection, setTestingConnection] = useState(false);
    const [testResult, setTestResult] = useState<string | null>(null);

    const currentUserRole = useMemo(() => {
        return accessList.find(a => a.userId === user?.id)?.role;
    }, [accessList, user?.id]);

    const isOwner = currentUserRole === 'owner';

    useEffect(() => {
        async function loadData() {
            try {
                const [deviceRes, accessRes] = await Promise.all([
                    api.get(`/devices/${deviceId}`),
                    api.get(`/devices/${deviceId}/access`)
                ]);
                setDevice(deviceRes.data);
                setNewName(deviceRes.data.friendlyName);
                setAccessList(accessRes.data.access || []);
                setPendingInvites(accessRes.data.invites || []);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }
        if (user?.id) loadData();
    }, [deviceId, user?.id]);

    const handleRevokeAccess = async (targetUserId: string) => {
        if (!confirm('Are you sure you want to revoke access for this user?')) return;
        try {
            await api.delete(`/devices/${deviceId}/access/${targetUserId}`);
            setAccessList(accessList.filter(a => a.userId !== targetUserId));
        } catch (err) {
            alert('Failed to revoke access');
        }
    };

    const handleUpdateName = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await updateDevice(deviceId, { friendlyName: newName });
            setDevice({ ...device, friendlyName: newName });
            onUpdate();
        } catch (err) {
            alert('Failed to update device');
        } finally {
            setSaving(false);
        }
    };

    const handleClearQueue = async () => {
        if (!confirm('Are you sure you want to clear all messages for this printer? This will delete all pending and sent messages.')) return;
        try {
            await clearMessageQueue(deviceId);
            alert('Message queue cleared');
        } catch (err) {
            alert('Failed to clear message queue');
        }
    };

    const handleUnclaim = async () => {
        if (!confirm('Are you sure you want to remove this device? You will need the code to claim it again.')) return;
        try {
            await unclaimDevice(deviceId);
            onClose();
            onUpdate();
        } catch (err) {
            alert('Failed to remove device');
        }
    };

    const handleInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!user?.id) return;
        setInviteLoading(true);
        try {
            const data = await createInviteLink(deviceId, inviteEmail || undefined);
            const link = `${window.location.origin}/invite/${data.token}`;
            setInviteLink(link);
        } catch (err: any) {
            alert(err.response?.data?.error || 'Failed to create invite');
        } finally {
            setInviteLoading(false);
        }
    };

    const handleDownloadLogs = async () => {
        if (!user?.id) return;
        setLogsLoading(true);
        setLogMessage('');
        try {
            const res = await downloadDeviceLogs(deviceId, logType, parseInt(logLines) || 500);
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

    const handleTestConnection = async () => {
        setTestingConnection(true);
        setTestResult(null);
        try {
            // We'll implement a simple ping/pong via the existing message system or a new endpoint
            // For now, let's just check if the device is 'online' in the DB
            const res = await api.get(`/devices/${deviceId}`);
            if (res.data.status === 'online') {
                setTestResult('Device is online and connected to WebSocket.');
            } else {
                setTestResult('Device appears offline. Check its power and WiFi.');
            }
        } catch (err) {
            setTestResult('Failed to test connection.');
        } finally {
            setTestingConnection(false);
        }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(inviteLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (loading) return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4 backdrop-blur-sm">
            <div className="bg-white rounded-3xl p-8 w-full max-w-lg shadow-2xl">
                <div className="flex flex-col items-center gap-4">
                    <RefreshCw className="animate-spin text-coral-500" size={32} />
                    <p className="text-gray-500 font-medium">Loading settings...</p>
                </div>
            </div>
        </div>
    );

    if (!device) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4 backdrop-blur-sm overflow-y-auto">
            <div className="bg-white rounded-3xl w-full max-w-lg shadow-2xl my-8 animate-in zoom-in-95 duration-200">
                <div className="sticky top-0 bg-white/80 backdrop-blur-md px-6 py-4 border-b border-gray-100 flex justify-between items-center rounded-t-3xl z-10">
                    <h2 className="text-xl font-bold text-charcoal-800">Printer Settings</h2>
                    <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full transition">
                        <X size={24} className="text-gray-400" />
                    </button>
                </div>

                <div className="p-6 space-y-8 max-h-[70vh] overflow-y-auto">
                    {/* Device Info */}
                    <section>
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">Device Info</h3>
                        <form onSubmit={handleUpdateName} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-500 mb-1">Friendly Name</label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={newName}
                                        onChange={(e) => setNewName(e.target.value)}
                                        disabled={!isOwner}
                                        className="flex-1 px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none transition disabled:opacity-50 disabled:cursor-not-allowed"
                                    />
                                    <button
                                        type="submit"
                                        disabled={saving || newName === device.friendlyName || !isOwner}
                                        className={`px-6 py-2 rounded-xl font-medium transition all duration-300 disabled:opacity-50 ${newName === device.friendlyName || !isOwner
                                            ? 'bg-emerald-50 text-emerald-600 border border-emerald-100 cursor-default'
                                            : 'bg-charcoal-800 text-white hover:bg-charcoal-700 active:scale-95'
                                            }`}
                                    >
                                        {saving ? 'Saving...' : (newName === device.friendlyName || !isOwner) ? 'Saved' : 'Save Changes'}
                                    </button>
                                </div>
                            </div>
                        </form>
                        <div className="mt-4 p-4 bg-gray-50 rounded-2xl border border-gray-100 flex justify-between items-center">
                            <div>
                                <p className="text-xs text-gray-400 font-medium uppercase">Device Code</p>
                                <p className="font-mono text-lg text-charcoal-800">{device.deviceCode}</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xs text-gray-400 font-medium uppercase">Status</p>
                                <div className="flex items-center gap-2 justify-end">
                                    <div className={`w-2 h-2 rounded-full ${device.status === 'online' ? 'bg-green-500' : 'bg-gray-300'}`} />
                                    <span className="capitalize font-medium text-charcoal-700">{device.status}</span>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Connection Test */}
                    <section className="p-4 bg-coral-50 rounded-2xl border border-coral-100">
                        <h3 className="text-sm font-bold text-coral-800 uppercase tracking-wider mb-2">Connection Troubleshooter</h3>
                        <p className="text-sm text-coral-700 mb-4">If your printer shows as offline, use this to verify its connection status.</p>
                        <button
                            onClick={handleTestConnection}
                            disabled={testingConnection}
                            className="w-full flex items-center justify-center gap-2 py-2 bg-white text-coral-600 rounded-xl font-bold border border-coral-200 hover:bg-coral-100 transition shadow-sm"
                        >
                            {testingConnection ? <RefreshCw className="animate-spin" size={18} /> : <RefreshCw size={18} />}
                            Test Connection
                        </button>
                        {testResult && (
                            <p className="mt-3 text-sm font-medium text-coral-800 bg-white/50 p-2 rounded-lg border border-coral-200">
                                {testResult}
                            </p>
                        )}
                    </section>

                    {/* Invites */}
                    <section>
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">Share Access</h3>

                        {/* Access List */}
                        {accessList.length > 0 && (
                            <div className="mb-6 space-y-3">
                                <h4 className="text-xs font-bold text-gray-400 uppercase ml-1">Users with Access</h4>
                                {accessList.map((access) => (
                                    <div key={access.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-100">
                                        <div>
                                            <p className="text-sm font-medium text-charcoal-800">{access.user.name}</p>
                                            <p className="text-xs text-gray-400">{access.user.email} • <span className="capitalize">{access.role}</span></p>
                                        </div>
                                        {device.ownerId === user?.id && access.userId !== user?.id && (
                                            <button
                                                onClick={() => handleRevokeAccess(access.userId)}
                                                className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                                                title="Revoke Access"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Pending Invites */}
                        {pendingInvites.length > 0 && (
                            <div className="mb-6 space-y-3">
                                <h4 className="text-xs font-bold text-gray-400 uppercase ml-1">Pending Invites</h4>
                                {pendingInvites.map((invite) => (
                                    <div key={invite.id} className="flex items-center justify-between p-3 bg-orange-50 rounded-xl border border-orange-100">
                                        <div>
                                            <p className="text-sm font-medium text-orange-800">{invite.inviteeEmail || 'Open Invite'}</p>
                                            <p className="text-xs text-orange-600">Sent by {invite.inviter.name}</p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] font-bold uppercase bg-orange-200 text-orange-700 px-1.5 py-0.5 rounded">Pending</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {isOwner && (
                            <>
                                <p className="text-sm text-gray-500 mb-4">Invite others to print to this device.</p>
                                <form onSubmit={handleInvite} className="space-y-3">
                                    <div className="flex gap-2">
                                        <input
                                            type="email"
                                            value={inviteEmail}
                                            onChange={(e) => setInviteEmail(e.target.value)}
                                            placeholder="friend@example.com"
                                            className="flex-1 px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none transition"
                                        />
                                        <button
                                            type="submit"
                                            disabled={inviteLoading}
                                            className="px-4 py-2 bg-charcoal-800 text-white rounded-xl font-medium hover:bg-charcoal-700 transition disabled:opacity-50"
                                        >
                                            {inviteLoading ? <RefreshCw className="animate-spin" size={20} /> : <Share2 size={20} />}
                                        </button>
                                    </div>
                                </form>
                            </>
                        )}
                        {inviteLink && isOwner && (
                            <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-xl flex items-center gap-2 animate-in slide-in-from-top-2">
                                <input
                                    type="text"
                                    readOnly
                                    value={inviteLink}
                                    className="flex-1 bg-transparent text-sm text-gray-600 font-mono outline-none"
                                />
                                <button
                                    onClick={copyToClipboard}
                                    className="p-2 text-coral-600 hover:bg-coral-50 rounded-lg transition"
                                >
                                    {copied ? <Check size={18} /> : <Copy size={18} />}
                                </button>
                            </div>
                        )}
                    </section>

                    {/* Logs */}
                    <section>
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">Debug Logs</h3>
                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase mb-1 ml-1">Type</label>
                                <select
                                    value={logType}
                                    onChange={(e) => setLogType(e.target.value)}
                                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:ring-2 focus:ring-coral-500 transition"
                                >
                                    <option value="agent">Agent</option>
                                    <option value="wifi">WiFi</option>
                                    <option value="system">System</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase mb-1 ml-1">Lines</label>
                                <input
                                    type="number"
                                    value={logLines}
                                    onChange={(e) => setLogLines(e.target.value)}
                                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:ring-2 focus:ring-coral-500 transition"
                                />
                            </div>
                        </div>
                        <button
                            onClick={handleDownloadLogs}
                            disabled={logsLoading}
                            className="w-full flex items-center justify-center gap-2 py-2 bg-gray-100 text-charcoal-700 rounded-xl font-bold hover:bg-gray-200 transition"
                        >
                            {logsLoading ? <RefreshCw className="animate-spin" size={18} /> : <Download size={18} />}
                            Download Logs
                        </button>
                        {logMessage && <p className="mt-2 text-xs text-center text-gray-500">{logMessage}</p>}
                    </section>

                    {/* Danger Zone */}
                    <section className="pt-6 border-t border-gray-100 space-y-4">
                        <h3 className="text-sm font-bold text-red-400 uppercase tracking-wider">Danger Zone</h3>
                        <div className="flex flex-col gap-3">
                            <button
                                onClick={handleClearQueue}
                                className="w-full flex items-center justify-center gap-2 py-2 border border-gray-200 text-gray-600 rounded-xl font-bold hover:bg-gray-50 transition"
                            >
                                <RefreshCw size={18} />
                                Clear Message Queue
                            </button>
                            <button
                                onClick={handleUnclaim}
                                className="w-full flex items-center justify-center gap-2 py-2 bg-red-50 text-red-600 rounded-xl font-bold hover:bg-red-100 transition"
                            >
                                <Trash2 size={18} />
                                Unclaim Device
                            </button>
                        </div>
                    </section>
                </div>

                <div className="sticky bottom-0 bg-white/80 backdrop-blur-md px-6 py-4 border-t border-gray-100 rounded-b-3xl">
                    <button
                        onClick={onClose}
                        className="w-full py-4 bg-charcoal-800 text-white rounded-2xl font-bold hover:bg-charcoal-700 transition-all active:scale-[0.98] shadow-lg shadow-charcoal-800/20"
                    >
                        Close Settings
                    </button>
                </div>
            </div>
        </div>
    );
}

interface FeedbackReply {
    id: string;
    feedbackId: string;
    isAdmin: boolean;
    message: string;
    createdAt: string;
}

interface UserFeedback {
    id: string;
    message: string;
    type: string;
    status: string;
    createdAt: string;
    replies: FeedbackReply[];
}

function FeedbackModal({ onClose, selectedDevice }: { onClose: () => void, selectedDevice?: Device }) {
    const [view, setView] = useState<'new' | 'history' | 'detail'>('new');
    const [message, setMessage] = useState('');
    const [reply, setReply] = useState('');
    const [type, setType] = useState('feedback');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const [history, setHistory] = useState<UserFeedback[]>([]);
    const [selectedTicket, setSelectedTicket] = useState<UserFeedback | null>(null);

    useEffect(() => {
        if (view === 'history') {
            loadHistory();
        }
    }, [view]);

    const loadHistory = async () => {
        setLoading(true);
        try {
            const res = await api.get('/feedback/my');
            setHistory(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const deviceInfo = {
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                browser: (navigator as any).vendor || 'unknown'
            };

            await api.post('/feedback/send', {
                message,
                type,
                deviceId: selectedDevice?.id,
                deviceName: selectedDevice?.friendlyName,
                deviceInfo
            });
            setSuccess(true);
            setTimeout(onClose, 2000);
        } catch (err) {
            alert('Failed to submit feedback');
        } finally {
            setLoading(false);
        }
    };

    const handleSendReply = async () => {
        if (!reply.trim() || !selectedTicket) return;
        setLoading(true);
        try {
            await api.post(`/feedback/${selectedTicket.id}/reply`, { message: reply });
            setReply('');
            // Refresh detail view
            const res = await api.get('/feedback/my');
            setHistory(res.data);
            setSelectedTicket(res.data.find((t: any) => t.id === selectedTicket.id));
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="bg-white rounded-3xl w-full max-w-sm overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200 flex flex-col max-h-[80vh]">
                <div className="bg-[#3D405B] p-4 pt-6 flex justify-between items-center relative">
                    <div className="flex flex-col">
                        <h2 className="text-white font-bold tracking-tight">Support & Help</h2>
                        <div className="flex gap-4 mt-3">
                            <button onClick={() => setView('new')} className={`text-[10px] font-bold tracking-widest transition-all ${view === 'new' ? 'text-[#E07A5F]' : 'text-white/40 hover:text-white/60'}`}>NEW MESSAGE</button>
                            <button onClick={() => setView('history')} className={`text-[10px] font-bold tracking-widest transition-all ${view === 'history' || view === 'detail' ? 'text-[#E07A5F]' : 'text-white/40 hover:text-white/60'}`}>MY TICKETS</button>
                        </div>
                    </div>
                    <button onClick={onClose} className="text-white/40 hover:text-white transition-colors absolute top-4 right-4"><X size={20} /></button>
                </div>

                <div className="flex-1 overflow-y-auto min-h-[300px] flex flex-col">
                    {success ? (
                        <div className="p-8 text-center animate-in fade-in zoom-in duration-300">
                            <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-inner">
                                <Check size={32} />
                            </div>
                            <h3 className="font-bold text-gray-900 mb-2">Message Received!</h3>
                            <p className="text-gray-500 text-sm">We'll get back to you shortly in the "My Tickets" section.</p>
                        </div>
                    ) : view === 'new' ? (
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div>
                                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5 ml-1 font-mono">Type</label>
                                <div className="grid grid-cols-2 gap-2">
                                    {['feedback', 'bug', 'question', 'feature'].map(t => (
                                        <button
                                            key={t}
                                            type="button"
                                            onClick={() => setType(t)}
                                            className={`py-2 px-3 rounded-xl text-xs font-bold capitalize transition-all border ${type === t ? 'bg-[#E07A5F] text-white border-[#E07A5F] shadow-lg shadow-[#E07A5F]/10' : 'bg-white text-gray-500 border-gray-100 hover:border-gray-300'}`}
                                        >
                                            {t}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5 ml-1 font-mono">Your Message</label>
                                <textarea
                                    required
                                    value={message}
                                    onChange={(e) => setMessage(e.target.value)}
                                    placeholder="How can we help?"
                                    className="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm focus:ring-4 focus:ring-[#E07A5F]/5 focus:border-[#E07A5F] outline-none transition-all resize-none h-32"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={loading || !message.trim()}
                                className="w-full py-4 bg-[#3D405B] text-white rounded-2xl font-bold hover:bg-[#2F3248] transition-all active:scale-[0.98] shadow-lg shadow-gray-200 disabled:opacity-50"
                            >
                                {loading ? 'Sending...' : 'Send Message'}
                            </button>
                        </form>
                    ) : view === 'history' ? (
                        <div className="p-4 space-y-3">
                            {loading && history.length === 0 ? <div className="p-8 text-center text-gray-400 text-sm">Loading history...</div> :
                                history.length === 0 ? <div className="p-12 text-center">
                                    <MessageSquare className="mx-auto text-gray-200 mb-2" size={40} />
                                    <p className="text-gray-400 text-sm">No support tickets yet.</p>
                                </div> :
                                    history.map(ticket => (
                                        <button
                                            key={ticket.id}
                                            onClick={() => {
                                                setSelectedTicket(ticket);
                                                setView('detail');
                                            }}
                                            className="w-full p-4 bg-white border border-gray-100 rounded-2xl hover:border-[#E07A5F]/30 hover:bg-[#E07A5F]/5 transition-all text-left group"
                                        >
                                            <div className="flex justify-between items-start mb-2">
                                                <span className={`px-2 py-0.5 rounded-lg text-[10px] font-bold uppercase tracking-wider ${ticket.status === 'resolved' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                                                    {ticket.status}
                                                </span>
                                                <span className="text-[10px] text-gray-400 font-medium font-mono">{new Date(ticket.createdAt).toLocaleDateString()}</span>
                                            </div>
                                            <p className="text-sm text-gray-800 font-bold truncate pr-4">{ticket.message}</p>
                                            {ticket.replies.some(r => r.isAdmin) && (
                                                <div className="mt-2 text-[10px] text-[#E07A5F] font-bold flex items-center gap-1 uppercase tracking-wider">
                                                    <div className="w-1.5 h-1.5 bg-[#E07A5F] rounded-full animate-pulse" />
                                                    Response from Support
                                                </div>
                                            )}
                                        </button>
                                    ))}
                        </div>
                    ) : (
                        <div className="flex flex-col h-full bg-gray-50/30 overflow-hidden">
                            {/* Detailed Chat-like View */}
                            <div className="flex-1 p-4 space-y-4 overflow-y-auto">
                                <button onClick={() => setView('history')} className="text-[10px] font-bold text-gray-400 uppercase mb-2 hover:text-gray-600 flex items-center gap-1 font-mono">← Back to tickets</button>

                                {/* User Opening Message */}
                                <div className="flex flex-col items-start max-w-[90%]">
                                    <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-none p-3 shadow-sm">
                                        <p className="text-sm text-gray-700 whitespace-pre-wrap">{selectedTicket?.message}</p>
                                        <div className="text-[9px] text-gray-400 mt-1 font-mono">{new Date(selectedTicket?.createdAt || '').toLocaleString()}</div>
                                    </div>
                                </div>

                                {/* Replies */}
                                {selectedTicket?.replies.map(r => (
                                    <div key={r.id} className={`flex flex-col ${r.isAdmin ? 'items-end' : 'items-start'} max-w-[90%] ${r.isAdmin ? 'ml-auto' : ''}`}>
                                        <div className={`${r.isAdmin ? 'bg-[#3D405B] text-white rounded-tr-none' : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none'} rounded-2xl p-3 shadow-sm`}>
                                            <p className="text-sm whitespace-pre-wrap">{r.message}</p>
                                            <div className={`text-[9px] mt-1 opacity-60 font-mono`}>{new Date(r.createdAt).toLocaleString()}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="bg-white border-t border-gray-100 p-4 shadow-[0_-10px_20px_rgba(0,0,0,0.02)]">
                                <div className="flex gap-2">
                                    <input
                                        value={reply}
                                        onChange={(e) => setReply(e.target.value)}
                                        placeholder="Send a reply..."
                                        className="flex-1 bg-gray-50 border border-gray-100 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-[#E07A5F]/30 outline-none"
                                        onKeyDown={(e) => e.key === 'Enter' && handleSendReply()}
                                    />
                                    <button
                                        disabled={loading || !reply.trim()}
                                        onClick={handleSendReply}
                                        className="bg-[#3D405B] text-white p-2 rounded-xl active:scale-95 transition-all shadow-lg shadow-gray-200 disabled:opacity-50"
                                    >
                                        <Rocket size={18} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

interface Device {
    id: string;
    friendlyName: string;
    status: string;
    deviceCode: string;
}

export function Dashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [devices, setDevices] = useState<Device[]>([]);
    const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    // Mobile Drawers
    const [showPrinters, setShowPrinters] = useState(false);
    const [showActivity, setShowActivity] = useState(false);

    // Scheduling State
    const [showScheduleModal, setShowScheduleModal] = useState(false);
    const [pendingImage, setPendingImage] = useState<string | null>(null);
    const [scheduledTime, setScheduledTime] = useState('');

    // BLE Provisioning Modal
    const [showBleModal, setShowBleModal] = useState(false);

    // Device Settings Modal
    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [settingsDeviceId, setSettingsDeviceId] = useState<string | null>(null);

    // Feedback
    const [showFeedbackModal, setShowFeedbackModal] = useState(false);


    useEffect(() => {
        if (!user) return;
        async function fetchDevices() {
            try {
                const res = await api.get('/devices');
                setDevices(res.data);
                if (res.data.length > 0 && !selectedDeviceId) {
                    setSelectedDeviceId(res.data[0].id);
                }
            } catch (error) {
                console.error(error);
            } finally {
                setLoading(false);
            }
        }
        fetchDevices();
    }, [user]);

    const handleSend = async (base64Image: string, scheduleDate?: string): Promise<boolean> => {
        if (!selectedDeviceId) return false;

        if (!user?.id) {
            alert('Error: User not identified. Please try logging out and back in.');
            return false;
        }

        if (!base64Image) {
            alert('Error: Canvas generation failed (Empty Image).');
            return false;
        }

        setSending(true);
        console.log('Sending Message Payload:', { deviceId: selectedDeviceId, senderId: user.id, contentLength: base64Image.length });
        try {
            await api.post('/messages', {
                deviceId: selectedDeviceId,
                contentType: 'image',
                content: base64Image, // Send raw base64 string
                scheduledAt: scheduleDate
            });
            setRefreshTrigger(prev => prev + 1); // Update feed
            setShowActivity(true); // Switch to activity view
            return true;
        } catch (error) {
            console.error(error);
            alert('Failed to send message');
            return false;
        } finally {
            setSending(false);
            setShowScheduleModal(false);
            setPendingImage(null);
            setScheduledTime('');
        }
    };

    const confirmSchedule = () => {
        if (pendingImage && scheduledTime) {
            handleSend(pendingImage, new Date(scheduledTime).toISOString());
        }
    };

    const PrinterList = () => (
        <div className="h-full flex flex-col bg-gray-50 border-r border-gray-200 p-4">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Printers</h2>
                {/* Mobile Close Button */}
                <button onClick={() => setShowPrinters(false)} className="md:hidden p-1 hover:bg-gray-200 rounded">
                    <X size={20} className="text-gray-500" />
                </button>
            </div>

            <div className="space-y-2 flex-1 overflow-y-auto">
                {loading && <div>Loading...</div>}
                {devices.map(device => (
                    <div
                        key={device.id}
                        onClick={() => {
                            setSelectedDeviceId(device.id);
                            setShowPrinters(false); // Close drawer on mobile selection
                        }}
                        className={`w-full flex items-center gap-3 p-3 rounded-xl transition text-left cursor-pointer ${selectedDeviceId === device.id
                            ? 'bg-white shadow-sm ring-1 ring-black/5'
                            : 'hover:bg-gray-100 text-gray-600'
                            }`}
                    >
                        <div className={`w-2 h-2 rounded-full ${device.status === 'online' ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <div className="flex-1 truncate">
                            <div className="font-medium text-charcoal-800 truncate">{device.friendlyName}</div>
                            <div className="text-xs text-gray-400 font-mono">{device.deviceCode}</div>
                        </div>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setSettingsDeviceId(device.id);
                                setShowSettingsModal(true);
                            }}
                            className="p-2 text-gray-400 hover:text-coral-500 hover:bg-gray-200 rounded-lg transition"
                            title="Device Settings"
                        >
                            <Settings size={18} />
                        </button>
                    </div>
                ))}
                <button
                    onClick={() => setShowBleModal(true)}
                    className="flex items-center gap-2 p-3 text-sm text-coral-600 hover:bg-coral-50 rounded-xl transition font-medium w-full"
                >
                    <Bluetooth size={16} />
                    Add Printer
                </button>

                <div className="border-t border-gray-100 my-2" />

                <button
                    onClick={() => setShowFeedbackModal(true)}
                    className="flex items-center gap-2 p-3 text-sm text-slate-500 hover:bg-slate-50 rounded-xl transition font-medium w-full"
                >
                    <MessageSquare size={16} />
                    Feedback & Support
                </button>
            </div>
        </div>
    );

    return (
        <Layout>
            <div className="flex h-[calc(100dvh-64px)] relative overflow-hidden">

                {/* 1. Printer Sidebar (Desktop) */}
                <div className="hidden md:block w-64 h-full">
                    <PrinterList />
                </div>

                {/* Mobile Printer Drawer (Overlay) */}
                {showPrinters && (
                    <div className="fixed inset-0 z-50 md:hidden flex">
                        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowPrinters(false)} />
                        <div className="relative w-4/5 max-w-sm bg-gray-50 h-full shadow-2xl animate-in slide-in-from-left">
                            <PrinterList />
                        </div>
                    </div>
                )}

                {/* 2. Main Canvas Area */}
                <div className="flex-1 bg-neutral-900 overflow-hidden flex flex-col relative">

                    {/* Mobile Top Bar (Printers Toggle) */}
                    <div className="md:hidden bg-white border-b border-gray-200 p-2 flex justify-between items-center z-10 shrink-0">
                        <button onClick={() => setShowPrinters(true)} className="flex items-center gap-2 px-3 py-2 text-charcoal-700 bg-gray-50 rounded-lg text-sm font-medium">
                            <Printer size={18} />
                            {devices.find(d => d.id === selectedDeviceId)?.friendlyName || 'Select Printer'}
                        </button>
                        <button onClick={() => setShowActivity(true)} className="p-2 text-charcoal-600 hover:bg-gray-100 rounded-lg">
                            <Activity size={20} />
                        </button>
                    </div>

                    <div className="flex-1 overflow-hidden relative">
                        {loading ? (
                            <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-4">
                                <RefreshCw className="animate-spin text-coral-500" size={32} />
                                <p className="font-medium">Finding your printers...</p>
                            </div>
                        ) : selectedDeviceId ? (
                            <div className="w-full h-full flex flex-col">
                                <CanvasComposer
                                    onSend={async (img) => handleSend(img)}
                                    onSchedule={(img) => {
                                        setPendingImage(img);
                                        setShowScheduleModal(true);
                                    }}
                                    sending={sending}
                                />
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-gray-500 p-8 text-center">
                                <Printer size={48} className="text-gray-200 mb-4" />
                                <h3 className="text-xl font-bold text-charcoal-800 mb-2">No Printers Found</h3>
                                <p className="text-gray-400 mb-6 max-w-xs">Connect your first PaperDrop printer to start sending messages.</p>
                                <button onClick={() => setShowBleModal(true)} className="bg-coral-500 text-white px-8 py-3 rounded-full shadow-lg font-bold hover:bg-coral-600 transition">
                                    Add Printer
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* 3. Activity Feed (Desktop) */}
                <div className="hidden lg:block w-80 h-full border-l border-gray-200 bg-white">
                    <ActivityFeed refreshTrigger={refreshTrigger} />
                </div>

                {/* Mobile Activity Drawer (Overlay) */}
                {showActivity && (
                    <div className="fixed inset-0 z-50 lg:hidden flex justify-end">
                        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowActivity(false)} />
                        <div className="relative w-4/5 max-w-sm bg-white h-full shadow-2xl animate-in slide-in-from-right p-4">
                            <div className="flex justify-between items-center mb-4 border-b border-gray-100 pb-2">
                                <h3 className="font-bold text-lg">Activity</h3>
                                <button onClick={() => setShowActivity(false)}><X size={24} /></button>
                            </div>
                            <div className="h-full overflow-hidden">
                                <ActivityFeed refreshTrigger={refreshTrigger} />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Schedule Modal */}
            {showScheduleModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-semibold text-charcoal-800">Schedule Print</h3>
                            <button onClick={() => setShowScheduleModal(false)}><X size={20} className="text-gray-400 hover:text-gray-600" /></button>
                        </div>
                        <div className="mb-6">
                            <label className="block text-sm font-medium text-gray-600 mb-2">When should this print?</label>
                            <input
                                type="datetime-local"
                                value={scheduledTime}
                                onChange={(e) => setScheduledTime(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none"
                            />
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowScheduleModal(false)}
                                className="flex-1 py-2 text-charcoal-600 hover:bg-gray-50 rounded-xl font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmSchedule}
                                disabled={!scheduledTime}
                                className="flex-1 py-2 bg-coral-500 text-white rounded-xl font-medium hover:bg-coral-600 disabled:opacity-50"
                            >
                                Schedule
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Device Settings Modal */}
            {showSettingsModal && settingsDeviceId && (
                <DeviceSettingsModal
                    deviceId={settingsDeviceId}
                    onClose={() => {
                        setShowSettingsModal(false);
                        setSettingsDeviceId(null);
                    }}
                    onUpdate={() => {
                        // Refresh devices to get new name
                        api.get('/devices').then(res => setDevices(res.data));
                    }}
                />
            )}

            {/* BLE Provisioning Modal */}
            <BleProvisioningModal
                isOpen={showBleModal}
                onClose={() => setShowBleModal(false)}
                onSuccess={(deviceId) => {
                    setShowBleModal(false);
                    // Navigate to claim page with the device ID
                    navigate(`/claim?code=${deviceId}`);
                }}
            />
            {showFeedbackModal && (
                <FeedbackModal
                    onClose={() => setShowFeedbackModal(false)}
                    selectedDevice={devices.find(d => d.id === selectedDeviceId)}
                />
            )}
        </Layout>
    );
}
