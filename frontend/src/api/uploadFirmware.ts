const CHUNK_BYTES = 8 * 1024 * 1024;

export async function uploadFirmware(baseUrl: string, password: string, form: FormData, progress: (percent: number) => void) {
    const file = form.get('file');
    if (!(file instanceof File) || !file.size || file.size > 600 * 1024 * 1024) throw Error('Choose a firmware package smaller than 600 MB.');
    const id = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(value => value.toString(16).padStart(2, '0')).join('');
    const base = `${baseUrl}/api/admin/firmware-upload/${id}`;
    async function request(url: string, options: RequestInit) {
        for (let attempt = 0; attempt < 3; attempt++) {
            try {
                const res = await fetch(url, { ...options, signal: AbortSignal.timeout(45000) });
                if (res.ok) return await res.json();
                const message = await res.json().catch(() => ({}));
                if (res.status < 500 || attempt === 2) throw Object.assign(Error(message.error || `Upload failed (${res.status}).`), { permanent: true });
            } catch (error) {
                if (attempt === 2 || (error as { permanent?: boolean }).permanent) throw error;
            }
        }
    }
    const count = Math.ceil(file.size / CHUNK_BYTES);
    for (let index = 0; index < count; index++) {
        await request(`${base}/chunks/${index}`, { method: 'PUT', headers: { 'x-admin-password': password, 'Content-Type': 'application/octet-stream' }, body: file.slice(index * CHUNK_BYTES, (index + 1) * CHUNK_BYTES) });
        progress(Math.round((index + 1) / count * 100));
    }
    return request(`${base}/complete`, { method: 'POST', headers: { 'x-admin-password': password, 'Content-Type': 'application/json' }, body: JSON.stringify({ count, version: form.get('version'), description: form.get('description'), isCritical: form.get('isCritical') === 'true' }) });
}
