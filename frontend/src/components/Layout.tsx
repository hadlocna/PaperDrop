import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface LayoutProps {
    children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div className="min-h-screen bg-sand-50 text-charcoal-500 font-sans">
            <nav className="bg-white shadow-sm sticky top-0 z-10">
                <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
                    <Link to="/" className="flex items-center gap-2 text-xl font-semibold text-charcoal-700">
                        <span className="text-2xl">📜</span>
                        PaperDrop
                    </Link>

                    <div className="flex items-center gap-4">
                        {user && (
                            <>
                                <span className="text-sm font-medium text-charcoal-500 hidden sm:block">
                                    {user.name}
                                </span>
                                <button
                                    onClick={handleLogout}
                                    className="text-sm text-charcoal-400 hover:text-coral-500 transition-colors"
                                >
                                    Sign Out
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </nav>

            <main className="w-full">
                {children}
            </main>
        </div>
    );
}
