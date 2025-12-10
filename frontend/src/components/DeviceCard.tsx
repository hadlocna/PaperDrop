import { Link } from 'react-router-dom';

interface Device {
    id: string;
    friendlyName: string;
    status: string; // 'online' | 'offline' | 'setup_pending'
}

interface DeviceCardProps {
    device: Device;
}

export function DeviceCard({ device }: DeviceCardProps) {
    const isOnline = device.status === 'online';

    return (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-4">
                <div>
                    <h3 className="text-lg font-semibold text-charcoal-700">{device.friendlyName}</h3>
                    <div className="flex items-center gap-2 mt-1">
                        <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <span className="text-sm text-gray-500 capitalize">{device.status?.replace('_', ' ')}</span>
                    </div>
                </div>
                <div className="text-2xl">
                    {isOnline ? '🏠' : '😴'}
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
                <Link
                    to={`/device/${device.id}/compose`}
                    className="flex justify-center items-center py-2 px-4 bg-coral-500 text-white rounded-xl font-medium hover:bg-coral-600 transition"
                >
                    Send Note
                </Link>
                <Link
                    to={`/device/${device.id}/history`}
                    className="flex justify-center items-center py-2 px-4 bg-sand-100 text-charcoal-600 rounded-xl font-medium hover:bg-sand-200 transition"
                >
                    History
                </Link>
            </div>
            <div className="mt-3 text-center">
                <Link to={`/device/${device.id}/settings`} className="text-xs text-gray-400 hover:text-gray-600">
                    Settings
                </Link>
            </div>
        </div>
    );
}
