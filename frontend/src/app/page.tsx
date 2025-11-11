'use client';

import { useState, useEffect, useRef } from 'react';
import { ADR, AnalyzeADRRequest, GenerateADRRequest, TaskResponse } from '@/types/api';
import { apiClient } from '@/lib/api';
import { ADRCard } from '@/components/ADRCard';
import { GenerateADRModal } from '@/components/GenerateADRModal';
import { ImportExportModal } from '@/components/ImportExportModal';
import { useCacheStatusWebSocket } from '@/hooks/useCacheStatusWebSocket';

export default function Home() {
  const [adrs, setAdrs] = useState<ADR[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showImportExportModal, setShowImportExportModal] = useState(false);
  const [tasks, setTasks] = useState<Record<string, { status: string; message: string; startTime?: number }>>({});
  const [generationStartTime, setGenerationStartTime] = useState<number | undefined>(undefined);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  
  // Multi-select state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedADRs, setSelectedADRs] = useState<Set<string>>(new Set());

  // Use WebSocket for real-time cache status updates
  const { isRebuilding: cacheRebuilding, lastSyncTime, isConnected: wsConnected } = useCacheStatusWebSocket();

  useEffect(() => {
    loadADRs();
  }, []);

  // Update current time every second for timer display
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const loadADRs = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getADRs();
      setAdrs(response.adrs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load ADRs');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeADR = async (adrId: string) => {
    try {
      const request: AnalyzeADRRequest = { adr_id: adrId };
      const response: TaskResponse = await apiClient.analyzeADR(request);

      setTasks(prev => ({
        ...prev,
        [response.task_id]: { status: 'queued', message: response.message }
      }));

      // Start polling for task status
      pollTaskStatus(response.task_id, 'analysis');
    } catch (err) {
      console.error('Failed to queue analysis:', err);
      alert('Failed to queue ADR analysis');
    }
  };

  const handleDeleteADR = async (adrId: string) => {
    try {
      await apiClient.deleteADR(adrId);
      // Reload ADRs after deletion
      await loadADRs();
    } catch (err) {
      console.error('Failed to delete ADR:', err);
      throw err; // Re-throw to be handled by the card component
    }
  };

  const handlePushToRAG = async (adrId: string) => {
    try {
      await apiClient.pushADRToRAG(adrId);
      // WebSocket upload status provides real-time feedback
    } catch (err) {
      console.error('Failed to push ADR to RAG:', err);

      // Check if it's a 503 error (cache rebuilding)
      if ((err as any).status === 503) {
        alert('Cache is currently rebuilding. Please try again in a moment.');
      } else if (err instanceof Error) {
        alert(`Failed to push ADR to RAG: ${err.message}`);
      } else {
        alert('Failed to push ADR to RAG');
      }
    }
  };

  const handleExportSingle = async (adrId: string) => {
    try {
      const blob = await apiClient.exportSingleADR(adrId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `adr_${adrId}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Failed to export ADR:', err);
      alert('Failed to export ADR');
    }
  };

  const handleExportAll = async () => {
    try {
      const blob = await apiClient.exportAllADRs();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `adrs_export_${adrs.length}_records.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Failed to export all ADRs:', err);
      alert('Failed to export all ADRs');
    }
  };

  const handleImport = async (files: File[], overwrite: boolean) => {
    try {
      const result = await apiClient.importADRsFromFiles(files, overwrite);

      // Reload ADRs after successful import
      if (result.imported_count > 0) {
        await loadADRs();
      }

      return result;
    } catch (err) {
      console.error('Failed to import ADRs:', err);
      throw err;
    }
  };

  const handleGenerateADR = async (request: GenerateADRRequest) => {
    try {
      const startTime = Date.now();
      setIsGenerating(true);
      setGenerationStartTime(startTime);

      const response: TaskResponse = await apiClient.generateADR(request);

      setTasks(prev => ({
        ...prev,
        [response.task_id]: { 
          status: 'queued', 
          message: response.message,
          startTime: startTime
        }
      }));

      setShowGenerateModal(false);

      // Start polling for task status
      pollTaskStatus(response.task_id, 'generation');
    } catch (err) {
      console.error('Failed to queue generation:', err);
      alert('Failed to queue ADR generation');
      setIsGenerating(false);
      setGenerationStartTime(undefined);
    }
  };

  const pollTaskStatus = async (taskId: string, type: 'analysis' | 'generation') => {
    const poll = async () => {
      try {
        const status = type === 'analysis'
          ? await apiClient.getAnalysisTaskStatus(taskId)
          : await apiClient.getGenerationTaskStatus(taskId);

        setTasks(prev => ({
          ...prev,
          [taskId]: {
            status: status.status,
            message: status.message || status.error || 'Processing...',
            startTime: prev[taskId]?.startTime // Preserve the start time
          }
        }));

        if (status.status === 'completed') {
          // Reload ADRs when generation completes
          if (type === 'generation') {
            await loadADRs();
            setIsGenerating(false);
            setGenerationStartTime(undefined);

            // Refresh ADR list
            await loadADRs();
          }
          // Stop polling
          return;
        }

        if (status.status === 'failed') {
          // Clear generation state on failure
          if (type === 'generation') {
            setIsGenerating(false);
            setGenerationStartTime(undefined);
          }
          // Stop polling
          return;
        }

        // Continue polling
        setTimeout(poll, 2000);
      } catch (err) {
        console.error('Failed to poll task status:', err);
        setTasks(prev => ({
          ...prev,
          [taskId]: { 
            status: 'failed', 
            message: 'Failed to check status',
            startTime: prev[taskId]?.startTime
          }
        }));
        if (type === 'generation') {
          setIsGenerating(false);
          setGenerationStartTime(undefined);
        }
      }
    };

    poll();
  };

  const formatTimeAgo = (timestamp: number | null): string => {
    if (!timestamp) return 'Never';
    
    const secondsAgo = Math.floor((currentTime - timestamp) / 1000);
    
    if (secondsAgo < 60) return `~${secondsAgo}s ago`;
    const minutesAgo = Math.floor(secondsAgo / 60);
    if (minutesAgo < 60) return `~${minutesAgo}min ago`;
    const hoursAgo = Math.floor(minutesAgo / 60);
    if (hoursAgo < 24) return `~${hoursAgo}h ago`;
    const daysAgo = Math.floor(hoursAgo / 24);
    return `~${daysAgo}d ago`;
  };

  const formatTimestamp = (timestamp: number | null): string => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleString();
  };

  // Multi-select handlers
  const toggleSelectionMode = () => {
    setSelectionMode(!selectionMode);
    setSelectedADRs(new Set()); // Clear selection when toggling mode
  };

  const toggleADRSelection = (adrId: string) => {
    setSelectedADRs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(adrId)) {
        newSet.delete(adrId);
      } else {
        newSet.add(adrId);
      }
      return newSet;
    });
  };

  const selectAllADRs = () => {
    setSelectedADRs(new Set(adrs.map(adr => adr.metadata.id)));
  };

  const unselectAllADRs = () => {
    setSelectedADRs(new Set());
  };

  const handleBulkDelete = async () => {
    if (selectedADRs.size === 0) return;
    
    const confirmMessage = `Are you sure you want to delete ${selectedADRs.size} ADR${selectedADRs.size > 1 ? 's' : ''}?`;
    if (!window.confirm(confirmMessage)) return;

    try {
      // Delete all selected ADRs
      await Promise.all(
        Array.from(selectedADRs).map(adrId => apiClient.deleteADR(adrId))
      );
      
      // Reload ADRs and clear selection
      await loadADRs();
      setSelectedADRs(new Set());
      setSelectionMode(false);
    } catch (err) {
      console.error('Failed to delete ADRs:', err);
      alert('Failed to delete some ADRs');
    }
  };

  const handleBulkExport = async () => {
    if (selectedADRs.size === 0) return;

    try {
      // Fetch all selected ADRs data
      const selectedADRsData = adrs.filter(adr => selectedADRs.has(adr.metadata.id));
      
      // Transform ADRs to match the backend's ADRExportV1 format (flattened structure)
      const transformedADRs = selectedADRsData.map(adr => ({
        // Metadata fields (flattened)
        id: adr.metadata.id,
        title: adr.metadata.title,
        status: adr.metadata.status,
        created_at: adr.metadata.created_at,
        updated_at: adr.metadata.updated_at,
        author: adr.metadata.author,
        tags: adr.metadata.tags,
        related_adrs: adr.metadata.related_adrs || [],
        custom_fields: adr.metadata.custom_fields || {},
        
        // Content fields (flattened)
        context_and_problem: adr.content.context_and_problem,
        decision_drivers: adr.content.decision_drivers || null,
        considered_options: adr.content.considered_options || [],
        decision_outcome: adr.content.decision_outcome,
        consequences: adr.content.consequences,
        confirmation: null, // Not in frontend type but required by backend
        pros_and_cons: adr.content.pros_and_cons || null,
        more_information: adr.content.more_information || null,
        
        // Extended fields
        options_details: adr.content.options_details || null,
        consequences_structured: adr.content.consequences_structured || null,
        referenced_adrs: adr.content.referenced_adrs || null,
        persona_responses: adr.persona_responses || null,
      }));
      
      // Create export data with correct versioned schema (matching BulkADRExport)
      const exportData = {
        schema: {
          schema_version: "1.0.0",
          exported_at: new Date().toISOString(),
          exported_by: null,
          total_records: selectedADRsData.length
        },
        adrs: transformedADRs
      };

      // Create and download file
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `adrs_export_${selectedADRsData.length}_selected.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      // Clear selection after export
      setSelectedADRs(new Set());
      setSelectionMode(false);
    } catch (err) {
      console.error('Failed to export ADRs:', err);
      alert('Failed to export ADRs');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading ADRs...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">Error: {error}</p>
          <button
            onClick={loadADRs}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Decision Generator & Analyzer</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-2">AI-powered ADR generation and analysis</p>
          </div>
          <div className="flex gap-3">
            {!selectionMode && (
              <>
                <button
                  onClick={() => setShowImportExportModal(true)}
                  className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 font-medium text-sm"
                >
                  Import/Export
                </button>
                <button
                  onClick={toggleSelectionMode}
                  className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 font-medium text-sm"
                  disabled={adrs.length === 0}
                >
                  Select Mode
                </button>
                <button
                  onClick={() => setShowGenerateModal(true)}
                  className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-semibold animate-pulse-border"
                >
                  Generate New ADR
                </button>
              </>
            )}
            {selectionMode && (
              <>
                <button
                  onClick={toggleSelectionMode}
                  className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 font-medium text-sm"
                >
                  Exit Select Mode
                </button>
              </>
            )}
          </div>
        </div>

        {/* RAG Cache Status */}
        <div className="mb-4 flex justify-end items-center gap-4">
          <div className="text-sm text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 px-4 py-2 rounded-md border border-gray-200 dark:border-gray-700 shadow-sm">
            <span className="font-medium">RAG Cache: </span>
            {cacheRebuilding ? (
              <span className="text-blue-600 dark:text-blue-400 font-semibold">Rebuilding...</span>
            ) : (
              <>
                  <span className="text-gray-800 dark:text-gray-200" title={formatTimestamp(lastSyncTime)}>
                  {formatTimestamp(lastSyncTime)}
                </span>
                  <span className="text-gray-500 dark:text-gray-500 ml-2">
                  ({formatTimeAgo(lastSyncTime)})
                </span>
              </>
            )}
          </div>
          <div className={`text-xs px-2 py-1 rounded-full ${wsConnected ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'}`}>
            {wsConnected ? '● Connected' : '○ Disconnected'}
          </div>
        </div>

        {/* Bulk Actions Bar - shown in selection mode */}
        {selectionMode && (
          <div className="mb-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {selectedADRs.size} of {adrs.length} selected
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={selectAllADRs}
                    className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700 transition-colors"
                  >
                    Select All
                  </button>
                  <button
                    onClick={unselectAllADRs}
                    className="text-sm bg-gray-600 text-white px-3 py-1.5 rounded-md hover:bg-gray-700 transition-colors"
                    disabled={selectedADRs.size === 0}
                  >
                    Unselect All
                  </button>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleBulkExport}
                  disabled={selectedADRs.size === 0}
                  className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  Export Selected
                </button>
                <button
                  onClick={handleBulkDelete}
                  disabled={selectedADRs.size === 0}
                  className="flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                  Delete Selected
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Task Status Notifications */}
        {Object.entries(tasks).length > 0 && (
          <div className="mb-6 space-y-2">
            {Object.entries(tasks).map(([taskId, task]) => {
              const elapsedSeconds = task.startTime 
                ? Math.floor((currentTime - task.startTime) / 1000)
                : 0;
              const showTimer = task.startTime && (task.status === 'queued' || task.status === 'progress');

              return (
                <div
                  key={taskId}
                  className={`p-4 rounded-md ${
                    task.status === 'completed'
                    ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                      : task.status === 'failed'
                      ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                      : 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                  }`}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 flex-1">
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {task.status === 'completed' && '✅ '}
                        {task.status === 'failed' && '❌ '}
                        {task.status === 'queued' && '⏳ '}
                        {task.status === 'progress' && '🔄 '}
                        {task.message}
                      </span>
                      {showTimer && (
                        <span className="text-sm font-semibold text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/40 px-2.5 py-1 rounded-md whitespace-nowrap">
                          {elapsedSeconds}s
                        </span>
                      )}
                    </div>
                    {task.status === 'completed' || task.status === 'failed' ? (
                      <button
                        onClick={() => setTasks(prev => {
                          const newTasks = { ...prev };
                          delete newTasks[taskId];
                          return newTasks;
                        })}
                        className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 text-sm flex-shrink-0"
                      >
                        ✕
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ADR Grid */}
        {adrs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400 text-lg mb-4">No ADRs found</p>
            <button
              onClick={() => setShowGenerateModal(true)}
              className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-medium"
            >
              Create Your First ADR
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {adrs.map((adr) => (
              <ADRCard
                key={adr.metadata.id}
                adr={adr}
                onAnalyze={handleAnalyzeADR}
                onDelete={handleDeleteADR}
                onPushToRAG={handlePushToRAG}
                onExport={handleExportSingle}
                cacheRebuilding={cacheRebuilding}
                selectionMode={selectionMode}
                isSelected={selectedADRs.has(adr.metadata.id)}
                onToggleSelection={toggleADRSelection}
              />
            ))}
          </div>
        )}

        {/* Generate ADR Modal */}
        {showGenerateModal && (
          <GenerateADRModal
            onClose={() => setShowGenerateModal(false)}
            onGenerate={handleGenerateADR}
            isGenerating={isGenerating}
            generationStartTime={generationStartTime}
          />
        )}

        {/* Import/Export Modal */}
        {showImportExportModal && (
          <ImportExportModal
            onClose={() => setShowImportExportModal(false)}
            onImport={handleImport}
            onExportAll={handleExportAll}
          />
        )}
      </div>
    </div>
  );
}
