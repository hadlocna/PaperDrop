import { IncomingMessage } from 'http';
import { BlockList, isIP } from 'net';

// Temporary, latest-only diagnostic authorized for this unclaimed unit.
export const IP_DIAGNOSTIC_DEVICE = 'PD-E0FC0D45';
export const IP_DIAGNOSTIC_TTL_MS = 15 * 60 * 1000;
export type PublicNetwork = { address: string; observedAt: string; source: 'socket' | 'trusted_proxy' };
let latest: PublicNetwork | null = null;
let expiry: NodeJS.Timeout | undefined;
const reserved = new BlockList();
for (const [address, prefix] of [
    ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8],
    ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24],
    ['192.168.0.0', 16], ['198.18.0.0', 15], ['198.51.100.0', 24], ['203.0.113.0', 24],
    ['224.0.0.0', 4], ['240.0.0.0', 4]
] as [string, number][]) reserved.addSubnet(address, prefix, 'ipv4');
reserved.addSubnet('2001:db8::', 32, 'ipv6');
reserved.addSubnet('2001::', 23, 'ipv6');
reserved.addSubnet('2002::', 16, 'ipv6');

export const normalizeAddress = (value: unknown): string | null => {
    if (typeof value !== 'string' || value.length > 64) return null;
    let address = value.trim().toLowerCase();
    if (address.startsWith('::ffff:') && isIP(address.slice(7)) === 4) address = address.slice(7);
    if (!isIP(address) || address.includes('%')) return null;
    return isIP(address) === 6 ? new URL(`http://[${address}]/`).hostname.slice(1, -1) : address;
};
export const isPublicAddress = (value: unknown): boolean => {
    const address = normalizeAddress(value);
    if (!address) return false;
    if (isIP(address) === 4) return !reserved.check(address, 'ipv4');
    // Conservatively accept global unicast only; never display link-local/ULA/multicast.
    return /^[23]/.test(address) && !reserved.check(address, 'ipv6');
};

export const observedPublicAddress = (req: IncomingMessage, trustedProxyAddresses = process.env.PAPERDROP_IP_TRUSTED_PROXIES || ''): Omit<PublicNetwork, 'observedAt'> | null => {
    const peer = normalizeAddress(req.socket.remoteAddress);
    if (!peer) return null;
    const trusted = new Set(trustedProxyAddresses.split(',').map(normalizeAddress).filter((ip): ip is string => Boolean(ip)));
    if (!trusted.has(peer)) return isPublicAddress(peer) ? { address: peer, source: 'socket' } : null;
    const forwarded = req.headers['x-forwarded-for'];
    if (typeof forwarded !== 'string' || forwarded.length > 1024) return null;
    const hops = forwarded.split(',').map(normalizeAddress);
    if (!hops.length || hops.length > 16 || hops.some(ip => !ip)) return null;
    // Walk from the verified peer toward the client, stopping at the first untrusted hop.
    for (let index = hops.length - 1; index >= 0; index--) {
        const address = hops[index]!;
        if (!trusted.has(address)) return isPublicAddress(address) ? { address, source: 'trusted_proxy' } : null;
    }
    return null;
};

export const observePublicNetwork = (deviceCode: string, req: IncomingMessage, now = Date.now()): void => {
    if (deviceCode !== IP_DIAGNOSTIC_DEVICE) return;
    if (expiry) clearTimeout(expiry);
    const observation = observedPublicAddress(req);
    latest = observation ? { ...observation, observedAt: new Date(now).toISOString() } : null;
    if (latest) {
        expiry = setTimeout(() => { latest = null; expiry = undefined; }, IP_DIAGNOSTIC_TTL_MS);
        expiry.unref();
    }
};
export const validatePublicNetwork = (value: unknown, now = Date.now()): PublicNetwork | null => {
    if (!value || typeof value !== 'object') return null;
    const candidate = value as PublicNetwork;
    const address = normalizeAddress(candidate.address);
    const observed = Date.parse(candidate.observedAt);
    if (!address || !isPublicAddress(address) || !Number.isFinite(observed) || observed > now || now - observed >= IP_DIAGNOSTIC_TTL_MS) return null;
    if (candidate.source !== 'socket' && candidate.source !== 'trusted_proxy') return null;
    return { address, observedAt: new Date(observed).toISOString(), source: candidate.source };
};
export const publicNetworkForAdmin = (deviceCode: string, relayObservation?: unknown, now = Date.now()): PublicNetwork | null => {
    if (deviceCode !== IP_DIAGNOSTIC_DEVICE) return null;
    const local = validatePublicNetwork(latest, now);
    if (!local) latest = null;
    const relay = validatePublicNetwork(relayObservation, now);
    return relay && (!local || relay.observedAt > local.observedAt) ? relay : local;
};
