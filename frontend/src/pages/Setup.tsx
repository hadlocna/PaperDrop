import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';

export function Setup() {
    const [deviceCode, setDeviceCode] = useState('');
    const [friendlyName, setFriendlyName] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const { user } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            await api.post('/devices/claim', {
                deviceCode,
                friendlyName,
                userId: user?.id
            });
            navigate('/');
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to claim device');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Layout>
            <div className="max-w-md mx-auto mt-12 p-6 bg-white rounded-2xl shadow-sm">
                <h1 className="text-2xl font-semibold mb-6 text-charcoal-700">Claim your PaperDrop</h1>

                {error && (
                    <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-charcoal-500 mb-1">
                            Device Code
                        </label>
                        <input
                            type="text"
                            value={deviceCode}
                            onChange={(e) => setDeviceCode(e.target.value.toUpperCase())}
                            placeholder="PD-XXXXXX"
                            className="w-full px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none uppercase"
                            required
                        />
                        <p className="text-xs text-gray-400 mt-1">Found on the bottom of your device or startup print.</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-charcoal-500 mb-1">
                            Give it a name
                        </label>
                        <input
                            type="text"
                            value={friendlyName}
                            onChange={(e) => setFriendlyName(e.target.value)}
                            placeholder="e.g. Grandma's House"
                            className="w-full px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-coral-500 outline-none"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 bg-coral-500 text-white font-medium rounded-xl hover:bg-coral-600 transition disabled:opacity-50"
                    >
                        {loading ? 'Claiming...' : 'Claim Device'}
                    </button>
                </form>
            </div>
        </Layout>
    );
}
