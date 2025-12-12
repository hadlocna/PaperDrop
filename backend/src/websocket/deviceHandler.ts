import { WebSocket, WebSocketServer } from 'ws';
import { IncomingMessage } from 'http';
import url from 'url';
import { prisma } from '../lib/prisma';
import { Server } from 'http';

// Map device IDs to WebSocket connections
export const deviceConnections = new Map<string, WebSocket>();

export const setupWebSocket = (server: Server) => {
    const wss = new WebSocketServer({ server, path: '/api/device/connect' });

    wss.on('connection', async (ws: WebSocket, req: IncomingMessage) => {
        // Extract device ID and secret from query params or headers
        // Spec says Headers: X-Device-Code, X-Device-Secret
        // But `server.ts` was using query param?
        // Agent `agent.py` uses `extra_headers`.
        // Let's implement Auth based on Spec (Headers).

        // request headers are incomingmessage
        const deviceCode = req.headers['x-device-code'] as string;
        const deviceSecret = req.headers['x-device-secret'] as string;

        if (!deviceCode || !deviceSecret) {
            console.log('Connection rejected: Missing credentials');
            ws.close(4001, 'Missing authentication');
            return;
        }

        // Verify or Create device
        let device = await prisma.device.findUnique({
            where: { deviceCode }
        });

        if (!device) {
            console.log(`New device verified: ${deviceCode}`);
            // Create new device
            device = await prisma.device.create({
                data: {
                    deviceCode,
                    deviceSecret,
                    status: 'online',
                    friendlyName: 'New Printer',
                    lastSeenAt: new Date()
                }
            });
        } else if (device.deviceSecret !== deviceSecret) {
            console.log(`Connection rejected: Invalid credentials for ${deviceCode}`);
            ws.close(4001, 'Invalid authentication');
            return;
        }

        const deviceId = device.id;
        console.log(`Device connected: ${deviceCode} (${deviceId})`);

        deviceConnections.set(deviceId, ws);

        // Update status to online
        await prisma.device.update({
            where: { id: deviceId },
            data: { status: 'online', lastSeenAt: new Date() }
        });

        ws.on('message', async (message) => {
            try {
                const data = JSON.parse(message.toString());
                handleDeviceMessage(deviceId, data);
            } catch (e) {
                console.error('Error parsing device message:', e);
            }
        });

        ws.on('close', async () => {
            console.log(`Device disconnected: ${deviceCode}`);
            deviceConnections.delete(deviceId);
            // Update status to offline
            await prisma.device.update({
                where: { id: deviceId },
                data: { status: 'offline' }
            });
        });

        // Initial Hello / Config sync could go here
    });
};

const handleDeviceMessage = async (deviceId: string, message: any) => {
    console.log(`Received from ${deviceId}:`, message);

    if (message.type === 'print_status') {
        // Update message status
        // message.message_id, message.status, message.error
        if (message.message_id) {
            await prisma.message.update({
                where: { id: message.message_id },
                data: {
                    status: message.status,
                    errorMessage: message.error || null,
                    printedAt: message.status === 'printed' ? new Date() : null
                }
            });
        }
    }
};

export const broadcastToDevice = (deviceId: string, data: any): boolean => {
    const ws = deviceConnections.get(deviceId);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
        return true;
    }
    return false;
};
