'use client';

import { useState, useEffect } from 'react';
import { ADR, AnalyzeADRRequest, GenerateADRRequest, TaskResponse } from '@/types/api';
import { apiClient } from '@/lib/api';
import { ADRCard } from '@/components/ADRCard';
import { GenerateADRModal } from '@/components/GenerateADRModal';

export default function Home() {
  const [adrs, setAdrs] = useState<ADR[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [tasks, setTasks] = useState<Record<string, { status: string; message: string; startTime?: number }>>({});
  const [generationStartTime, setGenerationStartTime] = useState<number | undefined>(undefined);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());

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
      const result = await apiClient.pushADRToRAG(adrId);
      alert(`Success: ${result.message}`);
    } catch (err) {
      console.error('Failed to push ADR to RAG:', err);
      alert('Failed to push ADR to RAG');
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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Decision Analyzer</h1>
            <p className="text-gray-600 mt-2">AI-powered ADR analysis and generation</p>
          </div>
          <button
            onClick={() => setShowGenerateModal(true)}
            className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-medium"
          >
            Generate New ADR
          </button>
        </div>

        {/* Task Status Notifications */}
        {Object.entries(tasks).length > 0 && (
          <div className="mb-6 space-y-2">
            {Object.entries(tasks).map(([taskId, task]) => {
              const elapsedSeconds = task.startTime 
                ? Math.floor((currentTime - task.startTime) / 1000)
                : 0;
              const showTimer = task.startTime && (task.status === 'queued' || task.status === 'progress');
              
              // Debug logging
              if (task.status === 'progress') {
                console.log('Task progress:', {
                  taskId,
                  startTime: task.startTime,
                  currentTime,
                  elapsedSeconds,
                  showTimer,
                  message: task.message
                });
              }
              
              return (
                <div
                  key={taskId}
                  className={`p-4 rounded-md ${
                    task.status === 'completed'
                      ? 'bg-green-50 border border-green-200'
                      : task.status === 'failed'
                      ? 'bg-red-50 border border-red-200'
                      : 'bg-blue-50 border border-blue-200'
                  }`}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 flex-1">
                      <span className="text-sm font-medium">
                        {task.status === 'completed' && '✅ '}
                        {task.status === 'failed' && '❌ '}
                        {task.status === 'queued' && '⏳ '}
                        {task.status === 'progress' && '🔄 '}
                        {task.message}
                      </span>
                      {showTimer && (
                        <span className="text-sm font-semibold text-blue-700 bg-blue-100 px-2.5 py-1 rounded-md whitespace-nowrap">
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
                        className="text-gray-400 hover:text-gray-600 text-sm flex-shrink-0"
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
            <p className="text-gray-500 text-lg mb-4">No ADRs found</p>
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
      </div>
    </div>
  );
}
