import { useState, useEffect, useRef, useCallback } from 'react';
import type { DetectionEvent } from '../types';

// ── Types ──

export interface UseWebSocketReturn {
  status: 'connecting' | 'connected' | 'disconnected';
  lastEvent: DetectionEvent | null;
  events: DetectionEvent[];
}

// ── Constants ──

const MAX_EVENTS = 100;
const MAX_DELAY_MS = 30_000;

// ── Helpers ──

/**
 * Calculate exponential backoff delay for reconnection attempts.
 * Formula: min(2^attempt * 1000, 30000) milliseconds.
 */
export function getReconnectDelay(attempt: number): number {
  return Math.min(Math.pow(2, attempt) * 1000, MAX_DELAY_MS);
}

// ── Hook ──

export function useWebSocket(url: string): UseWebSocketReturn {
  const [status, setStatus] = useState<UseWebSocketReturn['status']>('connecting');
  const [lastEvent, setLastEvent] = useState<DetectionEvent | null>(null);
  const [events, setEvents] = useState<DetectionEvent[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    setStatus('connecting');

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) return;
      attemptRef.current = 0;
      setStatus('connected');
    };

    ws.onmessage = (event: MessageEvent) => {
      if (unmountedRef.current) return;
      try {
        const parsed = JSON.parse(event.data as string) as DetectionEvent;
        setLastEvent(parsed);
        setEvents((prev) => [parsed, ...prev].slice(0, MAX_EVENTS));
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setStatus('disconnected');
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect is handled there
      ws.close();
    };
  }, [url]);

  const scheduleReconnect = useCallback(() => {
    if (unmountedRef.current) return;
    const delay = getReconnectDelay(attemptRef.current);
    attemptRef.current += 1;
    timerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;

      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { status, lastEvent, events };
}
