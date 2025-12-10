interface PrintPreviewProps {
    text?: string;
    image?: string | null;
}

export function PrintPreview({ text, image }: PrintPreviewProps) {
    return (
        <div className="bg-white border-x-2 border-dashed border-gray-200 p-6 shadow-sm max-w-sm mx-auto font-mono text-sm leading-relaxed text-charcoal-900 relative">
            {/* Paper tear effect top */}
            <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-b from-gray-100 to-transparent opacity-20" />

            <div className="text-center mb-4">
                <div className="text-xl font-bold">PaperDrop</div>
                <div className="text-xs text-gray-400">{new Date().toLocaleString()}</div>
            </div>

            <div className="my-4 border-b border-black/10" />

            <div className="min-h-[100px] whitespace-pre-wrap">
                {image && (
                    <img src={image} alt="Print" className="w-full grayscale contrast-125 mb-4" />
                )}
                {text || <span className="text-gray-300 italic">Empty message...</span>}
            </div>

            <div className="my-4 border-b border-black/10" />

            <div className="text-center text-xs text-gray-400 mt-4">
                www.paperdrop.com
            </div>

            {/* Paper tear effect bottom */}
            <div className="absolute bottom-0 left-0 w-full h-1 bg-white" style={{ clipPath: 'polygon(0% 0%, 5% 100%, 10% 0%, 15% 100%, 20% 0%, 25% 100%, 30% 0%, 35% 100%, 40% 0%, 45% 100%, 50% 0%, 55% 100%, 60% 0%, 65% 100%, 70% 0%, 75% 100%, 80% 0%, 85% 100%, 90% 0%, 95% 100%, 100% 0%)' }} />
        </div>
    );
}
