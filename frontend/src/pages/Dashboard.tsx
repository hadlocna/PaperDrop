import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { CanvasComposer } from '../components/CanvasComposer';
import { ActivityFeed } from '../components/ActivityFeed';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';
import { X, Activity, Printer } from 'lucide-react';

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

    // Mobile Drawers
    const [showPrinters, setShowPrinters] = useState(false);
    const [showActivity, setShowActivity] = useState(false);

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

    const handleSend = async (base64Image: string, scheduleDate?: string): Promise<boolean> => {
        if (!selectedDeviceId) return false;
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
                    <button
                        key={device.id}
                        onClick={() => {
                            setSelectedDeviceId(device.id);
                            setShowPrinters(false); // Close drawer on mobile selection
                        }}
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
    );

    return (
        <Layout>
            <div className="flex h-[calc(100vh-64px)] relative overflow-hidden">

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

                    <div className="flex-1 overflow-y-auto relative">
                        {selectedDeviceId ? (
                            <div className="w-full min-h-full flex flex-col">
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
                            <div className="flex items-center justify-center h-full text-gray-500">
                                <button onClick={() => setShowPrinters(true)} className="bg-white px-6 py-3 rounded-full shadow-lg font-medium text-coral-600">
                                    Select a printer to start
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* 3. Activity Feed (Desktop) */}
                <div className="hidden lg:block w-80 h-full border-l border-gray-200 bg-white">
                    <ActivityFeed deviceId={selectedDeviceId} refreshTrigger={refreshTrigger} />
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
                                <ActivityFeed deviceId={selectedDeviceId} refreshTrigger={refreshTrigger} />
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
        </Layout>
    );
}
