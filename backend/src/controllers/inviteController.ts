import { Request, Response } from 'express';
import crypto from 'crypto';
import { prisma } from '../lib/prisma';
import { AuthRequest } from '../middleware/authMiddleware';

export const createInvite = async (req: AuthRequest, res: Response) => {
    try {
        const { id: deviceId } = req.params;
        const { email } = req.body;
        const userId = req.user?.userId;

        if (!userId) {
            return res.status(401).json({ error: 'Unauthorized' });
        }

        const device = await prisma.device.findUnique({ where: { id: deviceId } });
        if (!device || device.ownerId !== userId) {
            return res.status(403).json({ error: 'Only the owner can invite others' });
        }

        const token = crypto.randomUUID();

        const invite = await prisma.deviceInvite.create({
            data: {
                token,
                deviceId,
                inviterId: userId,
                inviteeEmail: email || null,
            },
        });

        const inviteUrl = `${process.env.APP_URL || 'http://localhost:5173'}/invite/${invite.token}`;

        res.json({
            token: invite.token,
            status: invite.status,
            inviteUrl,
        });
    } catch (error) {
        console.error('Create invite error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getInviteDetails = async (req: Request, res: Response) => {
    try {
        const { token } = req.params;

        const invite = await prisma.deviceInvite.findUnique({
            where: { token },
            include: {
                device: { select: { id: true, friendlyName: true } },
                inviter: { select: { id: true, name: true, email: true } },
                acceptedBy: { select: { id: true, name: true, email: true } },
            },
        });

        if (!invite) {
            return res.status(404).json({ error: 'Invite not found' });
        }

        res.json(invite);
    } catch (error) {
        console.error('Get invite error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const acceptInvite = async (req: AuthRequest, res: Response) => {
    try {
        const { token } = req.params;
        const userId = req.user?.userId;

        if (!userId) {
            return res.status(401).json({ error: 'Unauthorized' });
        }

        const invite = await prisma.deviceInvite.findUnique({ where: { token } });
        if (!invite) {
            return res.status(404).json({ error: 'Invite not found' });
        }

        if (invite.status !== 'pending') {
            return res.status(400).json({ error: 'Invite is no longer active' });
        }

        const user = await prisma.user.findUnique({ where: { id: userId } });
        if (!user) {
            return res.status(404).json({ error: 'User not found' });
        }

        await prisma.$transaction(async (tx) => {
            const existingAccess = await tx.deviceAccess.findUnique({
                where: { deviceId_userId: { deviceId: invite.deviceId, userId } },
            });

            if (!existingAccess) {
                await tx.deviceAccess.create({
                    data: {
                        deviceId: invite.deviceId,
                        userId,
                        role: 'sender',
                    },
                });
            }

            await tx.deviceInvite.update({
                where: { id: invite.id },
                data: {
                    status: 'accepted',
                    acceptedById: userId,
                    acceptedAt: new Date(),
                },
            });
        });

        const device = await prisma.device.findUnique({
            where: { id: invite.deviceId },
            select: { id: true, friendlyName: true },
        });

        res.json({ status: 'accepted', device });
    } catch (error) {
        console.error('Accept invite error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};
