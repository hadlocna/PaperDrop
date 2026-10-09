const { test } = require('node:test');
const assert = require('node:assert/strict');
const { latestDeviceActivity } = require('../dist/lib/deviceActivity');
const { prisma } = require('../dist/lib/prisma');
const { getDevices, getDevice } = require('../dist/controllers/deviceController');

test('stale relay heartbeat cannot hide a fresh local heartbeat', () => {
    const now = Date.now();
    const result = latestDeviceActivity(new Date(now - 120000), new Date(now - 1000), new Date(now - 180000));
    assert.equal(result.getTime(), now - 1000);
    assert.ok(now - result.getTime() < 60000);
});

test('fresh relay or local connection timestamp wins regardless of input order', () => {
    const now = Date.now();
    assert.equal(latestDeviceActivity(new Date(now), new Date(now - 120000)).getTime(), now);
    assert.equal(latestDeviceActivity(new Date(now - 120000), new Date(now)).getTime(), now);
});

test('missing and malformed timestamps do not replace valid activity', () => {
    const valid = '2026-10-08T20:00:00Z';
    assert.equal(latestDeviceActivity('bad', undefined, valid, null).toISOString(), '2026-10-08T20:00:00.000Z');
    assert.equal(latestDeviceActivity(null, undefined, 'bad', new Date(NaN)), null);
});

test('list and detail endpoints keep a locally connected device online despite stale relay data', async () => {
    const now = new Date();
    const stale = new Date(now.getTime() - 120000).toISOString();
    const device = { id: 'probe', deviceCode: 'PD-TEST', ownerId: 'owner', lastHeartbeat: now, lastSeenAt: now };
    const originalFetch = global.fetch;
    const originalRelay = process.env.DEVICE_RELAY_URL;
    const originalMany = prisma.device.findMany;
    const originalUnique = prisma.device.findUnique;
    const originalAccess = prisma.deviceAccess.findUnique;
    try {
        process.env.DEVICE_RELAY_URL = 'https://relay.example';
        global.fetch = async () => ({ ok: true, json: async () => [{ code: 'PD-TEST', status: 'offline', lastHeartbeat: stale, lastSeen: stale }] });
        prisma.device.findMany = async () => [device];
        prisma.device.findUnique = async () => device;
        prisma.deviceAccess.findUnique = async () => null;
        for (const handler of [getDevices, getDevice]) {
            const response = { status() { return this; }, json(body) { this.body = body; } };
            await handler({ user: { userId: 'owner' }, params: { id: 'probe' }, headers: {} }, response);
            const result = Array.isArray(response.body) ? response.body[0] : response.body;
            assert.equal(result.status, 'online');
            assert.equal(result.lastHeartbeat.getTime(), now.getTime());
            assert.equal(result.lastSeenAt.getTime(), now.getTime());
        }
    } finally {
        global.fetch = originalFetch;
        if (originalRelay === undefined) delete process.env.DEVICE_RELAY_URL;
        else process.env.DEVICE_RELAY_URL = originalRelay;
        prisma.device.findMany = originalMany;
        prisma.device.findUnique = originalUnique;
        prisma.deviceAccess.findUnique = originalAccess;
    }
});
