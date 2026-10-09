const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');

function render(hasScanned = false) {
    const filename = path.resolve(__dirname, '../src/components/SpeakerSettings.tsx');
    const mod = new Module(filename);
    mod.paths = Module._nodeModulePaths(path.dirname(filename));
    const requests = [];
    let index = 0;
    const values = [{ devices: [], audioReady: true }, null, '', '', '', 50, hasScanned];
    const original = mod.require.bind(mod);
    mod.require = name => {
        if (name === 'react') return {
            useEffect() {},
            useState() { return [values[index++], () => {}]; },
        };
        if (name === './VoiceSettings') return { VoiceSettings: () => null };
        if (name === '../api/client') return { client: {
            async post(url, body) {
                requests.push({ url, body });
                return { data: { devices: [], audioReady: true } };
            },
        } };
        return original(name);
    };
    mod._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText, filename);
    const tree = mod.exports.SpeakerSettings({ deviceId: 'test-device' });
    const nodes = [];
    function visit(value) {
        if (Array.isArray(value)) return value.forEach(visit);
        if (!value || typeof value !== 'object') return;
        nodes.push(value);
        visit(value.props?.children);
    }
    visit(tree);
    return { nodes, requests };
}

test('Refresh requests discovery, not cached status', async () => {
    const { nodes, requests } = render();
    const refresh = nodes.find(node => node.type === 'button' && node.props.children === 'Refresh');
    await refresh.props.onClick();
    assert.deepEqual(requests, [{ url: '/devices/test-device/speaker', body: {
        action: 'scan', address: undefined, volume: undefined,
    } }]);
});

test('empty cached status is not presented as a failed scan', () => {
    const emptyMessage = nodes => nodes.some(node =>
        typeof node.props?.children === 'string' && node.props.children.startsWith('No speakers found'));
    assert.equal(emptyMessage(render(false).nodes), false);
    assert.equal(emptyMessage(render(true).nodes), true);
});
