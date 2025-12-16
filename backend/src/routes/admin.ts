import express from 'express';
import { prisma } from '../lib/prisma';

const router = express.Router();

// Middleware to check password
const checkAdminAuth = (req: express.Request, res: express.Response, next: express.NextFunction) => {
    const password = req.headers['x-admin-password'] || req.query.password;
    if (password !== 'nathan') {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
};

router.use(checkAdminAuth);

// List all devices
router.get('/devices', async (req, res) => {
    try {
        const devices = await prisma.device.findMany({
            orderBy: { lastSeenAt: 'desc' },
            include: {
                owner: {
                    select: { email: true }
                }
            }
        });

        res.json(devices.map(d => ({
            id: d.id,
            code: d.deviceCode,
            status: d.status,
            name: d.friendlyName,
            mac: d.macAddress,
            lastSeen: d.lastSeenAt,
            wifiSignal: d.wifiSignal,
            firmwareVersion: d.firmwareVersion,
            lastHeartbeat: d.lastHeartbeat,
            owner: d.owner ? d.owner.email : null
        })));
    } catch (e) {
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

export default router;
