
import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Draggable from 'react-draggable';
import { toCanvas } from 'html-to-image';
import {
    Type as TypeIcon,
    Image as ImageIcon,
    Sparkles,
    Clock,
    RotateCw,
    Scaling,
    X as XIcon,
    Trash2,
    Loader2,
    Eye,
    Edit3,
    AlertTriangle,
    Pencil,
    QrCode
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

interface PersonaRecord {
    id: string;
    name: string;
    imageDataUrl: string;
}

const PERSONA_STORAGE_KEY = 'personas';

export function CanvasComposer({ onSend, onSchedule, sending }: CanvasComposerProps) {
    const [elements, setElements] = useState<CanvasElement[]>([]);
    const [previewImage, setPreviewImage] = useState<string | null>(null);
    const [canvasHeight, setCanvasHeight] = useState(550);
    const canvasRef = useRef<HTMLDivElement>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const drawingCanvasRef = useRef<HTMLCanvasElement>(null);

    // Modals & AI State
    const [showAiModal, setShowAiModal] = useState(false);
    const [showClearConfirm, setShowClearConfirm] = useState(false);
    const [showDrawingModal, setShowDrawingModal] = useState(false);
    const [showQrModal, setShowQrModal] = useState(false);
    const [aiPrompt, setAiPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [aiProgress, setAiProgress] = useState(0);
    const [aiEtaSeconds, setAiEtaSeconds] = useState(0);
    const [isDrawing, setIsDrawing] = useState(false);
    const [qrContent, setQrContent] = useState('');
    const [qrError, setQrError] = useState('');
    const [isQrGenerating, setIsQrGenerating] = useState(false);
    const [drawingSize, setDrawingSize] = useState(6);
    const [lastPoint, setLastPoint] = useState<{ x: number; y: number } | null>(null);
    const drawingColor = '#000000';
    const [personas, setPersonas] = useState<PersonaRecord[]>([]);

    const selectedElement = elements.find(el => el.id === selectedId);

    const loadPersonas = () => {
        const stored = localStorage.getItem(PERSONA_STORAGE_KEY);
        if (!stored) {
            setPersonas([]);
            return;
        }
        try {
            const parsed = JSON.parse(stored) as PersonaRecord[];
            setPersonas(Array.isArray(parsed) ? parsed : []);
        } catch (error) {
            console.warn('Failed to parse saved personas', error);
            setPersonas([]);
        }
    };

    useEffect(() => {
        loadPersonas();
    }, []);

    useEffect(() => {
        if (showAiModal) {
            loadPersonas();
        }
    }, [showAiModal]);

    const confirmClear = () => {
        setElements([]);
        setPreviewImage(null);
        setCanvasHeight(550);
        setSelectedId(null);
        setShowClearConfirm(false);
    };

    const handleAiGenerate = async () => {
        if (!aiPrompt.trim()) return;
        setIsGenerating(true);
        setAiProgress(0);
        try {
            let image;

            // Mock Mode for testing without API usage
            if (aiPrompt.toLowerCase().includes('mock') || aiPrompt.toLowerCase().includes('test')) {
                // Return a random placeholder from Unsplash or similar to simulate AI
                await new Promise(r => setTimeout(r, 1500)); // Fake delay
                image = `https://placehold.co/1024x1024/png?text=Mock+AI+Image`;
            } else {
                const res = await api.post('/ai/generate', {
                    prompt: aiPrompt,
                    personas: personas.map((persona) => ({
                        name: persona.name,
                        image_base64: persona.imageDataUrl
                    }))
                });
                image = res.data.image;
            }

            // 1. Reset Canvas
            setElements([]);
            setCanvasHeight(550); // Image + margins

            // 2. Add Image
            const imgEl: CanvasElement = {
                id: crypto.randomUUID(),
                type: 'image',
                content: image,
                x: 28, // Centered roughly (576-520)/2 = 28
                y: 50, // Top margin
                width: 520, // Max width with padding
                rotation: 0
            };

            setElements([imgEl]);
            setShowAiModal(false);
            setAiPrompt('');
        } catch (error) {
            console.error(error);
            alert('Failed to generate design. Please try again.');
        } finally {
            setIsGenerating(false);
        }
    };

    const insertPersonaTag = (name: string) => {
        setAiPrompt((prev) => {
            const needsSpace = prev.length > 0 && !prev.endsWith(' ');
            return `${prev}${needsSpace ? ' ' : ''}@${name} `;
        });
    };

    const handleQrGenerate = async () => {
        const value = qrContent.trim();
        if (!value) {
            setQrError('Please enter a link or message to encode.');
            return;
        }
        setIsQrGenerating(true);
        setQrError('');
        try {
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=320x320&data=${encodeURIComponent(value)}`;
            const response = await fetch(qrUrl);
            if (!response.ok) {
                throw new Error('QR service unavailable');
            }
            const blob = await response.blob();

            const dataUrl = await new Promise<string>((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result as string);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });

            const newElement: CanvasElement = {
                id: crypto.randomUUID(),
                type: 'image',
                content: dataUrl,
                x: 80,
                y: 80,
                width: 200,
                rotation: 0
            };
            setElements([...elements, newElement]);
            setShowQrModal(false);
            setQrContent('');
        } catch (error) {
            console.error(error);
            setQrError('Could not generate the QR code. Try again.');
        } finally {
            setIsQrGenerating(false);
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

        // 1. DESELECT everything to hide controls (handles, delete buttons, etc.)
        // We must wait for React to re-render the "clean" state.
        setSelectedId(null);
        await new Promise(resolve => setTimeout(resolve, 100)); // Short delay for render cycle

        try {
            // 2. Capture - Faithful Screenshot logic via html-to-image
            // Uses SVG foreignObject for near-native text rendering (fixes html2canvas artifacts)
            if (!canvasRef.current) return '';

            const tempCanvas = await toCanvas(canvasRef.current, {
                backgroundColor: '#ffffff',
                pixelRatio: 2, // Capture high-res for clean downsampling
                filter: (node) => {
                    // Exclude elements with 'no-print' class
                    if (node instanceof HTMLElement && node.classList.contains('no-print')) {
                        return false;
                    }
                    return true;
                }
            });

            // 3. Downscale to exact Printer Width (576px)
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

            // 4. Simple Threshold (Strict Black & White)
            // This replaces dithering with a clean "stamp" look
            const imageData = ctx.getImageData(0, 0, finalWidth, finalHeight);
            const data = imageData.data;
            for (let i = 0; i < data.length; i += 4) {
                const r = data[i];
                const g = data[i + 1];
                const b = data[i + 2];
                // Luminance
                const gray = (r * 0.299) + (g * 0.587) + (b * 0.114);
                // Hard threshold
                const val = gray > 128 ? 255 : 0;
                data[i] = val;
                data[i + 1] = val;
                data[i + 2] = val;
            }
            ctx.putImageData(imageData, 0, 0);

            return outputCanvas.toDataURL('image/png');
        } catch (err) {
            console.error("Capture failed:", err);
            return '';
        } finally {
            // Optional: Restore selection if you want, but usually clearing it is fine for UX
            // setSelectedId(previousSelection); 
        }
    };

    const handleSendClick = async () => {
        // If we are in preview mode, use the existing preview image
        // Otherwise generate a new one
        const img = previewImage || await generateImage();
        const success = await onSend(img);

        if (success) {
            // Reset Canvas for next message
            setElements([]);
            setPreviewImage(null);
            setCanvasHeight(550);
            setSelectedId(null);
        }
    };

    useEffect(() => {
        if (showDrawingModal && drawingCanvasRef.current) {
            const canvas = drawingCanvasRef.current;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
    }, [showDrawingModal]);

    useEffect(() => {
        if (showQrModal) {
            setQrError('');
        }
    }, [showQrModal]);

    useEffect(() => {
        if (!isGenerating) {
            setAiEtaSeconds(0);
            return;
        }

        const estimatedSeconds = 20;
        const startTime = Date.now();
        setAiEtaSeconds(estimatedSeconds);

        const interval = window.setInterval(() => {
            const elapsedSeconds = (Date.now() - startTime) / 1000;
            const progress = Math.min(0.9, elapsedSeconds / estimatedSeconds);
            const remaining = Math.max(1, Math.ceil(estimatedSeconds - elapsedSeconds));
            setAiProgress(progress);
            setAiEtaSeconds(remaining);
        }, 250);

        return () => {
            window.clearInterval(interval);
            setAiProgress(1);
            setAiEtaSeconds(0);
        };
    }, [isGenerating]);

    const getPoint = (e: React.MouseEvent | React.TouchEvent) => {
        const canvas = drawingCanvasRef.current;
        if (!canvas) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
        const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY
        };
    };

    const drawStroke = (from: { x: number; y: number }, to: { x: number; y: number }) => {
        const ctx = drawingCanvasRef.current?.getContext('2d');
        if (!ctx) return;
        ctx.strokeStyle = drawingColor;
        ctx.lineWidth = drawingSize;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();
    };

    const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
        e.preventDefault();
        const point = getPoint(e);
        setIsDrawing(true);
        setLastPoint(point);
        drawStroke(point, point);
    };

    const continueDrawing = (e: React.MouseEvent | React.TouchEvent) => {
        if (!isDrawing || !lastPoint) return;
        e.preventDefault();
        const point = getPoint(e);
        drawStroke(lastPoint, point);
        setLastPoint(point);
    };

    const stopDrawing = () => {
        setIsDrawing(false);
        setLastPoint(null);
    };

    const clearDrawing = () => {
        const canvas = drawingCanvasRef.current;
        const ctx = canvas?.getContext('2d');
        if (canvas && ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
    };

    const addDrawingToCanvas = () => {
        const canvas = drawingCanvasRef.current;
        if (!canvas) return;
        const dataUrl = canvas.toDataURL('image/png');
        const newElement: CanvasElement = {
            id: crypto.randomUUID(),
            type: 'image',
            content: dataUrl,
            x: 50,
            y: 50,
            width: 300,
            rotation: 0
        };
        setElements([...elements, newElement]);
        setShowDrawingModal(false);
    };

    return (
        <div className="flex flex-col w-full h-full relative">
            {/* Clear Confirmation Modal */}
            {showClearConfirm && (
                <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
                    <div className="bg-white rounded-2xl w-full max-w-xs shadow-2xl p-6 animate-in zoom-in-95 duration-200">
                        <div className="flex flex-col items-center text-center gap-4">
                            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center text-red-600">
                                <AlertTriangle size={24} />
                            </div>
                            <div>
                                <h3 className="font-bold text-lg text-charcoal-900">Clear Canvas?</h3>
                                <p className="text-sm text-charcoal-500">This will remove all text and images. This action cannot be undone.</p>
                            </div>
                            <div className="flex gap-3 w-full mt-2">
                                <button
                                    onClick={() => setShowClearConfirm(false)}
                                    className="flex-1 py-2 px-4 rounded-xl border border-gray-200 text-charcoal-700 font-medium hover:bg-gray-50 transition"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={confirmClear}
                                    className="flex-1 py-2 px-4 rounded-xl bg-red-500 text-white font-bold hover:bg-red-600 transition shadow-sm active:scale-95"
                                >
                                    Clear
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

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
                                Describe your message (e.g., "Bedtime note for @Alma with a dinosaur").
                            </p>
                            <textarea
                                value={aiPrompt}
                                onChange={(e) => setAiPrompt(e.target.value)}
                                className="w-full h-24 p-3 border border-gray-200 rounded-xl mb-4 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-purple-500 outline-none resize-none transition"
                                placeholder="A loving note..."
                            />
                            <div className="mb-4">
                                <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                                    <span>Insert a saved persona</span>
                                    <Link to="/personas" className="text-purple-500 hover:text-purple-600 font-medium">
                                        Manage personas
                                    </Link>
                                </div>
                                {personas.length ? (
                                    <div className="flex flex-wrap gap-2">
                                        {personas.map((persona) => (
                                            <button
                                                key={persona.id}
                                                type="button"
                                                onClick={() => insertPersonaTag(persona.name)}
                                                className="px-3 py-1 rounded-full bg-purple-50 text-purple-600 text-xs font-semibold hover:bg-purple-100 transition"
                                            >
                                                @{persona.name}
                                            </button>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-xs text-gray-400">
                                        No personas saved yet. Add one in the Personas page to reference with @name.
                                    </p>
                                )}
                            </div>
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
                            {isGenerating && (
                                <div className="mt-4 space-y-2">
                                    <div className="w-full h-2 rounded-full bg-gray-100 overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-purple-500 to-indigo-600 transition-all duration-300"
                                            style={{ width: `${Math.round(aiProgress * 100)}%` }}
                                        />
                                    </div>
                                    <p className="text-xs text-gray-500 text-center">
                                        Est. {aiEtaSeconds}s remaining
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Drawing Modal */}
            {showDrawingModal && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
                    <div className="bg-white rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-4 bg-gradient-to-r from-coral-500 to-orange-500 text-white flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2">
                                <Pencil size={18} />
                                Draw a note
                            </h3>
                            <button onClick={() => setShowDrawingModal(false)} className="text-white/80 hover:text-white">
                                <XIcon size={20} />
                            </button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="flex flex-wrap items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-semibold text-charcoal-700">Thickness</span>
                                    <input
                                        type="range"
                                        min={2}
                                        max={50}
                                        value={drawingSize}
                                        onChange={(e) => setDrawingSize(Number(e.target.value))}
                                        className="w-40"
                                    />
                                    <span className="text-xs text-charcoal-500 w-8 text-right">{drawingSize}px</span>
                                </div>
                            </div>
                            <div className="bg-gray-50 border border-gray-200 rounded-2xl overflow-hidden shadow-inner">
                                <canvas
                                    ref={drawingCanvasRef}
                                    width={700}
                                    height={480}
                                    className="w-full h-[360px] md:h-[420px] bg-white cursor-crosshair"
                                    onMouseDown={startDrawing}
                                    onMouseMove={continueDrawing}
                                    onMouseUp={stopDrawing}
                                    onMouseLeave={stopDrawing}
                                    onTouchStart={startDrawing}
                                    onTouchMove={continueDrawing}
                                    onTouchEnd={stopDrawing}
                                />
                            </div>
                            <div className="flex flex-wrap gap-3 justify-between items-center">
                                <div className="flex gap-2">
                                    <button
                                        onClick={clearDrawing}
                                        className="px-4 py-2 rounded-lg border border-gray-200 text-charcoal-700 hover:bg-gray-50 transition"
                                    >
                                        Clear
                                    </button>
                                    <button
                                        onClick={() => setShowDrawingModal(false)}
                                        className="px-4 py-2 rounded-lg border border-gray-200 text-charcoal-700 hover:bg-gray-50 transition"
                                    >
                                        Cancel
                                    </button>
                                </div>
                                <button
                                    onClick={addDrawingToCanvas}
                                    className="px-5 py-2 rounded-lg bg-coral-500 text-white font-bold hover:bg-coral-600 shadow active:scale-95 transition"
                                >
                                    Add to canvas
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* QR Modal */}
            {showQrModal && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in">
                    <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-4 bg-gradient-to-r from-emerald-500 to-teal-500 text-white flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2">
                                <QrCode size={18} />
                                QR Creator
                            </h3>
                            <button onClick={() => setShowQrModal(false)} className="text-white/80 hover:text-white">
                                <XIcon size={20} />
                            </button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="text-sm font-semibold text-charcoal-700 block mb-2" htmlFor="qr-content">
                                    QR content
                                </label>
                                <textarea
                                    id="qr-content"
                                    value={qrContent}
                                    onChange={(e) => {
                                        setQrContent(e.target.value);
                                        if (qrError) setQrError('');
                                    }}
                                    className="w-full h-24 p-3 border border-gray-200 rounded-xl bg-gray-50 focus:bg-white focus:ring-2 focus:ring-emerald-500 outline-none resize-none transition"
                                    placeholder="Paste a song link, video URL, or a short message..."
                                />
                                <p className="mt-2 text-xs text-gray-500">
                                    Keep it simple: links to songs, videos, tickets, or a quick family note.
                                </p>
                                {qrError && (
                                    <p className="mt-2 text-xs text-red-500">{qrError}</p>
                                )}
                            </div>
                            <div className="flex gap-3">
                                <button
                                    onClick={() => setShowQrModal(false)}
                                    className="flex-1 py-2 px-4 rounded-xl border border-gray-200 text-charcoal-700 font-medium hover:bg-gray-50 transition"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleQrGenerate}
                                    disabled={isQrGenerating}
                                    className="flex-1 py-2 px-4 rounded-xl bg-emerald-500 text-white font-bold hover:bg-emerald-600 transition shadow-sm active:scale-95 disabled:opacity-60"
                                >
                                    {isQrGenerating ? 'Building...' : 'Add QR'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Sticky Header Toolbar */}
            <div className="sticky top-0 z-40 bg-white/90 backdrop-blur border-b border-gray-200 shadow-sm px-2 sm:px-4 py-3 flex justify-between items-center transition-all h-[64px] overflow-x-auto no-scrollbar">
                <div className="flex gap-1 sm:gap-2 items-center flex-shrink-0">
                    {/* Design Tools OR Context Tools */}
                    {!previewImage && (
                        selectedElement && selectedElement.type === 'text' ? (
                            <div className="flex items-center gap-2 sm:gap-4 animate-in fade-in slide-in-from-left-2">
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
                                    <span className="w-6 sm:w-8 text-center text-xs font-mono">{selectedElement.fontSize || 32}</span>
                                    <button
                                        className="p-1 px-3 hover:bg-white rounded-md text-sm font-bold active:scale-95 transition"
                                        onClick={() => updateElement(selectedElement.id, { fontSize: Math.min(120, (selectedElement.fontSize || 32) + 4) })}
                                    >
                                        A+
                                    </button>
                                </div>

                                {/* Font Family Toggle */}
                                <button
                                    className="p-2 hover:bg-gray-100 rounded-lg border border-gray-200 text-xs font-bold w-12 sm:w-16 truncate"
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
                                <button
                                    onClick={() => setShowDrawingModal(true)}
                                    className="p-2 hover:bg-gray-100 rounded-lg text-charcoal-700 active:bg-gray-200 transition"
                                    title="Draw"
                                >
                                    <Pencil size={24} />
                                </button>
                                <button
                                    onClick={() => setShowQrModal(true)}
                                    className="p-2 hover:bg-gray-100 rounded-lg text-charcoal-700 active:bg-gray-200 transition"
                                    title="QR Creator"
                                >
                                    <QrCode size={22} />
                                </button>
                                <label className="p-2 hover:bg-gray-100 rounded-lg text-charcoal-700 active:bg-gray-200 transition cursor-pointer" title="Add Image">
                                    <ImageIcon size={24} />
                                    <input type="file" accept="image/*" className="hidden" onChange={addImage} />
                                </label>

                                {/* Divider - Hidden on very small screens? */}
                                <div className="w-px h-8 bg-gray-200 mx-1 sm:mx-2" />

                                <button
                                    onClick={() => setShowClearConfirm(true)}
                                    disabled={elements.length === 0}
                                    className={`p-2 rounded-lg transition ${elements.length > 0
                                        ? 'text-charcoal-900 hover:bg-red-50 hover:text-red-600'
                                        : 'text-gray-300 cursor-not-allowed'
                                        }`}
                                    title="Clear Canvas"
                                >
                                    <Trash2 size={20} />
                                </button>
                            </>
                        )
                    )}
                </div>

                {/* Print / Preview Actions */}
                <div className="flex gap-1 sm:gap-2 flex-shrink-0 ml-4">
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
                        className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-bold border transition flex items-center gap-2 ${previewImage ? 'bg-black text-white border-black' : 'bg-white text-charcoal-700 border-gray-300 hover:bg-gray-50'}`}
                    >
                        {previewImage ? (
                            <>
                                <Edit3 size={16} />
                                <span className="hidden sm:inline">Edit</span>
                            </>
                        ) : (
                            <>
                                <Eye size={16} />
                                <span className="hidden sm:inline">Preview</span>
                            </>
                        )}
                    </button>

                    <button
                        onClick={handleSendClick}
                        disabled={sending || (!elements.length && !previewImage)}
                        className={`px-4 sm:px-6 py-2 rounded-lg text-sm font-bold text-white transition shadow-md flex items-center gap-2 ${sending ? 'bg-coral-400 cursor-wait' : 'bg-coral-500 hover:bg-coral-600 active:scale-95'
                            }`}
                    >
                        {sending ? 'Sending...' : 'PRINT'}
                    </button>
                </div>
            </div>

            {/* Main Infinite Canvas Area */}
            <div className="flex-1 bg-gray-100 overflow-y-auto overflow-x-hidden relative flex flex-col items-center pt-4 sm:pt-8 pb-32" onClick={() => setSelectedId(null)}>
                {/* Visual shadow for roll depth */}
                <div className="fixed top-[64px] left-0 right-0 h-6 bg-gradient-to-b from-black/5 to-transparent pointer-events-none z-30" />

                {/* Paper Roll Simulation */}
                <div className="flex flex-col items-center gap-4 w-full origin-top transform scale-[0.55] xs:scale-[0.65] sm:scale-[0.85] md:scale-100 transition-transform duration-300">
                    <div
                        className="relative bg-white shadow-xl border border-gray-200 transition-all duration-300"
                        style={{
                            width: '640px', // 80mm Full Width Visual
                            minHeight: `${canvasHeight}px`
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
                                </div>
                            ) : (
                                <div
                                    ref={canvasRef}
                                    className="bg-white relative h-full cursor-text"
                                    style={{ minHeight: `${canvasHeight}px` }}
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
                </div>
            </div>

            {/* Footer Actions - Add Paper */}
            {!previewImage && (
                <div className="w-full bg-white border-t border-gray-200 p-4 shrink-0 z-50 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] pb-[calc(1rem+env(safe-area-inset-bottom))]">
                    <button
                        onClick={() => setCanvasHeight(h => h + 400)}
                        className="w-full bg-gray-100 hover:bg-gray-200 text-charcoal-800 py-3 rounded-xl text-base font-bold transition flex items-center justify-center gap-2 active:scale-[0.98]"
                    >
                        <span className="text-xl leading-none font-light block pb-0.5">+</span>
                        Add Paper
                    </button>
                </div>
            )}
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
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const lastTap = useRef(0);

    // Internal state for smooth dragging/rotating without constant parent re-renders until stop
    // For React-Draggable, we strictly control position via props to ensure sync, 
    // BUT to avoid "reset" issues, we must rely on the parent state passed in `element.x / y`.

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.setSelectionRange(inputRef.current.value.length, inputRef.current.value.length);
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
            onStop={(_, data) => onUpdate({ x: data.x, y: data.y })}
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
                onTouchStart={() => {
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
                    <div className={`relative ${isEditing ? 'z-50' : 'z-auto'}`}>
                        {element.type === 'image' ? (
                            <div className={`relative transition-all duration-200 ${isSelected ? 'outline outline-2 outline-coral-400' : 'group-hover:outline group-hover:outline-2 group-hover:outline-coral-400'}`}>
                                <img
                                    src={element.content}
                                    alt="Element"
                                    crossOrigin="anonymous"
                                    className="pointer-events-none select-none max-w-full"
                                    style={{ width: `${element.width || 200}px` }}
                                />

                                {/* Resize Handle (Bottom Right) */}
                                <div
                                    className={`no-drag absolute -bottom-4 -right-4 w-10 h-10 bg-white border border-charcoal-300 rounded-full shadow cursor-nwse-resize flex items-center justify-center transition-all z-50 ${isSelected ? 'opacity-100 scale-100' : 'opacity-0 group-hover:opacity-100 scale-90 group-hover:scale-100'}`}
                                    onMouseDown={handleResize}
                                    onTouchStart={handleResize}
                                    title="Resize"
                                >
                                    <Scaling size={16} className="text-charcoal-600" />
                                </div>
                            </div>
                        ) : (
                            isEditing ? (
                                <textarea
                                    ref={inputRef}
                                    value={element.content}
                                    onChange={(e) => onUpdate({ content: e.target.value })}
                                    onBlur={() => setIsEditing(false)}
                                    rows={Math.max(2, element.content.split('\n').length)}
                                    // Removed onTouchEnd
                                    className="bg-white/80 backdrop-blur border-2 border-coral-500 rounded-lg outline-none p-4 no-drag text-charcoal-900 resize-none text-center shadow-xl overflow-hidden"
                                    style={{
                                        fontSize: element.fontSize || 32,
                                        fontFamily: element.fontFamily || 'handwriting',
                                        width: '400px',
                                        maxWidth: '500px'
                                    }}
                                />
                            ) : (
                                <div
                                    data-type="text"
                                    className={`p-2 border-2 rounded select-none transition-all ${isSelected ? 'border-coral-400 bg-coral-50/20' : 'border-transparent hover:border-gray-300'}`}
                                    style={{
                                        color: '#000000', // Explicit black for capture
                                        lineHeight: 1.2,
                                        fontSize: element.fontSize || 32,
                                        fontFamily: element.fontFamily || 'handwriting',
                                        maxWidth: '500px',
                                        whiteSpace: 'pre-wrap',
                                        wordBreak: 'break-word',
                                        textAlign: 'center'
                                    }}
                                >
                                    {element.content}
                                </div>
                            )
                        )}

                        {/* Controls Container (Visible when selected or hovered) */}
                        <div className={`absolute top-0 left-0 w-full h-full pointer-events-none ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}>
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
