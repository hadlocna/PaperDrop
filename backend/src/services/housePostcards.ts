import crypto from 'crypto';
import { prisma } from '../lib/prisma';
import { deviceConnections } from '../websocket/session';

// Explicit family-device mappings confirmed by the owner. These are routing IDs,
// not credentials. Clients cannot choose an arbitrary printer or sender label.
export const HOUSES: Record<string, { name: string; deviceId: string; children: Record<string, string> }> = {
    portugal: { name: 'Lisbon', deviceId: 'e040873b-82d8-4bc7-9978-b35b95f9fd32', children: { alma: 'Alma', theodore: 'Theodore', margo: 'Margaux' } },
    ohio: { name: 'Ohio', deviceId: '176462fe-7f6d-4b88-a3e8-79166b41ac08', children: { andy: 'Andi', sloan: 'Sloan', rue: 'Roux' } },
    dusseldorf: { name: 'Düsseldorf', deviceId: '2ca9894f-2681-4975-ba78-30bd119e566b', children: { elise: 'Elise', lore: 'Laure' } },
};
export function postcardId(source: string, id: string) {
    const h = crypto.createHash('sha256').update(`house-postcard:${source}:${id}`).digest('hex');
    return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20,32)}`;
}
function reply(source: string, event: any) {
    const ws = deviceConnections.get(source);
    if (ws?.readyState === 1) ws.send(JSON.stringify({type:'postcard_result', ...event}));
}
const starts = new Map<string, number[]>();
export async function handleHousePostcard(sourceId: string, event: any) {
    const requestId = event.id;
    if (typeof requestId !== 'string' || !/^[a-f0-9]{32}$/.test(requestId)) return;
    const source = Object.values(HOUSES).find(h => h.deviceId === sourceId);
    if (!source) { reply(sourceId,{id:requestId,error:'This station is not connected to the family.'}); return; }
    const id = postcardId(sourceId, requestId);
    try {
        const owner = await prisma.device.findUnique({where:{id:sourceId},select:{ownerId:true}});
        if (!owner?.ownerId) throw Error('Station must have an owner.');
        let message = await prisma.message.findUnique({where:{id}});
        if (event.type === 'postcard_status') {
            if (!message || message.senderId !== owner.ownerId) {
                reply(sourceId,{id:requestId,status:'not_found'}); return;
            }
            reply(sourceId,{id:requestId,message_id:id,status:message.status}); return;
        }
        const target = HOUSES[event.house];
        if (!target || target === source || !Object.prototype.hasOwnProperty.call(target.children,event.recipient)) throw Error('Choose a cousin at another house.');
        if (typeof event.image !== 'string' || event.image.length > 4000000 || !/^[A-Za-z0-9+/]+={0,2}$/.test(event.image)) throw Error('Invalid image.');
        const image = Buffer.from(event.image,'base64');
        if (image.length < 8 || image.subarray(0,8).toString('hex') !== '89504e470d0a1a0a') throw Error('A PNG postcard is required.');
        if (message) {
            if (message.deviceId !== target.deviceId || message.senderId !== owner.ownerId || message.content !== event.image) throw Error('This postcard was already submitted with different contents.');
            reply(sourceId,{id:requestId,message_id:id,status:message.status}); return;
        }
        const destination = await prisma.device.findUnique({where:{id:target.deviceId},select:{ownerId:true}});
        if (!destination?.ownerId) throw Error('Recipient printer is not set up.');
        const recent=(starts.get(sourceId)||[]).filter(t=>Date.now()-t<3600000);
        if(recent.length>=30) throw Error('Please try again later.');
        starts.set(sourceId,[...recent,Date.now()]);
        const targetWs=deviceConnections.get(target.deviceId);
        const dispatchNow=targetWs?.readyState===1;
        try {
            message = await prisma.message.create({data:{id,deviceId:target.deviceId,senderId:owner.ownerId,
                contentType:'image',content:event.image,status:dispatchNow?'dispatching':'queued'}});
        } catch (error: any) {
            if (error.code !== 'P2002') throw error;
            message = await prisma.message.findUnique({where:{id}});
            if (!message || message.content !== event.image || message.deviceId !== target.deviceId) throw Error('Postcard conflict.');
            reply(sourceId,{id:requestId,message_id:id,status:message.status}); return;
        }
        if (dispatchNow && targetWs) {
            // Created as dispatching, so reconnect queue delivery cannot race this send.
            // An ambiguous disconnect never resubmits automatically.
            try {
                targetWs.send(JSON.stringify({type:'new_message',message:{...message,
                    senderName:`${source.name} - To: ${target.children[event.recipient]}`}}));
                await prisma.message.updateMany({where:{id,status:'dispatching'},data:{status:'sent',sentAt:new Date()}});
            } catch {
                // Leave dispatching as uncertain: paper could already be in progress.
            }
        }
        const current=await prisma.message.findUnique({where:{id}});
        reply(sourceId,{id:requestId,message_id:id,status:current?.status||'queued'});
    } catch (error) {
        // No source content or credentials in error output.
        reply(sourceId,{id:requestId,error:error instanceof Error && [
            'Station must have an owner.','Choose a cousin at another house.','Invalid image.',
            'A PNG postcard is required.','This postcard was already submitted with different contents.',
            'Recipient printer is not set up.','Please try again later.','Postcard conflict.'
        ].includes(error.message) ? error.message : 'The postcard could not be saved. Try again.'});
    }
}
