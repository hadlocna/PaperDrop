import { Request, Response } from 'express';
import { prisma } from '../lib/prisma';
import { broadcastToDevice } from '../websocket/deviceHandler';
import crypto from 'crypto';

export const claimDevice = async (req: Request, res: Response) => {
    try {
        const { deviceCode, userId, friendlyName } = req.body;

        if (!deviceCode || !userId) {
            return res.status(400).json({ error: 'Missing device code or user ID' });
        }

        // Find device
        const device = await prisma.device.findUnique({
            where: { deviceCode },
        });

        if (!device) {
            return res.status(404).json({ error: 'Device not found' });
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

        // Notify device
        broadcastToDevice(device.id, {
            type: 'claimed',
            owner_name: 'Owner' // Ideally fetch user name
        });

        res.json(updatedDevice);

    } catch (error) {
        console.error('Claim device error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getDevices = async (req: Request, res: Response) => {
    try {
        const { userId } = req.query;

        if (!userId) {
            return res.status(400).json({ error: 'Missing user ID' });
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

        // Add isOnline status from connection map? 
        // Real-time status in DB might lag if we rely solely on 'status' field updates.
        // For now, DB status is fine as updated by WS handler.

        res.json(devices);
    } catch (error) {
        console.error('Get devices error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getDevice = async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const { userId } = req.query;

        if (!userId) {
            return res.status(400).json({ error: 'Missing user ID' });
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

        res.json(device);
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const updateDevice = async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const { userId, friendlyName } = req.body;

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

export const testPrint = async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const { userId } = req.body;

        // Check access... generic logic repeatedly used, ideally middleware.
        const access = await prisma.deviceAccess.findUnique({
            where: { deviceId_userId: { deviceId: id, userId: String(userId) } }
        });
        if (!access) return res.status(403).json({ error: 'Access denied' });

        const requestId = crypto.randomUUID();
        const success = broadcastToDevice(id, {
            type: 'test_print',
            request_id: requestId
        });

        if (success) {
            res.json({ success: true, message: 'Test print sent' });
        } else {
            res.status(503).json({ error: 'Device offline' });
        }
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getAccess = async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const { userId } = req.query;

        const device = await prisma.device.findUnique({ where: { id } });
        if (!device || device.ownerId !== String(userId)) {
            return res.status(403).json({ error: 'Only owner can view access' });
        }

        const access = await prisma.deviceAccess.findMany({
            where: { deviceId: id },
            include: { user: { select: { id: true, name: true, email: true } } }
        });

        res.json(access);
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const grantAccess = async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const { userId, email } = req.body;

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

export const revokeAccess = async (req: Request, res: Response) => {
    try {
        const { id, userId: targetUserId } = req.params;
        const { userId } = req.body; // Owner ID from body/session

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
