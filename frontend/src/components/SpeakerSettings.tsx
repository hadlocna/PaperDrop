import { VoiceSettings } from './VoiceSettings';
import { useEffect, useState } from 'react';
import { Bluetooth, Mic, RefreshCw, Volume2 } from 'lucide-react';
import { client as api } from '../api/client';

interface Speaker {
    address: string;
    name: string;
    connected: boolean;
    paired: boolean;
    selected: boolean;
    microphoneSupported: boolean;
}
interface SpeakerState {
    audioReady: boolean;
    powered: boolean;
    devices: Speaker[];
    selectedAddress?: string;
}

export function SpeakerSettings({ deviceId }: { deviceId: string }) {
    const [state, setState] = useState<SpeakerState | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');

    useEffect(() => {
        let active = true;
        setBusy('status');
        api.get(`/devices/${deviceId}/speaker`, { timeout: 65000 })
            .then(res => { if (active) setState(res.data); })
            .catch(err => { if (active) setError(err.response?.data?.error || 'Unable to reach PaperDrop.'); })
            .finally(() => { if (active) setBusy(null); });
        return () => { active = false; };
    }, [deviceId]);

    const run = async (action: string, address?: string) => {
        setBusy(action);
        setError('');
        setMessage('');
        try {
            const res = await api.post(`/devices/${deviceId}/speaker`, { action, address }, { timeout: 65000 });
            setState(res.data);
            setMessage(res.data.message || (action === 'scan' ? 'Scan finished.' : action === 'connect' ? 'Speaker connected and saved.' : ''));
        } catch (err: any) {
            setError(err.response?.data?.error || 'Unable to reach PaperDrop. Check its power and Wi-Fi.');
        } finally {
            setBusy(null);
        }
    };
    const selected = state?.devices.find(speaker => speaker.selected);

    return <section className="space-y-3" aria-label="Speaker and microphone">
        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2"><Bluetooth size={17} /> Speaker & microphone</h3>
        <p className="text-sm text-gray-500">Put your speaker in pairing mode near PaperDrop, then scan. PaperDrop searches using its own Bluetooth.</p>
        {state && !state.audioReady && <p className="text-sm text-amber-700">Bluetooth audio support needs a device update before connecting.</p>}
        <div className="flex gap-2">
            <button disabled={!!busy} onClick={() => run('scan')} className="px-4 py-2 bg-charcoal-800 text-white rounded-xl text-sm font-medium disabled:opacity-50 flex items-center gap-2">
                <RefreshCw size={16} className={busy === 'scan' ? 'animate-spin' : ''} />{busy === 'scan' ? 'Scanning nearby…' : 'Scan for speakers'}
            </button>
            <button disabled={!!busy} onClick={() => run('status')} className="px-3 py-2 border rounded-xl text-sm disabled:opacity-50">Refresh</button>
        </div>
        {busy && <p role="status" className="text-sm text-gray-500">{busy === 'microphone_test' ? 'Speak now: recording for 5 seconds, then playing it back…' : busy === 'connect' ? 'Pairing and connecting… This can take up to a minute.' : busy === 'test' ? 'Playing test sound…' : busy === 'scan' ? 'Looking for speakers for 10 seconds…' : 'Checking speaker…'}</p>}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
        {state?.devices.length === 0 && !busy && <p className="text-sm text-gray-500">No speakers found yet. Enable pairing mode and scan again.</p>}
        <ul className="space-y-2">
            {state?.devices.map(speaker => <li key={speaker.address} className="p-3 bg-gray-50 border border-gray-100 rounded-xl flex items-center justify-between gap-3">
                <div className="min-w-0"><p className="font-medium text-sm text-charcoal-800 break-words">{speaker.name}</p><p className="text-xs text-gray-500">{speaker.connected ? 'Connected' : speaker.paired ? 'Paired' : 'Available'}{speaker.selected ? ' · Selected' : ''}</p></div>
                <button disabled={!!busy || !state.audioReady} onClick={() => run(speaker.connected && speaker.selected ? 'disconnect' : 'connect', speaker.address)} className="px-3 py-2 border rounded-xl bg-white text-sm disabled:opacity-50">{speaker.connected && speaker.selected ? 'Disconnect' : 'Connect'}</button>
            </li>)}
        </ul>
        {selected && <div className="space-y-3 border-t pt-3">
            <button disabled={!!busy || !selected.connected} onClick={() => run('test')} className="flex items-center gap-2 text-sm font-medium text-coral-600 disabled:opacity-50"><Volume2 size={17} /> Play test sound</button>
            <p className="text-sm text-gray-500 flex items-center gap-2"><Mic size={17} />{selected.microphoneSupported ? 'Bluetooth microphone supported. Available for voice conversations.' : 'This speaker does not advertise a Bluetooth microphone.'}</p>
            {selected.microphoneSupported && <><p className="text-xs text-gray-500">Microphone test records 5 seconds, plays it on the speaker, then deletes it. Nothing is uploaded. Wake-phrase listening is controlled separately below.</p><button disabled={!!busy || !selected.connected} onClick={() => run('microphone_test')} className="px-3 py-2 border rounded-xl text-sm disabled:opacity-50">Test microphone (5 seconds)</button></>}
        </div>}
        <VoiceSettings deviceId={deviceId} />
    </section>;
}
