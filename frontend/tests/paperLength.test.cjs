const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const Module = require('node:module');
const path = require('node:path');
const filename=path.resolve(__dirname,'../src/utils/paperLength.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const mod=new Module(filename);mod._compile(compiled,filename);
const {paperHeightFromBounds,paperLengthMillimetres,measurePrintableHeight,MAX_PAPER_HEIGHT}=mod.exports;
test('wrapped text or rotated artwork beyond the initial page expands automatically',()=>{
 assert.equal(paperHeightFromBounds(100,1,[{bottom:1200}]),1108);
 assert.equal(paperLengthMillimetres(1108),139);
 assert.equal(paperHeightFromBounds(100,1,[]),550);
 assert.equal(paperHeightFromBounds(100,1,[{bottom:400}]),550);
});
test('responsive viewport scaling never changes printable millimetres',()=>{
 for(const scale of [0.55,0.65,0.85,1]) assert.equal(paperHeightFromBounds(100,scale,[{bottom:100+1100*scale}]),1108);
});
test('DOM measurement selects printable content only and can shrink after removal',()=>{
 let content=[{getBoundingClientRect:()=>({bottom:1400})}];
 const canvas={getBoundingClientRect:()=>({top:100,width:576}),querySelectorAll(selector){assert.equal(selector,'[data-print-content]');return content;}};
 assert.equal(measurePrintableHeight(canvas),1308);content=[];assert.equal(measurePrintableHeight(canvas),550);
});
test('oversized content is reported honestly without silently truncating it',()=>{
 assert.ok(paperHeightFromBounds(0,1,[{bottom:MAX_PAPER_HEIGHT+1}])>MAX_PAPER_HEIGHT);
 assert.equal(paperHeightFromBounds(0,0,[]),550);
});
