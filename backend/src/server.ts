import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import userRoutes from './routes/users';
import deviceRoutes from './routes/devices';
import authRoutes from './routes/auth';
import messageRoutes from './routes/messages';
import aiRoutes from './routes/aiRoutes';
import adminRoutes from './routes/admin';
import inviteRoutes from './routes/invites';
import { WebSocket } from 'ws';
import { IncomingMessage } from 'http';
import url from 'url';
import { setupWebSocket } from './websocket/deviceHandler';
import { setupAdminWebSocket } from './websocket/adminHandler';
import { prisma } from './lib/prisma';

const app = express();
const server = createServer(app);

process.on('uncaughtException', (err) => {
    console.error('UNCAUGHT EXCEPTION:', err);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('UNHANDLED REJECTION at:', promise, 'reason:', reason);
});

// Setup WebSockets
const deviceWss = setupWebSocket();
const adminWss = setupAdminWebSocket();

// Handle WebSocket upgrades manually
server.on('upgrade', (request, socket, head) => {
    const { pathname } = url.parse(request.url || '');

    if (pathname === '/api/device/connect') {
        deviceWss.handleUpgrade(request, socket, head, (ws) => {
            deviceWss.emit('connection', ws, request);
        });
    } else if (pathname === '/api/admin/connect') {
        adminWss.handleUpgrade(request, socket, head, (ws) => {
            adminWss.emit('connection', ws, request);
        });
    } else {
        socket.destroy();
    }
});

// Middleware
app.use(helmet());
app.use(cors({
    origin: [
        'https://paperdrop.me',
        'https://www.paperdrop.me',
        'https://paperdrop-frontend.onrender.com',
        'http://localhost:5173',
        'http://localhost:3000'
    ],
    credentials: true
}));
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

app.use('/api/users', userRoutes);
app.use('/api/devices', deviceRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/messages', messageRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/ai', aiRoutes);
app.use('/api/invites', inviteRoutes);

// Serve uploaded firmware files
import path from 'path';
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

// Basic health check
app.get('/health', async (req, res) => {
    try {
        const deviceCount = await prisma.device.count();
        res.json({ status: 'ok', version: '1.0.2', db: 'connected', devices: deviceCount });
    } catch (e) {
        console.error('Health check DB error:', e);
        res.status(500).json({ status: 'error', db: 'disconnected', error: String(e) });
    }
});

// Start scheduled message processor
import { scheduledMessageProcessor } from './jobs/scheduledMessages';
scheduledMessageProcessor.start();

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`PaperDrop API running on port ${PORT}`);
});
