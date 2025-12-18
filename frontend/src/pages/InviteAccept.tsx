import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { acceptInvite, getInviteDetails } from '../api/client';
import { useAuth } from '../context/AuthContext';
import logoHorizontal from '../assets/logo-horizontal.png';

interface InviteDetails {
    token: string;
    status: string;
    inviteeEmail?: string | null;
    device: { id: string; friendlyName: string };
    inviter: { id: string; name: string; email: string };
}

export function InviteAccept() {
    const { token } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const { user } = useAuth();
    const [invite, setInvite] = useState<InviteDetails | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [accepting, setAccepting] = useState(false);
    const [accepted, setAccepted] = useState(false);

    const loginState = useMemo(() => ({ from: location }), [location]);

    useEffect(() => {
        async function loadInvite() {
            try {
                const data = await getInviteDetails(token!);
                setInvite(data);
                setAccepted(data.status === 'accepted');
            } catch (err: any) {
                setError(err.response?.data?.error || 'Invite not found');
            } finally {
                setLoading(false);
            }
        }
        if (token) loadInvite();
    }, [token]);

    const handleAccept = async () => {
        if (!user || !invite) return;
        setAccepting(true);
        setError('');
        try {
            const result = await acceptInvite(invite.token);
            if (result.status === 'accepted') {
                setAccepted(true);
                setInvite({ ...invite, status: 'accepted' });
                setTimeout(() => navigate('/'), 800);
            }
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to accept invite');
        } finally {
            setAccepting(false);
        }
    };

    return (
        <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4">
            <div className="max-w-lg w-full bg-white rounded-2xl shadow-sm border border-neutral-100 p-8">
                <div className="text-center mb-6">
                    <img src={logoHorizontal} alt="PaperDrop" className="h-20 w-auto mx-auto mb-4" />
                    <h1 className="text-2xl font-bold text-neutral-900">Printer invite</h1>
                    <p className="text-neutral-600 mt-1">Join a friend on their PaperDrop.</p>
                </div>

                {loading ? (
                    <div className="text-center text-neutral-500">Loading invite...</div>
                ) : error ? (
                    <div className="text-red-600 text-center">{error}</div>
                ) : invite ? (
                    <div className="space-y-4">
                        <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-4">
                            <p className="text-sm text-neutral-600">Printer</p>
                            <p className="text-lg font-semibold text-neutral-900">{invite.device.friendlyName}</p>
                            <p className="text-sm text-neutral-500 mt-1">Invited by {invite.inviter.name} ({invite.inviter.email})</p>
                            {invite.inviteeEmail && (
                                <p className="text-xs text-neutral-400 mt-1">Invite sent to {invite.inviteeEmail}</p>
                            )}
                        </div>

                        {accepted ? (
                            <div className="bg-green-50 border border-green-200 text-green-700 p-4 rounded-xl text-center">
                                You're all set! Redirecting to your dashboard...
                            </div>
                        ) : user ? (
                            <button
                                onClick={handleAccept}
                                disabled={accepting}
                                className="w-full bg-primary-600 hover:bg-primary-700 text-white font-medium py-3 rounded-xl transition disabled:opacity-50"
                            >
                                {accepting ? 'Joining...' : 'Accept invite'}
                            </button>
                        ) : (
                            <div className="space-y-3">
                                <p className="text-sm text-neutral-600 text-center">Login or create an account to accept this invite.</p>
                                <div className="grid grid-cols-2 gap-3">
                                    <Link
                                        to="/login"
                                        state={loginState}
                                        className="w-full text-center border border-neutral-200 text-neutral-700 font-medium py-2.5 rounded-xl hover:bg-neutral-50"
                                    >
                                        Login
                                    </Link>
                                    <Link
                                        to="/register"
                                        state={loginState}
                                        className="w-full text-center bg-primary-600 text-white font-medium py-2.5 rounded-xl hover:bg-primary-700"
                                    >
                                        Register
                                    </Link>
                                </div>
                            </div>
                        )}
                    </div>
                ) : null}
            </div>
        </div>
    );
}
