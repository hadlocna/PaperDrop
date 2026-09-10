import { useEffect, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { client as api } from '../api/client';

type VoiceState = { enabled: boolean; state: string; error?: string; ready: boolean };
export function VoiceSettings({ deviceId }: { deviceId: string }) {
    const [state, setState] = useState<VoiceState | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    async function run(action: string) {
        setBusy(true); setError('');
        try { setState((await api.post(`/devices/${deviceId}/voice`, { action }, { timeout: 30000 })).data); }
        catch (e: any) { setError(e.response?.data?.error || 'Unable to reach PaperDrop.'); }
        finally { setBusy(false); }
    }
    useEffect(() => {
        let active = true;
        const refresh = () => api.get(`/devices/${deviceId}/voice`, { timeout: 30000 })
            .then(r => { if (active) { setState(r.data); setError(''); } })
            .catch(e => { if (active) setError(e.response?.data?.error || 'Voice controls need the latest device update.'); });
        void refresh();
        const timer = setInterval(refresh, 10000);
        return () => { active = false; clearInterval(timer); };
    }, [deviceId]);
    return <section className="border-t pt-4 space-y-3" aria-label="PaperDrop voice assistant">
        <h3 className="font-semibold flex items-center gap-2"><Mic size={18} /> Hey Paper Drop</h3>
        <p className="text-sm text-gray-600">Say “Hey Paper Drop”, wait for the reply, then ask for a picture. PaperDrop will draw it and print it for you.</p>
        <p className="text-xs text-gray-500">When enabled, the microphone listens locally for the wake phrase. After waking, conversation audio goes to OpenAI for an AI voice reply. PaperDrop does not save voice recordings or transcripts. Conversations end after 2 minutes at most. One picture per conversation.</p>
        <p role="status" className="text-sm">{state?.enabled ? `Voice on · ${state.state}` : 'Voice listening off'}</p>
        {(error || state?.error) && <p role="alert" className="text-sm text-red-700">{error || state?.error}</p>}
        <div className="flex flex-wrap gap-2">
            <button disabled={busy || !state} onClick={() => run(state?.enabled ? 'disable' : 'enable')} className="px-3 py-2 rounded-xl bg-charcoal-800 text-white text-sm flex gap-2 items-center disabled:opacity-50">{state?.enabled ? <MicOff size={16} /> : <Mic size={16} />}{state?.enabled ? 'Turn listening off' : 'Enable voice listening'}</button>
            <button disabled={busy || !state?.enabled || state.state !== 'listening'} onClick={() => run('wake')} className="px-3 py-2 border rounded-xl text-sm disabled:opacity-50">Try a conversation</button>
        </div>
        {state?.enabled && <p className="text-xs text-gray-500">Turn listening off before changing the Bluetooth speaker or running a sound or microphone test.</p>}
    </section>;
}
