import crypto from 'crypto';
import { prisma } from '../lib/prisma';
import { deviceConnections } from '../websocket/session';
import { HOUSES } from './housePostcards';

const TYPE = 'cousin_mail';
const houseFor = (device: string) => Object.entries(HOUSES).find(([, h]) => h.deviceId === device);
const reply = (device: string, event: any) => {
    const ws = deviceConnections.get(device);
    if (ws?.readyState === 1) ws.send(JSON.stringify(event));
};
export const mailId = (device: string, id: string) => crypto.createHash('sha256').update(`cousin-mail:${device}:${id}`).digest('hex');
const starts = new Map<string, number[]>();

function validWave(bytes: Buffer): boolean {
    if (bytes.length < 44 || bytes.length > 2000000 || bytes.toString('ascii', 0, 4) !== 'RIFF'
        || bytes.toString('ascii', 8, 12) !== 'WAVE') return false;
    let rate = 0, channels = 0, dataSize = 0;
    for (let offset = 12; offset + 8 <= bytes.length;) {
        const kind = bytes.toString('ascii', offset, offset + 4);
        const size = bytes.readUInt32LE(offset + 4);
        if (offset + 8 + size > bytes.length) return false;
        if (kind === 'fmt ') {
            if (size < 16 || bytes.readUInt16LE(offset + 8) !== 1 || bytes.readUInt16LE(offset + 22) !== 16) return false;
            channels = bytes.readUInt16LE(offset + 10);
            rate = bytes.readUInt32LE(offset + 12);
        }
        if (kind === 'data') dataSize = size;
        offset += 8 + size + (size % 2);
    }
    return [1, 2].includes(channels) && rate >= 8000 && rate <= 48000
        && dataSize > 0 && dataSize % (channels * 2) === 0 && dataSize / (rate * channels * 2) <= 20;
}

// Mail is sent only in response to a capable device's authenticated mailbox sync.
// Older printer agents must never interpret a voice envelope as printable text.
export async function handleCousinMail(device: string, event: any) {
    const source = houseFor(device);
    if (!source) return;
    try {
        if (event.type === 'mail_sync') {
            const messages = await prisma.message.findMany({where: {deviceId: device, contentType: TYPE,
                status: {in: ['queued', 'sent']}}, orderBy: {createdAt: 'asc'}, take: 20});
            for (const message of messages) {
                reply(device, {type: 'cousin_mail', message: {id: message.id, ...JSON.parse(message.content)}});
                await prisma.message.updateMany({where: {id: message.id, status: 'queued'}, data: {status: 'sent', sentAt: new Date()}});
            }
            return;
        }
        if (event.type === 'mail_receipt') {
            if (typeof event.id !== 'string' || !/^[a-f0-9]{64}$/.test(event.id)) return;
            const message = await prisma.message.findUnique({where: {id: event.id}});
            if (!message || message.deviceId !== device || message.contentType !== TYPE) return;
            const body = JSON.parse(message.content);
            const allowed = body.kind === 'voice' ? ['received', 'read'] : ['printed', 'failed'];
            if (!allowed.includes(event.status)) return;
            if (['read', 'printed'].includes(message.status || '')) return;
            await prisma.message.updateMany({where: {id: message.id, deviceId: device, contentType: TYPE,
                status: {notIn: ['read', 'printed']}}, data: {status: event.status,
                ...(event.status === 'printed' ? {printedAt: new Date()} : {})}});
            return;
        }
        if (typeof event.id !== 'string' || !/^[a-f0-9]{32}$/.test(event.id)) return;
        const id = mailId(device, event.id);
        if (event.type === 'mail_status') {
            const message = await prisma.message.findUnique({where: {id}});
            reply(device, {type: 'mail_result', id: event.id, status: message?.status || 'not_found'});
            return;
        }
        const target = HOUSES[event.house];
        if (!target || target.deviceId === device || !Object.prototype.hasOwnProperty.call(target.children, event.recipient)
            || !Object.prototype.hasOwnProperty.call(source[1].children, event.sender)) throw Error('Choose the sending child and a cousin at another house.');
        if (!['voice', 'drawing'].includes(event.kind) || typeof event.media !== 'string'
            || event.media.length > 4000000 || !/^[A-Za-z0-9+/]+={0,2}$/.test(event.media)) throw Error('Invalid mail media.');
        const bytes = Buffer.from(event.media, 'base64');
        if (event.kind === 'drawing' && bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw Error('Invalid picture.');
        if (event.kind === 'voice' && !validWave(bytes)) throw Error('Invalid recording.');
        const content = JSON.stringify({kind: event.kind, sender: event.sender, senderHouse: source[0],
            senderName: source[1].children[event.sender], recipient: event.recipient, house: event.house,
            recipientName: target.children[event.recipient], media: event.media});
        const owner = await prisma.device.findUnique({where: {id: device}, select: {ownerId: true}});
        const destination = await prisma.device.findUnique({where: {id: target.deviceId}, select: {ownerId: true}});
        if (!owner?.ownerId || !destination?.ownerId) throw Error('House setup is incomplete.');
        let message = await prisma.message.findUnique({where: {id}});
        if (!message) {
            const recent = (starts.get(device) || []).filter(t => Date.now() - t < 3600000);
            if (recent.length >= 30) throw Error('Please try again later.');
            starts.set(device, [...recent, Date.now()]);
            try {
                message = await prisma.message.create({data: {id, deviceId: target.deviceId, senderId: owner.ownerId,
                    contentType: TYPE, content, status: 'queued'}});
            } catch (error: any) {
                if (error.code !== 'P2002') throw error;
                message = await prisma.message.findUnique({where: {id}});
            }
        }
        if (!message || message.content !== content || message.deviceId !== target.deviceId || message.senderId !== owner.ownerId)
            throw Error('This message ID already has different contents.');
        reply(device, {type: 'mail_result', id: event.id, status: message.status});
    } catch {
        reply(device, {type: 'mail_result', id: event.id, error: 'Mail could not be saved. Check the sender and recipient, then retry.'});
    }
}
