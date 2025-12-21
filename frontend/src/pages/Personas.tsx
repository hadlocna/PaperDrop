import { useEffect, useMemo, useState } from 'react';
import { Layout } from '../components/Layout';
import { Image as ImageIcon, Plus, Trash2, Copy, Check } from 'lucide-react';

interface Persona {
    id: string;
    name: string;
    imageDataUrl: string;
    createdAt: string;
}

const STORAGE_KEY = 'personas';

const normalizeName = (name: string) => name.trim();

const resizeImage = (dataUrl: string, maxWidth = 1024, maxHeight = 1024): Promise<string> => {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            let width = img.width;
            let height = img.height;

            if (width > height) {
                if (width > maxWidth) {
                    height *= maxWidth / width;
                    width = maxWidth;
                }
            } else {
                if (height > maxHeight) {
                    width *= maxHeight / height;
                    height = maxHeight;
                }
            }

            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            ctx?.drawImage(img, 0, 0, width, height);
            resolve(canvas.toDataURL('image/jpeg', 0.8));
        };
        img.src = dataUrl;
    });
};

const loadPersonas = (): Persona[] => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    try {
        const parsed = JSON.parse(stored) as Persona[];
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
};

const savePersonas = (personas: Persona[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(personas));
};

export function Personas() {
    const [personas, setPersonas] = useState<Persona[]>([]);
    const [name, setName] = useState('');
    const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [copiedId, setCopiedId] = useState<string | null>(null);

    useEffect(() => {
        setPersonas(loadPersonas());
    }, []);

    useEffect(() => {
        savePersonas(personas);
    }, [personas]);

    const normalizedName = useMemo(() => normalizeName(name), [name]);
    const nameExists = useMemo(() => {
        return personas.some((persona) => normalizeName(persona.name).toLowerCase() === normalizedName.toLowerCase());
    }, [personas, normalizedName]);

    const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onloadend = async () => {
            const resized = await resizeImage(reader.result as string);
            setImageDataUrl(resized);
        };
        reader.readAsDataURL(file);
    };

    const handleAddPersona = async (event: React.FormEvent) => {
        event.preventDefault();
        setError('');

        if (!normalizedName) {
            setError('Please enter a name for this cameo.');
            return;
        }

        if (nameExists) {
            setError('That cameo name already exists. Please pick a unique name.');
            return;
        }

        if (!imageDataUrl) {
            setError('Please upload a headshot image.');
            return;
        }

        setSaving(true);
        try {
            const persona: Persona = {
                id: crypto.randomUUID(),
                name: normalizedName,
                imageDataUrl,
                createdAt: new Date().toISOString()
            };
            setPersonas((prev) => [persona, ...prev]);
            setName('');
            setImageDataUrl(null);
        } finally {
            setSaving(false);
        }
    };

    const handleRemovePersona = (personaId: string) => {
        setPersonas((prev) => prev.filter((persona) => persona.id !== personaId));
    };

    const handleCopy = async (persona: Persona) => {
        await navigator.clipboard.writeText(`@${persona.name}`);
        setCopiedId(persona.id);
        setTimeout(() => setCopiedId(null), 1500);
    };

    return (
        <Layout>
            <div className="max-w-5xl mx-auto px-4 py-8">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
                    <div>
                        <h1 className="text-2xl font-semibold text-charcoal-700">Personas</h1>
                        <p className="text-sm text-gray-500 mt-1">
                            Upload headshots and reference them in prompts using <span className="font-medium text-charcoal-700">@name</span>.
                        </p>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,_360px)_minmax(0,_1fr)] gap-8">
                    <form onSubmit={handleAddPersona} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-5">
                        <div className="flex items-center gap-2 text-charcoal-700">
                            <Plus size={18} />
                            <h2 className="text-lg font-semibold">Add a new cameo</h2>
                        </div>

                        {error && (
                            <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-600">
                                {error}
                            </div>
                        )}

                        <div>
                            <label className="block text-sm font-medium text-gray-600 mb-2">Name</label>
                            <input
                                value={name}
                                onChange={(event) => setName(event.target.value)}
                                className="w-full px-4 py-2 rounded-xl border border-gray-200 bg-gray-50 focus:ring-2 focus:ring-coral-500 outline-none transition"
                                placeholder="e.g. Lucy"
                            />
                            <p className="mt-2 text-xs text-gray-400">Use a short, unique label. You will reference it as @name.</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-600 mb-2">Headshot</label>
                            <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center hover:border-coral-300 transition-colors">
                                {imageDataUrl ? (
                                    <div className="space-y-3">
                                        <img
                                            src={imageDataUrl}
                                            alt="Headshot preview"
                                            className="h-40 w-40 object-cover rounded-full mx-auto shadow-sm"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setImageDataUrl(null)}
                                            className="text-sm text-red-500 hover:text-red-700 font-medium"
                                        >
                                            Remove image
                                        </button>
                                    </div>
                                ) : (
                                    <label className="cursor-pointer block">
                                        <div className="w-14 h-14 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-3 text-gray-400">
                                            <ImageIcon size={28} />
                                        </div>
                                        <p className="text-charcoal-600 font-medium">Click to upload a headshot</p>
                                        <p className="text-xs text-gray-400 mt-1">PNG or JPG up to 50MB</p>
                                        <input
                                            type="file"
                                            accept="image/*"
                                            className="hidden"
                                            onChange={handleImageUpload}
                                        />
                                    </label>
                                )}
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={saving}
                            className="w-full py-2.5 rounded-xl bg-coral-500 text-white font-semibold hover:bg-coral-600 transition disabled:opacity-60"
                        >
                            {saving ? 'Saving...' : 'Save persona'}
                        </button>
                    </form>

                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-semibold text-charcoal-700">Saved personas</h2>
                            <span className="text-sm text-gray-400">{personas.length} total</span>
                        </div>

                        {personas.length === 0 ? (
                            <div className="text-center py-16 text-gray-400">
                                <p className="font-medium">No personas yet</p>
                                <p className="text-sm mt-2">Upload a headshot to get started.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {personas.map((persona) => (
                                    <div key={persona.id} className="border border-gray-100 rounded-2xl p-4 flex flex-col gap-4">
                                        <div className="flex items-start gap-4">
                                            <img
                                                src={persona.imageDataUrl}
                                                alt={persona.name}
                                                className="h-16 w-16 rounded-full object-cover border border-gray-100"
                                            />
                                            <div className="flex-1">
                                                <p className="font-semibold text-charcoal-700">{persona.name}</p>
                                                <p className="text-xs text-gray-400">Use @ in prompts</p>
                                                <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-gray-50 px-3 py-1 text-xs font-medium text-gray-600">
                                                    @{persona.name}
                                                </div>
                                            </div>
                                        </div>

                                        <div className="flex items-center justify-between gap-2">
                                            <button
                                                type="button"
                                                onClick={() => handleCopy(persona)}
                                                className="flex items-center gap-2 text-sm text-charcoal-500 hover:text-coral-500 transition"
                                            >
                                                {copiedId === persona.id ? <Check size={16} /> : <Copy size={16} />}
                                                {copiedId === persona.id ? 'Copied' : 'Copy tag'}
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => handleRemovePersona(persona.id)}
                                                className="flex items-center gap-2 text-sm text-red-500 hover:text-red-600 transition"
                                            >
                                                <Trash2 size={16} />
                                                Remove
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </Layout>
    );
}
