import { Router } from 'express';
import { PrismaClient } from '@prisma/client';
import { authenticateToken } from '../middleware/authMiddleware';

const router = Router();
const prisma = new PrismaClient();

// Post feedback
router.post('/send', authenticateToken, async (req: any, res) => {
    try {
        const { message, type, deviceId, deviceName, deviceInfo } = req.body;
        const { userId, email } = req.user;

        if (!message) {
            return res.status(400).json({ error: 'Message is required' });
        }

        const user = await prisma.user.findUnique({
            where: { id: userId }
        });

        const feedback = await prisma.feedback.create({
            data: {
                userId,
                userEmail: email,
                userName: user?.name || 'Unknown',
                message,
                type: type || 'feedback',
                deviceId,
                deviceName,
                userAgent: deviceInfo?.userAgent,
                platform: deviceInfo?.platform,
                browser: deviceInfo?.browser
            }
        });

        res.json({ success: true, feedback });
    } catch (err) {
        console.error('Feedback error:', err);
        res.status(500).json({ error: 'Failed to submit feedback' });
    }
});

// Admin get feedback
router.get('/all', async (req, res) => {
    const adminPassword = req.headers['x-admin-password'];
    if (adminPassword !== 'nathan') {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
        const feedbacks = await prisma.feedback.findMany({
            orderBy: { createdAt: 'desc' }
        });
        res.json(feedbacks);
    } catch (err) {
        res.status(500).json({ error: 'Failed to fetch feedback' });
    }
});

export default router;
