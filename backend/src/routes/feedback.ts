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

// User: Get my feedback history
router.get('/my', authenticateToken, async (req: any, res) => {
    try {
        const { userId } = req.user;
        const feedbacks = await prisma.feedback.findMany({
            where: { userId },
            include: {
                replies: {
                    orderBy: { createdAt: 'asc' }
                }
            },
            orderBy: { createdAt: 'desc' }
        });
        res.json(feedbacks);
    } catch (err) {
        res.status(500).json({ error: 'Failed to fetch your feedback' });
    }
});

// Admin: Get all feedback with replies
router.get('/all', async (req, res) => {
    const adminPassword = req.headers['x-admin-password'];
    if (adminPassword !== 'nathan') {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
        const feedbacks = await prisma.feedback.findMany({
            include: {
                replies: {
                    orderBy: { createdAt: 'asc' }
                }
            },
            orderBy: { createdAt: 'desc' }
        });
        res.json(feedbacks);
    } catch (err) {
        res.status(500).json({ error: 'Failed to fetch feedback' });
    }
});

// Admin: Update status (Mark resolved/completed)
router.patch('/:id/status', async (req, res) => {
    const adminPassword = req.headers['x-admin-password'];
    if (adminPassword !== 'nathan') {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
        const { id } = req.params;
        const { status } = req.body;
        const feedback = await prisma.feedback.update({
            where: { id },
            data: { status }
        });
        res.json(feedback);
    } catch (err) {
        res.status(500).json({ error: 'Failed to update status' });
    }
});

// Admin: Delete feedback
router.delete('/:id', async (req, res) => {
    const adminPassword = req.headers['x-admin-password'];
    if (adminPassword !== 'nathan') {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
        const { id } = req.params;
        await prisma.feedback.delete({
            where: { id }
        });
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: 'Failed to delete feedback' });
    }
});

// Admin or User: Post a reply
router.post('/:id/reply', async (req: any, res) => {
    // Check if admin or authenticated user
    const adminPassword = req.headers['x-admin-password'];
    const isAdmin = adminPassword === 'nathan';

    let userId = null;
    if (!isAdmin) {
        // Must be authenticated user for non-admin replies
        return authenticateToken(req, res, async () => {
            const { id } = req.params;
            const { message } = req.body;
            try {
                const reply = await prisma.feedbackReply.create({
                    data: {
                        feedbackId: id,
                        senderId: req.user.userId,
                        isAdmin: false,
                        message
                    }
                });
                res.json(reply);
            } catch (err) {
                res.status(500).json({ error: 'Failed to post reply' });
            }
        });
    }

    // Admin reply logic
    try {
        const { id } = req.params;
        const { message } = req.body;
        const reply = await prisma.feedbackReply.create({
            data: {
                feedbackId: id,
                isAdmin: true,
                message
            }
        });
        res.json(reply);
    } catch (err) {
        res.status(500).json({ error: 'Failed to post admin reply' });
    }
});

export default router;
