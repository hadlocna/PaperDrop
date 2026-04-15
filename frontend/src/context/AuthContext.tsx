import React, { createContext, useContext, useState, useEffect } from 'react';
import { AUTH_EXPIRED_EVENT } from '../auth/events';


interface User {
    id: string;
    name: string;
    email: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (data: { user: User; token: string }) => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const clearSession = () => {
        localStorage.removeItem('user');
        localStorage.removeItem('token');
        setUser(null);
        setToken(null);
    };

    useEffect(() => {
        // Load user and token from local storage
        const storedUser = localStorage.getItem('user');
        const storedToken = localStorage.getItem('token');

        if (storedUser && storedToken && storedUser !== 'undefined') {
            try {
                setUser(JSON.parse(storedUser));
                setToken(storedToken);
            } catch (e) {
                console.error('Failed to parse stored user:', e);
                clearSession();
            }
        }
        setIsLoading(false);
    }, []);

    useEffect(() => {
        const handleAuthExpired = () => {
            clearSession();
        };

        const handleStorage = (event: StorageEvent) => {
            if (event.key === 'token' && event.newValue === null) {
                clearSession();
            }
        };

        window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
        window.addEventListener('storage', handleStorage);

        return () => {
            window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
            window.removeEventListener('storage', handleStorage);
        };
    }, []);

    const login = (data: { user: User; token: string }) => {
        localStorage.setItem('user', JSON.stringify(data.user));
        localStorage.setItem('token', data.token);
        setUser(data.user);
        setToken(data.token);
    };

    const logout = () => {
        clearSession();
    };

    return (
        <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
