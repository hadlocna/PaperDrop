const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const sockets = [];
class FakeSocket extends EventEmitter {
    static OPEN = 1;
    readyState = 1; bufferedAmount = 0; sent = [];
    constructor() { super(); sockets.push(this); }
    send(raw) { this.sent.push(JSON.parse(raw)); }
    close() { this.readyState = 3; this.emit('close'); }
}
require('ws');
require.cache[require.resolve('ws')].exports = FakeSocket;
let generated = 0;
require('openai');
require.cache[require.resolve('openai')].exports = class FakeAI {
    moderations = { create: async () => ({results:[{flagged:false}]}) };
    images = { generate: async () => { generated++; return {data:[{b64_json:'dGVzdA=='}]}; } };
};
const { prisma } = require('../dist/lib/prisma');
const { deviceConnections } = require('../dist/websocket/session');
const { handleVoice, closeVoice } = require('../dist/services/realtimeVoice');
process.env.OPENAI_API_KEY = 'test-only';
test('disabled devices never open an OpenAI connection', async () => {
    prisma.device.findUnique = async () => ({ ownerId:'owner',config:'{"voiceEnabled":false}' });
    await handleVoice('disabled', {type:'voice_start'});
    assert.equal(sockets.length,0);
});
test('duplicate wake events open one session and spoken stop finishes it', async () => {
    prisma.device.findUnique = async () => ({ ownerId:'owner',config:'{"voiceEnabled":true}' });
    const replies=[];
    deviceConnections.set('enabled',{readyState:1,send(raw){replies.push(JSON.parse(raw));}});
    await Promise.all([handleVoice('enabled',{type:'voice_start'}),handleVoice('enabled',{type:'voice_start'})]);
    assert.equal(sockets.length,1);
    const ws=sockets[0];
    ws.emit('message',JSON.stringify({type:'session.updated'}));
    await handleVoice('enabled',{type:'voice_audio',audio:'AAAA'});
    assert.ok(ws.sent.some(e=>e.type==='input_audio_buffer.append'));
    ws.emit('message',JSON.stringify({type:'response.function_call_arguments.done',name:'end_conversation',call_id:'stop'}));
    ws.emit('message',JSON.stringify({type:'response.done',response:{output:[{type:'function_call'}]}}));
    assert.ok(replies.some(e=>e.type==='voice_finish'));
    closeVoice('enabled');
    assert.equal(ws.readyState,3);
    const n=ws.sent.length;
    await handleVoice('enabled',{type:'voice_audio',audio:'AAAA'});
    assert.equal(ws.sent.length,n);
});

test('unconfirmed requests cannot generate or print and require a new affirmative turn', async () => {
    prisma.device.findUnique = async () => ({ ownerId:'owner',config:'{"voiceEnabled":true}' });
    let writes=0;
    prisma.message.create = async () => { writes++; throw Error('unexpected print'); };
    const replies=[];
    deviceConnections.set('confirmation',{readyState:1,send(raw){replies.push(JSON.parse(raw));}});
    await handleVoice('confirmation',{type:'voice_start'});
    const ws=sockets.at(-1);
    const emit=e=>ws.emit('message',JSON.stringify(e));
    emit({type:'input_audio_buffer.speech_started',item_id:'request'});
    emit({type:'conversation.item.input_audio_transcription.completed',item_id:'request',transcript:'Draw a lizard'});
    emit({type:'response.function_call_arguments.done',name:'create_picture',call_id:'proposal',arguments:'{"prompt":"A lizard"}'});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(writes,0);
    assert.ok(ws.sent.some(e=>e.item?.output?.includes('confirmation_required')));
    assert.ok(!replies.some(e=>e.state==='drawing'));
    emit({type:'response.done',response:{output:[{type:'function_call'}]}});
    assert.ok(ws.sent.some(e=>e.type==='response.create'));
    // Repeated tool calls and unrelated new speech cannot bypass the gate.
    emit({type:'input_audio_buffer.speech_started',item_id:'correction'});
    emit({type:'conversation.item.input_audio_transcription.completed',item_id:'correction',transcript:'No, add Theodore underneath'});
    emit({type:'response.function_call_arguments.done',name:'create_picture',call_id:'unconfirmed',arguments:'{"prompt":"A lizard"}'});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(writes,0);
    assert.ok(!replies.some(e=>e.state==='drawing'));
    closeVoice('confirmation');
});

test('new explicit confirmation generates only the reviewed prompt once', async () => {
    prisma.device.findUnique = async () => ({ ownerId:'owner',config:'{"voiceEnabled":true}' });
    prisma.message.create = async ({data}) => ({id:'confirmed-image',...data});
    const replies=[];
    deviceConnections.set('approved',{readyState:1,send(raw){replies.push(JSON.parse(raw));}});
    await handleVoice('approved',{type:'voice_start'});
    const ws=sockets.at(-1), emit=e=>ws.emit('message',JSON.stringify(e));
    emit({type:'input_audio_buffer.speech_started',item_id:'request'});
    emit({type:'response.function_call_arguments.done',name:'create_picture',call_id:'prepare',arguments:'{"prompt":"A lizard with Theodore underneath"}'});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(generated,0);
    emit({type:'input_audio_buffer.speech_started',item_id:'yes'});
    emit({type:'conversation.item.input_audio_transcription.completed',item_id:'yes',transcript:'Yes, please.'});
    emit({type:'response.function_call_arguments.done',name:'create_picture',call_id:'approved',arguments:'{"prompt":"A lizard with Theodore underneath"}'});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(generated,1);
    assert.equal(replies.filter(e=>e.type==='new_message').length,1);
    closeVoice('approved');
});
