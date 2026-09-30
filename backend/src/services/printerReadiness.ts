import crypto from 'crypto';
import { prisma } from '../lib/prisma';
import { HOUSES } from './housePostcards';
import { deviceConnections } from '../websocket/session';

const TYPE = 'printer_notice';
export const readinessId = (source: string) => crypto.createHash('sha256').update(`printer-ready-v1:${source}`).digest('hex');
const send = (id: string, event: any) => {
    const ws = deviceConnections.get(id);
    if (ws?.readyState === 1) ws.send(JSON.stringify(event));
};

export async function handlePrinterReadiness(deviceId: string, event: any) {
    const source = Object.entries(HOUSES).find(([, house]) => house.deviceId === deviceId);
    if (!source) return;
    const destination = HOUSES.portugal.deviceId;
    try {
        if (event.type === 'printer_ready') {
            if (event.ready !== true || typeof event.firmware !== 'string' || !/^[A-Za-z0-9._-]{1,80}$/.test(event.firmware)) return;
            if (deviceId !== destination) {
                const owner = await prisma.device.findUnique({where: {id: destination}, select: {ownerId: true}});
                if (!owner?.ownerId) return;
                const id = readinessId(deviceId);
                // A persistent, deterministic ID prevents reconnect/reboot notification storms.
                try {
                    await prisma.message.create({data: {id, deviceId: destination, senderId: owner.ownerId,
                        contentType: TYPE, status: 'queued', content: JSON.stringify({house: source[0],
                            name: source[1].name, firmware: event.firmware, readyAt: new Date().toISOString()})}});
                } catch (error: any) {
                    if (error.code !== 'P2002') throw error;
                }
            }
            send(deviceId, {type: 'printer_ready_ack'});
        } else if (event.type === 'printer_notice_sync' && deviceId === destination) {
            const notices = await prisma.message.findMany({where: {deviceId, contentType: TYPE,
                status: {in: ['queued','sent']}}, orderBy: {createdAt: 'asc'}, take: 10});
            for (const notice of notices) {
                send(deviceId, {type: 'printer_notice', message: {id: notice.id, ...JSON.parse(notice.content)}});
                await prisma.message.updateMany({where: {id: notice.id, status: 'queued'}, data: {status: 'sent', sentAt: new Date()}});
            }
        } else if (event.type === 'printer_notice_receipt' && deviceId === destination
                   && typeof event.id === 'string' && /^[a-f0-9]{64}$/.test(event.id)
                   && ['printed', 'failed'].includes(event.status)) {
            await prisma.message.updateMany({where: {id: event.id, deviceId, contentType: TYPE, status: {in: ['queued','sent']}},
                data: {status: event.status, ...(event.status === 'printed' ? {printedAt: new Date()} : {})}});
        }
    } catch {
        // No acknowledgement on failure: the station retries after the next readiness check.
        console.warn('Printer readiness notification unavailable');
    }
}
