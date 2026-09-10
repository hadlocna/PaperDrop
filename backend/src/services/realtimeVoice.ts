import WebSocket from 'ws';
import OpenAI from 'openai';
import { prisma } from '../lib/prisma';
import { deviceConnections } from '../websocket/session';

type Voice = { ws: WebSocket; timer: NodeJS.Timeout; ready: boolean; printed: boolean; ending?: boolean; calls: Set<string>; generation?: Promise<void> };
const sessions = new Map<string, Voice>();
const starts = new Map<string, number[]>();
function send(deviceId: string, event: any) {
    const ws = deviceConnections.get(deviceId);
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(event));
}
export function closeVoice(deviceId: string) {
    const session = sessions.get(deviceId);
    if (!session) return;
    sessions.delete(deviceId);
    clearTimeout(session.timer);
    session.ws.close();
    send(deviceId, { type: 'voice_end' });
}
export const VOICE_INSTRUCTIONS = `You are PaperDrop, a cheerful AI drawing helper speaking with a child.
Use short, warm, playful sentences and simple words. You are an AI, never pretend to be human.
Help the child choose a picture and use create_picture exactly once when they clearly request one.
Keep drawings child-appropriate. Do not request names, age, address, school, secrets or other personal information.
Do not form exclusive relationships or encourage secrecy. For topics beyond drawing, briefly suggest asking a trusted grown-up.
Never claim a picture printed: the tool only confirms whether a picture was sent to the printer.
When a drawing request is clear, say one short acknowledgement and call the tool without extra questions.
After the tool returns, tell them it was sent or explain that it did not work. Then say goodbye briefly.
If asked to stop, be quiet, go to sleep, or wait for the wake word, call end_conversation. Never just promise to wait while keeping the conversation open.`;

