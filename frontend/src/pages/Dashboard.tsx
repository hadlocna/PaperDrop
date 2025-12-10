import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { DeviceCard } from '../components/DeviceCard';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';

interface Device {
    id: string;
    friendlyName: string;
    status: string;
    deviceCode: string;
    ownerId: string;
}

export function Dashboard() {
    const { user } = useAuth();
    const [devices, setDevices] = useState<Device[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!user) return;

        async function fetchDevices() {
            try {
                const res = await api.get('/devices', {
                    params: { userId: user?.id }
                });
                setDevices(res.data);
            } catch (error) {
                console.error('Failed to fetch devices:', error);
            } finally {
                setLoading(false);
            }
        }

        fetchDevices();
    }, [user]);

    return (
        <Layout>
            <div className="max-w-4xl mx-auto p-4 sm:p-6 lg:p-8">
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-2xl font-semibold text-charcoal-700">Your Devices</h1>
                    <Link
                        to="/setup"
                        className="flex items-center gap-2 px-4 py-2 bg-charcoal-800 text-white rounded-xl hover:bg-charcoal-700 transition"
                    >
                        <span>+ Add Device</span>
                    </Link>
                </div>

                {loading ? (
                    <div className="text-center py-12">Loading...</div>
                ) : devices.length === 0 ? (
                    <div className="text-center py-16 bg-white rounded-3xl border border-dashed border-gray-200">
                        <div className="text-4xl mb-4">📭</div>
                        <h2 className="text-lg font-medium text-charcoal-700 mb-2">No devices yet</h2>
                        <p className="text-gray-500 mb-6">Claim your first PaperDrop to get started.</p>
                        <Link
                            to="/setup"
                            className="inline-flex items-center gap-2 px-6 py-3 bg-coral-500 text-white rounded-xl font-medium hover:bg-coral-600 transition"
                        >
                            Claim Device
                        </Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {devices.map(device => (
                            <DeviceCard key={device.id} device={device} />
                        ))}
                    </div>
                )}
            </div>
        </Layout>
    );
}
