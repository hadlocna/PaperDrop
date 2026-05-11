import axios from 'axios';
import { AUTH_EXPIRED_EVENT, AUTH_FAILURE_MESSAGES } from '../auth/events';
import { API_URL } from './baseUrl';

export const client = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add a request interceptor to include the JWT token
client.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

client.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error.response?.status;
        const message = error.response?.data?.error;
        const isAuthFailure = (status === 401 || status === 403) && AUTH_FAILURE_MESSAGES.has(message);

        if (isAuthFailure && typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, {
                detail: { status, message }
            }));
        }

        return Promise.reject(error);
    }
);

export const registerUser = async (email: string, name: string, password: string) => {
    const response = await client.post('/users', { email, name, password });
    return response.data;
};

export const claimDevice = async (deviceCode: string) => {
    const response = await client.post('/devices/claim', { deviceCode });
    return response.data;
};

export const updateDevice = async (deviceId: string, data: any) => {
    const response = await client.patch(`/devices/${deviceId}`, data);
    return response.data;
};

export const unclaimDevice = async (deviceId: string) => {
    const response = await client.delete(`/devices/${deviceId}/claim`);
    return response.data;
};

export const clearMessageQueue = async (deviceId: string) => {
    const response = await client.delete('/messages/queue', { data: { deviceId } });
    return response.data;
};

export const createInviteLink = async (deviceId: string, email?: string) => {
    const response = await client.post(`/invites/devices/${deviceId}/invites`, { email });
    return response.data;
};

export const downloadDeviceLogs = async (
    deviceId: string,
    type: string,
    lines: number
) => {
    const response = await client.get(`/devices/${deviceId}/logs`, {
        params: { type, lines },
        responseType: 'blob'
    });
    return response;
};

export const getInviteDetails = async (token: string) => {
    const response = await client.get(`/invites/${token}`);
    return response.data;
};

export const acceptInvite = async (token: string) => {
    const response = await client.post(`/invites/${token}/accept`);
    return response.data;
};
