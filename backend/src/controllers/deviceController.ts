import { Request, Response } from 'express';
import { prisma } from '../lib/prisma';
import { broadcastToDevice, requestFromDevice, requestLogsFromDevice } from '../websocket/deviceHandler';
import crypto from 'crypto';
import { AuthRequest } from '../middleware/authMiddleware';
import { fetchRelayDeviceStatuses, relayIsOnline, relayLastActive, relayMessageToDevice } from '../lib/deviceRelay';

export const claimDevice = async (req: AuthRequest, res: Response) => {
    try {
        const { deviceCode, friendlyName } = req.body;
        const userId = req.user?.userId;

        if (!deviceCode || !userId) {
            return res.status(400).json({ error: 'Missing device code or user ID' });
        }

        // Find device or create it (for BLE-provisioned devices)
        let device = await prisma.device.findUnique({
            where: { deviceCode },
        });

        if (!device) {
            // Device was provisioned via BLE but hasn't connected to backend yet
            // Create it now so user can claim it immediately
            console.log(`Creating new device from claim request: ${deviceCode}`);
            device = await prisma.device.create({
                data: {
                    deviceCode,
                    deviceSecret: crypto.randomBytes(32).toString('hex'),
                    status: 'offline',
                    friendlyName: friendlyName || 'My PaperDrop',
                    lastSeenAt: new Date()
                }
            });
        }

        if (device.ownerId) {
            return res.status(409).json({ error: 'Device already claimed' });
        }

        // Claim device
        const updatedDevice = await prisma.$transaction(async (tx) => {
            const dev = await tx.device.update({
                where: { id: device.id },
                data: {
                    ownerId: userId,
                    friendlyName: friendlyName || 'My PaperDrop',
                    status: 'online'
                },
            });

            await tx.deviceAccess.create({
                data: {
                    deviceId: dev.id,
                    userId: userId,
                    role: 'owner'
                }
            });

            return dev;
        });

        // Notify device and validate connection
        broadcastToDevice(device.id, {
            type: 'claimed',
            owner_name: 'Owner'
        });

        // Post-claim validation: request a connection test
        setTimeout(() => {
            broadcastToDevice(device.id, { type: 'test_connection' });
        }, 2000);

        res.json(updatedDevice);

    } catch (error) {
        console.error('Claim device error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getDevices = async (req: AuthRequest, res: Response) => {
    try {
        const userId = req.user?.userId;
        const requestId = req.headers['x-request-id'] || req.headers['render-request-id'];

        if (!userId) {
            console.warn('[GET /api/devices] unauthorized request', { requestId });
            return res.status(401).json({ error: 'Unauthorized' });
        }

        const devices = await prisma.device.findMany({
            where: {
                OR: [
                    { ownerId: String(userId) },
                    { deviceAccess: { some: { userId: String(userId) } } }
                ]
            },
            include: {
                owner: {
                    select: { name: true, email: true }
                }
            }
        });

        console.info('[GET /api/devices] loaded devices', {
            requestId,
            userId,
            count: devices.length,
            deviceIds: devices.map((device) => device.id),
            deviceCodes: devices.map((device) => device.deviceCode)
        });

        const relayStatuses = await fetchRelayDeviceStatuses();

        // Calculate real-time status based on local or relay heartbeats
        const now = new Date().getTime();
        const devicesWithStatus = devices.map(d => {
            const relayDevice = relayStatuses.get(d.deviceCode);
            const lastActive = relayLastActive(relayDevice) || d.lastHeartbeat || d.lastSeenAt;
            const isOnline = lastActive && (now - new Date(lastActive).getTime() < 60000);
            return {
                ...d,
                status: isOnline || relayIsOnline(relayDevice) ? 'online' : 'offline',
                lastSeenAt: relayDevice?.lastSeen ? new Date(relayDevice.lastSeen) : d.lastSeenAt,
                lastHeartbeat: relayDevice?.lastHeartbeat ? new Date(relayDevice.lastHeartbeat) : d.lastHeartbeat,
                wifiSignal: relayDevice?.wifiSignal ?? d.wifiSignal,
                firmwareVersion: relayDevice?.firmwareVersion ?? d.firmwareVersion
            };
        });

        res.json(devicesWithStatus);
    } catch (error) {
        console.error('Get devices error:', {
            requestId: req.headers['x-request-id'] || req.headers['render-request-id'],
            userId: req.user?.userId,
            error
        });
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getDevice = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const userId = req.user?.userId;

        if (!userId) {
            return res.status(401).json({ error: 'Unauthorized' });
        }

        const device = await prisma.device.findUnique({
            where: { id },
            include: {
                owner: {
                    select: { name: true, email: true }
                }
            }
        });

        if (!device) {
            return res.status(404).json({ error: 'Device not found' });
        }

        // Check access
        const access = await prisma.deviceAccess.findUnique({
            where: { deviceId_userId: { deviceId: id, userId: String(userId) } }
        });

        if (!access && device.ownerId !== String(userId)) {
            return res.status(403).json({ error: 'Access denied' });
        }

        const relayStatuses = await fetchRelayDeviceStatuses();
        const relayDevice = relayStatuses.get(device.deviceCode);

        // Calculate real-time status
        const lastActive = relayLastActive(relayDevice) || device.lastHeartbeat || device.lastSeenAt;
        const isOnline = lastActive && (new Date().getTime() - new Date(lastActive).getTime() < 60000);
        const deviceWithStatus = {
            ...device,
            status: isOnline || relayIsOnline(relayDevice) ? 'online' : 'offline',
            lastSeenAt: relayDevice?.lastSeen ? new Date(relayDevice.lastSeen) : device.lastSeenAt,
            lastHeartbeat: relayDevice?.lastHeartbeat ? new Date(relayDevice.lastHeartbeat) : device.lastHeartbeat,
            wifiSignal: relayDevice?.wifiSignal ?? device.wifiSignal,
            firmwareVersion: relayDevice?.firmwareVersion ?? device.firmwareVersion
        };

        res.json(deviceWithStatus);
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const updateDevice = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const { friendlyName } = req.body;
        const userId = req.user?.userId;

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device) return res.status(404).json({ error: 'Device not found' });

        if (device.ownerId !== userId) {
            return res.status(403).json({ error: 'Only owner can update device' });
        }

        const updated = await prisma.device.update({
            where: { id },
            data: { friendlyName }
        });

        res.json(updated);
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const testPrint = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const userId = req.user?.userId;

        if (!userId) return res.status(401).json({ error: 'Unauthorized' });

        // Check access... generic logic repeatedly used, ideally middleware.
        const access = await prisma.deviceAccess.findUnique({
            where: { deviceId_userId: { deviceId: id, userId: String(userId) } }
        });
        if (!access) return res.status(403).json({ error: 'Access denied' });

        const payload = {
            type: 'test_print'
        };

        try {
            const result = await requestFromDevice(id, payload, 20000);
            if (result.ok === false) {
                return res.status(500).json({ error: result.error || 'Test print failed' });
            }
            return res.json({ success: true, message: 'Test print completed' });
        } catch (err: any) {
            if (err?.message !== 'device_offline') {
                if (err?.message === 'device_timeout') {
                    return res.status(504).json({ error: 'Device did not confirm test print' });
                }
                throw err;
            }
        }

        const relayed = await relayMessageToDevice(id, payload);
        if (relayed) {
            return res.status(202).json({
                success: true,
                message: 'Test print relayed; confirmation is unavailable through the compatibility relay'
            });
        }

        res.status(503).json({ error: 'Device offline' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const downloadLogs = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const { type = 'agent', lines = '500' } = req.query;
        const userId = req.user?.userId;

        if (!userId) {
            return res.status(401).json({ error: 'Unauthorized' });
        }

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device) {
            return res.status(404).json({ error: 'Device not found' });
        }

        const access = await prisma.deviceAccess.findUnique({
            where: { deviceId_userId: { deviceId: id, userId: String(userId) } }
        });

        if (!access && device.ownerId !== String(userId)) {
            return res.status(403).json({ error: 'Access denied' });
        }

        const lineCount = parseInt(String(lines)) || 500;

        try {
            const response = await requestLogsFromDevice(id, {
                type: String(type),
                lines: lineCount
            });

            const filename = `${device.friendlyName || 'device'}-${String(type)}-logs.txt`;
            res.setHeader('Content-Type', 'text/plain');
            res.setHeader('Content-Disposition', `attachment; filename="${filename.replace(/\s+/g, '_')}"`);
            res.send(response.content || '');
        } catch (err: any) {
            if (err?.message === 'device_offline') {
                return res.status(503).json({ error: 'Device offline' });
            }
            if (err?.message === 'device_timeout') {
                return res.status(504).json({ error: 'Device did not respond with logs' });
            }
            console.error('Download logs error:', err);
            return res.status(500).json({ error: 'Failed to fetch logs from device' });
        }
    } catch (error) {
        console.error('Download logs error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getAccess = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const userId = req.user?.userId;

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device) return res.status(404).json({ error: 'Device not found' });

        // Check if user has access to view this
        const userAccess = await prisma.deviceAccess.findUnique({
            where: { deviceId_userId: { deviceId: id, userId: String(userId) } }
        });

        if (!userAccess && device.ownerId !== userId) {
            return res.status(403).json({ error: 'Access denied' });
        }

        const access = await prisma.deviceAccess.findMany({
            where: { deviceId: id },
            include: { user: { select: { id: true, name: true, email: true } } }
        });

        const invites = await prisma.deviceInvite.findMany({
            where: { deviceId: id, status: 'pending' },
            include: { inviter: { select: { name: true } } }
        });

        res.json({ access, invites });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const grantAccess = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const { email } = req.body;
        const userId = req.user?.userId;

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device || device.ownerId !== userId) {
            return res.status(403).json({ error: 'Only owner can grant access' });
        }

        const invitee = await prisma.user.findUnique({ where: { email } });
        if (!invitee) {
            return res.json({ status: 'pending', message: 'User not found, invite email sent (mock)' });
        }

        // Check existing
        const existing = await prisma.deviceAccess.findUnique({
            where: { deviceId_userId: { deviceId: id, userId: invitee.id } }
        });

        if (existing) {
            return res.status(409).json({ error: 'User already has access' });
        }

        await prisma.deviceAccess.create({
            data: {
                deviceId: id,
                userId: invitee.id,
                role: 'sender'
            }
        });

        res.json({ status: 'granted' });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const revokeAccess = async (req: AuthRequest, res: Response) => {
    try {
        const { id, userId: targetUserId } = req.params;
        const userId = req.user?.userId;

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device || device.ownerId !== userId) {
            return res.status(403).json({ error: 'Only owner can revoke access' });
        }

        if (targetUserId === userId) {
            return res.status(400).json({ error: 'Cannot revoke own access' });
        }

        await prisma.deviceAccess.delete({
            where: { deviceId_userId: { deviceId: id, userId: targetUserId } }
        });

        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const unclaimDevice = async (req: AuthRequest, res: Response) => {
    try {
        const { id } = req.params;
        const userId = req.user?.userId;

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device) return res.status(404).json({ error: 'Device not found' });

        if (device.ownerId !== userId) {
            return res.status(403).json({ error: 'Only owner can disconnect device' });
        }

        await prisma.$transaction([
            prisma.device.update({
                where: { id },
                data: { ownerId: null, status: 'offline' }
            }),
            prisma.deviceAccess.deleteMany({
                where: { deviceId: id }
            })
        ]);

        res.json({ success: true });
    } catch (error) {
        console.error('Unclaim device error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};
