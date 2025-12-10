import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';

export function DeviceSettings() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [device, setDevice] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadDevice() {
            try {
                const res = await api.get(`/devices/${id}`, {
                    params: { userId: user?.id }
                });
                setDevice(res.data);
            } catch (err) {
                console.error(err);
                navigate('/');
            } finally {
                setLoading(false);
            }
        }
        if (user?.id) loadDevice();
    }, [id, user?.id, navigate]);

    if (loading) return <Layout><div>Loading...</div></Layout>;
    if (!device) return <Layout><div>Device not found</div></Layout>;

    return (
        <Layout>
            <div className="max-w-2xl mx-auto mt-8 px-4">
                <h1 className="text-xl font-semibold mb-6 text-charcoal-700">Settings: {device.friendlyName}</h1>

                <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                    <h2 className="text-lg font-medium mb-4">Device Info</h2>
                    <p>Connect Code: <span className="font-mono bg-gray-100 px-2 py-1 rounded">{device.deviceCode}</span></p>
                    <p className="mt-2">Status: {device.status}</p>
                </div>

                {/* Invite Sender Section (Placeholder) */}
                <div className="bg-white rounded-2xl p-6 shadow-sm">
                    <h2 className="text-lg font-medium mb-4">Sharing</h2>
                    <p className="text-gray-500">Invite functionality coming soon.</p>
                </div>
            </div>
        </Layout>
    );
}
