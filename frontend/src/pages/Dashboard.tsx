import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { CanvasComposer } from '../components/CanvasComposer';
import { ActivityFeed } from '../components/ActivityFeed';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';
import { Printer, Calendar as CalendarIcon, X } from 'lucide-react';

interface Device {
    id: string;
    friendlyName: string;
    status: string;
    deviceCode: string;
}

export function Dashboard() {
    const { user } = useAuth();
    const [devices, setDevices] = useState<Device[]>([]);
    const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    // Scheduling State
    const [showScheduleModal, setShowScheduleModal] = useState(false);
    const [pendingImage, setPendingImage] = useState<string | null>(null);
    const [scheduledTime, setScheduledTime] = useState('');

    useEffect(() => {
        if (!user) return;
        async function fetchDevices() {
            try {
                const res = await api.get('/devices', { params: { userId: user?.id } });
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

    const handleSend = async (base64Image: string, scheduleDate?: string) => {
        if (!selectedDeviceId) return;
        setSending(true);
        try {
            await api.post('/messages', {
                deviceId: selectedDeviceId,
                senderId: user?.id,
                contentType: 'image',
                content: base64Image, // Send raw base64 string
                scheduledAt: scheduleDate
            });
            setRefreshTrigger(prev => prev + 1); // Update feed
        } catch (error) {
            console.error(error);
            alert('Failed to send message');
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

    return (
        <Layout>
            <div className="flex h-[calc(100vh-64px)] overflow-hidden">
                {/* 1. Device Sidebar */}
                <div className="w-64 bg-gray-50 border-r border-gray-200 p-4 flex flex-col">
                    <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">Printers</h2>
                    <div className="space-y-2 flex-1 overflow-y-auto">
                        {loading && <div>Loading...</div>}
                        {devices.map(device => (
                            <button
                                key={device.id}
                                onClick={() => setSelectedDeviceId(device.id)}
                                className={`w-full flex items-center gap-3 p-3 rounded-xl transition text-left ${selectedDeviceId === device.id
                                    ? 'bg-white shadow-sm ring-1 ring-black/5'
                                    : 'hover:bg-gray-100 text-gray-600'
                                    }`}
                            >
                                <div className={`w-2 h-2 rounded-full ${device.status === 'online' ? 'bg-green-500' : 'bg-gray-300'}`} />
                                <div className="flex-1 truncate">
                                    <div className="font-medium text-charcoal-800 truncate">{device.friendlyName}</div>
                                    <div className="text-xs text-gray-400 font-mono">{device.deviceCode}</div>
                                </div>
                            </button>
                        ))}
                        <Link to="/setup" className="flex items-center gap-2 p-3 text-sm text-coral-600 hover:bg-coral-50 rounded-xl transition font-medium">
                            + Add Printer
                        </Link>
                    </div>
                </div>

                {/* 2. Main Canvas Area */}
                <div className="flex-1 bg-gray-100 p-8 overflow-y-auto flex flex-col items-center">
                    {selectedDeviceId ? (
                        <>
                            <div className="mb-6 text-center">
                                <h1 className="text-2xl font-semibold text-charcoal-800">Compose Message</h1>
                                <p className="text-gray-500">Design your receipt for {devices.find(d => d.id === selectedDeviceId)?.friendlyName}</p>
                            </div>
                            <CanvasComposer
                                onSend={async (img) => handleSend(img)}
                                onSchedule={(img) => {
                                    setPendingImage(img);
                                    setShowScheduleModal(true);
                                }}
                                sending={sending}
                            />
                        </>
                    ) : (
                        <div className="flex items-center justify-center h-full text-gray-400">
                            Select a printer to start
                        </div>
                    )}
                </div>

                {/* 3. Activity Feed (Right) */}
                <div className="w-80 h-full">
                    <ActivityFeed deviceId={selectedDeviceId} refreshTrigger={refreshTrigger} />
                </div>
            </div>

            {/* Schedule Modal */}
            {showScheduleModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
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
        </Layout>
    );
}
