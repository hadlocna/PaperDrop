const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const jwt = require('jsonwebtoken');
const { prisma } = require('../dist/lib/prisma');
const { createEnrollment, redeemEnrollment } = require('../dist/controllers/enrollmentController');
const response = () => ({code:200,headers:{},setHeader(k,v){this.headers[k]=v;},status(v){this.code=v;return this;},json(v){this.body=v;return this;}});
beforeEach(()=>{process.env.JWT_SECRET='test-only-key'; prisma.device.findUnique=async()=>({id:'device',ownerId:'owner',deviceCode:'PD-TEST',deviceSecret:'private-device-secret'});});
test('recovery file is owner-only and does not contain the device secret', async()=>{
 let res=response();await createEnrollment({params:{id:'device'},user:{userId:'other'}},res);assert.equal(res.code,403);
 res=response();await createEnrollment({params:{id:'device'},user:{userId:'owner'}},res);assert.equal(res.code,200);assert.ok(res.body.token);assert.ok(!JSON.stringify(res.body).includes('private-device-secret'));assert.equal(res.headers['Cache-Control'],'no-store');
 const output=response();await redeemEnrollment({body:res.body},output);assert.equal(output.body.device_code,'PD-TEST');assert.equal(output.body.device_secret,'private-device-secret');
});
test('expired, wrong-purpose, and transferred-owner recovery tokens fail',async()=>{
 for(const claims of [{purpose:'paperdrop-enrollment',deviceId:'device',ownerId:'old-owner'},{purpose:'login',deviceId:'device',ownerId:'owner'},{purpose:'paperdrop-enrollment',deviceId:'device',ownerId:'owner',exp:1}]){
  const token=jwt.sign(claims,process.env.JWT_SECRET,{audience:'paperdrop-device-enrollment'});const res=response();await redeemEnrollment({body:{token}},res);assert.equal(res.code,403);
 }
});
