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
        console.log('New connection attempt');

        try {
            const parsedUrl = url.parse(req.url || '', true);
            const query = parsedUrl.query;

            const deviceCode = (query['deviceCode'] as string) || (req.headers['x-device-code'] as string);
            const deviceSecret = (query['deviceSecret'] as string) || (req.headers['x-device-secret'] as string);

            if (!deviceCode || !deviceSecret) {
                console.log('Connection rejected: Missing credentials');
                ws.close(4001, 'Missing authentication');
                return;
            }

            // Verify or Create device
            let device;
            try {
                device = await prisma.device.findUnique({
                    where: { deviceCode }
                });
            } catch (e) {
                console.error('Prisma findUnique error:', e);
                ws.close(4005, 'DB Error: findUnique');
                return;
            }

            if (!device) {
                console.log(`New device verified: ${deviceCode}`);
                try {
                    device = await prisma.device.create({
                        data: {
                            deviceCode,
                            deviceSecret,
                            status: 'online',
                            friendlyName: 'New Printer',
                            lastSeenAt: new Date()
                        }
                    });
                } catch (e) {
                    console.error('Prisma create error:', e);
                    ws.close(4006, 'DB Error: create');
                    return;
                }
            } else if (device.deviceSecret !== deviceSecret) {
                if (!device.ownerId) {
                    console.log(`Updating secret for unclaimed device: ${deviceCode}`);
                    try {
                        device = await prisma.device.update({
                            where: { id: device.id },
                            data: { deviceSecret }
                        });
                    } catch (e) {
                        console.error('Prisma update secret error:', e);
                        ws.close(4007, 'DB Error: update secret');
                        return;
                    }
                } else {
                    console.log(`Connection rejected: Secret mismatch for ${deviceCode}`);
                    ws.close(4003, 'Secret mismatch');
                    return;
                }
            }

            const deviceId = device.id;
            console.log(`Device connected: ${deviceCode} (${deviceId})`);
            deviceConnections.set(deviceId, ws);

            ws.on('message', (message) => {
                try {
                    const data = JSON.parse(message.toString());
                    console.log(`Received from ${deviceCode}:`, data.type);
                    // Handle message in a separate async call to not block
                    handleDeviceMessage(deviceId, data).catch(e => {
                        console.error('handleDeviceMessage error:', e);
                    });
                } catch (e) {
                    console.error('JSON parse error:', e);
                }
            });

            ws.on('close', (code, reason) => {
                console.log(`Device disconnected: ${deviceCode} (Code: ${code}, Reason: ${reason})`);
                deviceConnections.delete(deviceId);
            });

            ws.on('error', (err) => {
                console.error(`WebSocket error for ${deviceCode}:`, err);
            });

        } catch (error) {
            console.error('Critical error in WebSocket connection handler:', error);
            ws.close(1011, 'Internal server error');
        }
    });
};

const handleDeviceMessage = async (deviceId: string, message: any) => {
    if (message.type === 'device_hello') {
        console.log('Handling device_hello for', deviceId);
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
