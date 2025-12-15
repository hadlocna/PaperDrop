import { WebSocket, WebSocketServer } from 'ws';
import { IncomingMessage } from 'http';
import url from 'url';
import { prisma } from '../lib/prisma';
import { Server } from 'http';
import { deviceConnections, shellSessions } from './session';

export const setupWebSocket = (server: Server) => {
    const wss = new WebSocketServer({ server, path: '/api/device/connect' });

    wss.on('connection', async (ws: WebSocket, req: IncomingMessage) => {
        // Extract device ID and secret from query params or headers
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
            // Close any shell session
            const adminWs = shellSessions.get(deviceId);
            if (adminWs) {
                shellSessions.delete(deviceId);
                if (adminWs.readyState === WebSocket.OPEN) {
                    adminWs.send(JSON.stringify({ type: 'device_disconnected', deviceId }));
                }
            }

            // Update status to offline
            await prisma.device.update({
                where: { id: deviceId },
                data: { status: 'offline' }
            });
        });
    });
};

const handleDeviceMessage = async (deviceId: string, message: any) => {
    // console.log(`Received from ${deviceId}:`, message.type);

    if (message.type === 'device_hello') {
        // Update device info
        await prisma.device.update({
            where: { id: deviceId },
            data: {
                firmwareVersion: message.firmware_version,
                macAddress: message.mac_address,
                lastSeenAt: new Date()
            }
        });
    }
    else if (message.type === 'print_status') {
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
    else if (message.type === 'shell_output') {
        // Forward to admin
        const adminWs = shellSessions.get(deviceId);
        if (adminWs && adminWs.readyState === WebSocket.OPEN) {
            adminWs.send(JSON.stringify({ type: 'shell_output', deviceId: deviceId, data: message.data }));
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
