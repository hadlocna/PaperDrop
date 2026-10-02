interface DesignApi {
    post(url: string, body: { prompt: string }): Promise<{ data: unknown }>;
}
interface ImageSize { width: number; height: number }

const decodeGeneratedImage = (source: string): Promise<ImageSize> => new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => image.naturalWidth > 0 && image.naturalHeight > 0
        ? resolve({ width: image.naturalWidth, height: image.naturalHeight })
        : reject(new Error('The image service returned an unreadable image.'));
    image.onerror = () => reject(new Error('The image service returned an unreadable image.'));
    image.src = source;
});

export async function requestMagicDesign(api: DesignApi, prompt: string, decode = decodeGeneratedImage) {
    const request = prompt.trim();
    if (!request || request.length > 3000) throw new Error('Please enter a request of 1 to 3000 characters.');
    // All requests use the existing authenticated client. Prompt words never select a mock path.
    const response = await api.post('/ai/generate', { prompt: request });
    const data = response.data as { image?: unknown } | null;
    const image = data?.image;
    if (typeof image !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(image)) {
        throw new Error('The image service did not return a generated image.');
    }
    const size = await decode(image);
    return { image, aspectRatio: size.width / size.height };
}

export function magicDesignError(error: unknown): string {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 401 || status === 403) return 'Your session needs attention. Sign in again and retry.';
    if (status === 503) return 'Image generation is unavailable because the service is not configured.';
    if (status === 429) return 'Image generation is busy. Please try again later.';
    if (status === 400) return 'Please use a family-friendly request of 1 to 3000 characters.';
    return 'Image generation failed. Please try again. No image was added.';
}
