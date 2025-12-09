'use client';

import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
import { ADR, AnalyzeADRRequest, GenerateADRRequest, TaskResponse } from '@/types/api';
import { apiClient } from '@/lib/api';
import { ADRCard } from '@/components/ADRCard';
import { GenerateADRModal } from '@/components/GenerateADRModal';
import { ImportExportModal } from '@/components/ImportExportModal';
import { QueueViewerModal } from '@/components/QueueViewerModal';
import { SettingsModal } from '@/components/SettingsModal';
import { Toast } from '@/components/Toast';
import { useCacheStatusWebSocket } from '@/hooks/useCacheStatusWebSocket';
import { useTaskQueueWebSocket } from '@/hooks/useTaskQueueWebSocket';
import { useGlobalUploadStatus } from '@/hooks/useUploadStatus';
import { useInterfaceSettings } from '@/hooks/useInterfaceSettings';

export default function Home() {
  const [adrs, setAdrs] = useState<ADR[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showImportExportModal, setShowImportExportModal] = useState(false);
  const [showQueueViewer, setShowQueueViewer] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [tasks, setTasks] = useState<Record<string, { status: string; message: string; startTime?: number }>>({});
  const [generationStartTime, setGenerationStartTime] = useState<number | undefined>(undefined);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Interface settings
  const { settings: interfaceSettings, updateSettings: updateInterfaceSettings } = useInterfaceSettings();
  const processedTaskIds = useRef<Set<string>>(new Set());
  
  // Multi-select state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedADRs, setSelectedADRs] = useState<Set<string>>(new Set());

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastType, setToastType] = useState<'info' | 'success' | 'warning' | 'error'>('success');

  // Track newly imported ADRs for pulsing outline effect
  const [newlyImportedADRs, setNewlyImportedADRs] = useState<Set<string>>(new Set());

  // Record type selection state
  const [selectedRecordType, setSelectedRecordType] = useState<'decision' | 'principle'>('decision');
  const [showGenerateDropdown, setShowGenerateDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Use WebSocket for real-time cache status updates
  const { isRebuilding: cacheRebuilding, lastSyncTime, isConnected: wsConnected } = useCacheStatusWebSocket();

  // Use WebSocket for real-time queue status updates
  const { queueStatus } = useTaskQueueWebSocket();

  useEffect(() => {
    loadADRs();
  }, []);

  // Load selected record type from localStorage
  useEffect(() => {
    const savedType = localStorage.getItem('selectedRecordType');
    if (savedType === 'decision' || savedType === 'principle') {
      setSelectedRecordType(savedType);
    }
  }, []);

  // Auto-dismiss completed tasks based on settings
  useEffect(() => {
    if (!interfaceSettings.autoDismissToasts) return;

    Object.entries(tasks).forEach(([taskId, task]) => {
      if ((task.status === 'completed' || task.status === 'failed' || task.status === 'revoked') && !processedTaskIds.current.has(taskId)) {
        processedTaskIds.current.add(taskId);
        setTimeout(() => {
          setTasks(prev => {
            const newTasks = { ...prev };
            delete newTasks[taskId];
            return newTasks;
          });
          processedTaskIds.current.delete(taskId);
        }, interfaceSettings.toastDismissTimeout * 1000);
      }
    });
  }, [tasks, interfaceSettings]);

  // Update current time every second for timer display
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Global listener for upload_status messages from WebSocket (for refinements, uploads, etc.)
  useGlobalUploadStatus((adrId, info) => {
    if (info.status === 'completed') {
      setToastMessage(info.message || 'Operation completed successfully');
      setToastType('success');
      setShowToast(true);

      // Reload ADRs to get the updated version
      loadADRs();
    } else if (info.status === 'failed') {
      setToastMessage(info.message || 'Operation failed');
      setToastType('error');
      setShowToast(true);
    }
  });

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
      // WebSocket upload status provides real-time feedback for new uploads with track_id
      // For already-existing documents, the ADRCard will re-check status after this completes
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
      throw err; // Re-throw so ADRCard knows it failed
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

  const handleRefineQueued = (taskId: string) => {
    const startTime = Date.now();
    setIsGenerating(true);
    setGenerationStartTime(startTime);

    setTasks(prev => ({
      ...prev,
      [taskId]: {
        status: 'queued',
        message: 'Refining persona perspectives...',
        startTime: startTime
      }
    }));

    // Start polling for task status
    pollTaskStatus(taskId, 'refinement');
  };

  const pollTaskStatus = async (taskId: string, type: 'analysis' | 'generation' | 'refinement') => {
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
          // Reload ADRs when generation or refinement completes
          if (type === 'generation' || type === 'refinement') {
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
          if (type === 'generation' || type === 'refinement') {
            setIsGenerating(false);
            setGenerationStartTime(undefined);
          }

          // Stop polling
          return;
        }

        if (status.status === 'revoked') {
          // Task was cancelled - clear generation state
          if (type === 'generation' || type === 'refinement') {
            setIsGenerating(false);
            setGenerationStartTime(undefined);
          }

          // Stop polling
          return;
        }        // Continue polling
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

  // Save selected record type to localStorage
  const handleRecordTypeChange = (type: 'decision' | 'principle') => {
    setSelectedRecordType(type);
    localStorage.setItem('selectedRecordType', type);
    setShowGenerateDropdown(false);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowGenerateDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

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

  const handleLongPress = (adrId: string) => {
    if (!selectionMode) {
      setSelectionMode(true);
      setSelectedADRs(new Set([adrId]));
    } else {
      toggleADRSelection(adrId);
    }
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

  const handleImportSuccess = (importedCount: number, importedIds: string[]) => {
    // Show success toast
    setToastMessage(`Successfully imported ${importedCount} record${importedCount !== 1 ? 's' : ''}.`);
    setToastType('success');
    setShowToast(true);
    
    // Track newly imported ADRs for pulsing outline
    setNewlyImportedADRs(new Set(importedIds));
    
    // Clear the pulsing outline after 10 seconds
    setTimeout(() => {
      setNewlyImportedADRs(new Set());
    }, 10000);
  };

  const handleExportSuccess = () => {
    // Show success toast
    setToastMessage('Export completed successfully.');
    setToastType('success');
    setShowToast(true);
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
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4 relative">
          <div className="w-full md:w-auto flex justify-between items-center">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-gray-100">Decision Generator & Analyzer</h1>
              <p className="text-sm md:text-base text-gray-600 dark:text-gray-400 mt-1 md:mt-2">AI-powered ADR generation and analysis</p>
            </div>

            {/* Mobile Menu Toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md"
            >
              {mobileMenuOpen ? (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              )}
            </button>
          </div>

          {/* Desktop Actions */}
          <div className="hidden md:flex gap-3 items-center">
            {!selectionMode && (
              <>
                <button
                  onClick={() => setShowSettings(true)}
                  className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-3 py-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 font-medium text-sm transition-colors"
                  title="Settings"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>
                <Link
                  href="/personas"
                  className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-3 py-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 font-medium text-sm transition-colors flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                  </svg>
                  Personas
                </Link>
                <button
                  onClick={() => setShowImportExportModal(true)}
                  className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 font-medium text-sm whitespace-nowrap"
                >
                  Import/Export
                </button>
                <button
                  onClick={() => setShowQueueViewer(true)}
                  className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 font-medium text-sm relative whitespace-nowrap"
                >
                  View Queue
                  {queueStatus.total_tasks > 0 && (
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                      {queueStatus.total_tasks}
                    </span>
                  )}
                </button>
                <button
                  onClick={toggleSelectionMode}
                  className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 font-medium text-sm whitespace-nowrap"
                  disabled={adrs.length === 0}
                >
                  Select Mode
                </button>
                <div className="relative inline-flex rounded-md shadow-sm" ref={dropdownRef}>
                  <button
                    type="button"
                    onClick={() => setShowGenerateModal(true)}
                    className="relative inline-flex items-center bg-blue-600 text-white px-4 py-2 rounded-l-md hover:bg-blue-700 font-semibold animate-pulse-border whitespace-nowrap border-r border-blue-700"
                  >
                    Generate {selectedRecordType === 'decision' ? 'ADR' : 'Principle'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowGenerateDropdown(!showGenerateDropdown)}
                    className="relative inline-flex items-center bg-blue-600 text-white px-2 py-2 rounded-r-md hover:bg-blue-700 focus:z-10"
                  >
                    <span className="sr-only">Open options</span>
                    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                    </svg>
                  </button>
                  {showGenerateDropdown && (
                    <div className="absolute right-0 top-full mt-1 w-48 origin-top-right rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-20">
                      <div className="py-1">
                        <button
                          onClick={() => handleRecordTypeChange('decision')}
                          className={`block w-full px-4 py-2 text-left text-sm ${selectedRecordType === 'decision' ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                        >
                          Generate ADR
                        </button>
                        <button
                          onClick={() => handleRecordTypeChange('principle')}
                          className={`block w-full px-4 py-2 text-left text-sm ${selectedRecordType === 'principle' ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                        >
                          Generate Principle
                        </button>
                      </div>
                    </div>
                  )}
                </div>
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

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden flex flex-col gap-3 mb-6 bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700">
            {!selectionMode && (
              <>
                <button
                  onClick={() => { setShowGenerateModal(true); setMobileMenuOpen(false); }}
                  className="bg-blue-600 text-white px-4 py-3 rounded-md hover:bg-blue-700 font-semibold text-center"
                >
                  Generate New {selectedRecordType === 'decision' ? 'ADR' : 'Principle'}
                </button>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => { setShowImportExportModal(true); setMobileMenuOpen(false); }}
                    className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 font-medium text-sm text-center"
                  >
                    Import/Export
                  </button>
                  <button
                    onClick={() => { setShowQueueViewer(true); setMobileMenuOpen(false); }}
                    className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 font-medium text-sm relative text-center"
                  >
                    View Queue
                    {queueStatus.total_tasks > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                        {queueStatus.total_tasks}
                      </span>
                    )}
                  </button>
                </div>
                <button
                  onClick={() => { toggleSelectionMode(); setMobileMenuOpen(false); }}
                  className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 font-medium text-sm text-center"
                  disabled={adrs.length === 0}
                >
                  Select Mode
                </button>
                <Link
                  href="/personas"
                  onClick={() => setMobileMenuOpen(false)}
                  className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-4 py-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 font-medium text-sm text-center flex items-center justify-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                  </svg>
                  Personas
                </Link>
                <button
                  onClick={() => { setShowSettings(true); setMobileMenuOpen(false); }}
                  className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-4 py-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 font-medium text-sm text-center flex items-center justify-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Settings
                </button>
              </>
            )}
            {selectionMode && (
              <>
                <button
                  onClick={() => { toggleSelectionMode(); setMobileMenuOpen(false); }}
                  className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 font-medium text-sm text-center"
                >
                  Exit Select Mode
                </button>
              </>
            )}
          </div>
        )}

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
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full md:w-auto">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                  {selectedADRs.size} of {adrs.length} selected
                </span>
                <div className="flex gap-2 w-full sm:w-auto">
                  <button
                    onClick={selectAllADRs}
                    className="flex-1 sm:flex-none text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700 transition-colors text-center"
                  >
                    Select All
                  </button>
                  <button
                    onClick={unselectAllADRs}
                    className="flex-1 sm:flex-none text-sm bg-gray-600 text-white px-3 py-1.5 rounded-md hover:bg-gray-700 transition-colors text-center"
                    disabled={selectedADRs.size === 0}
                  >
                    Unselect All
                  </button>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
                <button
                  onClick={handleBulkExport}
                  disabled={selectedADRs.size === 0}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  Export
                </button>
                <button
                  onClick={handleBulkDelete}
                  disabled={selectedADRs.size === 0}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                  Delete
                </button>
                <button
                  onClick={toggleSelectionMode}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 px-4 py-2 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors text-sm font-medium"
                >
                  Exit
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Task Status Notifications - Active/Pending (Inline) */}
        {Object.values(tasks).filter(t => t.status !== 'completed' && t.status !== 'failed' && t.status !== 'revoked').length > 0 && (
          <div className="mb-6 space-y-2">
            {Object.entries(tasks)
              .filter(([, t]) => t.status !== 'completed' && t.status !== 'failed' && t.status !== 'revoked')
              .map(([taskId, task]) => {
                const elapsedSeconds = task.startTime
                  ? Math.floor((currentTime - task.startTime) / 1000)
                  : 0;
                const showTimer = task.startTime && (task.status === 'queued' || task.status === 'progress');

                return (
                  <div
                    key={taskId}
                    className="p-4 rounded-md bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 flex-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
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
                    </div>
                  </div>
                );
              })}
          </div>
        )}

        {/* Task Status Notifications - Completed/Failed (Floating Stack) */}
        {Object.values(tasks).filter(t => t.status === 'completed' || t.status === 'failed' || t.status === 'revoked').length > 0 && (
          <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm pointer-events-none">
            {Object.entries(tasks)
              .filter(([, t]) => t.status === 'completed' || t.status === 'failed' || t.status === 'revoked')
              .map(([taskId, task]) => (
                <div
                  key={taskId}
                  className={`p-4 rounded-lg shadow-lg pointer-events-auto flex items-center justify-between gap-4 animate-slide-up ${task.status === 'completed'
                    ? 'bg-green-600 text-white'
                    : task.status === 'failed'
                      ? 'bg-red-600 text-white'
                      : 'bg-orange-600 text-white'
                    }`}
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-sm font-medium">
                      {task.status === 'failed' && '❌ '}
                      {task.status === 'revoked' && '🚫 '}
                      {task.message}
                    </span>
                  </div>
                  <button
                    onClick={() => setTasks(prev => {
                      const newTasks = { ...prev };
                      delete newTasks[taskId];
                      return newTasks;
                    })}
                    className="text-white/80 hover:text-white transition-colors"
                    aria-label="Close"
                  >
                    ✕
                  </button>
                </div>
              ))}
          </div>
        )}

        {/* ADR Grid */}
        {adrs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400 text-lg mb-4">No records found</p>
            <button
              onClick={() => setShowGenerateModal(true)}
              className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-medium"
            >
              Create Your First {selectedRecordType === 'decision' ? 'ADR' : 'Principle'}
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
                onLongPress={handleLongPress}
                isNewlyImported={newlyImportedADRs.has(adr.metadata.id)}
                onRefineQueued={handleRefineQueued}
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
            initialRecordType={selectedRecordType}
            interfaceSettings={interfaceSettings}
          />
        )}        {/* Import/Export Modal */}
        {showImportExportModal && (
          <ImportExportModal
            onClose={() => setShowImportExportModal(false)}
            onImport={handleImport}
            onExportAll={handleExportAll}
            onImportSuccess={handleImportSuccess}
            onExportSuccess={handleExportSuccess}
          />
        )}

        {/* Queue Viewer Modal */}
        {showQueueViewer && (
          <QueueViewerModal
            onClose={() => setShowQueueViewer(false)}
            totalTasks={queueStatus.total_tasks}
            activeTasks={queueStatus.active_tasks}
            pendingTasks={queueStatus.pending_tasks}
            workersOnline={queueStatus.workers_online}
          />
        )}

        {/* Settings Modal */}
        {showSettings && (
          <SettingsModal
            onClose={() => setShowSettings(false)}
            interfaceSettings={interfaceSettings}
            onUpdateInterfaceSettings={updateInterfaceSettings}
          />
        )}

        {/* Toast Notification */}
        {showToast && (
          <Toast
            message={toastMessage}
            type={toastType}
            onClose={() => setShowToast(false)}
            position="top"
          />
        )}
      </div>
    </div>
  );
}
