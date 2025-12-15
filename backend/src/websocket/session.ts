import { WebSocket } from 'ws';

// Map deviceId -> Device WebSocket
export const deviceConnections = new Map<string, WebSocket>();

// Map deviceId -> Admin WebSocket (active shell session)
export const shellSessions = new Map<string, WebSocket>();
