import { useEffect, useState, useRef } from 'react';
import { apiClient } from '@/lib/api';

interface QueueStatus {
  total_tasks: number;
  active_tasks: number;
  pending_tasks: number;
  workers_online: number;
}

interface TaskStatus {
  task_id: string;
  task_name: string;
  status: 'queued' | 'active' | 'completed' | 'failed';
  position: number | null;
  message?: string;
}

interface QueueStatusMessage {
  type: 'queue_status';
  total_tasks: number;
  active_tasks: number;
  pending_tasks: number;
  workers_online: number;
}

interface TaskStatusMessage {
  type: 'task_status';
  task_id: string;
  task_name: string;
  status: 'queued' | 'active' | 'completed' | 'failed';
  position: number | null;
  message?: string;
}

type QueueWebSocketMessage = QueueStatusMessage | TaskStatusMessage;

/**
 * Hook to manage WebSocket connection for real-time queue and task status updates.
 * 
 * This hook:
 * - Connects to the existing WebSocket endpoint (same as cache status)
 * - Receives queue_status messages (overall queue metrics)
 * - Receives task_status messages (individual task updates)
 * - Automatically reconnects on disconnection (with exponential backoff)
 * - Provides current queue status and task tracking
 * - Falls back to REST API on initial load if WebSocket is not yet connected
 * 
 * @returns Object with queue status, task tracking, and connection state
 */
export function useTaskQueueWebSocket() {
  const [queueStatus, setQueueStatus] = useState<QueueStatus>({
    total_tasks: 0,
    active_tasks: 0,
    pending_tasks: 0,
    workers_online: 0,
  });
  const [trackedTasks, setTrackedTasks] = useState<Map<string, TaskStatus>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);
  const initialFetchDoneRef = useRef(false);

  // Fetch initial queue status via REST API as fallback (optional, non-blocking)
  useEffect(() => {
    if (!initialFetchDoneRef.current) {
      // Don't await - let it happen in background
      apiClient.getQueueStatus()
        .then((data) => {
          if (isMountedRef.current) {
            setQueueStatus(data);
            initialFetchDoneRef.current = true;
          }
        })
        .catch((error: unknown) => {
          // Silently fail - WebSocket will provide updates anyway
          console.debug('Initial queue status fetch failed (non-critical):', error);
        });
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    const connect = () => {
      if (!isMountedRef.current) return;

      // Use the same pattern as useCacheStatusWebSocket for LAN discovery
      // For LAN: frontend on :3000, backend on :8000
      // For production with LB: frontend and backend on same host (no port in URL)
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname;
      const frontendPort = window.location.port;

      let wsUrl: string;
      // If accessed with a custom port (e.g., :3000), assume LAN mode with backend on :8000
      // If accessed without port or with standard port (80/443), assume production mode
      if (frontendPort && frontendPort !== '80' && frontendPort !== '443') {
        // LAN mode: backend on port 8000
        wsUrl = `${protocol}//${host}:8000/api/v1/adrs/ws/cache-status`;
      } else {
        // Production mode: backend on same host (load balancer handles routing)
        wsUrl = `${protocol}//${host}/api/v1/adrs/ws/cache-status`;
      }

      console.log('Connecting to WebSocket for queue updates:', wsUrl);

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('✅ WebSocket connected for queue updates');
          setIsConnected(true);
          reconnectAttemptsRef.current = 0;

          // Start ping interval to keep connection alive
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send('ping');
            }
          }, 30000); // Ping every 30 seconds
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as QueueWebSocketMessage;
            
            if (message.type === 'queue_status') {
              setQueueStatus({
                total_tasks: message.total_tasks,
                active_tasks: message.active_tasks,
                pending_tasks: message.pending_tasks,
                workers_online: message.workers_online,
              });
            } else if (message.type === 'task_status') {
              setTrackedTasks((prev) => {
                const newMap = new Map(prev);
                newMap.set(message.task_id, {
                  task_id: message.task_id,
                  task_name: message.task_name,
                  status: message.status,
                  position: message.position,
                  message: message.message,
                });
                
                // Clean up completed/failed tasks after 30 seconds
                if (message.status === 'completed' || message.status === 'failed') {
                  setTimeout(() => {
                    setTrackedTasks((current) => {
                      const updated = new Map(current);
                      updated.delete(message.task_id);
                      return updated;
                    });
                  }, 30000);
                }
                
                return newMap;
              });
            }
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
          console.log('WebSocket closed');
          setIsConnected(false);
          
          // Clear ping interval
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
          }

          // Attempt to reconnect with exponential backoff
          if (isMountedRef.current) {
            const backoffDelay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            console.log(`Reconnecting in ${backoffDelay}ms...`);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current += 1;
              connect();
            }, backoffDelay);
          }
        };
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
      }
    };

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
      }
    };
  }, []);

  /**
   * Get the status of a specific task
   */
  const getTaskStatus = (taskId: string): TaskStatus | undefined => {
    return trackedTasks.get(taskId);
  };

  /**
   * Track a new task (useful when creating a task)
   */
  const trackTask = (taskId: string, taskName: string) => {
    setTrackedTasks((prev) => {
      const newMap = new Map(prev);
      newMap.set(taskId, {
        task_id: taskId,
        task_name: taskName,
        status: 'queued',
        position: null,
      });
      return newMap;
    });
  };

  return {
    queueStatus,
    trackedTasks,
    isConnected,
    getTaskStatus,
    trackTask,
  };
}
