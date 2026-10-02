const { test } = require('node:test');
const assert = require('node:assert/strict');
const { observedPublicAddress, observePublicNetwork, publicNetworkForAdmin, validatePublicNetwork, IP_DIAGNOSTIC_TTL_MS } = require('../dist/lib/publicNetwork');
const req = (peer, forwarded) => ({socket:{remoteAddress:peer},headers:forwarded === undefined ? {} : {'x-forwarded-for':forwarded}});

test('untrusted forwarding headers cannot replace the actual public peer', () => {
 assert.deepEqual(observedPublicAddress(req('8.8.8.8','1.1.1.1'), ''), {address:'8.8.8.8',source:'socket'});
 assert.equal(observedPublicAddress(req('10.0.0.2','8.8.8.8'), ''), null);
 assert.deepEqual(observedPublicAddress(req('::ffff:8.8.8.8'), ''), {address:'8.8.8.8',source:'socket'});
});
test('explicit trusted proxy chain stops at first untrusted hop, not spoofed leftmost client', () => {
 assert.deepEqual(observedPublicAddress(req('10.0.0.2','1.1.1.1, 8.8.8.8, 10.0.0.3'),'10.0.0.2,10.0.0.3'),{address:'8.8.8.8',source:'trusted_proxy'});
 assert.equal(observedPublicAddress(req('10.0.0.2','8.8.8.8, 192.168.1.1'),'10.0.0.2'),null);
 for(const malformed of ['bad, 8.8.8.8','8.8.8.8:443','8.8.8.8,',Array(17).fill('8.8.8.8').join(',')]) assert.equal(observedPublicAddress(req('10.0.0.2',malformed),'10.0.0.2'),null);
});
test('private, shared NAT, documentation and multicast addresses are not public-IP evidence', () => {
 for(const address of ['127.0.0.1','10.0.0.1','172.16.0.1','192.168.1.1','100.64.0.1','169.254.1.1','192.0.2.1','198.51.100.1','203.0.113.1','224.0.0.1','::1','fc00::1','fe80::1','2001:db8::1']) assert.equal(observedPublicAddress(req(address),''),null,address);
 assert.deepEqual(observedPublicAddress(req('2606:4700:4700::1111'),''),{address:'2606:4700:4700::1111',source:'socket'});
});
test('only authorized target is retained, latest replaces previous, samples expire', () => {
 const now=Date.now();
 observePublicNetwork('PD-E0FC0D45',req('8.8.8.8'),now);
 observePublicNetwork('PD-780420ea',req('1.1.1.1'),now);
 assert.equal(publicNetworkForAdmin('PD-780420ea',undefined,now),null);
 assert.equal(publicNetworkForAdmin('PD-E0FC0D45',undefined,now).address,'8.8.8.8');
 observePublicNetwork('PD-E0FC0D45',req('1.1.1.1'),now+1);
 assert.equal(publicNetworkForAdmin('PD-E0FC0D45',undefined,now+1).address,'1.1.1.1');
 assert.equal(publicNetworkForAdmin('PD-E0FC0D45',undefined,now+1+IP_DIAGNOSTIC_TTL_MS),null);
});
test('relay observations must be fresh, public, valid and authorized for this code', () => {
 const now=Date.now(); const sample={address:'8.8.8.8',observedAt:new Date(now).toISOString(),source:'socket'};
 assert.deepEqual(publicNetworkForAdmin('PD-E0FC0D45',sample,now),sample);
 assert.equal(publicNetworkForAdmin('PD-883bfd8f',sample,now),null);
 for(const changed of [{address:'10.0.0.1'},{source:'device_reported'},{observedAt:'invalid'},{observedAt:new Date(now+1).toISOString()},{observedAt:new Date(now-IP_DIAGNOSTIC_TTL_MS).toISOString()}]) assert.equal(validatePublicNetwork({...sample,...changed},now),null);
});
