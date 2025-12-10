import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

export const client = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const registerUser = async (email: string, name: string, password: string) => {
    const response = await client.post('/users', { email, name, password });
    return response.data;
};

export const claimDevice = async (deviceCode: string, userId: string) => {
    const response = await client.post('/devices/claim', { deviceCode, userId });
    return response.data;
};
