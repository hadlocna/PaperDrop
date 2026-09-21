const {test,beforeEach}=require('node:test');const assert=require('node:assert/strict');
const {prisma}=require('../dist/lib/prisma');const {deviceConnections}=require('../dist/websocket/session');
const {handleHousePostcard,HOUSES,postcardId}=require('../dist/services/housePostcards');
let db,events,prints;const source=HOUSES.portugal.deviceId;
const event={type:'postcard_send',id:'a'.repeat(32),house:'dusseldorf',recipient:'lore',image:Buffer.from('89504e470d0a1a0a00000000','hex').toString('base64')};
beforeEach(()=>{db=new Map();events=[];prints=[];deviceConnections.clear();
 deviceConnections.set(source,{readyState:1,send:r=>events.push(JSON.parse(r))});
 prisma.device.findUnique=async()=>({ownerId:'owner'});
 prisma.message.findUnique=async({where})=>db.get(where.id)||null;
 prisma.message.create=async({data})=>{if(db.has(data.id))throw {code:'P2002'};db.set(data.id,{...data});return {...data};};
 prisma.message.updateMany=async({where,data})=>{const m=db.get(where.id);if(m&&(!where.status||m.status===where.status)){Object.assign(m,data);return {count:1};}return {count:0};};
});
test('known cousin receives one image; duplicate send never prints twice',async()=>{
 deviceConnections.set(HOUSES.dusseldorf.deviceId,{readyState:1,send:r=>prints.push(JSON.parse(r))});
 await handleHousePostcard(source,event);await handleHousePostcard(source,event);
 assert.equal(prints.length,1);assert.equal(db.size,1);assert.match(prints[0].message.senderName,/Lisbon.*Laure/);
 assert.equal(events.at(-1).status,'sent');
});
test('offline house queues durably and status reflects later print',async()=>{
 const e={...event,house:'ohio',recipient:'andy'};await handleHousePostcard(source,e);
 assert.equal(events.at(-1).status,'queued');const id=postcardId(source,e.id);db.get(id).status='printed';
 await handleHousePostcard(source,{type:'postcard_status',id:e.id});assert.equal(events.at(-1).status,'printed');
});
test('unknown station or mismatched recipient cannot send',async()=>{
 await handleHousePostcard('unmapped',event);await handleHousePostcard(source,{...event,recipient:'andy'});
 assert.equal(db.size,0);assert.ok(events.at(-1).error);
});
test('same id with different content is rejected',async()=>{
 await handleHousePostcard(source,event);await handleHousePostcard(source,{...event,image:event.image.replace(/A/g,'B')});
 assert.equal(db.size,1);assert.ok(events.at(-1).error);
});
test('concurrent duplicate requests create and dispatch once',async()=>{
 deviceConnections.set(HOUSES.dusseldorf.deviceId,{readyState:1,send:r=>prints.push(JSON.parse(r))});
 await Promise.all([handleHousePostcard(source,event),handleHousePostcard(source,event)]);
 assert.equal(prints.length,1);assert.equal(db.size,1);
});
test('fast print acknowledgement is not overwritten as sent',async()=>{
 deviceConnections.set(HOUSES.dusseldorf.deviceId,{readyState:1,send:r=>{const p=JSON.parse(r);db.get(p.message.id).status='printed';}});
 await handleHousePostcard(source,event);assert.equal(events.at(-1).status,'printed');
});
test('ambiguous dispatch never retries automatically',async()=>{
 deviceConnections.set(HOUSES.dusseldorf.deviceId,{readyState:1,send:()=>{throw Error('connection lost');}});
 await handleHousePostcard(source,event);assert.equal(events.at(-1).status,'dispatching');
 await handleHousePostcard(source,event);assert.equal(db.size,1);assert.equal(events.at(-1).status,'dispatching');
});
