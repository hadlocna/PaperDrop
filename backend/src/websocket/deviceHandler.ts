import { WebSocket, WebSocketServer } from 'ws';
import { IncomingMessage } from 'http';
import { Server } from 'http';
import { deviceConnections } from './session';

export const setupWebSocket = (server: Server) => {
    const wss = new WebSocketServer({ server, path: '/api/device/connect' });

    wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
        console.log('DEBUG: New connection attempt');

        ws.on('message', (message) => {
            console.log('DEBUG: Received:', message.toString());
            try {
                const data = JSON.parse(message.toString());
                if (data.type === 'device_hello') {
                    ws.send(JSON.stringify({ type: 'ack', message: 'Hello received' }));
                }
            } catch (e) {
                console.error('DEBUG: JSON parse error');
            }
        });

        ws.on('close', (code, reason) => {
            console.log(`DEBUG: Closed (Code: ${code}, Reason: ${reason})`);
        });

        ws.on('error', (err) => {
            console.error('DEBUG: Error:', err);
        });
    });
};

export const broadcastToDevice = (deviceId: string, data: any): boolean => {
    const ws = deviceConnections.get(deviceId);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
        return true;
    }
    return false;
};

export const requestLogsFromDevice = async (deviceId: string, options: any) => {
    throw new Error('Not implemented in debug mode');
};
