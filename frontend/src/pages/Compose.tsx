import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';

export function Compose() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [message, setMessage] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');

    const handleSend = async () => {
        if (!message.trim()) return;
        setSending(true);
        setError('');

        try {
            await api.post('/messages', {
                deviceId: id,
                senderId: user?.id,
                contentType: 'text',
                content: {
                    body: message,
                    timestamp: true
                }
            });
            navigate('/');
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to send');
            setSending(false);
        }
    };

    return (
        <Layout>
            <div className="max-w-2xl mx-auto mt-8 px-4">
                <div className="bg-white rounded-2xl shadow-sm p-6">
                    <h1 className="text-xl font-semibold mb-4 text-charcoal-700">New Message</h1>

                    {error && (
                        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    <div className="mb-4">
                        <div className="border border-gray-200 rounded-xl p-4 min-h-[200px] flex flex-col">
                            <textarea
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                placeholder="Type your message here..."
                                className="w-full h-full resize-none outline-none text-lg font-handwriting"
                                autoFocus
                                maxLength={500}
                            />
                            <div className="text-right text-xs text-gray-400 mt-2">
                                {message.length}/500
                            </div>
                        </div>
                    </div>

                    <div className="flex justify-end gap-3">
                        <button
                            onClick={() => navigate('/')}
                            className="px-6 py-2 text-charcoal-500 hover:bg-gray-50 rounded-xl font-medium"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSend}
                            disabled={sending || !message.trim()}
                            className="px-6 py-2 bg-coral-500 text-white font-medium rounded-xl hover:bg-coral-600 transition disabled:opacity-50"
                        >
                            {sending ? 'Sending...' : 'Send Now'}
                        </button>
                    </div>
                </div>
            </div>
        </Layout>
    );
}
