import OpenAI, { toFile } from 'openai';
import { prisma } from '../lib/prisma';
import { deviceConnections } from '../websocket/session';

type Session = { id: string; ownerId?: string; busy: boolean; messageId?: string; timer: NodeJS.Timeout; abort: AbortController };
const sessions = new Map<string, Session>();
const starts = new Map<string, number[]>();
function send(deviceId: string, s: Session, event: any) {
    const ws = deviceConnections.get(deviceId);
    if (ws?.readyState === 1) ws.send(JSON.stringify({ ...event, session_id: s.id }));
}
export function hasRecordedVoice(deviceId: string) { return sessions.has(deviceId); }
export function closeRecordedVoice(deviceId: string) {
    const s = sessions.get(deviceId);
    if (!s) return;
    sessions.delete(deviceId); clearTimeout(s.timer); s.abort.abort();
    send(deviceId, s, { type: 'voice_end' });
}
export function recordedPrintStatus(deviceId: string, messageId: string, status: string) {
    const s = sessions.get(deviceId);
    if (!s || s.messageId !== messageId || !['printed', 'failed'].includes(status)) return;
    send(deviceId, s, { type: 'voice_print_complete', ok: status === 'printed' });
    closeRecordedVoice(deviceId);
}
export async function handleRecordedVoice(deviceId: string, event: any) {
    if (event.type === 'voice_start') {
        if (sessions.has(deviceId)) return;
        const s: Session = { id: event.session_id, busy: false, abort: new AbortController(), timer: setTimeout(() => {
            send(deviceId, s, { type: 'voice_error', error: 'Drawing request timed out. Please try again.' });
            closeRecordedVoice(deviceId);
        }, 180000) };
        sessions.set(deviceId, s);
        const recent = (starts.get(deviceId) || []).filter(t => Date.now() - t < 3600000);
        if (recent.length >= 20) { send(deviceId, s, {type:'voice_error', error:'Please try again later.'}); closeRecordedVoice(deviceId); return; }
        starts.set(deviceId, [...recent, Date.now()]);
        try {
            const device = await prisma.device.findUnique({ where: { id: deviceId } });
            if (sessions.get(deviceId) !== s) return;
            if (!device?.ownerId || JSON.parse(device.config || '{}').voiceEnabled !== true || !process.env.OPENAI_API_KEY) throw Error('Voice listening is not enabled.');
            s.ownerId = device.ownerId;
            send(deviceId, s, { type: 'voice_ready', mode: 'recorded' });
        } catch { send(deviceId, s, {type:'voice_error', error:'Voice listening is unavailable.'}); closeRecordedVoice(deviceId); }
        return;
    }
    const s = sessions.get(deviceId);
    if (!s || s.id !== event.session_id) return;
    if (event.type === 'voice_stop') { closeRecordedVoice(deviceId); return; }
    if (event.type !== 'voice_request' || s.busy || !s.ownerId) return;
    s.busy = true;
    try {
        if (typeof event.audio !== 'string' || event.audio.length > 2200000 || !/^[A-Za-z0-9+/]*={0,2}$/.test(event.audio)) throw Error('Invalid audio');
        const audio = Buffer.from(event.audio, 'base64');
        if (audio.length < 16044 || audio.length > 1600044 || audio.toString('ascii',0,4) !== 'RIFF' || audio.toString('ascii',8,12) !== 'WAVE') throw Error('Invalid recording');
        const ai = new OpenAI({timeout:90000, maxRetries:0});
        const options = {signal:s.abort.signal};
        const result = await ai.audio.transcriptions.create({model:'gpt-4o-mini-transcribe', file:await toFile(audio,'request.wav',{type:'audio/wav'})}, options);
        if (sessions.get(deviceId) !== s) return;
        const prompt = result.text.trim();
        if (prompt.length < 4 || prompt.length > 1500 || /^(thank you|thanks|you|yes|no|stop|bye|goodbye|hey paper drop)[.!?]*$/i.test(prompt)) throw Error('No drawing request');
        send(deviceId, s, {type:'voice_heard', text:prompt});
        const moderation = await ai.moderations.create({model:'omni-moderation-latest',input:prompt}, options);
        if (moderation.results.some(r=>r.flagged)) throw Error('Choose a child-friendly picture');
        const image = await ai.images.generate({model:'gpt-image-2.5-flare',prompt:`Create exactly the child's requested picture: ${prompt}. Preserve requested subjects and captions; do not invent extra text. Child-friendly black and white line art, bold outlines, white background, no shading or large black areas. Simple charming drawing for a thermal printer.`,n:1,size:'1024x1024',quality:'medium',output_format:'png',background:'opaque'}, options);
        const content=image.data?.[0]?.b64_json;
        if (!content) throw Error('Image generation failed');
        const current=await prisma.device.findUnique({where:{id:deviceId}});
        if (sessions.get(deviceId)!==s || JSON.parse(current?.config || '{}').voiceEnabled!==true) return;
        const message=await prisma.message.create({data:{deviceId,senderId:s.ownerId,contentType:'image',content,status:'sent',sentAt:new Date()}});
        if (sessions.get(deviceId)!==s) {
            await prisma.message.update({where:{id:message.id},data:{status:'failed',errorMessage:'Voice request cancelled before delivery'}});
            return;
        }
        s.messageId=message.id;
        send(deviceId,s,{type:'voice_print_pending',message_id:message.id});
        send(deviceId,s,{type:'new_message',message:{...message,senderName:'PaperDrop'}});
        // Pencil sound continues until this exact job reports printed or failed.
    } catch {
        if (sessions.get(deviceId)===s) {
            send(deviceId,s,{type:'voice_error',error:'I could not make that picture. Please try again.'});
            closeRecordedVoice(deviceId);
        }
    }
}
