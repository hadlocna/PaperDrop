import { useState } from 'react';
import { client as api } from '../api/client';

export function RecoverySettings({ deviceId }: { deviceId: string }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const downloadImage = async () => {
        setBusy(true); setError('');
        try {
            const response = await fetch('https://api.paperdrop.me/uploads/image.json', { cache: 'no-store' });
            if (!response.ok) throw Error('The image is not available yet.');
            const image = await response.json();
            const url = new URL(image.url);
            if (url.origin !== 'https://api.paperdrop.me' || !url.pathname.startsWith('/uploads/')) throw Error('Invalid image link.');
            const link = document.createElement('a'); link.href = url.href; link.click();
        } catch { setError('The image is not available yet. Please try again later.'); }
        finally { setBusy(false); }
    };
    const download = async () => {
        setBusy(true); setError('');
        try {
            const response = await api.post(`/devices/${deviceId}/enrollment`);
            const url = URL.createObjectURL(new Blob([JSON.stringify(response.data)], { type: 'application/json' }));
            const link = document.createElement('a'); link.href = url; link.download = 'paperdrop-enrollment.json'; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error: any) { setError(error.response?.data?.error || 'Unable to prepare the recovery file.'); }
        finally { setBusy(false); }
    };
    return <section className="space-y-3 border-t pt-4">
        <h3 className="font-semibold">Replace the SD card</h3>
        <p className="text-sm text-gray-500">After writing the PaperDrop image, copy this private recovery file onto the card’s bootfs drive before its first startup. It keeps this device’s account and family connections. The file expires after seven days.</p>
        <button disabled={busy} onClick={downloadImage} className="px-3 py-2 border rounded-xl text-sm disabled:opacity-50">Download PaperDrop image</button>
        <button disabled={busy} onClick={download} className="px-3 py-2 border rounded-xl text-sm disabled:opacity-50">{busy ? 'Preparing…' : 'Download recovery file'}</button>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </section>;
}
