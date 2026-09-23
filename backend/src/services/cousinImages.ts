import { readFile } from 'node:fs/promises';
import path from 'node:path';
import OpenAI, { toFile } from 'openai';
import { IMAGE_MODEL } from './thermalArtwork';

// These are the eight portraits used by the cousin buttons. Include the names
// children actually say as well as the spellings shown on the buttons.
const cousins = [
    { name: 'Alma', names: ['Alma'], portrait: 'alma.png' },
    { name: 'Theodore', names: ['Theodore', 'Théodore'], portrait: 'theodore.png' },
    { name: 'Margaux', names: ['Margaux', 'Margo'], portrait: 'margaux.png' },
    { name: 'Andi', names: ['Andi', 'Andy'], portrait: 'andi.png' },
    { name: 'Sloan', names: ['Sloan'], portrait: 'sloan.png' },
    { name: 'Roux', names: ['Roux', 'Rue'], portrait: 'roux.png' },
    { name: 'Elise', names: ['Elise', 'Élise'], portrait: 'elise.png' },
    { name: 'Laure', names: ['Laure', 'Lore'], portrait: 'laure.png' }
] as const;

const portraitRoot = path.resolve(__dirname, '../../assets/cousins');

export function namedCousins(prompt: string) {
    return cousins.filter(cousin => cousin.names.some(name =>
        new RegExp(`(?<![\\p{L}\\p{N}])${name}(?![\\p{L}\\p{N}])`, 'iu').test(prompt)
    ));
}

export async function generateCousinPicture(ai: OpenAI, requested: string, prompt: string, quality: 'low' | 'medium' = 'medium', options?: { signal?: AbortSignal }) {
    const matches = namedCousins(requested);
    const settings = { model: IMAGE_MODEL, n: 1, size: '1024x1024', quality, output_format: 'png', background: 'opaque' } as const;
    if (!matches.length) return ai.images.generate({ ...settings, prompt }, options);

    // The edits endpoint accepts image references. Generations does not.
    // Fail if a named portrait is unavailable instead of silently inventing a face.
    const images = await Promise.all(matches.map(async cousin =>
        toFile(await readFile(path.join(portraitRoot, cousin.portrait)), cousin.portrait, { type: 'image/png' })
    ));
    const references = matches.map((cousin, index) => `Image ${index + 1} is ${cousin.name}.`).join(' ');
    return ai.images.edit({
        ...settings,
        image: images,
        prompt: `${references} Use these portraits as the identity references for the named children. Keep each child's recognizable face and age while drawing the requested scene. ${prompt}`
    }, options);
}
