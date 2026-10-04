// Local integration fixture: real voice handler and WebSocket transport, with
// database/provider boundaries replaced. No credentials or hardware are used.
const { WebSocketServer } = require('ws');
let transcriptions = 0, images = 0, messages = 0;
const starts = [], statuses = [];
class FakeAI {
    audio = { transcriptions: { create: async () => {
        transcriptions++;
        return { text: 'A friendly snail in a garden' };
    } } };
    moderations = { create: async () => ({ results: [{ flagged: false }] }) };
    images = { generate: async () => {
        images++;
        return { data: [{ b64_json: process.env.PAPERDROP_TEST_IMAGE }] };
    } };
}
require('openai');
require.cache[require.resolve('openai')].exports = { __esModule: true, default: FakeAI, toFile: async a => a };
process.env.OPENAI_API_KEY = 'integration-test-only';
const { prisma } = require('../../dist/lib/prisma');
const { deviceConnections } = require('../../dist/websocket/session');
const { handleVoice, closeVoice } = require('../../dist/services/realtimeVoice');
prisma.device.findUnique = async () => ({ ownerId: 'test-owner', config: '{"voiceEnabled":false}' });
prisma.message.create = async ({ data }) => ({ ...data, id: `drawing-${++messages}` });
const server = new WebSocketServer({ host: '127.0.0.1', port: 0 });
server.on('listening', () => console.log(JSON.stringify({ port: server.address().port })));
server.on('connection', ws => {
    deviceConnections.set('test-device', ws);
    ws.on('message', async raw => {
        try {
            const event = JSON.parse(raw);
            if (event.type === 'test_stats') {
                ws.send(JSON.stringify({ type: 'test_stats', transcriptions, images, messages, starts, statuses }));
            } else if (event.type === 'print_status') {
                statuses.push(event);
            } else {
                if (event.type === 'voice_start') starts.push(event);
                await handleVoice('test-device', event);
            }
        } catch (error) {
            ws.send(JSON.stringify({ type: 'fixture_error', error: String(error) }));
        }
    });
    ws.on('close', () => closeVoice('test-device'));
});
