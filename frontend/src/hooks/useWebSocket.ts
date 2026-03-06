'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { getMockMode } from '@/components/DevModeToggle';
import { getWebSocketUrl } from '@/lib/apiRuntime';

export interface WSMessage {
  type: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

interface UseWebSocketOptions {
  onMessage?: (message: WSMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

const WS_URL = getWebSocketUrl();

export function useWebSocket(url: string = WS_URL, options: UseWebSocketOptions = {}) {
  const { 
    onMessage, 
    onConnect, 
    onDisconnect, 
    reconnectInterval = 3000, 
    reconnectAttempts = 5 
  } = options;
  
  // Use refs to avoid dependency issues
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  
  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);
  
  useEffect(() => {
    onConnectRef.current = onConnect;
  }, [onConnect]);
  
  useEffect(() => {
    onDisconnectRef.current = onDisconnect;
  }, [onDisconnect]);
  
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const mockIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);

  // Clear all timers
  const clearAllTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (mockIntervalRef.current) {
      clearInterval(mockIntervalRef.current);
      mockIntervalRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  // Disconnect function
  const disconnect = useCallback(() => {
    clearAllTimers();
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
    isConnectingRef.current = false;
  }, [clearAllTimers]);

  // Connect function - stable reference
  const connect = useCallback(() => {
    if (isConnectingRef.current) return;
    isConnectingRef.current = true;
    
    const isMockMode = getMockMode();
    clearAllTimers();
    
    if (isMockMode) {
      // Mock mode simulation
      setIsConnected(true);
      isConnectingRef.current = false;
      onConnectRef.current?.();
      
      // Send initial message
      const initialMsg: WSMessage = {
        type: 'connected',
        data: { message: 'Mock WebSocket connected' },
        timestamp: new Date().toISOString(),
      };
      setLastMessage(initialMsg);
      onMessageRef.current?.(initialMsg);
      
      // Simulate periodic status updates
      mockIntervalRef.current = setInterval(() => {
        const mockMsg: WSMessage = {
          type: 'status_update',
          data: {
            mode: 'BACKTEST',
            is_running: false,
            connected_markets_count: 5,
            timestamp: new Date().toISOString(),
          },
          timestamp: new Date().toISOString(),
        };
        setLastMessage(mockMsg);
        onMessageRef.current?.(mockMsg);
      }, 5000);
      
      return;
    }

    // Real WebSocket connection
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        isConnectingRef.current = false;
        reconnectCountRef.current = 0;
        onConnectRef.current?.();
        
        // Ping every 30s to keep alive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WSMessage;
          setLastMessage(message);
          onMessageRef.current?.(message);
        } catch (err) {
          console.error('WebSocket parse error:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        isConnectingRef.current = false;
        onDisconnectRef.current?.();
        clearAllTimers();
        
        // Attempt reconnection
        if (reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++;
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = () => {
        setIsConnected(false);
        isConnectingRef.current = false;
        ws.close();
      };
    } catch {
      // Retry on error
      setIsConnected(false);
      isConnectingRef.current = false;
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, reconnectInterval);
    }
  }, [url, reconnectInterval, reconnectAttempts, clearAllTimers]);

  // Main effect - only runs once on mount and when disconnect changes
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - only run once on mount

  const sendMessage = useCallback((message: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    disconnect,
  };
}
