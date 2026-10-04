const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const ts=require('typescript');const Module=require('node:module');const path=require('node:path');
const filename=path.resolve(__dirname,'../src/api/uploadFirmware.ts');const mod=new Module(filename);mod.paths=Module._nodeModulePaths(path.dirname(filename));
mod._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename);
const {uploadFirmware}=mod.exports;
test('large upload retries the same failed chunk and completes once with checksum and unchanged bytes',async()=>{
 const previous=global.fetch;const calls=[];const progress=[];let failed=false;
 const bytes=Buffer.alloc(8*1024*1024+17,7);const form=new FormData();form.set('file',new File([bytes],'firmware.tar.gz'));form.set('version','test-1');
 global.fetch=async(url,options)=>{calls.push({url,options});if(url.endsWith('/chunks/1')&&!failed){failed=true;throw Error('connection lost');}return {ok:true,json:async()=>({version:'test-1'})};};
 try {
  await uploadFirmware('https://api.paperdrop.me','test-only',form,p=>progress.push(p));
  assert.equal(calls.length,4);assert.equal(calls[1].url,calls[2].url);
  assert.equal(calls[0].options.body.size,8*1024*1024);assert.equal(calls[2].options.body.size,17);
  const manifest=JSON.parse(calls[3].options.body);assert.equal(manifest.count,2);assert.equal(manifest.version,'test-1');assert.deepEqual(progress,[50,100]);
  const id=require('node:crypto').createHash('sha256').update(bytes).digest('hex');assert.ok(calls[3].url.includes(id));
 } finally {global.fetch=previous;}
});
test('authentication failure is surfaced without retrying or completing',async()=>{
 const previous=global.fetch;let calls=0;const form=new FormData();form.set('file',new File(['x'],'firmware.tar.gz'));
 global.fetch=async()=>{calls++;return {ok:false,status:401,json:async()=>({error:'Unauthorized'})};};
 try {await assert.rejects(uploadFirmware('https://api.paperdrop.me','test-only',form,()=>{}),/Unauthorized/);assert.equal(calls,1);}
 finally {global.fetch=previous;}
});
