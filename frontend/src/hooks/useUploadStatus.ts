import { useEffect, useState } from 'react';

type UploadStatus = 'processing' | 'completed' | 'failed' | null;

interface UploadStatusInfo {
  status: UploadStatus;
  message?: string;
  timestamp?: number;
}

// Global event emitter for upload status updates from WebSocket
const uploadStatusListeners = new Map<string, Set<(status: UploadStatusInfo) => void>>();
const globalUploadStatusListeners = new Set<(adrId: string, status: UploadStatusInfo) => void>();

export function emitUploadStatus(adrId: string, status: UploadStatusInfo) {
  // Emit to specific ADR listeners
  const listeners = uploadStatusListeners.get(adrId);
  if (listeners) {
    listeners.forEach(listener => listener(status));
  }

  // Emit to global listeners
  globalUploadStatusListeners.forEach(listener => listener(adrId, status));
}

/**
 * Hook to track upload status for a specific ADR.
 * 
 * Listens to WebSocket upload_status messages and provides the current
 * upload status for the given ADR ID.
 * 
 * @param adrId - The ADR ID to track
 * @returns Upload status info: { status, message }
 */
export function useUploadStatus(adrId: string) {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>(null);
  const [uploadMessage, setUploadMessage] = useState<string | undefined>(undefined);

  useEffect(() => {
    const listener = (info: UploadStatusInfo) => {
      setUploadStatus(info.status);
      setUploadMessage(info.message);

      // Auto-clear after 5 seconds if completed
      if (info.status === 'completed') {
        setTimeout(() => {
          setUploadStatus(null);
          setUploadMessage(undefined);
        }, 5000);
      }
    };

    // Register listener
    if (!uploadStatusListeners.has(adrId)) {
      uploadStatusListeners.set(adrId, new Set());
    }
    uploadStatusListeners.get(adrId)!.add(listener);

    // Cleanup on unmount
    return () => {
      const listeners = uploadStatusListeners.get(adrId);
      if (listeners) {
        listeners.delete(listener);
        if (listeners.size === 0) {
          uploadStatusListeners.delete(adrId);
        }
      }
    };
  }, [adrId]);

  return {
    uploadStatus,
    uploadMessage,
  };
}

/**
 * Hook to listen to all upload status events globally.
 * 
 * Useful for showing toasts or notifications for any ADR operation.
 * 
 * @param callback - Called when any ADR status changes
 */
export function useGlobalUploadStatus(callback: (adrId: string, status: UploadStatusInfo) => void) {
  useEffect(() => {
    globalUploadStatusListeners.add(callback);

    return () => {
      globalUploadStatusListeners.delete(callback);
    };
  }, [callback]);
}
