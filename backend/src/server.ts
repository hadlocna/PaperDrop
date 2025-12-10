import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import userRoutes from './routes/users';
import deviceRoutes from './routes/devices';
import authRoutes from './routes/auth';
import messageRoutes from './routes/messages';
import { WebSocket } from 'ws';
import { IncomingMessage } from 'http';
import url from 'url';
import { setupWebSocket } from './websocket/deviceHandler';
const app = express();
const server = createServer(app);

// Setup WebSocket
setupWebSocket(server);

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

app.use('/api/users', userRoutes);
app.use('/api/devices', deviceRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/messages', messageRoutes);

// Basic health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok', version: '1.0.0' });
});

// Start scheduled message processor
import { scheduledMessageProcessor } from './jobs/scheduledMessages';
scheduledMessageProcessor.start();

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`PaperDrop API running on port ${PORT}`);
});
