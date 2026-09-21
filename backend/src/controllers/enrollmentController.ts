import { Request, Response } from 'express';
import jwt from 'jsonwebtoken';
import { AuthRequest } from '../middleware/authMiddleware';
import { prisma } from '../lib/prisma';
import { HOUSES } from '../services/housePostcards';

// The owner downloads this private, expiring file alongside the public image.
// Reusing the registered credential preserves ownership and postcard routing.
export async function createEnrollment(req: AuthRequest, res: Response) {
    const device = await prisma.device.findUnique({ where: { id: req.params.id } });
    if (!device || device.ownerId !== req.user?.userId) return res.status(403).json({ error: 'Only the device owner can prepare its replacement card.' });
    const secret = process.env.JWT_SECRET;
    if (!secret) return res.status(503).json({ error: 'Recovery enrollment is not configured.' });
    const token = jwt.sign({ purpose: 'paperdrop-enrollment', deviceId: device.id, ownerId: device.ownerId }, secret, { algorithm: 'HS256', expiresIn: '7d', audience: 'paperdrop-device-enrollment' });
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Disposition', 'attachment; filename="paperdrop-enrollment.json"');
    return res.json({ token });
}

export async function redeemEnrollment(req: Request, res: Response) {
    res.setHeader('Cache-Control', 'no-store');
    try {
        const secret = process.env.JWT_SECRET;
        if (!secret || typeof req.body?.token !== 'string' || req.body.token.length > 4096) throw Error('Invalid token');
        const value = jwt.verify(req.body.token, secret, { algorithms: ['HS256'], audience: 'paperdrop-device-enrollment' }) as jwt.JwtPayload;
        if (value.purpose !== 'paperdrop-enrollment' || typeof value.deviceId !== 'string') throw Error('Wrong purpose');
        const device = await prisma.device.findUnique({ where: { id: value.deviceId } });
        if (!device || !device.ownerId || device.ownerId !== value.ownerId) throw Error('Owner changed');
        const station = Object.entries(HOUSES).find(([, house]) => house.deviceId === device.id)?.[0];
        return res.json({ device_code: device.deviceCode, device_secret: device.deviceSecret, station });
    } catch {
        return res.status(403).json({ error: 'Recovery file is invalid or expired. Download a new one from device settings.' });
    }
}
