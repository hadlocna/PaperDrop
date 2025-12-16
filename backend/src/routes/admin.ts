import express from 'express';
import { prisma } from '../lib/prisma';
import { broadcastToDevice } from '../websocket/deviceHandler';

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

// ─────────────────────────────────────────────────────────────────
// FIRMWARE MANAGEMENT
// ─────────────────────────────────────────────────────────────────

// List all firmware releases
router.get('/firmware', async (req, res) => {
    try {
        const releases = await prisma.firmwareRelease.findMany({
            orderBy: { createdAt: 'desc' }
        });
        res.json(releases);
    } catch (e) {
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

// Create new firmware release
router.post('/firmware', async (req, res) => {
    try {
        const { version, url, description, isCritical } = req.body;

        if (!version || !url) {
            return res.status(400).json({ error: 'version and url are required' });
        }

        const release = await prisma.firmwareRelease.create({
            data: {
                version,
                url,
                description: description || '',
                isCritical: isCritical || false
            }
        });

        res.json(release);
    } catch (e: any) {
        if (e.code === 'P2002') {
            return res.status(400).json({ error: 'Version already exists' });
        }
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

// Deploy firmware to device(s)
router.post('/firmware/deploy', async (req, res) => {
    try {
        const { deviceId, version, deployAll } = req.body;

        // Get the firmware release
        const release = await prisma.firmwareRelease.findUnique({
            where: { version }
        });

        if (!release) {
            return res.status(404).json({ error: 'Firmware version not found' });
        }

        let targetDevices: string[] = [];

        if (deployAll) {
            // Get all online devices
            const devices = await prisma.device.findMany({
                where: { status: 'online' },
                select: { id: true }
            });
            targetDevices = devices.map(d => d.id);
        } else if (deviceId) {
            targetDevices = [deviceId];
        } else {
            return res.status(400).json({ error: 'deviceId or deployAll required' });
        }

        // Send update command to each device
        const results = targetDevices.map(id => {
            const sent = broadcastToDevice(id, {
                type: 'update',
                version: release.version,
                url: release.url,
                critical: release.isCritical
            });
            return { deviceId: id, sent };
        });

        res.json({
            message: `Deploy command sent to ${results.filter(r => r.sent).length} devices`,
            results
        });
    } catch (e) {
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

export default router;

