import { Request, Response } from 'express';
import { prisma } from '../lib/prisma';
import { broadcastToDevice } from '../websocket/deviceHandler';

export const sendMessage = async (req: Request, res: Response) => {
    try {
        const { senderId, deviceId, content, contentType } = req.body;

        if (!senderId || !deviceId || !content) {
            return res.status(400).json({ error: 'Missing required fields' });
        }

        // Verify access
        const access = await prisma.deviceAccess.findUnique({
            where: {
                deviceId_userId: {
                    deviceId,
                    userId: senderId
                }
            }
        });

        // Also check if owner
        const device = await prisma.device.findUnique({ where: { id: deviceId } });
        const isOwner = device?.ownerId === senderId;

        if (!access && !isOwner) {
            return res.status(403).json({ error: 'Not authorized to send to this device' });
        }

        // Create message
        const message = await prisma.message.create({
            data: {
                senderId,
                deviceId,
                content: JSON.stringify(content), // Storing as JSON string for SQLite compatibility
                contentType: contentType || 'text',
                status: 'queued'
            }
        });

        // Broadcast to device via WebSocket
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

        res.status(201).json(message);

    } catch (error) {
        console.error('Send message error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getMessages = async (req: Request, res: Response) => {
    try {
        const { userId, deviceId, limit = 50, offset = 0 } = req.query;

        if (!userId) {
            return res.status(400).json({ error: 'Missing user ID' });
        }

        const where: any = { senderId: String(userId) };
        if (deviceId) where.deviceId = String(deviceId);

        const messages = await prisma.message.findMany({
            where,
            orderBy: { createdAt: 'desc' },
            take: Number(limit),
            skip: Number(offset),
            include: {
                device: {
                    select: { id: true, friendlyName: true }
                }
            }
        });

        const total = await prisma.message.count({ where });

        res.json({ messages, total });
    } catch (error) {
        console.error('Get messages error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};
