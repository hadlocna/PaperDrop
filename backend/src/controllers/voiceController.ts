import { Response } from 'express';
import { AuthRequest } from '../middleware/authMiddleware';
import { prisma } from '../lib/prisma';
import { requestFromDevice } from '../websocket/deviceHandler';
import { closeVoice } from '../services/realtimeVoice';

export async function voiceCommand(req: AuthRequest, res: Response) {
    try {
        const device = await prisma.device.findUnique({ where: { id: req.params.id } });
        if (!device || device.ownerId !== req.user?.userId) return res.status(403).json({ error: 'Only the owner can enable voice listening.' });
        const action = req.method === 'GET' ? 'status' : req.body?.action;
        if (!['status', 'enable', 'disable', 'wake'].includes(action)) return res.status(400).json({ error: 'Unsupported voice action.' });
        const config = JSON.parse(device.config || '{}');
        if (action === 'enable' || action === 'disable') {
            config.voiceEnabled = action === 'enable';
            await prisma.device.update({ where: { id: device.id }, data: { config: JSON.stringify(config) } });
            if (action === 'disable') closeVoice(device.id);
        }
        if (action === 'wake' && config.voiceEnabled !== true) return res.status(409).json({ error: 'Enable voice listening first.' });
        if (action === 'wake') closeVoice(device.id);
        const result = await requestFromDevice(device.id, { type: 'voice_control', action, enabled: config.voiceEnabled === true }, 25000);
        return res.status(result.ok ? 200 : 409).json(result);
    } catch (error: any) {
        return res.status(error.message === 'device_offline' ? 503 : 504).json({ error: 'PaperDrop did not respond. Check its power, Wi-Fi and firmware, then refresh.' });
    }
}
