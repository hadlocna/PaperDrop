import { Request, Response } from 'express';
import { prisma } from '../lib/prisma';

export const claimDevice = async (req: Request, res: Response) => {
    try {
        const { deviceCode, userId } = req.body; // In real app, userId comes from session/token

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
        // Transaction to update device and add access
        const updatedDevice = await prisma.$transaction(async (tx) => {
            const dev = await tx.device.update({
                where: { id: device.id },
                data: {
                    ownerId: userId,
                    status: 'online' // Updating status to indicate it's now active
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

        res.json(updatedDevice);

    } catch (error) {
        console.error('Claim device error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};
