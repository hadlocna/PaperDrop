import { useState, useRef, useEffect } from 'react';
import Draggable from 'react-draggable';
import html2canvas from 'html2canvas';
import { Image as ImageIcon, Type as TypeIcon, X as XIcon, Eye as EyeIcon, Clock } from 'lucide-react';
import { applyDithering } from '../utils/dithering';

interface CanvasElement {
    id: string;
    type: 'text' | 'image';
    content: string; // text content or base64 image
    x: number;
    y: number;
}

interface CanvasComposerProps {
    onSend: (base64Image: string) => Promise<void>;
    onSchedule: (base64Image: string) => void;
    sending: boolean;
}

export function CanvasComposer({ onSend, onSchedule, sending }: CanvasComposerProps) {
    const [elements, setElements] = useState<CanvasElement[]>([]);
    const [previewImage, setPreviewImage] = useState<string | null>(null);
    const canvasRef = useRef<HTMLDivElement>(null);


    const addText = () => {
        const newElement: CanvasElement = {
            id: crypto.randomUUID(),
            type: 'text',
            content: 'Double click to edit',
            x: 50,
            y: 50
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
                    y: 50
                };
                setElements([...elements, newElement]);
            };
            reader.readAsDataURL(file);
        }
    };

    const removeElement = (id: string) => {
        setElements(elements.filter(el => el.id !== id));
    };

    const updateElementContent = (id: string, newContent: string) => {
        setElements(elements.map(el => el.id === id ? { ...el, content: newContent } : el));
    };

    const generateImage = async (): Promise<string> => {
        if (!canvasRef.current) return '';

        // Temporarily hide handles/borders if any (not implemented yet, but good practice)
        // Capture
        const canvas = await html2canvas(canvasRef.current, {
            scale: 1, // 1:1 scale for printer
            backgroundColor: '#ffffff',
            width: 384, // Explicit width
        });

        // Dither
        const ctx = canvas.getContext('2d');
        if (!ctx) return '';

        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const ditheredData = applyDithering(imageData);
        ctx.putImageData(ditheredData, 0, 0);

        return canvas.toDataURL('image/png');
    };

    const togglePreview = async () => {
        if (previewImage) {
            setPreviewImage(null);
        } else {
            const img = await generateImage();
            setPreviewImage(img);
        }
    };

    const handleSendClick = async () => {
        const img = await generateImage();
        await onSend(img);
    };

    return (
        <div className="flex flex-col items-center gap-4">
            {/* Toolbar */}
            <div className="flex gap-2 bg-white p-2 rounded-xl shadow-sm border border-gray-100">
                <button onClick={addText} className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 rounded-lg text-sm font-medium text-charcoal-700">
                    <TypeIcon size={18} /> Add Text
                </button>
                <label className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 rounded-lg text-sm font-medium text-charcoal-700 cursor-pointer">
                    <ImageIcon size={18} /> Add Image
                    <input type="file" accept="image/*" className="hidden" onChange={addImage} />
                </label>
                <div className="w-px bg-gray-200 mx-1" />
                <button
                    onClick={togglePreview}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition ${previewImage ? 'bg-coral-100 text-coral-700' : 'hover:bg-gray-50 text-charcoal-700'}`}
                >
                    <EyeIcon size={18} /> {previewImage ? 'Edit' : 'Preview B/W'}
                </button>
            </div>

            {/* Canvas Container */}
            <div className="relative border-4 border-gray-300 rounded-lg bg-gray-500 overflow-hidden shadow-inner">
                {/* 384px is standard thermal printer width. We can set height or let it grow */}
                <div
                    ref={canvasRef}
                    className="bg-white relative overflow-hidden transition-all"
                    style={{
                        width: '384px',
                        minHeight: '300px',
                        height: '500px'
                    }}
                >
                    {previewImage ? (
                        <img src={previewImage} alt="Preview" className="w-full h-full object-contain" />
                    ) : (
                        elements.map((el) => (
                            <DraggableElement
                                key={el.id}
                                element={el}
                                onRemove={() => removeElement(el.id)}
                                onUpdate={(val) => updateElementContent(el.id, val)}
                            />
                        ))
                    )}

                    {!previewImage && elements.length === 0 && (
                        <div className="absolute inset-0 flex items-center justify-center text-gray-300 pointer-events-none">
                            <p>Canvas Area (384px)</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Actions */}
            <div className="w-full max-w-sm flex gap-2">
                <button
                    onClick={handleSendClick}
                    disabled={sending || elements.length === 0}
                    className="flex-1 py-3 bg-coral-500 text-white font-medium rounded-xl hover:bg-coral-600 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md"
                >
                    {sending ? 'Printing...' : 'Print Now'}
                </button>
                <button
                    onClick={async () => {
                        const img = await generateImage();
                        if (img) onSchedule(img);
                    }}
                    disabled={sending || elements.length === 0}
                    className="px-4 py-3 bg-white text-coral-500 font-medium rounded-xl border border-coral-200 hover:bg-coral-50 transition disabled:opacity-50"
                    title="Schedule Print"
                >
                    <Clock size={20} />
                </button>
            </div>
        </div>
    );
}

function DraggableElement({ element, onRemove, onUpdate }: { element: CanvasElement, onRemove: () => void, onUpdate: (val: string) => void }) {
    const [isEditing, setIsEditing] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isEditing]);

    return (
        <Draggable bounds="parent" defaultPosition={{ x: element.x, y: element.y }}>
            <div className="absolute cursor-move group">
                <div className={`relative ${isEditing ? 'z-50' : 'z-auto'}`}>
                    {/* Content */}
                    {element.type === 'image' ? (
                        <div className="relative group-hover:outline group-hover:outline-1 group-hover:outline-coral-400">
                            {/* Valid HTML requires resizing images usually, but basic img tag works for now. 
                                 Max width 200 to fit manageable area? */}
                            <img src={element.content} alt="Element" className="max-w-[200px] pointer-events-none" />
                        </div>
                    ) : (
                        isEditing ? (
                            <input
                                ref={inputRef}
                                value={element.content}
                                onChange={(e) => onUpdate(e.target.value)}
                                onBlur={() => setIsEditing(false)}
                                onKeyDown={(e) => e.key === 'Enter' && setIsEditing(false)}
                                className="bg-transparent border-b border-coral-500 outline-none min-w-[100px] font-handwriting text-xl"
                            />
                        ) : (
                            <div
                                onDoubleClick={() => setIsEditing(true)}
                                className="font-handwriting text-xl p-1 border border-transparent hover:border-dashed hover:border-gray-300 rounded"
                            >
                                {element.content}
                            </div>
                        )
                    )}

                    {/* Controls (visible on hover) */}
                    <button
                        onClick={onRemove}
                        className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Remove"
                    >
                        <XIcon size={12} />
                    </button>
                </div>
            </div>
        </Draggable>
    );
}
