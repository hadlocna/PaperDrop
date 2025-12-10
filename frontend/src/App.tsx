import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Register } from './pages/Register';

function Dashboard() {
    return (
        <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
            <div className="text-center p-8">
                <h1 className="text-4xl font-bold text-charcoal-500 mb-4">📜 PaperDrop</h1>
                <p className="text-gray-600">Welcome to your PaperDrop dashboard.</p>
            </div>
        </div>
    );
}

function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/register" element={<Register />} />
                <Route path="/dashboard" element={<Navigate to="/" replace />} />
            </Routes>
        </Router>
    );
}

export default App;
