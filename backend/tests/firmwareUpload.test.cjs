const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const express = require('express');
const http = require('node:http');
const { firmwareUploadRouter } = require('../dist/routes/firmwareUpload');

async function fixture(run) {
 const root = await fs.mkdtemp(path.join(os.tmpdir(), 'paperdrop-firmware-'));
 const source = path.join(root, 'source'); await fs.mkdir(source);
 await fs.writeFile(path.join(source, 'release.json'), JSON.stringify({format:2,version:'test-1'}));
 const archive = path.join(root,'test.tar.gz'); execFileSync('tar',['-czf',archive,'-C',source,'release.json']);
 const data = await fs.readFile(archive); const id = crypto.createHash('sha256').update(data).digest('hex');
 let release, creates=0;
 const db = {firmwareRelease:{findUnique:async()=>release || null, create:async({data})=>{creates++;return release={id:'release',...data};}}};
 const app=express();app.use(express.json());app.use('/upload',firmwareUploadRouter(root,db));
 const server=http.createServer(app);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base=`http://127.0.0.1:${server.address().port}/upload/${id}`;
 const put=(index,body,override=base)=>fetch(`${override}/chunks/${index}`,{method:'PUT',headers:{'Content-Type':'application/octet-stream'},body});
 const complete=(body={},override=base)=>fetch(`${override}/complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count:2,version:'test-1',...body})});
 try {await run({root,data,id,base,put,complete,creates:()=>creates});}
 finally {server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await fs.rm(root,{recursive:true,force:true});}
}

test('chunks can be retried and completed twice after a lost response without another release or publication',()=>fixture(async f=>{
 const split=Math.floor(f.data.length/2);
 assert.equal((await f.put(1,f.data.subarray(split))).status,200);
 assert.equal((await f.put(0,f.data.subarray(0,split))).status,200);
 assert.equal((await f.put(0,f.data.subarray(0,split))).status,200);
 const first=await f.complete();assert.equal(first.status,200);const release=await first.json();assert.equal(release.sha256,f.id);
 assert.equal((await f.complete()).status,200);assert.equal(f.creates(),1);
 assert.deepEqual(await fs.readFile(path.join(f.root,path.basename(release.url))),f.data);
 assert.ok(!(await fs.readdir(f.root)).includes('stable.json'));
}));
test('missing chunks and corrupted checksum never register a release',()=>fixture(async f=>{
 await f.put(0,f.data.subarray(0,10));assert.equal((await f.complete()).status,400);
 await f.put(1,Buffer.from('corrupted'));assert.equal((await f.complete()).status,400);assert.equal(f.creates(),0);
}));
test('version mismatch and unsafe manifests are rejected',()=>fixture(async f=>{
 await f.put(0,f.data.subarray(0,10));await f.put(1,f.data.subarray(10));
 assert.equal((await f.complete({version:'wrong-version'})).status,400);
 assert.equal((await f.complete({version:'../escape'})).status,400);
 assert.equal((await f.complete({count:76})).status,400);assert.equal(f.creates(),0);
 assert.equal((await f.put(75,Buffer.from('x'))).status,400);
 assert.equal((await f.put(0,Buffer.from('x'),f.base.replace(f.id,'not-a-sha'))).status,400);
}));
test('a chunk over 8 MiB is refused before saving',()=>fixture(async f=>{
 const response=await f.put(0,Buffer.alloc(8*1024*1024+1));assert.equal(response.status,413);
 assert.ok(!(await fs.readdir(f.root)).includes('.firmware-parts'));
}));
test('another archive cannot replace an existing version',()=>fixture(async f=>{
 await f.put(0,f.data.subarray(0,10));await f.put(1,f.data.subarray(10));assert.equal((await f.complete()).status,200);
 await fs.writeFile(path.join(f.root,'source','release.json'),JSON.stringify({format:2,version:'test-1',different:true}));
 const other=execFileSync('tar',['-czf','-','-C',path.join(f.root,'source'),'release.json']);const id=crypto.createHash('sha256').update(other).digest('hex');const base=f.base.replace(f.id,id);
 await f.put(0,other,base);assert.equal((await f.complete({count:1},base)).status,409);assert.equal(f.creates(),1);
}));
test('production chunk route is protected by existing admin authentication',async()=>{
 const router=require('../dist/routes/admin').default;
 const app=express();app.use('/api/admin',router);const server=http.createServer(app);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try {
  const base=`http://127.0.0.1:${server.address().port}/api/admin/firmware-upload/invalid/chunks/0`;
  assert.equal((await fetch(base,{method:'PUT',body:'x'})).status,401);
  assert.equal((await fetch(base,{method:'PUT',headers:{'x-admin-password':'incorrect-test-only'},body:'x'})).status,401);
 } finally {server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
