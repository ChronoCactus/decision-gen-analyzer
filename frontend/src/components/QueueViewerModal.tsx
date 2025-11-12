'use client';

import { useEffect, useState } from 'react';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { apiClient } from '@/lib/api';
import { useTaskQueueWebSocket } from '@/hooks/useTaskQueueWebSocket';

interface QueueTask {
  task_id: string;
  task_name: string;
  status: string;  // Changed from union type to string to match API
  position: number | null;
  args: unknown[];
  kwargs: Record<string, unknown>;
  worker: string | null;
  started_at: number | null;
  eta: string | null;
}

interface QueueViewerModalProps {
  onClose: () => void;
  totalTasks: number;
  activeTasks: number;
  pendingTasks: number;
  workersOnline: number;
}

export function QueueViewerModal({
  onClose,
  totalTasks,
  activeTasks,
  pendingTasks,
  workersOnline,
}: QueueViewerModalProps) {
  const [tasks, setTasks] = useState<QueueTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Use WebSocket for real-time updates
  const { trackedTasks } = useTaskQueueWebSocket();

  useEscapeKey(onClose);

  // Initial fetch and periodic refresh (as backup to WebSocket)
  useEffect(() => {
    let isInitialLoad = true;
    
    const fetchTasks = async () => {
      try {
        // Only show loading spinner on initial load
        if (isInitialLoad) {
          setLoading(true);
        }
        const data = await apiClient.getQueueTasks();
        setTasks(data.tasks || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (isInitialLoad) {
          setLoading(false);
          isInitialLoad = false;
        }
      }
    };

    fetchTasks();

    // Refresh every 30 seconds as backup (WebSocket + caching is primary update mechanism)
    const interval = setInterval(fetchTasks, 30000);
    return () => clearInterval(interval);
  }, []);

  // Update tasks from WebSocket tracked tasks
  useEffect(() => {
    if (trackedTasks.size > 0) {
      // Merge WebSocket tracked tasks with fetched tasks
      const wsTasksArray = Array.from(trackedTasks.values()).map(task => ({
        task_id: task.task_id,
        task_name: task.task_name,
        status: task.status,
        position: task.position,
        args: [],
        kwargs: {},
        worker: null,
        started_at: null,
        eta: null,
      }));
      
      // If we have WebSocket data, prefer it
      if (wsTasksArray.length > 0) {
        setTasks(wsTasksArray);
      }
    }
  }, [trackedTasks]);


  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300';
      case 'pending':
      case 'scheduled':
        return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300';
      case 'completed':
        return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300';
      case 'failed':
        return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300';
      default:
        return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300';
    }
  };

  const getTaskDisplayName = (taskName: string) => {
    if (taskName.includes('generate_adr')) return 'Generate ADR';
    if (taskName.includes('analyze_adr')) return 'Analyze ADR';
    if (taskName.includes('monitor_upload')) return 'Monitor Upload';
    return taskName;
  };

  const formatElapsedTime = (startedAt: number | null) => {
    if (!startedAt) return null;
    const elapsed = Math.floor(Date.now() / 1000 - startedAt);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Task Queue</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                View all tasks currently in the queue
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl leading-none"
              aria-label="Close"
            >
              ×
            </button>
          </div>

          {/* Queue Stats */}
          <div className="grid grid-cols-4 gap-4 mt-4">
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-sm text-gray-500 dark:text-gray-400">Total Tasks</div>
              <div className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{totalTasks}</div>
            </div>
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <div className="text-sm text-blue-600 dark:text-blue-400">Active</div>
              <div className="text-2xl font-semibold text-blue-900 dark:text-blue-300">{activeTasks}</div>
            </div>
            <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
              <div className="text-sm text-yellow-600 dark:text-yellow-400">Pending</div>
              <div className="text-2xl font-semibold text-yellow-900 dark:text-yellow-300">{pendingTasks}</div>
            </div>
            <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
              <div className="text-sm text-green-600 dark:text-green-400">Workers</div>
              <div className="text-2xl font-semibold text-green-900 dark:text-green-300">{workersOnline}</div>
            </div>
          </div>
        </div>

        {/* Tasks List */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">Loading tasks...</div>
          ) : error ? (
            <div className="text-center py-8 text-red-600 dark:text-red-400">
              Error: {error}
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              No tasks in queue
            </div>
          ) : (
            <div className="space-y-3">
              {tasks.map((task) => (
                <div
                  key={task.task_id}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800/50"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-gray-100">
                          {getTaskDisplayName(task.task_name)}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(task.status)}`}>
                          {task.status}
                        </span>
                        {task.position !== null && (
                          <span className="text-sm text-gray-500 dark:text-gray-400">
                            Position: {task.position + 1}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">
                        {task.task_id}
                      </div>
                    </div>
                    {task.started_at && (
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        {formatElapsedTime(task.started_at)}
                      </div>
                    )}
                  </div>

                  {/* Task Details */}
                  <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                    {task.worker && (
                      <div>
                        <span className="font-medium">Worker:</span> {task.worker}
                      </div>
                    )}
                    {task.eta && (
                      <div>
                        <span className="font-medium">ETA:</span> {task.eta}
                      </div>
                    )}
                    {task.kwargs && Object.keys(task.kwargs).length > 0 && (
                      <div className="mt-2">
                        <div className="font-medium mb-1">Parameters:</div>
                        <div className="bg-gray-50 dark:bg-gray-900/50 rounded p-2 text-xs font-mono overflow-x-auto">
                          {Object.entries(task.kwargs).map(([key, value]) => (
                            <div key={key}>
                              <span className="text-blue-600 dark:text-blue-400">{key}:</span>{' '}
                              {typeof value === 'string' && value.length > 50
                                ? `${String(value).substring(0, 50)}...`
                                : JSON.stringify(value)}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
              <span className="inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              Real-time updates via WebSocket
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
