import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Register } from './pages/Register';
import { Login } from './pages/Login';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Dashboard } from './pages/Dashboard';
import { Setup } from './pages/Setup';
import { Compose } from './pages/Compose';
import { History } from './pages/History';
import { DeviceSettings } from './pages/DeviceSettings';

import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth();
    const location = useLocation();

    if (isLoading) {
        return <div>Loading...</div>; // Or a nice spinner
    }

    if (!user) {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }

    return <>{children}</>;
}

function App() {
    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route
                        path="/"
                        element={
                            <ProtectedRoute>
                                <Dashboard />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/setup"
                        element={
                            <ProtectedRoute>
                                <Setup />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/device/:id/compose"
                        element={
                            <ProtectedRoute>
                                <Compose />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/device/:id/history"
                        element={
                            <ProtectedRoute>
                                <History />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/device/:id/settings"
                        element={
                            <ProtectedRoute>
                                <DeviceSettings />
                            </ProtectedRoute>
                        }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </Router>
        </AuthProvider>
    );
}

export default App;