export async function handleVoice(deviceId: string, event: any) {
    if (event.type === 'voice_stop') { closeVoice(deviceId); return; }
    if (event.type === 'voice_audio') {
        const s = sessions.get(deviceId);
        if (s?.ready && s.ws.readyState === WebSocket.OPEN && typeof event.audio === 'string' && event.audio.length <= 32768 && /^[A-Za-z0-9+/]*={0,2}$/.test(event.audio)) {
            if (s.ws.bufferedAmount > 256000) { closeVoice(deviceId); return; }
            s.ws.send(JSON.stringify({ type: 'input_audio_buffer.append', audio: event.audio }));
        }
        return;
    }
    if (event.type !== 'voice_start' || sessions.has(deviceId)) return;
    // Reserve before awaiting the database: concurrent wake events cannot open duplicate sessions.
    const now = Date.now();
    const recent = (starts.get(deviceId) || []).filter(t => now - t < 3600000);
    if (recent.length >= 20 || (recent.length && now - recent[recent.length - 1] < 5000)) {
        send(deviceId, { type: 'voice_error', error: 'Please wait a moment before another conversation.' }); return;
    }
    starts.set(deviceId, [...recent, now]);
    const device = await prisma.device.findUnique({ where: { id: deviceId } });
    if (!device?.ownerId || JSON.parse(device.config || '{}').voiceEnabled !== true || !process.env.OPENAI_API_KEY) {
        send(deviceId, { type: 'voice_error', error: 'Voice listening is not enabled or configured.' }); return;
    }
    const ws = new WebSocket(`wss://api.openai.com/v1/realtime?model=${encodeURIComponent(process.env.OPENAI_REALTIME_MODEL || 'gpt-realtime-2.1')}`, { headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` } });
    const session: Voice = { ws, ready: false, printed: false, calls: new Set(), timer: setTimeout(() => { send(deviceId, { type: 'voice_notice', reason: session.printed ? 'image' : 'no-request' }); closeVoice(deviceId); }, 120000) };
    sessions.set(deviceId, session);
    ws.on('open', () => ws.send(JSON.stringify({ type: 'session.update', session: {
        type: 'realtime', output_modalities: ['audio'], instructions: VOICE_INSTRUCTIONS,
        audio: { input: { format: { type: 'audio/pcm', rate: 24000 }, transcription: { model: 'gpt-4o-mini-transcribe' }, noise_reduction: { type: 'far_field' }, turn_detection: { type: 'server_vad', threshold: 0.35, silence_duration_ms: 900, interrupt_response: false } },
                 output: { format: { type: 'audio/pcm', rate: 24000 }, voice: 'cedar' } },
        tools: [{ type: 'function', name: 'create_picture', description: 'Generate one child-friendly drawing and send it to this PaperDrop printer.', parameters: { type: 'object', properties: { prompt: { type: 'string', description: 'Describe the requested drawing and any requested caption.' } }, required: ['prompt'], additionalProperties: false } },
        { type: 'function', name: 'end_conversation', description: 'Return to local wake-word listening when asked to stop, be quiet, sleep, wait for the keyword or end the conversation.', parameters: { type: 'object', properties: {}, additionalProperties: false } }],
        tool_choice: 'auto', max_output_tokens: 600
    } })));
    ws.on('message', async raw => {
        try {
            const e = JSON.parse(raw.toString());
            if (sessions.get(deviceId) !== session) return;
            if (e.type === 'session.updated' && !session.ready) {
                session.ready = true;
                send(deviceId, { type: 'voice_ready' });
                ws.send(JSON.stringify({ type: 'response.create', response: { instructions: 'Say exactly: I’m here! What would you like me to draw?' } }));
            } else if (e.type === 'conversation.item.input_audio_transcription.completed') {
                send(deviceId, { type: 'voice_heard', text: String(e.transcript || '').slice(0, 800) });
            } else if (e.type === 'input_audio_buffer.speech_started') {
                send(deviceId, { type: 'voice_progress', state: 'hearing_request' });
            } else if (e.type === 'input_audio_buffer.speech_stopped') {
                send(deviceId, { type: 'voice_progress', state: 'thinking' });
            } else if (e.type === 'response.output_audio_transcript.done') {
                send(deviceId, { type: 'voice_reply', text: String(e.transcript || '').slice(0, 800) });
            } else if (e.type === 'response.done' && e.response?.status === 'failed') {
                send(deviceId, { type: 'voice_error', error: 'The voice service could not complete its reply. Start another conversation.' });
                closeVoice(deviceId);
            } else if (e.type === 'response.output_audio.delta') {
                send(deviceId, { type: 'voice_output', audio: e.delta });
            } else if (e.type === 'response.output_audio.done') {
                send(deviceId, { type: 'voice_output_done' });
            } else if (e.type === 'response.function_call_arguments.done' && e.name === 'end_conversation') {
                session.ending = true;
                ws.send(JSON.stringify({ type: 'conversation.item.create', item: { type: 'function_call_output', call_id: e.call_id, output: '{"ok":true}' } }));
            } else if (e.type === 'response.function_call_arguments.done' && e.name === 'create_picture' && !session.calls.has(e.call_id)) {
                session.calls.add(e.call_id);
                session.generation = (async () => {
                    let result: any;
                    try {
                        const args = JSON.parse(e.arguments);
                        if (session.printed) throw Error('One picture per conversation. Say Hey Paper Drop again for another.');
                        if (typeof args.prompt !== 'string' || !args.prompt.trim() || args.prompt.length > 1500) throw Error('Please ask for a shorter drawing description.');
                        session.printed = true;
                        send(deviceId, { type: 'voice_progress', state: 'drawing' });
                        const ai = new OpenAI({ timeout: 90000, maxRetries: 0 });
                        const moderation = await ai.moderations.create({ model: 'omni-moderation-latest', input: args.prompt });
                        if (moderation.results.some(r => r.flagged)) throw Error('Please choose a different, child-friendly drawing.');
                        const image = await ai.images.generate({ model: 'gpt-image-2.5-flare', prompt: `Create a child-friendly drawing: ${args.prompt}. Black and white line art, bold outlines, white background, no shading, no large black areas. Simple charming doodle for a thermal receipt printer. Include only text explicitly requested.`, n: 1, size: '1024x1024', quality: 'medium', output_format: 'png', background: 'opaque' });
                        const content = image.data?.[0]?.b64_json;
                        if (!content) throw Error('The drawing could not be generated.');
                        const current = await prisma.device.findUnique({ where: { id: deviceId } });
                        if (sessions.get(deviceId) !== session || JSON.parse(current?.config || '{}').voiceEnabled !== true) return;
                        const message = await prisma.message.create({ data: { deviceId, senderId: device.ownerId!, contentType: 'image', content, status: 'sent', sentAt: new Date() } });
                        send(deviceId, { type: 'new_message', message: { ...message, senderName: 'PaperDrop' } });
                        result = { ok: true, status: 'sent_to_printer', messageId: message.id };
                    } catch (error: any) {
                        result = { ok: false, error: error.message?.slice(0, 180) || 'The drawing failed. Please try again.' };
                        if (sessions.get(deviceId) === session) {
                            send(deviceId, { type: 'voice_notice', reason: 'image' });
                            send(deviceId, { type: 'voice_error', error: 'The picture could not be created. Please try another request.' });
                            closeVoice(deviceId);
                        }
                    }
                    if (ws.readyState === WebSocket.OPEN && sessions.get(deviceId) === session) {
                        ws.send(JSON.stringify({ type: 'conversation.item.create', item: { type: 'function_call_output', call_id: e.call_id, output: JSON.stringify(result) } }));
                        ws.send(JSON.stringify({ type: 'response.create' }));
                        send(deviceId, { type: 'voice_progress', state: 'talking' });
                    }
                })();
                await session.generation;
            } else if (e.type === 'error') {
                console.error('[Voice] Realtime error:', e.error?.code);
                send(deviceId, { type: 'voice_error', error: 'The voice service could not respond. Please try again.' });
                closeVoice(deviceId);
            } else if (e.type === 'response.done' && (session.ending || (session.printed && !e.response?.output?.some((o: any) => o.type === 'function_call')))) {
                send(deviceId, { type: 'voice_finish' });
            }
        } catch { send(deviceId, { type: 'voice_error', error: 'Voice conversation failed. Please try again.' }); closeVoice(deviceId); }
    });
    ws.on('error', () => { send(deviceId, { type: 'voice_error', error: 'Unable to connect to the voice service.' }); closeVoice(deviceId); });
    ws.on('close', () => { if (sessions.get(deviceId) === session) closeVoice(deviceId); });
}
