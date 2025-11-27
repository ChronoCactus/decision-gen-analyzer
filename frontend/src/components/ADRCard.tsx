'use client';

import { useState, useEffect } from 'react';
import { ADR } from '@/types/api';
import { ADRModal } from './ADRModal';
import { DeleteConfirmationModal } from './DeleteConfirmationModal';
import { Toast } from './Toast';
import { apiClient } from '@/lib/api';
import { useUploadStatus } from '@/hooks/useUploadStatus';

interface ADRCardProps {
  adr: ADR;
  onAnalyze: (adrId: string) => void;
  onDelete: (adrId: string) => Promise<void>;
  onPushToRAG: (adrId: string) => void;
  onExport: (adrId: string) => void;
  cacheRebuilding: boolean;
  selectionMode?: boolean;
  isSelected?: boolean;
  onToggleSelection?: (adrId: string) => void;
  isNewlyImported?: boolean;
  onRefineQueued?: (taskId: string) => void;
}

export function ADRCard({ adr, onAnalyze, onDelete, onPushToRAG, onExport, cacheRebuilding, selectionMode = false, isSelected = false, onToggleSelection, isNewlyImported = false, onRefineQueued }: ADRCardProps) {
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [existsInRAG, setExistsInRAG] = useState<boolean | null>(null);
  const [checkingRAGStatus, setCheckingRAGStatus] = useState(true);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastType, setToastType] = useState<'info' | 'success' | 'warning' | 'error'>('info');
  const [currentAdr, setCurrentAdr] = useState<ADR>(adr);

  // Track upload status via WebSocket
  const { uploadStatus, uploadMessage } = useUploadStatus(currentAdr.metadata.id);

  // Update currentAdr when prop changes
  useEffect(() => {
    setCurrentAdr(adr);
  }, [adr]);

  // Update RAG status when upload completes
  useEffect(() => {
    if (uploadStatus === 'completed') {
      setExistsInRAG(true);
    }
  }, [uploadStatus]);

  // Check if ADR exists in RAG on mount and when cache rebuild completes
  useEffect(() => {
    let mounted = true;

    const checkRAGStatus = async () => {
      try {
        const response = await apiClient.getADRRAGStatus(currentAdr.metadata.id);
        if (mounted) {
          setExistsInRAG(response.exists_in_rag);
          setCheckingRAGStatus(false);
        }
      } catch (error) {
        console.error('Failed to check RAG status:', error);
        if (mounted) {
          // If we can't check, assume it might not exist (show button)
          setExistsInRAG(false);
          setCheckingRAGStatus(false);
        }
      }
    };

    checkRAGStatus();

    return () => {
      mounted = false;
    };
  }, [currentAdr.metadata.id, cacheRebuilding]); // Re-check when cache rebuild status changes

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    try {
      await onAnalyze(currentAdr.metadata.id);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(currentAdr.metadata.id);
      setShowDeleteModal(false);
    } catch (error) {
      console.error('Failed to delete ADR:', error);
      alert('Failed to delete ADR');
    } finally {
      setIsDeleting(false);
    }
  };

  const handlePushToRAG = () => {
    // Check if cache is rebuilding
    if (cacheRebuilding) {
      setToastMessage('Cache is currently rebuilding. Please try again in a moment.');
      setToastType('warning');
      setShowToast(true);
      return;
    }

    onPushToRAG(currentAdr.metadata.id);
    // Don't optimistically update - wait for WebSocket to confirm upload status
    // The upload status hook will handle showing "Processing RAG..." state
  };

  const handleExport = () => {
    onExport(currentAdr.metadata.id);
  };

  const handleADRUpdate = (updatedAdr: ADR) => {
    setCurrentAdr(updatedAdr);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300';
      case 'proposed':
        return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300';
      case 'rejected':
        return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300';
      case 'deprecated':
        return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300';
      case 'superseded':
        return 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300';
      default:
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300';
    }
  };

  const handleCardClick = () => {
    if (selectionMode && onToggleSelection) {
      onToggleSelection(currentAdr.metadata.id);
    }
  };

  return (
    <>
      <div 
        className={`relative bg-white dark:bg-gray-800 rounded-lg shadow-md p-3 md:p-6 hover:shadow-lg transition-all border ${
          selectionMode 
            ? isSelected 
              ? 'border-blue-500 dark:border-blue-400 ring-2 ring-blue-500 dark:ring-blue-400 cursor-pointer' 
              : 'border-gray-300 dark:border-gray-600 cursor-pointer hover:border-blue-300 dark:hover:border-blue-600' 
            : isNewlyImported
              ? 'border-blue-500 dark:border-blue-400 animate-pulse-border'
              : 'border-transparent dark:border-gray-700'
        }`}
        onClick={handleCardClick}
      >
        {/* Selection checkbox - shown in selection mode */}
        {selectionMode && (
          <div className="absolute top-4 right-4 z-10" onClick={(e) => e.stopPropagation()}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggleSelection?.(currentAdr.metadata.id)}
              className="w-5 h-5 text-blue-600 bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 rounded focus:ring-blue-500 focus:ring-2 cursor-pointer"
            />
          </div>
        )}

        <div className="flex justify-between items-start mb-3 md:mb-4">
          <h3 className="text-base md:text-lg font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 pr-2">
            {currentAdr.metadata.title}
          </h3>
          {!selectionMode && (
            <span className={`flex-shrink-0 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(currentAdr.metadata.status)}`}>
              {currentAdr.metadata.status}
            </span>
          )}
        </div>

        <p className="text-gray-600 dark:text-gray-400 text-xs md:text-sm mb-3 md:mb-4 line-clamp-3">
          {currentAdr.content.context_and_problem}
        </p>

        <div className="flex flex-wrap gap-1 mb-4">
          {currentAdr.metadata.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs rounded-md"
            >
              {tag}
            </span>
          ))}
          {currentAdr.metadata.tags.length > 3 && (
            <span className="px-2 py-1 bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded-md">
              +{currentAdr.metadata.tags.length - 3} more
            </span>
          )}
        </div>

        <div className="flex justify-between items-center text-sm text-gray-500 dark:text-gray-400 mb-4">
          <span>By {currentAdr.metadata.author}</span>
          <span>{new Date(currentAdr.metadata.created_at).toLocaleDateString()}</span>
        </div>

        {/* Hide buttons in selection mode */}
        {!selectionMode && (
          <>
            <div className="flex gap-2">
              <button
                onClick={() => setShowModal(true)}
                className="flex-1 bg-blue-600 text-white px-2 md:px-4 py-2 rounded-md hover:bg-blue-700 transition-colors text-sm flex items-center justify-center gap-2"
                title="View Details"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className="hidden md:inline">View</span>
              </button>
              <button
                onClick={handleAnalyze}
                disabled={true}
                className="flex-1 bg-green-600 text-white px-2 md:px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm flex items-center justify-center gap-2"
                title="Analyze"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                </svg>
                <span className="hidden md:inline">{isAnalyzing ? 'Analyzing...' : 'Analyze'}</span>
              </button>
            </div>

            <div className="flex gap-2 mt-2">
              {/* Show upload status button if upload is in progress or recently completed */}
              {uploadStatus === 'processing' && (
                <button
                  disabled
                  className="flex-1 bg-blue-600 text-white px-2 md:px-4 py-2 rounded-md opacity-75 cursor-wait transition-colors text-sm flex items-center justify-center gap-2"
                  title="Processing in RAG..."
                  aria-label="Processing in RAG"
                >
                  <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="hidden md:inline">Processing...</span>
                </button>
              )}

              {uploadStatus === 'completed' && (
                <button
                  disabled
                  className="flex-1 bg-green-600 text-white px-2 md:px-4 py-2 rounded-md opacity-90 cursor-default transition-all text-sm flex items-center justify-center gap-2 animate-pulse"
                  title="Successfully uploaded to RAG"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="hidden md:inline">Uploaded</span>
                </button>
              )}

              {uploadStatus === 'failed' && (
                <button
                  onClick={handlePushToRAG}
                  className="flex-1 bg-red-600 text-white px-2 md:px-4 py-2 rounded-md hover:bg-red-700 transition-colors text-sm flex items-center justify-center gap-2"
                  title={uploadMessage || 'Upload failed - click to retry'}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                  </svg>
                  <span className="hidden md:inline">Retry</span>
                </button>
              )}

              {/* Only show Push to RAG button if:
                  1. Not checking status
                  2. No upload in progress
                  3. Doesn't exist in RAG
              */}
              {!checkingRAGStatus && !uploadStatus && !existsInRAG && (
                <button
                  onClick={handlePushToRAG}
                  disabled={cacheRebuilding}
                  className="flex-1 bg-purple-600 text-white px-2 md:px-4 py-2 rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm flex items-center justify-center gap-2"
                  title={cacheRebuilding ? 'Cache is rebuilding...' : 'Push to RAG'}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                  </svg>
                  <span className="hidden md:inline">{cacheRebuilding ? 'Rebuilding...' : 'Push to RAG'}</span>
                </button>
              )}

              <button
                onClick={handleExport}
                className="flex-1 bg-indigo-600 text-white px-2 md:px-4 py-2 rounded-md hover:bg-indigo-700 transition-colors text-sm flex items-center justify-center gap-2"
                title="Export"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                <span className="hidden md:inline">Export</span>
              </button>
              <button
                onClick={() => setShowDeleteModal(true)}
                className="flex-1 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 px-2 md:px-4 py-2 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm flex items-center justify-center"
                title="Delete ADR"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
              </button>
            </div>
          </>
        )}
      </div>

      {showModal && (
        <ADRModal
          adr={currentAdr}
          onClose={() => setShowModal(false)}
          onAnalyze={handleAnalyze}
          isAnalyzing={isAnalyzing}
          onADRUpdate={handleADRUpdate}
          onRefineQueued={onRefineQueued}
        />
      )}

      {showDeleteModal && (
        <DeleteConfirmationModal
          adrTitle={currentAdr.metadata.title}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteModal(false)}
          isDeleting={isDeleting}
        />
      )}

      {showToast && (
        <Toast
          message={toastMessage}
          type={toastType}
          onClose={() => setShowToast(false)}
        />
      )}
    </>
  );
}
