
import { useState, useRef, useEffect } from 'react';
import Draggable from 'react-draggable';
import html2canvas from 'html2canvas';
import { applyDithering } from '../utils/dithering';
import {
    Type as TypeIcon,
    Image as ImageIcon,
    Sparkles,
    Clock,
    RotateCw,
    Scaling,
    X as XIcon,
    Loader2
} from 'lucide-react';
import { client as api } from '../api/client';


interface CanvasElement {
    id: string;
    type: 'text' | 'image';
    content: string; // text content or base64 image
    x: number;
    y: number;
    width?: number; // For images
    rotation?: number;
    fontSize?: number;
    fontFamily?: string;
}

interface CanvasComposerProps {
    onSend: (base64Image: string) => Promise<boolean>;
    onSchedule: (base64Image: string) => void;
    sending: boolean;
}

export function CanvasComposer({ onSend, onSchedule, sending }: CanvasComposerProps) {
    const [elements, setElements] = useState<CanvasElement[]>([]);
    const [previewImage, setPreviewImage] = useState<string | null>(null);
    const [canvasHeight, setCanvasHeight] = useState(800);
    const canvasRef = useRef<HTMLDivElement>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    // AI State
    const [showAiModal, setShowAiModal] = useState(false);
    const [aiPrompt, setAiPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);

    const selectedElement = elements.find(el => el.id === selectedId);

    const handleAiGenerate = async () => {
        if (!aiPrompt.trim()) return;
        setIsGenerating(true);
        try {
            const res = await api.post('/ai/generate', { prompt: aiPrompt });
            const { image, caption, specs } = res.data;

            // 1. Reset Canvas
            setElements([]);
            setCanvasHeight(800);

            // 2. Add Image
            const imgEl: CanvasElement = {
                id: crypto.randomUUID(),
                type: 'image',
                content: image,
                x: 28, // Centered roughly (576-520)/2 = 28
                y: 50,
                width: 520, // Max width with padding
                rotation: 0
            };

            // 3. Add Caption (if any)
            const captionEl: CanvasElement = {
                id: crypto.randomUUID(),
                type: 'text',
                content: caption || '',
                x: 50,
                y: 600, // Below image
                rotation: 0,
                fontSize: 32,
                fontFamily: 'handwriting'
            };

            setElements(caption ? [imgEl, captionEl] : [imgEl]);
            setShowAiModal(false);
            setAiPrompt('');
        } catch (error) {
            console.error(error);
            alert('Failed to generate design. Please try again.');
        } finally {
            setIsGenerating(false);
        }
    };

    const addText = () => {
        const newElement: CanvasElement = {
            id: crypto.randomUUID(),
            type: 'text',
            content: 'Double click to edit',
            x: 50,
            y: 50,
            rotation: 0,
            fontSize: 32,
            fontFamily: 'handwriting'
        };
        setElements([...elements, newElement]);
    };

    const addImage = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                const newElement: CanvasElement = {
                    id: crypto.randomUUID(),
                    type: 'image',
                    content: reader.result as string,
                    x: 50,
                    y: 50,
                    width: 200, // Default width
                    rotation: 0
                };
                setElements([...elements, newElement]);
            };
            reader.readAsDataURL(file);
        }
    };

    const removeElement = (id: string) => {
        setElements(elements.filter(el => el.id !== id));
        if (selectedId === id) setSelectedId(null);
    };

    // Unified Update
    const updateElement = (id: string, updates: Partial<CanvasElement>) => {
        setElements(elements.map(el => el.id === id ? { ...el, ...updates } : el));
    };

    const generateImage = async (): Promise<string> => {
        if (!canvasRef.current) return '';

        // 1. Capture High-Res (2x) for better text rendering
        const tempCanvas = await html2canvas(canvasRef.current, {
            scale: 2,
            backgroundColor: '#ffffff',
            logging: false,
        });

        // 2. Downscale to exact Printer Width (576px)
        const finalWidth = 576;
        const scaleFactor = finalWidth / tempCanvas.width;
        const finalHeight = tempCanvas.height * scaleFactor;

        const outputCanvas = document.createElement('canvas');
        outputCanvas.width = finalWidth;
        outputCanvas.height = finalHeight;
        const ctx = outputCanvas.getContext('2d');
        if (!ctx) return '';

        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(tempCanvas, 0, 0, finalWidth, finalHeight);

        // 3. Dither
        const imageData = ctx.getImageData(0, 0, finalWidth, finalHeight);
        const ditheredData = applyDithering(imageData);
        ctx.putImageData(ditheredData, 0, 0);

        return outputCanvas.toDataURL('image/png');
    };

    const handleSendClick = async () => {
        const img = await generateImage();
        const success = await onSend(img);

        if (success) {
            // Reset Canvas for next message
            setElements([]);
            setPreviewImage(null);
            setCanvasHeight(800);
            setSelectedId(null);
        }
    };

    return (
        <div className="flex flex-col w-full h-full relative">
            {/* AI Modal */}
            {showAiModal && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
                    <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-4 bg-gradient-to-r from-purple-500 to-indigo-600 text-white flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2">
                                <Sparkles size={18} />
                                Magic Designer
                            </h3>
                            <button onClick={() => setShowAiModal(false)} className="text-white/80 hover:text-white">
                                <XIcon size={20} />
                            </button>
                        </div>
                        <div className="p-6">
                            <p className="text-sm text-gray-500 mb-4">
                                Describe your message (e.g., "Bedtime note for Alma with a dinosaur").
                            </p>
                            <textarea
                                value={aiPrompt}
                                onChange={(e) => setAiPrompt(e.target.value)}
                                className="w-full h-24 p-3 border border-gray-200 rounded-xl mb-4 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-purple-500 outline-none resize-none transition"
                                placeholder="A loving note..."
                            />
                            <button
                                onClick={handleAiGenerate}
                                disabled={isGenerating || !aiPrompt.trim()}
                                className="w-full py-3 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow transition hover:opacity-90 active:scale-95"
                            >
                                {isGenerating ? (
                                    <>
                                        <Loader2 size={18} className="animate-spin" />
                                        Designing...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles size={18} />
                                        Create Magic
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Sticky Header Toolbar */}
            <div className="sticky top-0 z-40 bg-white/90 backdrop-blur border-b border-gray-200 shadow-sm px-4 py-3 flex justify-between items-center transition-all h-[64px]">
                <div className="flex gap-2 items-center">
                    {/* Design Tools OR Context Tools */}
                    {!previewImage && (
                        selectedElement && selectedElement.type === 'text' ? (
                            <div className="flex items-center gap-4 animate-in fade-in slide-in-from-left-2">
                                {/* Font Context Menu */}
                                <button
                                    onClick={() => setSelectedId(null)}
                                    className="mr-2 text-gray-400 hover:text-gray-600"
                                >
                                    <XIcon size={20} />
                                </button>

                                {/* Font Size */}
                                <div className="flex items-center bg-gray-100 rounded-lg p-1">
                                    <button
                                        className="p-1 px-3 hover:bg-white rounded-md text-sm font-bold active:scale-95 transition"
                                        onClick={() => updateElement(selectedElement.id, { fontSize: Math.max(12, (selectedElement.fontSize || 32) - 4) })}
                                    >
                                        A-
                                    </button>
                                    <span className="w-8 text-center text-xs font-mono">{selectedElement.fontSize || 32}</span>
                                    <button
                                        className="p-1 px-3 hover:bg-white rounded-md text-sm font-bold active:scale-95 transition"
                                        onClick={() => updateElement(selectedElement.id, { fontSize: Math.min(120, (selectedElement.fontSize || 32) + 4) })}
                                    >
                                        A+
                                    </button>
                                </div>

                                {/* Font Family Toggle */}
                                <button
                                    className="p-2 hover:bg-gray-100 rounded-lg border border-gray-200 text-xs font-bold w-16 truncate"
                                    onClick={() => {
                                        const current = selectedElement.fontFamily || 'handwriting';
                                        const next = current === 'handwriting' ? 'monospace' : current === 'monospace' ? 'sans-serif' : 'handwriting';
                                        updateElement(selectedElement.id, { fontFamily: next });
                                    }}
                                >
                                    {selectedElement.fontFamily === 'handwriting' ? 'Script' : selectedElement.fontFamily === 'monospace' ? 'Mono' : 'Sans'}
                                </button>
                            </div>
                        ) : (
                            <>
                                <button
                                    onClick={() => setShowAiModal(true)}
                                    className="p-2 bg-gradient-to-br from-purple-100 to-indigo-100 text-indigo-600 hover:from-purple-200 hover:to-indigo-200 rounded-lg transition border border-indigo-200 shadow-sm"
                                    title="Magic Designer"
                                >
                                    <Sparkles size={24} />
                                </button>
                                <button onClick={addText} className="p-2 hover:bg-gray-100 rounded-lg text-charcoal-700 active:bg-gray-200 transition" title="Add Text">
                                    <TypeIcon size={24} />
                                </button>
                                <label className="p-2 hover:bg-gray-100 rounded-lg text-charcoal-700 active:bg-gray-200 transition cursor-pointer" title="Add Image">
                                    <ImageIcon size={24} />
                                    <input type="file" accept="image/*" className="hidden" onChange={addImage} />
                                </label>
                            </>
                        )
                    )}
                </div>

                {/* Print / Preview Actions */}
                <div className="flex gap-2">
                    <button
                        onClick={async () => {
                            const img = await generateImage();
                            if (img) onSchedule(img);
                        }}
                        disabled={sending || (!elements.length && !previewImage)}
                        className="p-2 rounded-lg text-charcoal-500 hover:bg-gray-100 border border-transparent hover:border-gray-200 transition disabled:opacity-50"
                        title="Schedule Print"
                    >
                        <Clock size={20} />
                    </button>

                    <button
                        onClick={async () => {
                            if (previewImage) {
                                setPreviewImage(null);
                            } else {
                                const img = await generateImage();
                                setPreviewImage(img);
                            }
                        }}
                        className={`px-4 py-2 rounded-lg text-sm font-bold border transition ${previewImage ? 'bg-charcoal-800 text-white border-charcoal-800' : 'bg-white text-charcoal-700 border-gray-300 hover:bg-gray-50'}`}
                    >
                        {previewImage ? 'Edit' : 'Preview'}
                    </button>

                    <button
                        onClick={handleSendClick}
                        disabled={sending || (!elements.length && !previewImage)}
                        className={`px-6 py-2 rounded-lg text-sm font-bold text-white transition shadow-md flex items-center gap-2 ${sending ? 'bg-coral-400 cursor-wait' : 'bg-coral-500 hover:bg-coral-600 active:scale-95'
                            }`}
                    >
                        {sending ? 'Sending...' : 'PRINT'}
                    </button>
                </div>
            </div>

            {/* Main Infinite Canvas Area */}
            <div className="flex-1 bg-neutral-900 overflow-y-auto overflow-x-hidden relative flex justify-col items-center py-8" onClick={() => setSelectedId(null)}>
                {/* Visual shadow for roll depth */}
                <div className="fixed top-[64px] left-0 right-0 h-8 bg-gradient-to-b from-black/20 to-transparent pointer-events-none z-30" />

                {/* Paper Roll Simulation */}
                <div className="flex flex-col items-center gap-4">
                    <div
                        className="relative bg-white shadow-2xl transition-all duration-300"
                        style={{
                            width: '640px', // 80mm Full Width Visual
                            minHeight: `${canvasHeight}px`, // Dynamic Height
                            boxShadow: '0 0 40px rgba(0,0,0,0.5)'
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Margins */}
                        {!previewImage && (
                            <>
                                <div className="absolute top-0 bottom-0 left-0 w-[32px] bg-neutral-50 border-r border-dashed border-gray-300 opacity-50 pointer-events-none" />
                                <div className="absolute top-0 bottom-0 right-0 w-[32px] bg-neutral-50 border-l border-dashed border-gray-300 opacity-50 pointer-events-none" />
                                <div className="absolute top-0 left-0 right-0 h-4 bg-neutral-50 border-b border-dashed border-gray-300 opacity-50 pointer-events-none flex justify-center items-center">
                                    <span className="text-[9px] text-gray-400 font-mono tracking-widest uppercase">Start of Roll</span>
                                </div>
                            </>
                        )}

                        {/* Content */}
                        <div className="mx-auto h-full relative" style={{ width: '576px' }}>
                            {previewImage ? (
                                <div className="w-full flex flex-col items-center py-8 animate-in fade-in duration-500">
                                    <img
                                        src={previewImage}
                                        alt="Preview"
                                        className="w-full object-contain border border-gray-200 shadow-sm"
                                        style={{ imageRendering: 'pixelated' }}
                                    />
                                    <div className="mt-8 text-center text-gray-400">
                                        <p className="text-xs font-mono uppercase tracking-widest mb-1">Preview Mode</p>
                                        <p className="text-[10px]">1-Bit Dithered • 576px Width</p>
                                    </div>
                                </div>
                            ) : (
                                <div
                                    ref={canvasRef}
                                    className="bg-white relative h-full cursor-text"
                                    style={{ minHeight: `${canvasHeight} px` }}
                                    onClick={(e) => {
                                        if (e.target === e.currentTarget && !previewImage) {
                                            setSelectedId(null);
                                        }
                                    }}
                                >
                                    {elements.map((el) => (
                                        <DraggableElement
                                            key={el.id}
                                            element={el}
                                            isSelected={el.id === selectedId}
                                            onSelect={() => setSelectedId(el.id)}
                                            onRemove={() => removeElement(el.id)}
                                            onUpdate={(vals) => updateElement(el.id, vals)}
                                        />
                                    ))}

                                    {elements.length === 0 && (
                                        <div className="absolute top-32 inset-x-0 text-center text-gray-300 pointer-events-none select-none">
                                            <p className="font-handwriting text-3xl mb-2 text-gray-200">Start Writing...</p>
                                            <p className="text-sm font-mono opacity-50">Tap tools above to add content</p>
                                            <div className="mt-8 border-2 border-dashed border-gray-100 w-32 h-32 mx-auto rounded-full flex items-center justify-center">
                                                <span className="text-4xl">✨</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Add More Paper Button */}
                    {!previewImage && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setCanvasHeight(h => h + 400);
                            }}
                            className="bg-neutral-800/50 hover:bg-neutral-800 text-neutral-400 hover:text-white px-6 py-2 rounded-full text-sm font-medium transition backdrop-blur-sm border border-white/10 flex items-center gap-2 mb-16"
                        >
                            <span>⬇️ Add 400px Paper</span>
                        </button>
                    )}
                </div>
            </div>

            {/* Optional Footer or "Cut" button? For now header is enough */}
        </div>
    );
}

function DraggableElement({
    element,
    onRemove,
    onUpdate,
    isSelected,
    onSelect
}: {
    element: CanvasElement,
    onRemove: () => void,
    onUpdate: (vals: Partial<CanvasElement>) => void,
    isSelected: boolean,
    onSelect: () => void
}) {
    const [isEditing, setIsEditing] = useState(false);
    const nodeRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const lastTap = useRef(0);

    // Internal state for smooth dragging/rotating without constant parent re-renders until stop
    // For React-Draggable, we strictly control position via props to ensure sync, 
    // BUT to avoid "reset" issues, we must rely on the parent state passed in `element.x / y`.

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isEditing]);

    const handleRotation = (e: any) => {
        e.stopPropagation();
        // Prevent default only if it's not a touch start needed for scrolling... 
        // actually for rotation/resize we DO want to prevent scroll.
        // e.preventDefault(); // Might block touchstart? React Polyfill handles it usually.

        // Unified clientY
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        const startRotation = element.rotation || 0;

        const onMove = (moveEvent: any) => { // Typing loose for MouseEvent | TouchEvent
            const curY = moveEvent.touches ? moveEvent.touches[0].clientY : moveEvent.clientY;
            const delta = curY - clientY;
            onUpdate({ rotation: startRotation + delta });
        };

        const onEnd = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onEnd);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onEnd);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);
        document.addEventListener('touchmove', onMove, { passive: false });
        document.addEventListener('touchend', onEnd);
    };

    const handleResize = (e: any) => {
        e.stopPropagation();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const startWidth = element.width || 200;

        const onMove = (moveEvent: any) => {
            const curX = moveEvent.touches ? moveEvent.touches[0].clientX : moveEvent.clientX;
            const delta = curX - clientX;
            onUpdate({ width: Math.max(50, startWidth + delta) });
        };

        const onEnd = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onEnd);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onEnd);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);
        document.addEventListener('touchmove', onMove, { passive: false });
        document.addEventListener('touchend', onEnd);
    };

    return (
        <Draggable
            nodeRef={nodeRef}
            bounds="parent"
            position={{ x: element.x, y: element.y }}
            onStop={(e, data) => onUpdate({ x: data.x, y: data.y })}
            onStart={() => onSelect()} // Just to ensure selection maybe?
            handle=".drag-handle" // Only drag via content, not handles
            cancel=".no-drag"
        >
            <div
                ref={nodeRef}
                className="absolute w-max"
                onClick={(e) => {
                    e.stopPropagation();
                    onSelect();
                }}
                // On touch start, select immediately & detect double tap
                onTouchStart={(e) => {
                    onSelect();
                    // Double tap detection
                    const now = Date.now();
                    if (now - lastTap.current < 300 && element.type === 'text') {
                        setIsEditing(true);
                    }
                    lastTap.current = now;
                }}
            >
                {/* Visual Wrapper with Rotation */
                /* Scale handles inversely to rotation? No, just rotate wrapper. */}
                <div
                    className="relative cursor-move drag-handle group"
                    style={{
                        transform: `rotate(${element.rotation || 0}deg)`,
                        transformOrigin: 'center center'
                    }}
                >
                    {/* Element Content */}
                    <div className={`relative ${isEditing ? 'z-50' : 'z-auto'} `}>
                        {element.type === 'image' ? (
                            <div className={`relative transition - all duration - 200 ${isSelected ? 'outline outline-2 outline-coral-400' : 'group-hover:outline group-hover:outline-2 group-hover:outline-coral-400'} `}>
                                <img
                                    src={element.content}
                                    alt="Element"
                                    className="pointer-events-none select-none"
                                    style={{ width: `${element.width || 200} px` }}
                                />

                                {/* Resize Handle (Bottom Right) */}
                                <div
                                    className={`no - drag absolute - bottom - 4 - right - 4 w - 10 h - 10 bg - white border border - charcoal - 300 rounded - full shadow cursor - nwse - resize flex items - center justify - center transition - all z - 50 ${isSelected ? 'opacity-100 scale-100' : 'opacity-0 group-hover:opacity-100 scale-90 group-hover:scale-100'} `}
                                    onMouseDown={handleResize}
                                    onTouchStart={handleResize}
                                    title="Resize"
                                >
                                    <Scaling size={16} className="text-charcoal-600" />
                                </div>
                            </div>
                        ) : (
                            isEditing ? (
                                <input
                                    ref={inputRef}
                                    value={element.content}
                                    onChange={(e) => onUpdate({ content: e.target.value })}
                                    onBlur={() => setIsEditing(false)}
                                    // Removed onTouchEnd to prevent accidental blur on mobile keyboard interaction
                                    onKeyDown={(e) => e.key === 'Enter' && setIsEditing(false)}
                                    className="bg-transparent border-b-2 border-coral-500 outline-none min-w-[100px] p-1 no-drag text-charcoal-900"
                                    style={{
                                        fontSize: element.fontSize || 32,
                                        fontFamily: element.fontFamily || 'handwriting'
                                    }}
                                />
                            ) : (
                                <div
                                    className={`p - 2 border - 2 rounded select - none transition - all ${isSelected ? 'border-coral-400 bg-coral-50/20' : 'border-transparent hover:border-gray-300'} `}
                                    style={{
                                        lineHeight: 1.2,
                                        fontSize: element.fontSize || 32,
                                        fontFamily: element.fontFamily || 'handwriting'
                                    }}
                                >
                                    {element.content}
                                </div>
                            )
                        )}

                        {/* Controls Container (Visible when selected or hovered) */}
                        <div className={`absolute top - 0 left - 0 w - full h - full pointer - events - none ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition - opacity`}>
                            {/* Remove Control */}
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onRemove();
                                }}
                                className="no-drag pointer-events-auto absolute -top-5 -right-5 bg-red-500 text-white rounded-full p-2 shadow-sm transform hover:scale-110 active:scale-95 transition z-50"
                                title="Remove"
                            >
                                <XIcon size={16} />
                            </button>

                            {/* Rotation Handle (Top Center) */}
                            <div
                                className="no-drag pointer-events-auto absolute -top-10 left-1/2 -translate-x-1/2 w-10 h-10 bg-white border border-charcoal-300 rounded-full shadow cursor-grab active:cursor-grabbing flex items-center justify-center hover:bg-coral-50 z-50"
                                onMouseDown={handleRotation}
                                onTouchStart={handleRotation}
                                title="Rotate"
                            >
                                <RotateCw size={16} className="text-charcoal-600" />
                            </div>

                            {/* Text Edit Button (Mobile Helper) */}
                            {element.type === 'text' && !isEditing && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setIsEditing(true);
                                    }}
                                    className="no-drag pointer-events-auto absolute -bottom-10 left-1/2 -translate-x-1/2 bg-charcoal-800 text-white text-xs font-bold px-3 py-1 rounded-full shadow-sm"
                                >
                                    EDIT
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </Draggable>
    );
}
