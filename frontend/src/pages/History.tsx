import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';

interface Message {
    id: string;
    content: string; // JSON string
    status: string;
    createdAt: string;
    contentType: string;
}

export function History() {
    const { id } = useParams();
    const { user } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadHistory() {
            try {
                const res = await api.get('/messages', {
                    params: {
                        userId: user?.id,
                        deviceId: id
                    }
                });
                setMessages(res.data.messages);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }
        if (user?.id) loadHistory();
    }, [id, user?.id]);

    const parseContent = (msg: Message) => {
        try {
            const parsed = JSON.parse(msg.content);
            if (msg.contentType === 'text') return parsed.body;
            return '[Complex Content]';
        } catch {
            return msg.content;
        }
    };

    return (
        <Layout>
            <div className="max-w-2xl mx-auto mt-8 px-4">
                <h1 className="text-xl font-semibold mb-6 text-charcoal-700">Message History</h1>

                {loading ? (
                    <div>Loading...</div>
                ) : messages.length === 0 ? (
                    <div className="text-center text-gray-500 py-12">No messages sent yet.</div>
                ) : (
                    <div className="space-y-4">
                        {messages.map(msg => (
                            <div key={msg.id} className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
                                <p className="font-handwriting text-lg text-charcoal-800 mb-2">
                                    {parseContent(msg)}
                                </p>
                                <div className="flex justify-between items-center text-xs text-gray-400">
                                    <span>{new Date(msg.createdAt).toLocaleString()}</span>
                                    <span className={`px-2 py-1 rounded-full ${msg.status === 'printed' ? 'bg-green-100 text-green-700' :
                                        msg.status === 'sent' ? 'bg-blue-100 text-blue-700' :
                                            'bg-gray-100 text-gray-600'
                                        }`}>
                                        {msg.status}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </Layout>
    );
}
