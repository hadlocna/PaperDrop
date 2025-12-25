import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import logoHorizontal from '../assets/logo-horizontal.png';

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
        <div className="h-[100dvh] bg-sand-50 text-charcoal-500 font-sans flex flex-col overflow-hidden">
            <nav className="bg-white shadow-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
                    <Link to="/dashboard" className="flex items-center gap-2 shrink-0">
                        <img src={logoHorizontal} alt="PaperDrop" className="h-10 sm:h-12 w-auto object-contain drop-shadow-sm" />
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

            <main className="flex-1 w-full overflow-hidden">
                {children}
            </main>
        </div>
    );
}
