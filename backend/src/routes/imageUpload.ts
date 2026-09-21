import express from 'express';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

// Mounted behind the existing admin middleware. Content-addressed image upload
// avoids proxy size limits without allowing arbitrary paths or public writes.
const router = express.Router();
const root = path.join(__dirname, '../../uploads');
const idOK = (id: string) => /^[a-f0-9]{64}$/.test(id);
router.put('/:id/chunks/:index', express.raw({ type: 'application/octet-stream', limit: '32mb' }), async (req, res) => {
    const { id, index } = req.params;
    if (!idOK(id) || !/^(0|[1-9][0-9]?)$/.test(index) || Number(index) > 63 || !Buffer.isBuffer(req.body) || !req.body.length) return res.status(400).json({ error: 'Invalid image chunk' });
    const directory = path.join(root, '.image-parts', id);
    try {
        await fs.promises.mkdir(directory, { recursive: true });
        const target=path.join(directory,index);const temp=target+'.'+crypto.randomUUID();
        await fs.promises.writeFile(temp,req.body);await fs.promises.rename(temp,target);
        res.json({ received: Number(index) });
    } catch { res.status(500).json({ error: 'Unable to save image chunk' }); }
});
router.post('/:id/complete', async (req, res) => {
    const { id } = req.params;const count=req.body.count;
    if (!idOK(id) || !Number.isInteger(count) || count < 1 || count > 64) return res.status(400).json({ error: 'Invalid image manifest' });
    const directory=path.join(root,'.image-parts',id);const temp=path.join(root,`.image-${crypto.randomUUID()}.tmp`);
    try {
        const hash=crypto.createHash('sha256');let bytes=0;
        for(let index=0;index<count;index++) {
            const data=await fs.promises.readFile(path.join(directory,String(index)));
            if(index===0 && data.subarray(0,6).toString('hex')!=='fd377a585a00') throw Error('Expected xz image');
            hash.update(data);bytes+=data.length;await fs.promises.appendFile(temp,data);
        }
        if(hash.digest('hex')!==id) throw Error('Image checksum mismatch');
        const filename=`paperdrop-factory-${id.slice(0,16)}.img.xz`;
        await fs.promises.rename(temp,path.join(root,filename));
        const manifest={url:`https://api.paperdrop.me/uploads/${filename}`,sha256:id,bytes};
        const manifestTemp=path.join(root,`.image-manifest-${crypto.randomUUID()}.tmp`);
        await fs.promises.writeFile(manifestTemp,JSON.stringify(manifest));await fs.promises.rename(manifestTemp,path.join(root,'image.json'));
        await fs.promises.rm(directory,{recursive:true,force:true});
        res.json(manifest);
    } catch {
        await fs.promises.unlink(temp).catch(()=>{});res.status(400).json({error:'Image incomplete or checksum invalid'});
    }
});
export default router;
