import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import userRoutes from './routes/users';
import deviceRoutes from './routes/devices';

const app = express();
const server = createServer(app);

// WebSocket server for device connections
const wss = new WebSocketServer({ server, path: '/api/device/connect' });

wss.on('connection', (ws) => {
    console.log('New device connection');
    ws.on('message', (message) => {
        console.log('Received:', message.toString());
    });
});

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

app.use('/api/users', userRoutes);
app.use('/api/devices', deviceRoutes);

// Basic health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok', version: '1.0.0' });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`PaperDrop API running on port ${PORT}`);
});
