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

export const setupWebSocket = () => {
    // Use noServer: true to handle upgrade manually in server.ts
    const wss = new WebSocketServer({ noServer: true });

    wss.on('connection', async (ws: WebSocket, req: IncomingMessage) => {
        console.log(`[WS] CONNECTION ATTEMPT: ${req.url}`);
        let deviceId: string | null = null;
        let deviceCode: string | null = null;

        console.log(`[WS] New connection attempt from ${req.socket.remoteAddress}`);

        // Keep-alive ping every 30 seconds
        const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.ping();
            }
        }, 30000);

        ws.on('pong', () => {
            // Connection is alive
        });

        const messageBuffer: any[] = [];

        // Single message listener to avoid race conditions
        ws.on('message', async (message) => {
            try {
                const data = JSON.parse(message.toString());
                if (deviceId) {
                    await handleDeviceMessage(deviceId, data);
                } else {
                    console.log(`[${deviceCode || 'unknown'}] Buffering message received before verification: ${data.type}`);
                    messageBuffer.push(data);
                }
            } catch (e) {
                console.error(`[${deviceCode || 'unknown'}] Error parsing device message:`, e);
            }
        });

        ws.on('close', async (code, reason) => {
            clearInterval(pingInterval);
            if (deviceCode) {
                console.log(`Device disconnected: ${deviceCode} (Code: ${code}, Reason: ${reason})`);
            }
            if (deviceId) {
                if (deviceConnections.get(deviceId) === ws) {
                    console.log(`Removing ${deviceCode} from active connections`);
                    deviceConnections.delete(deviceId);
                    try {
                        await prisma.device.update({
                            where: { id: deviceId },
                            data: { status: 'offline' }
                        });
                    } catch (e) {
                        console.error('Error updating device offline status:', e);
                    }
                } else {
                    console.log(`Device ${deviceCode} disconnected, but a newer connection is already active. Skipping map deletion.`);
                }
            }
        });

        ws.on('error', (err) => {
            console.error('WebSocket error:', err);
        });

        try {
            const parsedUrl = url.parse(req.url || '', true);
            const query = parsedUrl.query;

            // Extract device ID and secret from query params or headers
            deviceCode = (query['deviceCode'] as string) || (req.headers['x-device-code'] as string);
            const deviceSecret = (query['deviceSecret'] as string) || (req.headers['x-device-secret'] as string);

            if (!deviceCode || !deviceSecret) {
                console.log(`[WS] Connection rejected: Missing credentials (code: ${deviceCode}, secret: ${!!deviceSecret})`);
                ws.close(4001, 'Missing authentication');
                return;
            }

            console.log(`[WS] Verifying device: ${deviceCode}`);

            // Verify or Create device
            let device = await prisma.device.findUnique({
                where: { deviceCode }
            });

            if (!device) {
                console.log(`New device verified: ${deviceCode}`);
                device = await prisma.device.create({
                    data: {
                        deviceCode,
                        deviceSecret,
                        status: 'online',
                        friendlyName: 'New Printer',
                        lastSeenAt: new Date()
                    }
                });
                console.log(`[WS] Created new device: ${deviceCode} (${device.id})`);
            } else if (device.deviceSecret !== deviceSecret) {
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

            deviceId = device.id;
            console.log(`[WS] Device verified: ${deviceCode} (${deviceId})`);

            const oldWs = deviceConnections.get(deviceId);
            if (oldWs && oldWs !== ws) {
                console.log(`[WS] Closing old connection for device: ${deviceCode}`);
                oldWs.close(4009, 'New connection established');
            }
            deviceConnections.set(deviceId, ws);
            console.log(`[WS] Active connections: ${deviceConnections.size}`);

            // Update status to online
            try {
                await prisma.device.update({
                    where: { id: deviceId },
                    data: { status: 'online', lastSeenAt: new Date() }
                });
            } catch (e) {
                console.error(`[${deviceCode}] Error updating device status:`, e);
            }

            // Process buffered messages
            if (messageBuffer.length > 0) {
                console.log(`[${deviceCode}] Processing ${messageBuffer.length} buffered messages`);
                for (const msg of messageBuffer) {
                    try {
                        await handleDeviceMessage(deviceId, msg);
                    } catch (e) {
                        console.error(`[${deviceCode}] Error processing buffered message:`, e);
                    }
                }
                messageBuffer.length = 0;
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
                    } catch (e) { }

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

        } catch (error) {
            console.error('Critical error in WebSocket connection handler:', error);
            ws.close(1011, 'Internal server error');
        }
    });

    return wss;
};

const handleDeviceMessage = async (deviceId: string, message: any) => {
    if (message.type === 'device_hello') {
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
