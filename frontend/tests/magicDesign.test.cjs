const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const ts=require('typescript');const Module=require('node:module');const path=require('node:path');
const filename=path.resolve(__dirname,'../src/utils/magicDesign.ts');
const mod=new Module(filename);mod._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename);
const {requestMagicDesign,magicDesignError}=mod.exports;
const png='data:image/png;base64,iVBORw0KGgo=';
test('ordinary, test and mock prompts all reach the same authenticated generation client',async()=>{
 for(const prompt of ['A dinosaur','A test image for a contest','A mockingbird in a tree']) {
  const calls=[];const api={post:async(...args)=>{calls.push(args);return {data:{image:png}};}};
  const result=await requestMagicDesign(api,prompt,async()=>({width:1024,height:1536}));
  assert.deepEqual(calls,[['/ai/generate',{prompt}]]);assert.equal(result.image,png);assert.equal(result.aspectRatio,2/3);
 }
});
test('provider failure, malformed success and remote placeholders never become mock success',async()=>{
 for(const image of [undefined,'https://placehold.co/1024x1024/png?text=Mock+AI+Image','data:text/html;base64,AAAA',''])
  await assert.rejects(requestMagicDesign({post:async()=>({data:{image}})},'A test image',async()=>({width:1,height:1})));
 const unavailable={response:{status:503}};
 await assert.rejects(requestMagicDesign({post:async()=>{throw unavailable}},'A dinosaur'),error=>error===unavailable);
 assert.match(magicDesignError(unavailable),/not configured/);
 await assert.rejects(requestMagicDesign({post:async()=>({data:{image:png}})},'A dinosaur',async()=>{throw Error('cannot decode');}));
});
test('invalid prompts do not make requests; errors never disclose provider details',async()=>{
 let calls=0;const api={post:async()=>{calls++;throw Error('must not call');}};
 for(const prompt of ['','   ','a'.repeat(3001)]) await assert.rejects(requestMagicDesign(api,prompt));assert.equal(calls,0);
 assert.ok(!magicDesignError({message:'private-provider-details',response:{status:500}}).includes('private-provider-details'));
});
