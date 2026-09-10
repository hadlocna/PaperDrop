const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const { prisma } = require('../dist/lib/prisma');
const handler = require('../dist/websocket/deviceHandler');
const { voiceCommand } = require('../dist/controllers/voiceController');
let config, calls;
beforeEach(() => {
    config = { voiceEnabled: false, otherSetting: 'keep' }; calls = [];
    prisma.device.findUnique = async () => ({ id: 'device', ownerId: 'owner', config: JSON.stringify(config) });
    prisma.device.update = async ({data}) => { config = JSON.parse(data.config); };
    handler.requestFromDevice = async (...args) => { calls.push(args); return { ok: true }; };
});
async function request(action, userId = 'owner') {
    const res = { code: 200, status(n) { this.code=n;return this; }, json(b) {this.body=b;return this;} };
    await voiceCommand({ params:{id:'device'},method:'POST',body:{action},user:{userId} },res);
    return res;
}
test('senders cannot turn on a child device microphone', async () => {
    assert.equal((await request('enable','sender')).code,403); assert.equal(calls.length,0); assert.equal(config.voiceEnabled,false);
});
test('wake requires the owner to enable listening first', async () => {
    assert.equal((await request('wake')).code,409); assert.equal(calls.length,0);
});
test('enabling preserves existing device settings', async () => {
    assert.equal((await request('enable')).code,200); assert.equal(config.voiceEnabled,true); assert.equal(config.otherSetting,'keep'); assert.equal(calls[0][1].enabled,true);
});
test('disabling persists even if the device is offline', async () => {
    config.voiceEnabled=true;
    handler.requestFromDevice=async()=>{throw Error('device_offline')};
    assert.equal((await request('disable')).code,503); assert.equal(config.voiceEnabled,false);
});
