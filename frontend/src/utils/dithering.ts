export function applyDithering(imageData: ImageData): ImageData {
    const width = imageData.width;
    const height = imageData.height;
    const data = imageData.data;

    // Floyd-Steinberg Dithering
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = (y * width + x) * 4;

            // Greyscale conversion (using luminance)
            const oldR = data[i];
            const oldG = data[i + 1];
            const oldB = data[i + 2];
            const gray = 0.299 * oldR + 0.587 * oldG + 0.114 * oldB;

            // Threshold (1-bit)
            const newColor = gray < 128 ? 0 : 255;

            data[i] = newColor;     // R
            data[i + 1] = newColor; // G
            data[i + 2] = newColor; // B
            // Alpha remains 255 (fully opaque) unless it was transparent, but html2canvas usually gives opaque.

            const error = gray - newColor;

            // Distribute error to neighbors
            if (x + 1 < width) {
                distributeError(data, (y * width + (x + 1)) * 4, error * 7 / 16);
            }
            if (y + 1 < height) {
                if (x > 0) {
                    distributeError(data, ((y + 1) * width + (x - 1)) * 4, error * 3 / 16);
                }
                distributeError(data, ((y + 1) * width + x) * 4, error * 5 / 16);
                if (x + 1 < width) {
                    distributeError(data, ((y + 1) * width + (x + 1)) * 4, error * 1 / 16);
                }
            }
        }
    }
    return imageData;
}

function distributeError(data: Uint8ClampedArray, index: number, error: number) {
    // We only need to adjust RGB, not Alpha
    data[index] = Math.min(255, Math.max(0, data[index] + error));
    data[index + 1] = Math.min(255, Math.max(0, data[index + 1] + error));
    data[index + 2] = Math.min(255, Math.max(0, data[index + 2] + error));
}
