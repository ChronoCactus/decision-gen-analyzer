import { useEffect, useState, useRef } from 'react';
import { apiClient } from '@/lib/api';
import { emitUploadStatus } from './useUploadStatus';

interface CacheStatus {
  is_rebuilding: boolean;
  last_sync_time: number | null;
}

interface CacheStatusMessage {
  type: 'cache_status';
  is_rebuilding: boolean;
  last_sync_time: number | null;
}

interface UploadStatusMessage {
  type: 'upload_status';
  adr_id: string;
  status: 'processing' | 'completed' | 'failed';
  message?: string;
}

type WebSocketMessage = CacheStatusMessage | UploadStatusMessage;

/**
 * Hook to manage WebSocket connection for real-time cache status updates.
 * 
 * This hook:
 * - Establishes WebSocket connection to the backend
 * - Automatically reconnects on disconnection (with exponential backoff)
 * - Provides current cache status state
 * - Handles cleanup on unmount
 * - Falls back to REST API on initial load if WebSocket is not yet connected
 * 
 * @returns Object with cache status: { isRebuilding, lastSyncTime, isConnected }
 */
export function useCacheStatusWebSocket() {
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState<number | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);
  const initialFetchDoneRef = useRef(false);

  // Fetch initial cache status via REST API as fallback
  useEffect(() => {
    const fetchInitialStatus = async () => {
      if (initialFetchDoneRef.current) return;
      initialFetchDoneRef.current = true;

      try {
        const response = await apiClient.getCacheStatus();
        if (isMountedRef.current) {
          setIsRebuilding(response.is_rebuilding);
          setLastSyncTime(response.last_sync_time ? response.last_sync_time * 1000 : null);
        }
      } catch (error) {
        console.error('Failed to fetch initial cache status:', error);
      }
    };

    fetchInitialStatus();
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    
    const connect = () => {
      // Clean up existing connection if any
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      // Determine WebSocket URL - use same logic as API client
      // Backend always runs on port 8000, regardless of frontend port
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname;
      const port = '8000'; // Backend port is always 8000
      const wsUrl = `${protocol}//${host}:${port}/api/v1/adrs/ws/cache-status`;
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;

        setIsConnected(true);
        reconnectAttemptsRef.current = 0; // Reset reconnect attempts on successful connection

        // Send an immediate ping to confirm connection is working
        ws.send('ping');

        // Start sending ping messages every 30 seconds to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000); // 30 seconds
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          if (message.type === 'cache_status') {
            setIsRebuilding(message.is_rebuilding);
            setLastSyncTime(message.last_sync_time ? message.last_sync_time * 1000 : null); // Convert to milliseconds
          } else if (message.type === 'upload_status') {
            // Emit to upload status listeners
            emitUploadStatus(message.adr_id, {
              status: message.status,
              message: message.message,
              timestamp: Date.now(),
            });
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = (event) => {
        if (!isMountedRef.current) return;

        setIsConnected(false);
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Attempt to reconnect with exponential backoff
        reconnectAttemptsRef.current += 1;
        const backoffTime = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000); // Max 30 seconds

        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            connect();
          }
        }, backoffTime);
      };
    };

    // Initial connection
    connect();

    // Cleanup on unmount
    return () => {
      isMountedRef.current = false;
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []); // Empty dependency array - only run once on mount

  return {
    isRebuilding,
    lastSyncTime,
    isConnected
  };
}
