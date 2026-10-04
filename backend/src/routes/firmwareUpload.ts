import express from 'express';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { PrismaClient } from '@prisma/client';

const chunkBytes = 8 * 1024 * 1024;
const maxBytes = 600 * 1024 * 1024;
const validId = (id: string) => /^[a-f0-9]{64}$/.test(id);

// Mounted after admin authentication. Uploading never changes the stable channel.
export function firmwareUploadRouter(root: string, db: Pick<PrismaClient, 'firmwareRelease'>) {
    const router = express.Router();
    router.put('/:id/chunks/:index', express.raw({ type: 'application/octet-stream', limit: chunkBytes }), async (req, res) => {
        const { id, index } = req.params;
        if (!validId(id) || !/^(0|[1-9][0-9]?)$/.test(index) || Number(index) >= 75 || !Buffer.isBuffer(req.body) || !req.body.length) {
            return res.status(400).json({ error: 'Invalid firmware chunk' });
        }
        const directory = path.join(root, '.firmware-parts', id);
        const temporary = path.join(directory, `${index}.${crypto.randomUUID()}.tmp`);
        try {
            await fs.promises.mkdir(directory, { recursive: true });
            await fs.promises.writeFile(temporary, req.body);
            await fs.promises.rename(temporary, path.join(directory, index));
            res.json({ received: Number(index) });
        } catch {
            await fs.promises.unlink(temporary).catch(() => {});
            res.status(500).json({ error: 'Unable to save firmware chunk' });
        }
    });
    router.post('/:id/complete', async (req, res) => {
        const { id } = req.params;
        const { count, version, description, isCritical } = req.body || {};
        if (!validId(id) || !Number.isInteger(count) || count < 1 || count > 75 || typeof version !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(version)) {
            return res.status(400).json({ error: 'Invalid firmware manifest' });
        }
        const directory = path.join(root, '.firmware-parts', id);
        const filename = `paperdrop-${version}-${id}.tar.gz`;
        const destination = path.join(root, filename);
        const temporary = path.join(root, `.firmware-${crypto.randomUUID()}.tmp`);
        const url = `${(process.env.PUBLIC_API_URL || 'https://api.paperdrop.me').replace(/\/$/, '')}/uploads/${filename}`;
        try {
            const hash = crypto.createHash('sha256');
            let bytes = 0;
            const alreadyAssembled = fs.existsSync(destination);
            if (alreadyAssembled) {
                for await (const data of fs.createReadStream(destination)) hash.update(data);
            } else {
                for (let index = 0; index < count; index++) {
                    const data = await fs.promises.readFile(path.join(directory, String(index)));
                    if (!data.length || data.length > chunkBytes || (index === 0 && data.subarray(0, 2).toString('hex') !== '1f8b')) throw Error('Invalid archive');
                    bytes += data.length;
                    if (bytes > maxBytes) throw Error('Archive too large');
                    hash.update(data);
                    await fs.promises.appendFile(temporary, data);
                }
            }
            if (hash.digest('hex') !== id) throw Error('Checksum mismatch');
            const archive = alreadyAssembled ? destination : temporary;
            const { stdout } = await promisify(execFile)('tar', ['-xOzf', archive, 'release.json'], { maxBuffer: 8192, timeout: 30000 });
            const packaged = JSON.parse(stdout);
            if (packaged.format !== 2 || packaged.version !== version) throw Error('Managed release version mismatch');
            if (!alreadyAssembled) await fs.promises.rename(temporary, destination);
            let release = await db.firmwareRelease.findUnique({ where: { version } });
            if (release && release.url !== url) return res.status(409).json({ error: 'Version already exists with different firmware' });
            if (!release) {
                try {
                    release = await db.firmwareRelease.create({ data: { version, url, description: typeof description === 'string' ? description : '', isCritical: isCritical === true } });
                } catch (error: any) {
                    if (error.code !== 'P2002') throw error;
                    release = await db.firmwareRelease.findUnique({ where: { version } });
                    if (!release || release.url !== url) return res.status(409).json({ error: 'Version already exists with different firmware' });
                }
            }
            await fs.promises.rm(directory, { recursive: true, force: true }).catch(() => {});
            res.json({ ...release, sha256: id });
        } catch {
            res.status(400).json({ error: 'Firmware incomplete, invalid, or checksum mismatch' });
        } finally {
            await fs.promises.unlink(temporary).catch(() => {});
        }
    });
    return router;
}
