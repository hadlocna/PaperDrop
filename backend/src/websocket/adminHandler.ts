import { WebSocket, WebSocketServer } from 'ws';
import { IncomingMessage } from 'http';
import { Server } from 'http';
import { broadcastToDevice } from './deviceHandler';
import { deviceConnections, shellSessions } from './session';

export const adminConnections = new Set<WebSocket>();

export const setupAdminWebSocket = () => {
    // Use noServer: true to handle upgrade manually in server.ts
    const adminWss = new WebSocketServer({ noServer: true });

    adminWss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
        const url = new URL(req.url || '', 'http://localhost');
        const password = url.searchParams.get('password');

        if (password !== 'nathan') {
            ws.close(4001, 'Unauthorized');
            return;
        }

        console.log('Admin connected');
        adminConnections.add(ws);

        ws.on('message', (message) => {
            try {
                const data = JSON.parse(message.toString());
                handleAdminMessage(ws, data);
            } catch (e) {
                console.error('Error parsing admin message:', e);
            }
        });

        ws.on('close', () => {
            console.log('Admin disconnected');
            adminConnections.delete(ws);
            // Cleanup shell sessions
            for (const [deviceId, adminWs] of shellSessions.entries()) {
                if (adminWs === ws) {
                    shellSessions.delete(deviceId);
                    broadcastToDevice(deviceId, { type: 'stop_shell' });
                }
            }
        });
    });

    return adminWss;
};

const handleAdminMessage = (ws: WebSocket, message: any) => {
    const { type, deviceId, payload } = message;

    if (type === 'start_shell') {
        if (!deviceConnections.has(deviceId)) {
            ws.send(JSON.stringify({ type: 'error', message: 'Device offline' }));
            return;
        }
        shellSessions.set(deviceId, ws);
        broadcastToDevice(deviceId, { type: 'start_shell' });
    }
    else if (type === 'shell_input') {
        broadcastToDevice(deviceId, { type: 'shell_input', data: payload });
    }
    else if (type === 'resize_shell') {
        broadcastToDevice(deviceId, { type: 'resize_shell', cols: payload.cols, rows: payload.rows });
    }
    else if (type === 'stop_shell') {
        shellSessions.delete(deviceId);
        broadcastToDevice(deviceId, { type: 'stop_shell' });
    }
};

export const sendShellOutputToAdmin = (deviceId: string, data: string) => {
    const adminWs = shellSessions.get(deviceId);
    if (adminWs && adminWs.readyState === WebSocket.OPEN) {
        adminWs.send(JSON.stringify({ type: 'shell_output', deviceId, data }));
    }
};
