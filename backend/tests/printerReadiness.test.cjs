const {test,beforeEach}=require('node:test');const assert=require('node:assert/strict');
const {prisma}=require('../dist/lib/prisma');const {deviceConnections}=require('../dist/websocket/session');
const {HOUSES}=require('../dist/services/housePostcards');const {handlePrinterReadiness,readinessId}=require('../dist/services/printerReadiness');
let rows,events;const ohio=HOUSES.ohio.deviceId,lisbon=HOUSES.portugal.deviceId;
const matches=(r,w)=>Object.entries(w).every(([k,v])=>typeof v==='object'?v.in.includes(r[k]):r[k]===v);
beforeEach(()=>{rows=new Map();events=[];deviceConnections.clear();
 for(const d of [ohio,lisbon])deviceConnections.set(d,{readyState:1,send:s=>events.push({device:d,...JSON.parse(s)})});
 prisma.device.findUnique=async()=>({ownerId:'owner'});
 prisma.message.create=async({data})=>{if(rows.has(data.id))throw {code:'P2002'};rows.set(data.id,{...data});return data;};
 prisma.message.findMany=async({where})=>[...rows.values()].filter(r=>matches(r,where));
 prisma.message.updateMany=async({where,data})=>{for(const r of rows.values())if(matches(r,where))Object.assign(r,data);};
});
test('only actual ready report queues a notice; reconnects queue exactly one per cousin',async()=>{
 await handlePrinterReadiness(ohio,{type:'heartbeat'});await handlePrinterReadiness(ohio,{type:'printer_ready',ready:false,firmware:'2.1.1'});assert.equal(rows.size,0);
 await Promise.all([1,2,3].map(()=>handlePrinterReadiness(ohio,{type:'printer_ready',ready:true,firmware:'2.1.1'})));
 assert.equal(rows.size,1);const row=rows.get(readinessId(ohio));assert.equal(row.deviceId,lisbon);assert.equal(row.status,'queued');assert.equal(JSON.parse(row.content).house,'ohio');
});
test('Lisbon fetches retained notice and receipt stops redelivery; other devices cannot fetch or acknowledge',async()=>{
 await handlePrinterReadiness(ohio,{type:'printer_ready',ready:true,firmware:'2.1.1'});
 events=[];await handlePrinterReadiness(ohio,{type:'printer_notice_sync'});assert.equal(events.length,0);
 await handlePrinterReadiness(lisbon,{type:'printer_notice_sync'});assert.equal(events[0].message.id,readinessId(ohio));
 await handlePrinterReadiness(ohio,{type:'printer_notice_receipt',id:readinessId(ohio),status:'printed'});assert.equal(rows.get(readinessId(ohio)).status,'sent');
 await handlePrinterReadiness(lisbon,{type:'printer_notice_receipt',id:readinessId(ohio),status:'printed'});
 await handlePrinterReadiness(lisbon,{type:'printer_notice_receipt',id:readinessId(ohio),status:'failed'});assert.equal(rows.get(readinessId(ohio)).status,'printed');
 events=[];await handlePrinterReadiness(lisbon,{type:'printer_notice_sync'});assert.equal(events.length,0);
});
test('unmapped devices and Lisbon itself cannot create cousin notifications',async()=>{
 for(const id of ['unknown',lisbon])await handlePrinterReadiness(id,{type:'printer_ready',ready:true,firmware:'2.1.1'});assert.equal(rows.size,0);
});
