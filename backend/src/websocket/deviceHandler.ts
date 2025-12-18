import { WebSocket, WebSocketServer } from 'ws';
import { IncomingMessage } from 'http';
import url from 'url';
import { prisma } from '../lib/prisma';
import { Server } from 'http';
import crypto from 'crypto';
import { deviceConnections, shellSessions } from './session';

type PendingLogRequest = {
    resolve: (payload: any) => void;
    reject: (error: Error) => void;
    timer: NodeJS.Timeout;
};

const pendingLogRequests = new Map<string, PendingLogRequest>();

export const setupWebSocket = (server: Server) => {
    const wss = new WebSocketServer({ server, path: '/api/device/connect' });

    wss.on('connection', async (ws: WebSocket, req: IncomingMessage) => {
        // Attach listeners immediately to avoid race conditions
        ws.on('message', async (message) => {
            try {
                const data = JSON.parse(message.toString());
                // We'll handle it later once we have deviceId
            } catch (e) {
                console.error('Error handling device message:', e);
            }
        });

        try {
            const parsedUrl = url.parse(req.url || '', true);
            const query = parsedUrl.query;

            // Extract device ID and secret from query params or headers
            const deviceCode = (query['deviceCode'] as string) || (req.headers['x-device-code'] as string);
            const deviceSecret = (query['deviceSecret'] as string) || (req.headers['x-device-secret'] as string);

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
                // If the device is not yet claimed, allow updating the secret
                if (!device.ownerId) {
                    console.log(`Updating secret for unclaimed device: ${deviceCode}`);
                    device = await prisma.device.update({
                        where: { id: device.id },
                        data: { deviceSecret }
                    });
                } else {
                    console.log(`Connection rejected: Invalid credentials for ${deviceCode}`);
                    ws.close(4003, 'Invalid authentication: secret mismatch');
                    return;
                }
            }

            const deviceId = device.id;
            console.log(`Device connected: ${deviceCode} (${deviceId})`);

            deviceConnections.set(deviceId, ws);

            // Update status to online
            try {
                await prisma.device.update({
                    where: { id: deviceId },
                    data: { status: 'online', lastSeenAt: new Date() }
                });
            } catch (e) {
                console.error('Error updating device status:', e);
            }

            // Send pending messages
            try {
                const pendingMessages = await prisma.message.findMany({
                    where: {
                        deviceId: deviceId,
                        status: 'queued'
                    },
                    orderBy: { createdAt: 'asc' }
                });

                for (const message of pendingMessages) {
                    let content = message.content;
                    try {
                        content = JSON.parse(message.content);
                    } catch (e) {
                    }

                    const broadcastResult = broadcastToDevice(deviceId, {
                        type: 'new_message',
                        message: {
                            id: message.id,
                            content: content,
                            contentType: message.contentType,
                            createdAt: message.createdAt
                        }
                    });

                    if (broadcastResult) {
                        await prisma.message.update({
                            where: { id: message.id },
                            data: { status: 'sent', sentAt: new Date() }
                        });
                    }
                }
            } catch (e) {
                console.error('Error sending pending messages:', e);
            }

            // Re-attach proper message handler with deviceId
            ws.removeAllListeners('message');
            ws.on('message', async (message) => {
                try {
                    const data = JSON.parse(message.toString());
                    await handleDeviceMessage(deviceId, data);
                } catch (e) {
                    console.error('Error handling device message:', e);
                }
            });

            ws.on('close', async () => {
                console.log(`Device disconnected: ${deviceCode}`);
                deviceConnections.delete(deviceId);

                // Update status to offline
                try {
                    await prisma.device.update({
                        where: { id: deviceId },
                        data: { status: 'offline' }
                    });
                } catch (e) {
                    console.error('Error updating device offline status:', e);
                }
            });
        } catch (error) {
            console.error('Critical error in WebSocket connection handler:', error);
            ws.close(1011, 'Internal server error');
        }
    });
};

const handleDeviceMessage = async (deviceId: string, message: any) => {
    // console.log(`Received from ${deviceId}:`, message.type);

    if (message.type === 'device_hello') {
        // Update device info
        try {
            await prisma.device.update({
                where: { id: deviceId },
                data: {
                    firmwareVersion: message.firmware_version,
                    lastSeenAt: new Date()
                }
            });
        } catch (e) {
            console.error('Error updating device hello:', e);
        }
    }
    else if (message.type === 'print_status') {
        try {
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
        } catch (e) {
            console.error('Error updating print status:', e);
        }
    }
    else if (message.type === 'heartbeat') {
        try {
            await prisma.device.update({
                where: { id: deviceId },
                data: {
                    status: 'online',
                    lastSeenAt: new Date(),
                    firmwareVersion: message.firmware_version
                }
            });
        } catch (e) {
            console.error('Error updating device heartbeat:', e);
        }
    }
    else if (message.type === 'shell_output') {
        // Forward to admin
        const adminWs = shellSessions.get(deviceId);
        if (adminWs && adminWs.readyState === WebSocket.OPEN) {
            adminWs.send(JSON.stringify({ type: 'shell_output', deviceId: deviceId, data: message.data }));
        }
    }
    else if (message.type === 'log_bundle' && message.request_id) {
        const pending = pendingLogRequests.get(message.request_id);
        if (pending) {
            clearTimeout(pending.timer);
            pending.resolve(message);
            pendingLogRequests.delete(message.request_id);
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

export const requestLogsFromDevice = async (
    deviceId: string,
    options: { type: string; lines: number }
) => {
    const requestId = crypto.randomUUID();

    return new Promise<any>((resolve, reject) => {
        const success = broadcastToDevice(deviceId, {
            type: 'fetch_logs',
            request_id: requestId,
            log_type: options.type,
            lines: options.lines
        });

        if (!success) {
            return reject(new Error('device_offline'));
        }

        const timer = setTimeout(() => {
            pendingLogRequests.delete(requestId);
            reject(new Error('device_timeout'));
        }, 15000);

        pendingLogRequests.set(requestId, { resolve, reject, timer });
    });
};
