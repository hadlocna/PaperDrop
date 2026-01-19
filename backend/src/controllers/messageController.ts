import { Request, Response } from 'express';
import { prisma } from '../lib/prisma';
import { broadcastToDevice } from '../websocket/deviceHandler';
import { AuthRequest } from '../middleware/authMiddleware';

export const sendMessage = async (req: AuthRequest, res: Response) => {
    try {
        const { deviceId, content, contentType, scheduledAt } = req.body;
        const senderId = req.user?.userId;

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

        // Normalize content for consistent storage/printing
        let normalizedContent: any = content;

        if (contentType === 'image') {
            // Frontend may wrap the base64 payload or send it directly
            if (typeof content === 'object' && content !== null) {
                normalizedContent = content.content || content.image || content.image_url || content;
            }
        } else if (contentType === 'text' && typeof content === 'string') {
            // Wrap plain strings so the printer layout code can read `body`
            normalizedContent = { body: content };
        }

        // Validate and normalize scheduledAt
        let scheduledDate: Date | null = null;
        if (scheduledAt) {
            const sd = new Date(scheduledAt);
            if (isNaN(sd.getTime())) {
                return res.status(400).json({ error: 'Invalid scheduledAt timestamp' });
            }
            // If scheduled time is in the past or now, treat as immediate
            if (sd > new Date()) {
                scheduledDate = sd;
            }
        }

        // Create message
        const message = await prisma.message.create({
            data: {
                senderId,
                deviceId,
                content: JSON.stringify(normalizedContent), // Storing as JSON string for SQLite compatibility
                contentType: contentType || 'text',
                status: scheduledDate ? 'scheduled' : 'queued',
                scheduledAt: scheduledDate
            }
        });

        // Broadcast to device via WebSocket ONLY if not scheduled
        if (!message.scheduledAt) {
            // Fetch sender name for attribution
            const sender = await prisma.user.findUnique({
                where: { id: senderId },
                select: { name: true }
            });

            const broadcastResult = broadcastToDevice(deviceId, {
                type: 'new_message',
                message: {
                    id: message.id,
                    content: normalizedContent,
                    contentType: message.contentType,
                    createdAt: message.createdAt,
                    senderName: sender?.name || 'Unknown'
                }
            });

            if (broadcastResult) {
                await prisma.message.update({
                    where: { id: message.id },
                    data: { status: 'sent', sentAt: new Date() }
                });
            }
        }

        res.status(201).json(message);

    } catch (error) {
        console.error('Send message error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};

export const getMessages = async (req: AuthRequest, res: Response) => {
    try {
        const { deviceId, limit = 50, offset = 0, shared = 'false' } = req.query;
        const userId = req.user?.userId;

        if (!userId) {
            return res.status(401).json({ error: 'Unauthorized' });
        }

        let where: any = {};

        if (shared === 'true' && deviceId) {
            // Verify access to the device before showing shared history
            const access = await prisma.deviceAccess.findUnique({
                where: {
                    deviceId_userId: {
                        deviceId: String(deviceId),
                        userId: String(userId)
                    }
                }
            });
            const device = await prisma.device.findUnique({ where: { id: String(deviceId) } });
            const isOwner = device?.ownerId === userId;

            if (!access && !isOwner) {
                return res.status(403).json({ error: 'Not authorized to view history for this device' });
            }
            where.deviceId = String(deviceId);
        } else {
            // Default to only user's messages
            where.senderId = String(userId);
            if (deviceId) where.deviceId = String(deviceId);
        }

        const messages = await prisma.message.findMany({
            where,
            orderBy: { createdAt: 'desc' },
            take: Number(limit),
            skip: Number(offset),
            include: {
                device: {
                    select: { id: true, friendlyName: true }
                },
                sender: {
                    select: { id: true, name: true }
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

export const clearQueue = async (req: Request, res: Response) => {
    try {
        const { deviceId, deviceCode } = req.body;

        if (!deviceId && !deviceCode) {
            return res.status(400).json({ error: 'Missing device ID or code' });
        }

        let targetDeviceId = deviceId;

        if (deviceCode) {
            const device = await prisma.device.findUnique({
                where: { deviceCode }
            });
            if (!device) {
                return res.status(404).json({ error: 'Device not found' });
            }
            targetDeviceId = device.id;
        }

        // Delete all messages for this device
        const result = await prisma.message.deleteMany({
            where: {
                deviceId: String(targetDeviceId)
            }
        });

        res.json({ message: `Cleared ${result.count} messages` });
    } catch (error) {
        console.error('Clear queue error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
};
