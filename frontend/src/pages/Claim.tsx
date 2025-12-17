import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Layout } from '../components/Layout';

const API_BASE = import.meta.env.VITE_API_URL || '';

export function Claim() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { isLoading, user } = useAuth();
    const [claiming, setClaiming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const deviceCodeFromUrl = searchParams.get('code');

    // Get the code from URL or from storage (after login redirect)
    const code = deviceCodeFromUrl || sessionStorage.getItem('pendingDeviceCode');

    useEffect(() => {
        // Store the device code in sessionStorage so it persists through login
        if (deviceCodeFromUrl) {
            sessionStorage.setItem('pendingDeviceCode', deviceCodeFromUrl);
        }
    }, [deviceCodeFromUrl]);

    // Note: The ProtectedRoute in App.tsx handles the auth redirect
    // with the proper state, so when user logs in, they'll be redirected back here

    const handleClaim = async () => {
        if (!code) {
            setError('No device code provided');
            return;
        }

        if (!user?.id) {
            setError('You must be logged in to claim a device');
            return;
        }

        setClaiming(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/api/devices/claim`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ deviceCode: code, userId: user.id }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to claim device');
            }

            // Clear the stored code
            sessionStorage.removeItem('pendingDeviceCode');
            setSuccess(true);

            // Redirect to dashboard after a short delay
            setTimeout(() => {
                navigate('/');
            }, 2000);

        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to claim device');
        } finally {
            setClaiming(false);
        }
    };

    if (isLoading) {
        return (
            <Layout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <div className="text-gray-500">Loading...</div>
                </div>
            </Layout>
        );
    }

    if (!code) {
        return (
            <Layout>
                <div className="max-w-md mx-auto mt-12">
                    <div className="bg-white rounded-2xl shadow-lg p-8 text-center">
                        <div className="text-6xl mb-4">❌</div>
                        <h1 className="text-xl font-bold text-gray-800 mb-2">No Device Code</h1>
                        <p className="text-gray-500 mb-6">No device code was provided. Please go back to your device setup.</p>
                        <button
                            onClick={() => navigate('/')}
                            className="bg-gray-500 text-white px-6 py-3 rounded-xl font-medium"
                        >
                            Go to Dashboard
                        </button>
                    </div>
                </div>
            </Layout>
        );
    }

    if (success) {
        return (
            <Layout>
                <div className="max-w-md mx-auto mt-12">
                    <div className="bg-white rounded-2xl shadow-lg p-8 text-center">
                        <div className="text-6xl mb-4">🎉</div>
                        <h1 className="text-xl font-bold text-emerald-600 mb-2">Device Added!</h1>
                        <p className="text-gray-500 mb-2">Your PaperDrop device has been successfully added to your account.</p>
                        <p className="text-gray-400 text-sm">Redirecting to dashboard...</p>
                    </div>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="max-w-md mx-auto mt-12">
                <div className="bg-white rounded-2xl shadow-lg p-8 text-center">
                    <div className="text-6xl mb-4">📱</div>
                    <h1 className="text-xl font-bold text-gray-800 mb-2">Add Your Device</h1>
                    <p className="text-gray-500 mb-6">You're about to add a PaperDrop device to your account.</p>

                    <div className="bg-gradient-to-r from-rose-400 to-teal-400 text-white font-mono text-2xl tracking-widest py-3 px-6 rounded-xl mb-6">
                        {code}
                    </div>

                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl mb-4 text-sm">
                            {error}
                        </div>
                    )}

                    <button
                        onClick={handleClaim}
                        disabled={claiming}
                        className="w-full bg-rose-500 hover:bg-rose-600 text-white px-6 py-4 rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-rose-500/25"
                    >
                        {claiming ? 'Adding Device...' : 'Add Device to My Account'}
                    </button>

                    <button
                        onClick={() => navigate('/')}
                        className="mt-3 text-gray-500 hover:text-gray-700 text-sm"
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </Layout>
    );
}
