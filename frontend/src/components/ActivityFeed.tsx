import { useEffect, useState } from 'react';
import { client as api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Loader2, CheckCircle2, XCircle, Clock, Send } from 'lucide-react';

interface Message {
    id: string;
    status: string;
    createdAt: string;
    scheduledAt?: string;
    errorMessage?: string; // Corrected field name
}

interface ActivityFeedProps {
    deviceId: string | null;
    refreshTrigger: number;
}

export function ActivityFeed({ deviceId, refreshTrigger }: ActivityFeedProps) {
    const { user } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!deviceId || !user) return;

        async function fetchHistory() {
            setLoading(true);
            try {
                const res = await api.get('/messages', {
                    params: {
                        userId: user!.id,
                        deviceId: deviceId,
                        limit: 20
                    }
                });
                setMessages(res.data.messages);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }
        fetchHistory();

        // Polling for status updates every 5 seconds
        const interval = setInterval(fetchHistory, 5000);
        return () => clearInterval(interval);

    }, [deviceId, user, refreshTrigger]);

    if (!deviceId) {
        return <div className="p-4 text-center text-gray-400">Select a device to view activity</div>;
    }

    return (
        <div className="h-full flex flex-col bg-white border-l border-gray-100">
            <div className="p-4 border-b border-gray-100 font-semibold text-charcoal-700">
                Activity
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {loading && messages.length === 0 && (
                    <div className="flex justify-center p-4"><Loader2 className="animate-spin text-coral-500" /></div>
                )}

                {messages.map(msg => (
                    <div key={msg.id} className="flex items-start gap-3 text-sm">
                        <div className="mt-0.5">
                            {msg.status === 'printed' ? <CheckCircle2 size={16} className="text-green-500" /> :
                                msg.status === 'sent' ? <Send size={16} className="text-blue-500" /> :
                                    msg.status === 'queued' ? <Clock size={16} className="text-orange-500" /> :
                                        <XCircle size={16} className="text-red-500" />}
                        </div>
                        <div>
                            <p className="text-charcoal-800">
                                {msg.scheduledAt ? 'Scheduled Message' : 'Message'}
                            </p>
                            <p className="text-xs text-gray-400">
                                {new Date(msg.createdAt).toLocaleTimeString()}
                                <span className="capitalize ml-1">• {msg.status}</span>
                            </p>
                            {msg.errorMessage && (
                                <p className="text-xs text-red-500 mt-1">{msg.errorMessage}</p>
                            )}
                        </div>
                    </div>
                ))}

                {messages.length === 0 && !loading && (
                    <div className="text-center text-gray-400 py-8 text-sm">
                        No recent activity
                    </div>
                )}
            </div>
        </div>
    );
}
