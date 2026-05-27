import express from 'express';
import multer from 'multer';
import path from 'path';
import { prisma } from '../lib/prisma';
import { broadcastToDevice, requestFromDevice } from '../websocket/deviceHandler';
import { fetchRelayDeviceStatuses, relayIsOnline, relayLastActive, relayMessageToDevice } from '../lib/deviceRelay';

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
        const relayStatuses = await fetchRelayDeviceStatuses();
        const devices = await prisma.device.findMany({
            orderBy: { lastSeenAt: 'desc' },
            include: {
                owner: {
                    select: { email: true }
                }
            }
        });

        res.json(devices.map(d => {
            const relayDevice = relayStatuses.get(d.deviceCode);
            const relayActive = relayLastActive(relayDevice);
            const lastSeen = relayDevice?.lastSeen ? new Date(relayDevice.lastSeen) : d.lastSeenAt;
            const lastHeartbeat = relayDevice?.lastHeartbeat ? new Date(relayDevice.lastHeartbeat) : d.lastHeartbeat;
            const lastActive = relayActive || d.lastHeartbeat || d.lastSeenAt;
            const isOnline = lastActive && (new Date().getTime() - new Date(lastActive).getTime() < 60000);

            return {
                id: d.id,
                code: d.deviceCode,
                status: isOnline || relayIsOnline(relayDevice) ? 'online' : 'offline',
                name: d.friendlyName,
                mac: d.macAddress,
                lastSeen,
                wifiSignal: relayDevice?.wifiSignal ?? d.wifiSignal,
                firmwareVersion: relayDevice?.firmwareVersion ?? d.firmwareVersion,
                lastHeartbeat,
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
        const results = await Promise.all(targetDevices.map(async (id) => {
            const payload = {
                type: 'update',
                version: release.version,
                url: release.url,
                critical: release.isCritical
            };
            const sent = broadcastToDevice(id, payload) || await relayMessageToDevice(id, payload);
            return { deviceId: id, sent };
        }));

        res.json({
            message: `Deploy command sent to ${results.filter(r => r.sent).length} devices`,
            results
        });
    } catch (e) {
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

router.post('/relay-message', async (req, res) => {
    try {
        const { deviceId, payload } = req.body;

        if (!deviceId || !payload) {
            return res.status(400).json({ error: 'deviceId and payload are required' });
        }

        const sent = broadcastToDevice(deviceId, payload);
        res.status(sent ? 200 : 503).json({ sent });
    } catch (e) {
        console.error('Error relaying message:', e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

const requestDeviceOrRelay = async (
    deviceId: string,
    payload: any,
    timeoutMs = 20000
) => {
    try {
        const response = await requestFromDevice(deviceId, payload, timeoutMs);
        return {
            status: 200,
            body: { sent: true, relayed: false, response }
        };
    } catch (err: any) {
        if (err?.message !== 'device_offline') {
            return {
                status: err?.message === 'device_timeout' ? 504 : 500,
                body: { sent: false, error: err?.message || 'Device request failed' }
            };
        }

        const relayed = await relayMessageToDevice(deviceId, payload);
        if (relayed) {
            return {
                status: 202,
                body: {
                    sent: true,
                    relayed: true,
                    message: 'Command relayed; response is unavailable through the compatibility relay'
                }
            };
        }

        return {
            status: 503,
            body: { sent: false, error: 'Device offline' }
        };
    }
};

router.post('/devices/:id/diagnostics', async (req, res) => {
    try {
        const { id } = req.params;
        const result = await requestDeviceOrRelay(id, { type: 'collect_diagnostics' }, 30000);
        res.status(result.status).json(result.body);
    } catch (e) {
        console.error('Error requesting diagnostics:', e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

router.post('/devices/:id/commands', async (req, res) => {
    try {
        const { id } = req.params;
        const { command } = req.body;

        const allowedCommands = new Set([
            'agent_status',
            'ble_status',
            'disk_status',
            'network_status',
            'printer_status',
            'wifi_status',
            'restart_agent',
            'restart_network',
            'reboot'
        ]);

        if (!allowedCommands.has(command)) {
            return res.status(400).json({ error: 'Unsupported command' });
        }

        const result = await requestDeviceOrRelay(id, {
            type: 'run_command',
            command
        }, command === 'reboot' || command === 'restart_network' ? 5000 : 20000);
        res.status(result.status).json(result.body);
    } catch (e) {
        console.error('Error running device command:', e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

router.post('/devices/:id/config', async (req, res) => {
    try {
        const { id } = req.params;
        const { cloudWsUrl, restart = true } = req.body;

        if (!cloudWsUrl || typeof cloudWsUrl !== 'string') {
            return res.status(400).json({ error: 'cloudWsUrl is required' });
        }

        const result = await requestDeviceOrRelay(id, {
            type: 'set_config',
            cloud_ws_url: cloudWsUrl,
            restart
        }, 10000);
        res.status(result.status).json(result.body);
    } catch (e) {
        console.error('Error updating device config:', e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

router.post('/devices/:id/test-print', async (req, res) => {
    try {
        const { id } = req.params;
        const result = await requestDeviceOrRelay(id, { type: 'test_print' }, 20000);
        res.status(result.status).json(result.body);
    } catch (e) {
        console.error('Error requesting test print:', e);
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

router.post('/devices/:id/update', async (req, res) => {
    try {
        const { id } = req.params;
        const { version, url, sha256, critical } = req.body;

        if (!url && !version) {
            return res.status(400).json({ error: 'version or url is required' });
        }

        const result = await requestDeviceOrRelay(id, {
            type: 'update',
            version,
            url,
            sha256,
            critical: Boolean(critical)
        }, 10000);
        res.status(result.status).json(result.body);
    } catch (e) {
        console.error('Error requesting OTA update:', e);
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
        const baseUrl =
            process.env.PUBLIC_API_URL ||
            process.env.BACKEND_URL ||
            process.env.COOLIFY_URL ||
            process.env.RENDER_EXTERNAL_URL ||
            `http://localhost:${process.env.PORT || 3000}`;
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

// List all users
router.get('/users', async (req, res) => {
    try {
        const users = await prisma.user.findMany({
            orderBy: { createdAt: 'desc' },
            select: {
                id: true,
                email: true,
                name: true,
                createdAt: true,
                _count: {
                    select: { devices: true, deviceAccess: true }
                }
            }
        });
        res.json(users);
    } catch (e) {
        res.status(500).json({ error: 'Internal Server Error' });
    }
});

// Assign device to user
router.post('/devices/:id/assign', async (req, res) => {
    try {
        const { id } = req.params;
        const { email, role } = req.body;

        if (!email) {
            return res.status(400).json({ error: 'Email is required' });
        }

        const user = await prisma.user.findUnique({
            where: { email }
        });

        if (!user) {
            return res.status(404).json({ error: 'User not found' });
        }

        const device = await prisma.device.findUnique({
            where: { id }
        });

        if (!device) {
            return res.status(404).json({ error: 'Device not found' });
        }

        // Use transaction to update both Device and DeviceAccess
        await prisma.$transaction(async (tx) => {
            if (role === 'owner') {
                // If making them owner, update the device ownerId
                await tx.device.update({
                    where: { id },
                    data: { ownerId: user.id }
                });

                // Also ensure they have DeviceAccess as owner
                await tx.deviceAccess.upsert({
                    where: { deviceId_userId: { deviceId: id, userId: user.id } },
                    update: { role: 'owner' },
                    create: { deviceId: id, userId: user.id, role: 'owner' }
                });
            } else {
                // Just regular sender access
                await tx.deviceAccess.upsert({
                    where: { deviceId_userId: { deviceId: id, userId: user.id } },
                    update: { role: role || 'sender' },
                    create: { deviceId: id, userId: user.id, role: role || 'sender' }
                });
            }
        });

        res.json({ success: true, message: `Device assigned to ${email}` });
    } catch (e) {
        console.error('Error assigning device:', e);
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
