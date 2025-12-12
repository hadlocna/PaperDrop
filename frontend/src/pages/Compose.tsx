import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { client as api } from '../api/client';
import { Image as ImageIcon, Type as TypeIcon } from 'lucide-react';

export function Compose() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();

    const [mode, setMode] = useState<'text' | 'image'>('text');
    const [message, setMessage] = useState('');
    const [selectedImage, setSelectedImage] = useState<string | null>(null);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');

    const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                setSelectedImage(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleSend = async () => {
        if (mode === 'text' && !message.trim()) return;
        if (mode === 'image' && !selectedImage) return;

        setSending(true);
        setError('');

        try {
            const payload = mode === 'text'
                ? {
                    contentType: 'text',
                    content: { body: message, timestamp: true }
                }
                : {
                    contentType: 'image',
                    content: { content: selectedImage } // agent expects content to be base64 string directly or wrapped?
                    // Previous agent analysis: 
                    // if content_type == 'image': print_handler.print_image(msg_obj.get('content'))
                    // So we should send { content: base64 } or just base64 string as 'content'?
                    // print_handler.print_message uses msg_obj.get('content') -> body.
                    // print_handler.print_image uses msg_obj.get('content'). 
                    // So for consistency: content: selectedImage
                };

            // Refined payload logic based on server storing JSON
            let apiContent;
            if (mode === 'text') {
                apiContent = { body: message, timestamp: true };
            } else {
                // For image, we pass the base64 string directly in a field the agent reads.
                // Agent: msg_obj.get('content')
                apiContent = { content: selectedImage };
            }

            await api.post('/messages', {
                deviceId: id,
                senderId: user?.id,
                contentType: mode,
                content: apiContent
            });
            navigate('/');
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to send');
            setSending(false);
        }
    };

    return (
        <Layout>
            <div className="max-w-2xl mx-auto mt-8 px-4">
                <div className="bg-white rounded-2xl shadow-sm p-6">
                    <h1 className="text-xl font-semibold mb-6 text-charcoal-700">New Message</h1>

                    {error && (
                        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    {/* Tabs */}
                    <div className="flex gap-2 mb-6 bg-gray-50 p-1 rounded-xl w-fit">
                        <button
                            onClick={() => setMode('text')}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${mode === 'text' ? 'bg-white text-coral-500 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            <TypeIcon size={18} />
                            Text
                        </button>
                        <button
                            onClick={() => setMode('image')}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${mode === 'image' ? 'bg-white text-coral-500 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            <ImageIcon size={18} />
                            Image
                        </button>
                    </div>

                    <div className="mb-6">
                        {mode === 'text' ? (
                            <div className="border border-gray-200 rounded-xl p-4 min-h-[200px] flex flex-col focus-within:ring-2 focus-within:ring-coral-500/20 transition-all">
                                <textarea
                                    value={message}
                                    onChange={(e) => setMessage(e.target.value)}
                                    placeholder="Type your message here..."
                                    className="w-full h-full resize-none outline-none text-lg font-handwriting bg-transparent placeholder-gray-300"
                                    autoFocus
                                    maxLength={500}
                                />
                                <div className="text-right text-xs text-gray-400 mt-2">
                                    {message.length}/500
                                </div>
                            </div>
                        ) : (
                            <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-coral-300 transition-colors">
                                {selectedImage ? (
                                    <div className="relative">
                                        <img src={selectedImage} alt="Preview" className="max-h-64 mx-auto rounded-lg shadow-sm" />
                                        <button
                                            onClick={() => setSelectedImage(null)}
                                            className="mt-4 text-sm text-red-500 hover:text-red-700 font-medium"
                                        >
                                            Remove Image
                                        </button>
                                    </div>
                                ) : (
                                    <label className="cursor-pointer block">
                                        <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-3 text-gray-400">
                                            <ImageIcon size={32} />
                                        </div>
                                        <p className="text-charcoal-600 font-medium">Click to upload an image</p>
                                        <p className="text-xs text-gray-400 mt-1">Supports PNG, JPG (Max 2MB)</p>
                                        <input
                                            type="file"
                                            accept="image/*"
                                            className="hidden"
                                            onChange={handleImageUpload}
                                        />
                                    </label>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="flex justify-end gap-3 pt-4 border-t border-gray-50">
                        <button
                            onClick={() => navigate('/')}
                            className="px-6 py-2.5 text-charcoal-500 hover:bg-gray-50 rounded-xl font-medium transition"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSend}
                            disabled={sending || (mode === 'text' ? !message.trim() : !selectedImage)}
                            className="px-8 py-2.5 bg-coral-500 text-white font-medium rounded-xl hover:bg-coral-600 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md"
                        >
                            {sending ? 'Sending...' : 'Send Now'}
                        </button>
                    </div>
                </div>
            </div>
        </Layout>
    );
}
