import express from 'express';
import multer from 'multer';
import path from 'path';
import { prisma } from '../lib/prisma';
import { broadcastToDevice } from '../websocket/deviceHandler';

// Configure multer for firmware uploads
const storage = multer.diskStorage({
    destination: path.join(__dirname, '../../uploads'),
    filename: (req, file, cb) => {
        const version = req.body.version || 'unknown';
        cb(null, `firmware-${version}-${Date.now()}.tar.gz`);
    }
});
const upload = multer({ storage });

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

        res.json(devices.map(d => {
            // Calculate if device is actually online (seen in last 60 seconds)
            const isOnline = d.lastSeenAt && (new Date().getTime() - new Date(d.lastSeenAt).getTime() < 60000);

            return {
                id: d.id,
                code: d.deviceCode,
                status: isOnline ? 'online' : 'offline',
                name: d.friendlyName,
                mac: d.macAddress,
                lastSeen: d.lastSeenAt,
                wifiSignal: d.wifiSignal,
                firmwareVersion: d.firmwareVersion,
                lastHeartbeat: d.lastHeartbeat,
                owner: d.owner ? d.owner.email : null
            };
        }));
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

// Upload firmware file
router.post('/firmware/upload', upload.single('file'), async (req, res) => {
    try {
        const { version, description, isCritical } = req.body;

        if (!version || !req.file) {
            return res.status(400).json({ error: 'version and file are required' });
        }

        // Build URL for the file
        const baseUrl = process.env.RENDER_EXTERNAL_URL || `http://localhost:${process.env.PORT || 3000}`;
        const url = `${baseUrl}/uploads/${req.file.filename}`;

        const release = await prisma.firmwareRelease.create({
            data: {
                version,
                url,
                description: description || '',
                isCritical: isCritical === 'true' || isCritical === true
            }
        });

        res.json(release);
    } catch (e: any) {
        if (e.code === 'P2002') {
            return res.status(400).json({ error: 'Version already exists' });
        }
        console.error(e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

// Delete a device (Unprovision)
router.delete('/devices/:id', async (req, res) => {
    try {
        const { id } = req.params;

        // Delete device and all associated records
        // In our schema, DeviceAccess and DeviceInvite have onDelete: Cascade.
        // Message does not have onDelete: Cascade, so we delete them first.
        await prisma.$transaction([
            prisma.message.deleteMany({ where: { deviceId: id } }),
            prisma.device.delete({ where: { id } })
        ]);

        res.json({ success: true, message: 'Device unprovisioned' });
    } catch (e) {
        console.error('Error unprovisioning device:', e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

export default router;

