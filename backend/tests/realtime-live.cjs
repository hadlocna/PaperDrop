// Explicit live smoke check; no microphone capture or print job.
const fs = require('node:fs');
if (!process.env.PAPERDROP_LIVE_TEST) { console.log('Set PAPERDROP_LIVE_TEST=1 to run the paid Realtime smoke check.'); process.exit(0); }
for (const line of fs.readFileSync(require('node:path').join(__dirname, '../.env'),'utf8').split('\n')) {
 const m=line.match(/^OPENAI_API_KEY=(.*)$/); if(m)process.env.OPENAI_API_KEY=m[1].trim().replace(/^['"]|['"]$/g,'');
}
const {prisma}=require('../dist/lib/prisma');
const {deviceConnections}=require('../dist/websocket/session');
const {handleVoice,closeVoice}=require('../dist/services/realtimeVoice');
prisma.device.findUnique=async()=>({id:'smoke',ownerId:'owner',config:'{"voiceEnabled":true}'});
let size=0; const chunks=[];
const timeout=setTimeout(()=>{closeVoice('smoke');process.exit(1)},25000);
deviceConnections.set('smoke',{readyState:1,send(raw){const e=JSON.parse(raw);if(e.type==='voice_output'){const b=Buffer.from(e.audio,'base64');size+=b.length;chunks.push(b)}else console.log(e);if(e.type==='voice_output_done'){fs.writeFileSync('/tmp/paperdrop-realtime-greeting.pcm',Buffer.concat(chunks));console.log('PCM audio bytes:',size);clearTimeout(timeout);closeVoice('smoke')}}});
handleVoice('smoke',{type:'voice_start'});
