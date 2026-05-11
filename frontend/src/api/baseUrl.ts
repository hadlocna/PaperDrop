const PRODUCTION_BACKEND_URL = 'https://api.paperdrop.me';
const LEGACY_RENDER_BACKEND_URL = 'https://paperdrop-backend.onrender.com';

const productionFrontendHosts = new Set([
    'paperdrop.me',
    'www.paperdrop.me',
    'paperdrop-frontend-eidfq0.64.225.69.211.sslip.io'
]);

const configuredBaseUrl = import.meta.env.VITE_API_URL?.replace(/\/$/, '');
const currentHost = typeof window !== 'undefined' ? window.location.hostname : '';
const isProductionFrontend = productionFrontendHosts.has(currentHost);
const isStaleRenderUrl = configuredBaseUrl === LEGACY_RENDER_BACKEND_URL;

export const API_BASE_URL = isProductionFrontend && (!configuredBaseUrl || isStaleRenderUrl)
    ? PRODUCTION_BACKEND_URL
    : configuredBaseUrl || 'http://localhost:3000';

export const API_URL = `${API_BASE_URL}/api`;
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');
