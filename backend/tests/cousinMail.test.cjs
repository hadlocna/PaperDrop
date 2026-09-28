const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
const {prisma}=require('../dist/lib/prisma');
const {deviceConnections}=require('../dist/websocket/session');
const {handleCousinMail,mailId}=require('../dist/services/cousinMail');
const {HOUSES}=require('../dist/services/housePostcards');
let db,events;const source=HOUSES.portugal.deviceId,target=HOUSES.ohio.deviceId;
const wav=Buffer.alloc(32044);wav.write('RIFF');wav.write('WAVE',8);wav.writeUInt32LE(wav.length-8,4);wav.write('fmt ',12);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(16000,24);wav.writeUInt32LE(32000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(32000,40);
const event={type:'mail_send',id:'c'.repeat(32),sender:'alma',house:'ohio',recipient:'andy',kind:'voice',media:wav.toString('base64')};
function matches(m,w){return Object.entries(w).every(([k,v])=>typeof v==='object'?(v.in?v.in.includes(m[k]):!v.notIn.includes(m[k])):m[k]===v);}
beforeEach(()=>{db=new Map();events=[];deviceConnections.clear();
 for(const id of [source,target])deviceConnections.set(id,{readyState:1,send:r=>events.push({device:id,...JSON.parse(r)})});
 prisma.device.findUnique=async()=>({ownerId:'owner'});
 prisma.message.findUnique=async({where})=>db.get(where.id)||null;
 prisma.message.findMany=async({where})=>[...db.values()].filter(m=>matches(m,where));
 prisma.message.create=async({data})=>{if(db.has(data.id))throw {code:'P2002'};db.set(data.id,{...data});return {...data};};
 prisma.message.updateMany=async({where,data})=>{let count=0;for(const m of db.values())if(matches(m,where)){Object.assign(m,data);count++;}return {count};};
});
test('audio queues until capable recipient syncs; receipt survives reconnect and only recipient can acknowledge',async()=>{
 await handleCousinMail(source,event);assert.equal(db.size,1);assert.equal(events.at(-1).status,'queued');
 assert.equal(events.filter(e=>e.type==='cousin_mail').length,0);
 await handleCousinMail(target,{type:'mail_sync'});const delivery=events.at(-1);assert.equal(delivery.message.sender,'alma');assert.equal(delivery.message.recipient,'andy');
 const id=mailId(source,event.id);await handleCousinMail(source,{type:'mail_receipt',id,status:'read'});assert.equal(db.get(id).status,'sent');
 await handleCousinMail(target,{type:'mail_receipt',id,status:'received'});await handleCousinMail(target,{type:'mail_receipt',id,status:'read'});
 await handleCousinMail(target,{type:'mail_receipt',id,status:'received'});assert.equal(db.get(id).status,'read');
 events=[];await handleCousinMail(target,{type:'mail_sync'});assert.equal(events.length,0);
 await handleCousinMail(source,{type:'mail_status',id:event.id});assert.equal(events[0].status,'read');
});
test('repeated and concurrent send creates one durable message; altered recipient cannot reuse ID',async()=>{
 await Promise.all([handleCousinMail(source,event),handleCousinMail(source,event)]);assert.equal(db.size,1);
 await handleCousinMail(source,{...event,recipient:'sloan'});assert.ok(events.at(-1).error);assert.equal(db.size,1);
});
test('cross-house sender impersonation, wrong recipient and malformed media are rejected',async()=>{
 for(const patch of [{sender:'elise'},{recipient:'lore'},{media:'invalid'},{kind:'text'}])await handleCousinMail(source,{...event,...patch});
 assert.equal(db.size,0);
});
test('all houses can send back; drawing envelope retains labels and print acknowledgement is final',async()=>{
 await handleCousinMail(target,{...event,sender:'andy',recipient:'alma',house:'portugal',kind:'drawing',media:Buffer.from('89504e470d0a1a0a','hex').toString('base64')});
 await handleCousinMail(source,{type:'mail_sync'});const delivery=events.at(-1).message;
 assert.equal(delivery.senderName,'Andi');assert.equal(delivery.recipientName,'Alma');
 await handleCousinMail(source,{type:'mail_receipt',id:delivery.id,status:'printed'});
 await handleCousinMail(source,{type:'mail_receipt',id:delivery.id,status:'failed'});assert.equal(db.get(delivery.id).status,'printed');
});
test('lost receipt redelivers same ID on sync, never creates a second message',async()=>{
 await handleCousinMail(source,event);await handleCousinMail(target,{type:'mail_sync'});await handleCousinMail(target,{type:'mail_sync'});
 const deliveries=events.filter(e=>e.type==='cousin_mail');assert.equal(deliveries.length,2);assert.equal(deliveries[0].message.id,deliveries[1].message.id);
});
