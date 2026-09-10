import { Response } from 'express';
import { AuthRequest } from '../middleware/authMiddleware';
import { prisma } from '../lib/prisma';
import { requestFromDevice } from '../websocket/deviceHandler';

export const speakerCommand = async (req: AuthRequest, res: Response) => {
    const { id } = req.params;
    const action = req.method === 'GET' ? 'status' : req.body?.action;
    const address = req.body?.address;
    try {
        const device = await prisma.device.findUnique({ where: { id } });
        if (!device || device.ownerId !== req.user?.userId) {
            return res.status(403).json({ error: 'Only the device owner can manage speakers and microphones.' });
        }
        if (!['status', 'scan', 'connect', 'disconnect', 'test', 'microphone_test', 'play'].includes(action)) {
            return res.status(400).json({ error: 'Unsupported speaker action.' });
        }
        if (action === 'play' && (typeof req.body.audio !== 'string' || req.body.audio.length > 2000000)) {
            return res.status(400).json({ error: 'A short WAV audio clip is required.' });
        }
        if (['connect', 'disconnect'].includes(action) &&
            (typeof address !== 'string' || !/^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(address))) {
            return res.status(400).json({ error: 'Select a valid speaker.' });
        }
        // Live replies are required; the legacy relay cannot confirm pairing or capture.
        const response = await requestFromDevice(id, { type: 'speaker', action, address, audio: action === 'play' ? req.body.audio : undefined }, 60000);
        return res.status(response.ok ? 200 : 409).json(response);
    } catch (error: any) {
        const offline = error.message === 'device_offline';
        const timeout = error.message === 'device_timeout';
        return res.status(offline ? 503 : timeout ? 504 : 500).json({
            error: offline ? 'PaperDrop is offline. Check its power and Wi-Fi.' : timeout
                ? 'PaperDrop did not respond. It may need the latest speaker update.' : 'Unable to manage the speaker.'
        });
    }
};
