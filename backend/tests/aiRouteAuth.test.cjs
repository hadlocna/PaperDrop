const {test}=require('node:test');const assert=require('node:assert/strict');const express=require('express');const http=require('node:http');const jwt=require('jsonwebtoken');
const {AiController}=require('../dist/controllers/AiController');
let calls=0;AiController.generateDesign=async(req,res)=>{calls++;res.json({userId:req.user.userId});};
const router=require('../dist/routes/aiRoutes').default;
test('real image route requires a valid user session before invoking generation',async()=>{
 const previous=process.env.JWT_SECRET;process.env.JWT_SECRET='test-only-application-secret';
 const app=express();app.use(express.json());app.use('/api/ai',router);const server=http.createServer(app);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url=`http://127.0.0.1:${server.address().port}/api/ai/generate`;
 try {
  const request=token=>fetch(url,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify({prompt:'A test drawing'})});
  assert.equal((await request()).status,401);assert.equal((await request('invalid-test-token')).status,403);assert.equal(calls,0);
  const token=jwt.sign({userId:'test-user',email:'fixture@example.invalid'},process.env.JWT_SECRET,{expiresIn:60});const response=await request(token);assert.equal(response.status,200);assert.deepEqual(await response.json(),{userId:'test-user'});assert.equal(calls,1);
 } finally {if(previous===undefined)delete process.env.JWT_SECRET;else process.env.JWT_SECRET=previous;await new Promise(resolve=>server.close(resolve));}
});
