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
