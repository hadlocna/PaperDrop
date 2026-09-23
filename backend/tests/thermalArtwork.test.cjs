const {test}=require('node:test');
const assert=require('node:assert/strict');
let imageOptions,refineOptions,flagged=false;
class FakeAI {
 moderations={create:async()=>({results:[{flagged}]})};
 chat={completions:{create:async opts=>{refineOptions=opts;return {choices:[{message:{content:JSON.stringify({image_prompt:'A pirate map',layout_description:'A winding route with three landmarks',generation_instructions:'Keep the island readable'})}}]}}}};
 images={generate:async opts=>{imageOptions=opts;return {data:[{b64_json:'dGVzdA=='}]}},edit:async opts=>{imageOptions=opts;return {data:[{b64_json:'dGVzdA=='}]}}};
}
require('openai');require.cache[require.resolve('openai')].exports={__esModule:true,default:FakeAI,toFile:async value=>value};
const {AiController}=require('../dist/controllers/AiController');
const {IMAGE_MODEL,imagePrompt,DESIGN_SYSTEM_PROMPT}=require('../dist/services/thermalArtwork');
function response(){return {code:200,status(c){this.code=c;return this},json(v){this.body=v;return this}}}
test('web creator uses current model and preserves request and layout in the image call',async()=>{
 process.env.OPENAI_API_KEY='test';flagged=false;
 const prompt='A treasure map for Margaux with three islands and the words Bonjour Margaux';const res=response();
 await AiController.generateDesign({body:{prompt}},res);
 assert.equal(res.code,200);assert.equal(imageOptions.model,IMAGE_MODEL);assert.equal(IMAGE_MODEL,'gpt-image-2.5-flare');
 assert.equal(imageOptions.image.length,1);assert.match(imageOptions.prompt,/Image 1 is Margaux/);
 assert.ok(imageOptions.prompt.includes(prompt));assert.ok(imageOptions.prompt.includes('A winding route with three landmarks'));
 assert.equal(refineOptions.messages[0].content,DESIGN_SYSTEM_PROMPT);
 assert.ok(imageOptions.prompt.includes('coloring-page style only when requested'));
 assert.ok(imageOptions.prompt.includes('sparse hatching'));assert.ok(res.body.image.startsWith('data:image/png;base64,'));
});
test('blank and non-string prompts never reach generation',async()=>{
 for(const prompt of ['', ' ',42,{},'a'.repeat(3001)]){imageOptions=null;const res=response();await AiController.generateDesign({body:{prompt}},res);assert.equal(res.code,400);assert.equal(imageOptions,null)}
});
test('flagged web requests never reach image generation',async()=>{
 flagged=true;imageOptions=null;const res=response();await AiController.generateDesign({body:{prompt:'flagged fixture'}},res);
 assert.equal(res.code,400);assert.equal(imageOptions,null);flagged=false;
});
test('voice artwork contract preserves exact captions and supports functional formats',()=>{
 const prompt='A four-panel comic: "Olá avó!"';const result=imagePrompt(prompt);
 assert.ok(result.includes(JSON.stringify(prompt)));assert.ok(result.includes('comic strip'));assert.ok(result.includes('576'));
 assert.ok(result.includes('family'));assert.ok(result.includes('Avoid large dense black'));
});
