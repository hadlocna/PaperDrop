export const PRINT_DOTS_PER_MM = 8;
export const MIN_PAPER_HEIGHT = 550;
export const MAX_PAPER_HEIGHT = 16000;

export interface PrintableBounds { bottom: number }

// Browser bounds already include text wrapping, fonts, image proportions and rotation.
export function paperHeightFromBounds(canvasTop: number, viewportScale: number, content: PrintableBounds[]): number {
    if (!Number.isFinite(viewportScale) || viewportScale <= 0) return MIN_PAPER_HEIGHT;
    const bottom = content.reduce((maximum, item) => Number.isFinite(item.bottom)
        ? Math.max(maximum, (item.bottom - canvasTop) / viewportScale + 8) : maximum, 0);
    return Math.max(MIN_PAPER_HEIGHT, Math.ceil(bottom));
}

export function measurePrintableHeight(canvas: HTMLElement, width = 576): number {
    const root = canvas.getBoundingClientRect();
    return paperHeightFromBounds(root.top, root.width / width,
        Array.from(canvas.querySelectorAll<HTMLElement>('[data-print-content]')).map(node => node.getBoundingClientRect()));
}

export function paperLengthMillimetres(height: number): number {
    return Math.ceil(height / PRINT_DOTS_PER_MM);
}
