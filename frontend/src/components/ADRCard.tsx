'use client';

import { useState, useEffect, useRef } from 'react';
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
  onPushToRAG: (adrId: string) => Promise<void>;
  onExport: (adrId: string) => void;
  cacheRebuilding: boolean;
  selectionMode?: boolean;
  isSelected?: boolean;
  onToggleSelection?: (adrId: string) => void;
  onLongPress?: (adrId: string) => void;
  isNewlyImported?: boolean;
  onRefineQueued?: (taskId: string) => void;
  ragStatus?: {
    exists_in_rag: boolean;
    lightrag_doc_id?: string;
    upload_status?: { status: string; message?: string; track_id?: string; timestamp?: number } | null;
  };
  draggable?: boolean;
  availableFolders?: string[];
  availableTags?: string[];
  onFolderChange?: (adrId: string, folder: string | null) => void;
  onTagAdd?: (adrId: string, tag: string) => void;
  onTagRemove?: (adrId: string, tag: string) => void;
}

export function ADRCard({ adr, onAnalyze, onDelete, onPushToRAG, onExport, cacheRebuilding, selectionMode = false, isSelected = false, onToggleSelection, onLongPress, isNewlyImported = false, onRefineQueued, ragStatus, draggable = false, availableFolders = [], availableTags = [], onFolderChange, onTagAdd, onTagRemove }: ADRCardProps) {
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
  const [initialUploadStatus, setInitialUploadStatus] = useState<'processing' | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showFolderDropdown, setShowFolderDropdown] = useState(false);
  const [showTagDropdown, setShowTagDropdown] = useState(false);
  const [newTagInput, setNewTagInput] = useState('');
  const folderDropdownRef = useRef<HTMLDivElement>(null);
  const tagDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (folderDropdownRef.current && !folderDropdownRef.current.contains(e.target as Node)) {
        setShowFolderDropdown(false);
      }
      if (tagDropdownRef.current && !tagDropdownRef.current.contains(e.target as Node)) {
        setShowTagDropdown(false);
        setNewTagInput('');
      }
    };

    if (showFolderDropdown || showTagDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showFolderDropdown, showTagDropdown]);

  // Track upload status via WebSocket
  const { uploadStatus: wsUploadStatus, uploadMessage } = useUploadStatus(currentAdr.metadata.id);

  // Use WebSocket status if available, otherwise fall back to initial status from cache
  const uploadStatus = wsUploadStatus || initialUploadStatus;

  // Update currentAdr when prop changes
  useEffect(() => {
    setCurrentAdr(adr);
  }, [adr]);

  // Update RAG status when upload completes or fails
  useEffect(() => {
    if (uploadStatus === 'completed') {
      setExistsInRAG(true);
      // Clear initial status since upload completed
      setInitialUploadStatus(null);
    } else if (uploadStatus === 'failed') {
      // Clear initial status on failure too
      setInitialUploadStatus(null);
    }
  }, [uploadStatus]);

  // Use batched RAG status from parent
  useEffect(() => {
    if (!ragStatus) {
      // Still loading batch status
      setCheckingRAGStatus(true);
      return;
    }

    // Check if there's an active upload being tracked
    const hasActiveUpload = ragStatus.upload_status &&
      ragStatus.upload_status.status === 'processing' &&
    // Ignore stale statuses older than 5 minutes (300 seconds)
      ragStatus.upload_status.timestamp &&
      (Date.now() / 1000 - ragStatus.upload_status.timestamp) < 300;

    if (hasActiveUpload) {
      // Set initial upload status so button shows "Processing..." instead of "Push to RAG"
      setInitialUploadStatus('processing');
      setCheckingRAGStatus(false);
      // Don't set existsInRAG yet - let the WebSocket/monitoring update handle it
    } else {
    // No active upload or stale status, set final status
      setExistsInRAG(ragStatus.exists_in_rag);
      setCheckingRAGStatus(false);
      setInitialUploadStatus(null);
    }
  }, [ragStatus, cacheRebuilding]); // Re-check when ragStatus or cache rebuild status changes

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

  const handlePushToRAG = async () => {
    // Check if cache is rebuilding
    if (cacheRebuilding) {
      setToastMessage('Cache is currently rebuilding. Please try again in a moment.');
      setToastType('warning');
      setShowToast(true);
      return;
    }

    try {
      await onPushToRAG(currentAdr.metadata.id);
      // Re-check RAG status after push completes
      // This handles the case where document already existed (no WebSocket update)
      const response = await apiClient.getADRRAGStatus(currentAdr.metadata.id);
      setExistsInRAG(response.exists_in_rag);
    } catch (error) {
      console.error('Failed to push to RAG or check status:', error);
      // Error handling is done in parent component
    }
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

  const [longPressTimer, setLongPressTimer] = useState<NodeJS.Timeout | null>(null);
  const [isLongPress, setIsLongPress] = useState(false);
  const [dragStartPos, setDragStartPos] = useState<{ x: number; y: number } | null>(null);
  const hasDraggedRef = useRef(false);

  const DRAG_THRESHOLD = 10; // pixels of movement to consider it a drag

  const handleStart = (e: React.MouseEvent | React.TouchEvent) => {
    setIsLongPress(false);
    hasDraggedRef.current = false;

    // Record start position for drag detection
    const pos = 'touches' in e
      ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
      : { x: e.clientX, y: e.clientY };
    setDragStartPos(pos);

    const timer = setTimeout(() => {
      // Only trigger long press if we haven't started dragging
      if (!hasDraggedRef.current) {
        setIsLongPress(true);
        if (onLongPress) {
          onLongPress(currentAdr.metadata.id);
        }
      }
    }, 500); // 500ms for long press
    setLongPressTimer(timer);
  };

  const handleMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!dragStartPos || hasDraggedRef.current) return;

    const pos = 'touches' in e
      ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
      : { x: e.clientX, y: e.clientY };

    const distance = Math.sqrt(
      Math.pow(pos.x - dragStartPos.x, 2) + Math.pow(pos.y - dragStartPos.y, 2)
    );

    // If moved beyond threshold, cancel long press and mark as dragging
    if (distance > DRAG_THRESHOLD) {
      hasDraggedRef.current = true;
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        setLongPressTimer(null);
      }
    }
  };

  const handleEnd = () => {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      setLongPressTimer(null);
    }
    setDragStartPos(null);
  };

  const handleCardClick = (e: React.MouseEvent) => {
    // Prevent click if it was a long press or if we dragged
    if (isLongPress || hasDraggedRef.current) {
      e.stopPropagation();
      setIsLongPress(false);
      hasDraggedRef.current = false;
      return;
    }

    if (selectionMode && onToggleSelection) {
      onToggleSelection(currentAdr.metadata.id);
    }
  };  // Drag handlers for folder organization
  const handleDragStart = (e: React.DragEvent) => {
    if (!draggable || selectionMode) return;
    // Mark as dragged immediately to prevent long press from firing
    hasDraggedRef.current = true;
    setIsDragging(true);
    e.dataTransfer.setData('text/adr-id', currentAdr.metadata.id);
    e.dataTransfer.effectAllowed = 'move';

    // Create a semi-transparent drag ghost using canvas
    try {
      const target = e.currentTarget as HTMLElement;
      const rect = target.getBoundingClientRect();

      // Create a canvas to render the semi-transparent version
      const canvas = document.createElement('canvas');
      const scale = window.devicePixelRatio || 1;
      canvas.width = rect.width * scale;
      canvas.height = rect.height * scale;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;

      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.scale(scale, scale);
        ctx.globalAlpha = 0.4; // 40% opacity

        // Draw a simple representation (we can't use html2canvas without the library)
        // So we'll create a styled div instead
        const dragPreview = target.cloneNode(true) as HTMLElement;
        dragPreview.style.opacity = '0.4';
        dragPreview.style.transform = 'none';
        dragPreview.style.position = 'fixed';
        dragPreview.style.left = '-9999px';
        dragPreview.style.top = '0';
        dragPreview.style.width = `${rect.width}px`;
        dragPreview.style.zIndex = '9999';
        document.body.appendChild(dragPreview);

        // Use the preview element as drag image
        e.dataTransfer.setDragImage(dragPreview, e.nativeEvent.offsetX, e.nativeEvent.offsetY);

        // Clean up after a frame
        requestAnimationFrame(() => {
          if (document.body.contains(dragPreview)) {
            document.body.removeChild(dragPreview);
          }
        });
      }
    } catch (error) {
      console.error('Failed to create drag image:', error);
    }
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  return (
    <>
      <div 
        className={`relative bg-white dark:bg-gray-800 rounded-lg shadow-md p-3 md:p-6 hover:shadow-lg transition-all border ${
          isDragging
            ? 'ring-2 ring-blue-500 dark:ring-blue-400'
            : selectionMode
              ? isSelected
                ? 'border-blue-500 dark:border-blue-400 ring-2 ring-blue-500 dark:ring-blue-400 cursor-pointer'
                : 'border-gray-300 dark:border-gray-600 cursor-pointer hover:border-blue-300 dark:hover:border-blue-600'
              : isNewlyImported
                ? 'border-blue-500 dark:border-blue-400 animate-pulse-border'
                : 'border-transparent dark:border-gray-700'
          } select-none ${draggable && !selectionMode ? 'cursor-grab active:cursor-grabbing' : ''}`}
        style={isDragging ? { opacity: 1 } : undefined}
        onClick={handleCardClick}
        onMouseDown={handleStart}
        onMouseMove={handleMove}
        onMouseUp={handleEnd}
        onMouseLeave={handleEnd}
        onTouchStart={handleStart}
        onTouchMove={handleMove}
        onTouchEnd={handleEnd}
        draggable={draggable && !selectionMode}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        {/* Folder indicator with dropdown */}
        {onFolderChange && !selectionMode ? (
          <div className="absolute -top-2 left-3 z-10" ref={folderDropdownRef}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowFolderDropdown(!showFolderDropdown);
                setShowTagDropdown(false);
              }}
              className="flex items-center gap-1 px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded-full text-xs text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              title="Change folder"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <span className="truncate max-w-[100px]">
                {currentAdr.metadata.folder_path
                  ? currentAdr.metadata.folder_path.split('/').filter(Boolean).pop()
                  : 'No folder'}
              </span>
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            {showFolderDropdown && (
              <div
                className="absolute left-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg border border-gray-200 dark:border-gray-700 z-20 max-h-48 overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => {
                    onFolderChange(currentAdr.metadata.id, null);
                    setShowFolderDropdown(false);
                  }}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-100 dark:hover:bg-gray-700 ${!currentAdr.metadata.folder_path
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                    : 'text-gray-700 dark:text-gray-300'
                    }`}
                >
                  <span className="italic">No folder (root)</span>
                </button>
                {availableFolders.map((folder) => (
                  <button
                    key={folder}
                    onClick={() => {
                      onFolderChange(currentAdr.metadata.id, folder);
                      setShowFolderDropdown(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-100 dark:hover:bg-gray-700 ${currentAdr.metadata.folder_path === folder
                      ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                      : 'text-gray-700 dark:text-gray-300'
                      }`}
                  >
                    {folder}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : currentAdr.metadata.folder_path && (
          <div className="absolute -top-2 left-3 flex items-center gap-1 px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded-full text-xs text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-600">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3">
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
            </svg>
            <span className="truncate max-w-[100px]" title={currentAdr.metadata.folder_path}>
              {currentAdr.metadata.folder_path.split('/').filter(Boolean).pop()}
            </span>
          </div>
        )}

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
            <div className="flex flex-col items-end gap-1">
              <span className={`flex-shrink-0 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(currentAdr.metadata.status)}`}>
                {currentAdr.metadata.status}
              </span>
              {currentAdr.metadata.record_type && (
                <span className={`flex-shrink-0 px-2 py-1 rounded-full text-xs font-medium ${currentAdr.metadata.record_type === 'principle'
                    ? 'bg-teal-100 dark:bg-teal-900/30 text-teal-800 dark:text-teal-300'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                  }`}>
                  {currentAdr.metadata.record_type}
                </span>
              )}
            </div>
          )}
        </div>

        <p className="text-gray-600 dark:text-gray-400 text-xs md:text-sm mb-3 md:mb-4 line-clamp-3">
          {currentAdr.content.context_and_problem}
        </p>

        <div className="flex flex-wrap gap-1 mb-4">
          {currentAdr.metadata.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs rounded-md flex items-center gap-1 group"
            >
              {tag}
              {onTagRemove && !selectionMode && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onTagRemove(currentAdr.metadata.id, tag);
                  }}
                  className="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"
                  title={`Remove tag "${tag}"`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </span>
          ))}
          {currentAdr.metadata.tags.length > 3 && (
            <span className="px-2 py-1 bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded-md">
              +{currentAdr.metadata.tags.length - 3} more
            </span>
          )}
          {/* Add tag button */}
          {onTagAdd && !selectionMode && (
            <div className="relative" ref={tagDropdownRef}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowTagDropdown(!showTagDropdown);
                  setShowFolderDropdown(false);
                }}
                className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center gap-1"
                title="Add tag"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                Tag
              </button>
              {showTagDropdown && (
                <div
                  className="absolute left-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg border border-gray-200 dark:border-gray-700 z-20"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="p-2 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex gap-1">
                      <input
                        type="text"
                        value={newTagInput}
                        onChange={(e) => setNewTagInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && newTagInput.trim()) {
                            onTagAdd(currentAdr.metadata.id, newTagInput.trim());
                            setNewTagInput('');
                            setShowTagDropdown(false);
                          }
                        }}
                        placeholder="New tag..."
                        className="flex-1 text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        autoFocus
                      />
                      <button
                        onClick={() => {
                          if (newTagInput.trim()) {
                            onTagAdd(currentAdr.metadata.id, newTagInput.trim());
                            setNewTagInput('');
                            setShowTagDropdown(false);
                          }
                        }}
                        className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                  {availableTags.filter(t => !currentAdr.metadata.tags.includes(t)).length > 0 && (
                    <div className="max-h-32 overflow-y-auto">
                      {availableTags
                        .filter(t => !currentAdr.metadata.tags.includes(t))
                        .slice(0, 10)
                        .map((tag) => (
                          <button
                            key={tag}
                            onClick={() => {
                              onTagAdd(currentAdr.metadata.id, tag);
                              setShowTagDropdown(false);
                            }}
                            className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                          >
                            {tag}
                          </button>
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
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
          availableFolders={availableFolders}
          availableTags={availableTags}
          onFolderChange={onFolderChange}
          onTagAdd={onTagAdd}
          onTagRemove={onTagRemove}
        />
      )}

      {showDeleteModal && (
        <DeleteConfirmationModal
          adrTitle={currentAdr.metadata.title}
          recordType={currentAdr.metadata.record_type}
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
