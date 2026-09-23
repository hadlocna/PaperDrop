const {test}=require('node:test');
const assert=require('node:assert/strict');
const {existsSync}=require('node:fs');
const path=require('node:path');
const {namedCousins}=require('../dist/services/cousinImages');

test('each button face is available to named drawing requests',()=>{
    const names=['Alma','Theodore','Margaux','Andi','Sloan','Roux','Elise','Laure'];
    for(const name of names){
        const [person]=namedCousins(`Draw ${name} as a princess`);
        assert.equal(person?.name,name);
        assert.ok(existsSync(path.join(__dirname,'../assets/cousins',person.portrait)));
    }
});
test('whole names, case and spoken aliases are handled without substring matches',()=>{
    assert.deepEqual(namedCousins('I want a picture of Alma as a princess').map(p=>p.name),['Alma']);
    assert.deepEqual(namedCousins('andy and margo with rue').map(p=>p.name),['Margaux','Andi','Roux']);
    assert.deepEqual(namedCousins('Théodore et Élise').map(p=>p.name),['Theodore','Elise']);
    assert.deepEqual(namedCousins('A roadmap for somebody and a flower').map(p=>p.name),[]);
});
