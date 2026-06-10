export type DitherStyle = 'none' | 'photo' | 'vintage' | 'newspaper' | 'comic';

export const DITHER_STYLES: { id: DitherStyle; label: string }[] = [
    { id: 'none', label: 'B&W' },
    { id: 'photo', label: 'Photo' },
    { id: 'vintage', label: 'Vintage' },
    { id: 'newspaper', label: 'Newspaper' },
    { id: 'comic', label: 'Comic' },
];

/**
 * Renders an image at the exact pixel width it will occupy on paper and
 * applies the chosen dither style. Dithering must happen at final print
 * resolution — scaling a dithered image afterwards destroys the pattern.
 */
export async function processImageForPrint(
    src: string,
    targetWidth: number,
    style: DitherStyle
): Promise<string> {
    const img = await loadImage(src);
    const width = Math.max(16, Math.min(576, Math.round(targetWidth)));
    const height = Math.max(1, Math.round(img.naturalHeight * (width / img.naturalWidth)));

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2D context unavailable');

    // Composite onto white so transparency prints as paper, not black
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, width, height);

    const imageData = ctx.getImageData(0, 0, width, height);
    applyDitherStyle(imageData, style);
    ctx.putImageData(imageData, 0, 0);

    return canvas.toDataURL('image/png');
}

export function applyDitherStyle(imageData: ImageData, style: DitherStyle): ImageData {
    if (style === 'none') return imageData;

    const gray = toGrayscale(imageData);
    autoContrast(gray);

    switch (style) {
        case 'photo':
            floydSteinberg(gray, imageData.width, imageData.height);
            break;
        case 'vintage':
            atkinson(gray, imageData.width, imageData.height);
            break;
        case 'newspaper':
            halftone(gray, imageData.width, imageData.height);
            break;
        case 'comic':
            bayer(gray, imageData.width, imageData.height);
            break;
    }

    const data = imageData.data;
    for (let i = 0; i < gray.length; i++) {
        const v = gray[i] < 128 ? 0 : 255;
        data[i * 4] = v;
        data[i * 4 + 1] = v;
        data[i * 4 + 2] = v;
        data[i * 4 + 3] = 255;
    }
    return imageData;
}

function loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Failed to load image for print processing'));
        img.src = src;
    });
}

function toGrayscale(imageData: ImageData): Float32Array {
    const data = imageData.data;
    const gray = new Float32Array(imageData.width * imageData.height);
    for (let i = 0; i < gray.length; i++) {
        const r = data[i * 4];
        const g = data[i * 4 + 1];
        const b = data[i * 4 + 2];
        const a = data[i * 4 + 3] / 255;
        // Blend over white so transparent pixels stay paper-white
        gray[i] = (0.299 * r + 0.587 * g + 0.114 * b) * a + 255 * (1 - a);
    }
    return gray;
}

/**
 * Stretches levels so photos use the printer's full tonal range.
 * Thermal paper crushes midtones, so a contrast boost reads much better.
 */
function autoContrast(gray: Float32Array) {
    const histogram = new Uint32Array(256);
    for (let i = 0; i < gray.length; i++) {
        histogram[Math.max(0, Math.min(255, Math.round(gray[i])))]++;
    }

    const clip = gray.length * 0.01; // ignore the darkest/lightest 1%
    let low = 0;
    let high = 255;
    let count = 0;
    for (let i = 0; i < 256; i++) {
        count += histogram[i];
        if (count > clip) { low = i; break; }
    }
    count = 0;
    for (let i = 255; i >= 0; i--) {
        count += histogram[i];
        if (count > clip) { high = i; break; }
    }
    if (high - low < 32) return; // already flat or near-binary; leave alone

    const scale = 255 / (high - low);
    for (let i = 0; i < gray.length; i++) {
        gray[i] = Math.max(0, Math.min(255, (gray[i] - low) * scale));
    }
}

function floydSteinberg(gray: Float32Array, width: number, height: number) {
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = y * width + x;
            const old = gray[i];
            const next = old < 128 ? 0 : 255;
            gray[i] = next;
            const error = old - next;

            if (x + 1 < width) gray[i + 1] += error * 7 / 16;
            if (y + 1 < height) {
                if (x > 0) gray[i + width - 1] += error * 3 / 16;
                gray[i + width] += error * 5 / 16;
                if (x + 1 < width) gray[i + width + 1] += error * 1 / 16;
            }
        }
    }
}

function atkinson(gray: Float32Array, width: number, height: number) {
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = y * width + x;
            const old = gray[i];
            const next = old < 128 ? 0 : 255;
            gray[i] = next;
            const error = (old - next) / 8; // only 6/8 diffused: classic faded Mac look

            if (x + 1 < width) gray[i + 1] += error;
            if (x + 2 < width) gray[i + 2] += error;
            if (y + 1 < height) {
                if (x > 0) gray[i + width - 1] += error;
                gray[i + width] += error;
                if (x + 1 < width) gray[i + width + 1] += error;
            }
            if (y + 2 < height) gray[i + width * 2] += error;
        }
    }
}

const BAYER_4X4 = [
    0, 8, 2, 10,
    12, 4, 14, 6,
    3, 11, 1, 9,
    15, 7, 13, 5,
];

function bayer(gray: Float32Array, width: number, height: number) {
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = y * width + x;
            const threshold = ((BAYER_4X4[(y % 4) * 4 + (x % 4)] + 0.5) / 16) * 255;
            gray[i] = gray[i] < threshold ? 0 : 255;
        }
    }
}

function halftone(gray: Float32Array, width: number, height: number) {
    const cell = 6; // dot pitch in pixels (~34 dots/inch at 203 DPI)
    const out = new Float32Array(gray.length).fill(255);

    for (let cy = 0; cy < height; cy += cell) {
        for (let cx = 0; cx < width; cx += cell) {
            const cellW = Math.min(cell, width - cx);
            const cellH = Math.min(cell, height - cy);

            let sum = 0;
            for (let y = 0; y < cellH; y++) {
                for (let x = 0; x < cellW; x++) {
                    sum += gray[(cy + y) * width + (cx + x)];
                }
            }
            const darkness = 1 - sum / (cellW * cellH) / 255;
            // Dot area proportional to darkness => radius scales with sqrt
            const radius = (cell / 2) * Math.sqrt(darkness) * 1.15;
            if (radius <= 0) continue;

            const centerX = cx + cellW / 2;
            const centerY = cy + cellH / 2;
            for (let y = 0; y < cellH; y++) {
                for (let x = 0; x < cellW; x++) {
                    const dx = cx + x + 0.5 - centerX;
                    const dy = cy + y + 0.5 - centerY;
                    if (dx * dx + dy * dy <= radius * radius) {
                        out[(cy + y) * width + (cx + x)] = 0;
                    }
                }
            }
        }
    }
    gray.set(out);
}
