const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const { prisma } = require('../dist/lib/prisma');
const deviceHandler = require('../dist/websocket/deviceHandler');
const { speakerCommand } = require('../dist/controllers/speakerController');
let calls;
beforeEach(() => {
    calls = [];
    prisma.device.findUnique = async () => ({ id: 'device', ownerId: 'owner' });
    deviceHandler.requestFromDevice = async (...args) => { calls.push(args); return { ok: true, devices: [] }; };
});
async function request(body, userId = 'owner') {
    const res = { code: 200, status(code) { this.code = code; return this; }, json(body) { this.body = body; return this; } };
    await speakerCommand({ params: { id: 'device' }, method: 'POST', body, user: { userId } }, res);
    return res;
}
test('non-owner cannot discover, pair, or capture microphone audio', async () => {
    for (const action of ['scan', 'connect', 'microphone_test']) {
        assert.equal((await request({ action }, 'sender')).code, 403);
    }
    assert.equal(calls.length, 0);
});
test('invalid address is rejected before sending a device command', async () => {
    assert.equal((await request({ action: 'connect', address: 'AA:BB:CC:DD:EE:FF;reboot' })).code, 400);
    assert.equal(calls.length, 0);
});
test('unbounded audio uploads cannot reach the device', async () => {
    assert.equal((await request({ action: 'play', audio: 'x'.repeat(2000001) })).code, 400);
    assert.equal(calls.length, 0);
});
test('offline devices do not return successful pairing', async () => {
    deviceHandler.requestFromDevice = async () => { throw Error('device_offline'); };
    assert.equal((await request({ action: 'connect', address: 'AA:BB:CC:DD:EE:FF' })).code, 503);
});
test('a device pairing failure remains an error response', async () => {
    deviceHandler.requestFromDevice = async () => ({ ok: false, error: 'Pairing failed' });
    const response = await request({ action: 'connect', address: 'AA:BB:CC:DD:EE:FF' });
    assert.equal(response.code, 409);
    assert.equal(response.body.error, 'Pairing failed');
});
test('owner scan waits for the device result', async () => {
    const response = await request({ action: 'scan' });
    assert.equal(response.code, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], 'device');
    assert.equal(calls[0][1].type, 'speaker');
});
