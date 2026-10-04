const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
let transcriptions, images, transcript, pause, release, qualities, imageCalls;
class FakeAI {
 audio={transcriptions:{create:async()=>{transcriptions++; if(pause)await new Promise(r=>release=r);return {text:transcript};}}};
 moderations={create:async()=>({results:[{flagged:false}]})};
 images={
  generate:async(options)=>{imageCalls.push({kind:'generate',options});qualities.push(options.quality);images++;return {data:[{b64_json:'dGVzdA=='}]};},
  edit:async(options)=>{imageCalls.push({kind:'edit',options});qualities.push(options.quality);images++;return {data:[{b64_json:'dGVzdA=='}]};}
 };
}
require('openai');require.cache[require.resolve('openai')].exports={__esModule:true,default:FakeAI,toFile:async a=>a};
const {prisma}=require('../dist/lib/prisma');
const {deviceConnections}=require('../dist/websocket/session');
const {handleRecordedVoice,closeRecordedVoice,recordedPrintStatus}=require('../dist/services/recordedVoice');
beforeEach(()=>{qualities=[];imageCalls=[];transcriptions=images=0;transcript='A lizard with Theodore underneath';pause=false;process.env.OPENAI_API_KEY='test';prisma.device.findUnique=async()=>({ownerId:'owner',config:'{"voiceEnabled":true}'});prisma.message.create=async({data})=>({...data,id:'image'});});
function fixture(id){const events=[];deviceConnections.set(id,{readyState:1,send:r=>events.push(JSON.parse(r))});const b=Buffer.alloc(32044);b.write('RIFF');b.write('WAVE',8);return {events,request:{type:'voice_request',session_id:id,audio:b.toString('base64')}};}
test('one transcription and image; sound ends only for matching print acknowledgement',async()=>{
 const {events,request}=fixture('one');await handleRecordedVoice('one',{type:'voice_start',session_id:'one'});
 assert.equal(transcriptions,0);
 await handleRecordedVoice('one',request);await handleRecordedVoice('one',request);
 assert.equal(transcriptions,1);assert.equal(images,1);
 assert.equal(imageCalls[0].kind,'edit');
 assert.equal(imageCalls[0].options.image.length,1);
 assert.match(imageCalls[0].options.prompt,/Image 1 is Theodore/);
 assert.ok(events.some(e=>e.type==='new_message'));assert.ok(!events.some(e=>e.type==='voice_end'));
 recordedPrintStatus('one','other','printed');assert.ok(!events.some(e=>e.type==='voice_end'));
 recordedPrintStatus('one','image','printed');assert.ok(events.some(e=>e.type==='voice_print_complete'));
 assert.ok(events.some(e=>e.type==='voice_end'));assert.ok(!events.some(e=>e.type==='voice_output'));
});
test('disabled and stale requests never transcribe',async()=>{
 const {request}=fixture('disabled');prisma.device.findUnique=async()=>({ownerId:'owner',config:'{"voiceEnabled":false}'});
 await handleRecordedVoice('disabled',{type:'voice_start',session_id:'disabled'});await handleRecordedVoice('disabled',request);assert.equal(transcriptions,0);
});
test('button recorded drawing does not require wake phrase listening',async()=>{
 const {events,request}=fixture('button-recorded');prisma.device.findUnique=async()=>({ownerId:'owner',config:'{"voiceEnabled":false}'});
 await handleRecordedVoice('button-recorded',{type:'voice_start',session_id:'button-recorded',mode:'recorded',quality:'low'});
 await handleRecordedVoice('button-recorded',request);
 assert.equal(transcriptions,1);assert.equal(images,1);assert.deepEqual(qualities,['low']);
 assert.ok(events.some(e=>e.type==='voice_ready'));
 assert.ok(events.some(e=>e.type==='new_message'));
 closeRecordedVoice('button-recorded');
});
test('wake listening disabled during generation prevents delivery',async()=>{
 const {events,request}=fixture('disabled-during-generation');
 await handleRecordedVoice('disabled-during-generation',{type:'voice_start',session_id:'disabled-during-generation'});
 prisma.device.findUnique=async()=>({ownerId:'owner',config:'{"voiceEnabled":false}'});
 await handleRecordedVoice('disabled-during-generation',request);
 assert.ok(!events.some(e=>e.type==='new_message'));
 assert.ok(events.some(e=>e.type==='voice_end'));
});
test('ownership changed during button drawing prevents delivery',async()=>{
 const {events,request}=fixture('owner-changed');
 await handleRecordedVoice('owner-changed',{type:'voice_start',session_id:'owner-changed',mode:'recorded'});
 prisma.device.findUnique=async()=>({ownerId:'another-owner',config:'{"voiceEnabled":false}'});
 await handleRecordedVoice('owner-changed',request);
 assert.ok(!events.some(e=>e.type==='new_message'));
 assert.ok(events.some(e=>e.type==='voice_end'));
});
test('cancelled transcription cannot later create or print an image',async()=>{
 const {events,request}=fixture('cancel');await handleRecordedVoice('cancel',{type:'voice_start',session_id:'cancel'});pause=true;
 const job=handleRecordedVoice('cancel',request);await new Promise(r=>setImmediate(r));closeRecordedVoice('cancel');release();await job;
 assert.equal(images,0);assert.ok(!events.some(e=>e.type==='new_message'));
});
test('empty or common noise hallucination does not print',async()=>{
 const {request}=fixture('noise');transcript='Thank you.';await handleRecordedVoice('noise',{type:'voice_start',session_id:'noise'});await handleRecordedVoice('noise',request);assert.equal(images,0);
});

test('button station can explicitly select Flare low quality',async()=>{const {request}=fixture('low-quality');await handleRecordedVoice('low-quality',{type:'voice_start',session_id:'low-quality',quality:'low'});await handleRecordedVoice('low-quality',request);assert.deepEqual(qualities,['low']);closeRecordedVoice('low-quality');});
test('unnamed prompts use text generation and multiple named cousins use both faces',async()=>{
 const first=fixture('plain');transcript='A princess in a castle';
 await handleRecordedVoice('plain',{type:'voice_start',session_id:'plain'});await handleRecordedVoice('plain',first.request);
 assert.equal(imageCalls[0].kind,'generate');closeRecordedVoice('plain');
 const second=fixture('two');transcript='Alma and Elise as princesses';
 await handleRecordedVoice('two',{type:'voice_start',session_id:'two'});await handleRecordedVoice('two',second.request);
 assert.equal(imageCalls[1].kind,'edit');assert.equal(imageCalls[1].options.image.length,2);
 assert.match(imageCalls[1].options.prompt,/Image 1 is Alma\. Image 2 is Elise/);
 closeRecordedVoice('two');
});
