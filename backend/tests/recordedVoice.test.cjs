const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
let transcriptions, images, transcript, pause, release;
class FakeAI {
 audio={transcriptions:{create:async()=>{transcriptions++; if(pause)await new Promise(r=>release=r);return {text:transcript};}}};
 moderations={create:async()=>({results:[{flagged:false}]})};
 images={generate:async()=>{images++;return {data:[{b64_json:'dGVzdA=='}]};}};
}
require('openai');require.cache[require.resolve('openai')].exports={__esModule:true,default:FakeAI,toFile:async a=>a};
const {prisma}=require('../dist/lib/prisma');
const {deviceConnections}=require('../dist/websocket/session');
const {handleRecordedVoice,closeRecordedVoice,recordedPrintStatus}=require('../dist/services/recordedVoice');
beforeEach(()=>{transcriptions=images=0;transcript='A lizard with Theodore underneath';pause=false;process.env.OPENAI_API_KEY='test';prisma.device.findUnique=async()=>({ownerId:'owner',config:'{"voiceEnabled":true}'});prisma.message.create=async({data})=>({...data,id:'image'});});
function fixture(id){const events=[];deviceConnections.set(id,{readyState:1,send:r=>events.push(JSON.parse(r))});const b=Buffer.alloc(32044);b.write('RIFF');b.write('WAVE',8);return {events,request:{type:'voice_request',session_id:id,audio:b.toString('base64')}};}
test('one transcription and image; sound ends only for matching print acknowledgement',async()=>{
 const {events,request}=fixture('one');await handleRecordedVoice('one',{type:'voice_start',session_id:'one'});
 assert.equal(transcriptions,0);
 await handleRecordedVoice('one',request);await handleRecordedVoice('one',request);
 assert.equal(transcriptions,1);assert.equal(images,1);
 assert.ok(events.some(e=>e.type==='new_message'));assert.ok(!events.some(e=>e.type==='voice_end'));
 recordedPrintStatus('one','other','printed');assert.ok(!events.some(e=>e.type==='voice_end'));
 recordedPrintStatus('one','image','printed');assert.ok(events.some(e=>e.type==='voice_print_complete'));
 assert.ok(events.some(e=>e.type==='voice_end'));assert.ok(!events.some(e=>e.type==='voice_output'));
});
test('disabled and stale requests never transcribe',async()=>{
 const {request}=fixture('disabled');prisma.device.findUnique=async()=>({ownerId:'owner',config:'{"voiceEnabled":false}'});
 await handleRecordedVoice('disabled',{type:'voice_start',session_id:'disabled'});await handleRecordedVoice('disabled',request);assert.equal(transcriptions,0);
});
test('cancelled transcription cannot later create or print an image',async()=>{
 const {events,request}=fixture('cancel');await handleRecordedVoice('cancel',{type:'voice_start',session_id:'cancel'});pause=true;
 const job=handleRecordedVoice('cancel',request);await new Promise(r=>setImmediate(r));closeRecordedVoice('cancel');release();await job;
 assert.equal(images,0);assert.ok(!events.some(e=>e.type==='new_message'));
});
test('empty or common noise hallucination does not print',async()=>{
 const {request}=fixture('noise');transcript='Thank you.';await handleRecordedVoice('noise',{type:'voice_start',session_id:'noise'});await handleRecordedVoice('noise',request);assert.equal(images,0);
});
