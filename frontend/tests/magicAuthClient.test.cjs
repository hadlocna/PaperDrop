const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const ts=require('typescript');const Module=require('node:module');const path=require('node:path');
function load(file,overrides={}){const filename=path.resolve(__dirname,'../src',file);const mod=new Module(filename);mod.paths=Module._nodeModulePaths(path.dirname(filename));const original=mod.require.bind(mod);mod.require=name=>name in overrides?overrides[name]:original(name);mod._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename);return mod.exports;}
const {client}=load('api/client.ts',{'./baseUrl':{API_URL:'https://api.paperdrop.me/api'},'../auth/events':{AUTH_FAILURE_MESSAGES:new Set(),AUTH_EXPIRED_EVENT:'test-auth-expired'}});
const {requestMagicDesign}=load('utils/magicDesign.ts');
test('Magic uses production API base and the existing user JWT interceptor, never admin/provider credentials',async()=>{
 const previous=global.localStorage;global.localStorage={getItem:key=>key==='token'?'test-only-user-token':null};
 let request;client.defaults.adapter=async config=>{request=config;return {data:{image:'data:image/png;base64,iVBORw0KGgo='},status:200,statusText:'OK',headers:{},config};};
 try {await requestMagicDesign(client,'A test drawing',async()=>({width:576,height:800}));assert.equal(request.baseURL,'https://api.paperdrop.me/api');assert.equal(request.url,'/ai/generate');assert.equal(request.headers.Authorization,'Bearer test-only-user-token');assert.equal(request.headers['x-admin-password'],undefined);assert.deepEqual(JSON.parse(request.data),{prompt:'A test drawing'});}
 finally {if(previous===undefined)delete global.localStorage;else global.localStorage=previous;}
});
