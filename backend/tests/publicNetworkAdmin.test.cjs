const { test } = require('node:test');
const assert = require('node:assert/strict');
const express = require('express');
const http = require('node:http');
process.env.OPENAI_API_KEY='test-only-not-used';
delete process.env.DEVICE_RELAY_URL;
const { prisma } = require('../dist/lib/prisma');
const { observePublicNetwork } = require('../dist/lib/publicNetwork');
const router = require('../dist/routes/admin').default;

test('admin IP response requires configured private authentication and is scoped and non-cacheable', async () => {
 const app=express();app.use('/api/admin',router);
 const server=http.createServer(app);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const endpoint=`http://127.0.0.1:${server.address().port}/api/admin/devices`;
 const previousPassword=process.env.ADMIN_PASSWORD;
 try {
  const target={id:'target',deviceCode:'PD-E0FC0D45',macAddress:null,lastSeenAt:new Date(),lastHeartbeat:new Date(),createdAt:new Date(),friendlyName:'New Printer',deviceSecret:'must-not-leak',owner:null};
  prisma.device.findMany=async()=>[target,{...target,id:'other',deviceCode:'PD-780420ea'}];
  observePublicNetwork(target.deviceCode,{socket:{remoteAddress:'8.8.8.8'},headers:{}});
  process.env.ADMIN_PASSWORD='test-only-private-admin-password';
  const unauthorized=await fetch(endpoint);assert.equal(unauthorized.status,401);
  const wrong=await fetch(endpoint,{headers:{'x-admin-password':'wrong-test-password'}});assert.equal(wrong.status,401);
  const response=await fetch(endpoint,{headers:{'x-admin-password':process.env.ADMIN_PASSWORD}});
  assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');
  const data=await response.json();assert.equal(data[0].publicNetwork.address,'8.8.8.8');assert.equal(data[1].publicNetwork,null);
  assert.equal(data[0].publicNetworkDiagnostic.access,'private_admin_configured');
  assert.equal(data[0].publicNetworkDiagnostic.heartbeatSource,'local_database');
  assert.equal(data[0].publicNetworkDiagnostic.localCapture.status,'observed');
  assert.equal(data[1].publicNetworkDiagnostic,null);
  assert.ok(data[0].createdAt);assert.equal(data[0].mac,null);assert.ok(!JSON.stringify(data).includes('must-not-leak'));
  process.env.ADMIN_PASSWORD='weak-test-password';
  const weak=await fetch(endpoint,{headers:{'x-admin-password':process.env.ADMIN_PASSWORD}});
  assert.equal(weak.status,200);const weakData=await weak.json();assert.equal(weakData[0].publicNetwork,null);
  assert.equal(weakData[0].publicNetworkDiagnostic.access,'private_admin_required');
  assert.ok(!JSON.stringify(weakData).includes('8.8.8.8'));
 } finally {
  if(previousPassword===undefined) delete process.env.ADMIN_PASSWORD; else process.env.ADMIN_PASSWORD=previousPassword;
  await new Promise(resolve=>server.close(resolve));
 }
});
