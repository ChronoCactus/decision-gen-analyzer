import { useEffect, useState } from 'react';

export type UploadStatus = 'processing' | 'completed' | 'failed' | null;

interface UploadStatusInfo {
  status: UploadStatus;
  message?: string;
  timestamp?: number;
}

// Global event emitter for upload status updates from WebSocket
const uploadStatusListeners = new Map<string, Set<(status: UploadStatusInfo) => void>>();

export function emitUploadStatus(adrId: string, status: UploadStatusInfo) {
  const listeners = uploadStatusListeners.get(adrId);
  if (listeners) {
    listeners.forEach(listener => listener(status));
  }
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
