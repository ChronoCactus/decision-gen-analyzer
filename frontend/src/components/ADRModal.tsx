'use client';

import { useState, useRef, useEffect } from 'react';
import { ADR, ADRStatus, PersonaRefinementItem, Persona, LLMProvider } from '@/types/api';
import { PersonasModal } from './PersonasModal';
import { HoverCard } from './HoverCard';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { apiClient } from '@/lib/api';
import { Toast } from './Toast';
import { PersonaSelector } from './PersonaSelector';
import { SynthesisModelSelector } from './SynthesisModelSelector';

interface ADRModalProps {
  adr: ADR;
  onClose: () => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
  onADRUpdate?: (updatedAdr: ADR) => void;
  onRefineQueued?: (taskId: string) => void;
  availableFolders?: string[];
  availableTags?: string[];
  onFolderChange?: (adrId: string, folder: string | null) => void;
  onTagAdd?: (adrId: string, tag: string) => void;
  onTagRemove?: (adrId: string, tag: string) => void;
}

export function ADRModal({ adr, onClose, onAnalyze, isAnalyzing, onADRUpdate, onRefineQueued, availableFolders = [], availableTags = [], onFolderChange, onTagAdd, onTagRemove }: ADRModalProps) {
  const [showPersonas, setShowPersonas] = useState(false);
  const [currentAdr, setCurrentAdr] = useState<ADR>(adr);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [showBulkRefine, setShowBulkRefine] = useState(false);
  const [bulkRefinementPrompt, setBulkRefinementPrompt] = useState('');
  const [showOriginalPromptEdit, setShowOriginalPromptEdit] = useState(false);
  const [refinedContext, setRefinedContext] = useState('');
  const [refinedPrompt, setRefinedPrompt] = useState('');
  const [refinementToast, setRefinementToast] = useState<{ show: boolean; message: string; type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success'
  });
  const [mcpResultModal, setMcpResultModal] = useState<{ show: boolean; resultId: string; serverName: string; toolName: string; loading: boolean; data: any; error: string | null }>({
    show: false,
    resultId: '',
    serverName: '',
    toolName: '',
    loading: false,
    data: null,
    error: null
  });
  const [showFolderDropdown, setShowFolderDropdown] = useState(false);
  const [showTagDropdown, setShowTagDropdown] = useState(false);
  const [newTagInput, setNewTagInput] = useState('');

  // Manual editing state
  const [isManualEditMode, setIsManualEditMode] = useState(false);
  const [editedContentJson, setEditedContentJson] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [isSavingManualEdit, setIsSavingManualEdit] = useState(false);

  // Model selection state for bulk refinement
  const [allPersonas, setAllPersonas] = useState<Persona[]>([]);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');
  const [bulkSynthesisProviderId, setBulkSynthesisProviderId] = useState<string>('');
  const [loadingModels, setLoadingModels] = useState(true);
  const [bulkPersonaProviderOverrides, setBulkPersonaProviderOverrides] = useState<Record<string, string>>({});

  // Model selection state for original prompt refinement
  const [originalPromptPersonaProviderOverrides, setOriginalPromptPersonaProviderOverrides] = useState<Record<string, string>>({});
  const [originalPromptSynthesisProviderId, setOriginalPromptSynthesisProviderId] = useState<string>('');

  const bulkRefineRef = useRef<HTMLDivElement>(null);
  const originalPromptEditRef = useRef<HTMLDivElement>(null);
  const folderDropdownRef = useRef<HTMLDivElement>(null);
  const tagDropdownRef = useRef<HTMLDivElement>(null);

  const isPrinciple = currentAdr.metadata.record_type === 'principle';

  // Load personas and providers on mount
  useEffect(() => {
    Promise.all([
      apiClient.getPersonas(),
      apiClient.listProviders()
    ])
      .then(([personasResponse, providersResponse]) => {
        setAllPersonas(personasResponse.personas);
        setProviders(providersResponse.providers);

        // Set default provider
        const defaultProvider = providersResponse.providers.find(p => p.is_default);
        if (defaultProvider) {
          setSelectedProviderId(defaultProvider.id);
          setBulkSynthesisProviderId(defaultProvider.id);
        }
      })
      .catch(error => {
        console.error('Failed to load personas or providers:', error);
      })
      .finally(() => {
        setLoadingModels(false);
      });
  }, []);

  // Close this modal with ESC, but only if personas modal is not open
  useEscapeKey(onClose, !showPersonas && !showBulkRefine && !showOriginalPromptEdit && !mcpResultModal.show);

  // Scroll to bulk refinement section when it becomes visible
  useEffect(() => {
    if (showBulkRefine && bulkRefineRef.current) {
      bulkRefineRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [showBulkRefine]);

  // Scroll to original prompt edit section when it becomes visible
  useEffect(() => {
    if (showOriginalPromptEdit && originalPromptEditRef.current) {
      originalPromptEditRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [showOriginalPromptEdit]);

  // Click outside to close dropdowns
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (folderDropdownRef.current && !folderDropdownRef.current.contains(event.target as Node)) {
        setShowFolderDropdown(false);
      }
      if (tagDropdownRef.current && !tagDropdownRef.current.contains(event.target as Node)) {
        setShowTagDropdown(false);
        setNewTagInput('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleStatusChange = async (newStatus: string) => {
    if (newStatus === currentAdr.metadata.status) {
      return; // No change
    }

    setIsUpdatingStatus(true);
    try {
      const response = await apiClient.updateADRStatus(currentAdr.metadata.id, newStatus);
      const updatedAdr = response.adr;
      setCurrentAdr(updatedAdr);
      
      // Notify parent component of the update
      if (onADRUpdate) {
        onADRUpdate(updatedAdr);
      }
    } catch (error) {
      console.error('Failed to update ADR status:', error);
      alert('Failed to update ADR status. Please try again.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleViewMcpResult = async (resultId: string, serverName: string, toolName: string) => {
    setMcpResultModal({
      show: true,
      resultId,
      serverName,
      toolName,
      loading: true,
      data: null,
      error: null
    });

    try {
      const result = await apiClient.getMcpResult(resultId);
      setMcpResultModal(prev => ({
        ...prev,
        loading: false,
        data: result
      }));
    } catch (error) {
      console.error('Failed to fetch MCP result:', error);
      setMcpResultModal(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load tool result. It may have been deleted.'
      }));
    }
  };

  const closeMcpResultModal = () => {
    setMcpResultModal({
      show: false,
      resultId: '',
      serverName: '',
      toolName: '',
      loading: false,
      data: null,
      error: null
    });
  };

  const handleADRUpdate = async () => {
    try {
      const refreshedAdr = await apiClient.getADR(currentAdr.metadata.id);
      setCurrentAdr(refreshedAdr);

      // Notify parent component of the update
      if (onADRUpdate) {
        onADRUpdate(refreshedAdr);
      }
    } catch (error) {
      console.error('Failed to refresh ADR:', error);
    }
  };

  const handleRefinePersonas = async (
    refinements: PersonaRefinementItem[],
    refinementsToDelete?: Record<string, number[]>,
    personaProviderOverrides?: Record<string, string>,
    synthesisProviderId?: string
  ) => {
    try {
      const response = await apiClient.refinePersonas(currentAdr.metadata.id, {
        refinements,
        refinements_to_delete: refinementsToDelete,
        persona_provider_overrides: personaProviderOverrides,
        synthesis_provider_id: synthesisProviderId
      });

      // Close both modals so user can see progress
      setShowPersonas(false);
      onClose();

      // Notify parent to start polling for the refinement task
      if (onRefineQueued) {
        onRefineQueued(response.task_id);
      }

    } catch (error) {
      console.error('Failed to refine personas:', error);
      setRefinementToast({
        show: true,
        message: 'Failed to queue persona refinement. Please try again.',
        type: 'error'
      });

      // Auto-hide error toast after 5 seconds
      setTimeout(() => {
        setRefinementToast({ show: false, message: '', type: 'success' });
      }, 5000);
    }
  };

  const handleFolderChangeLocal = async (folderPath: string | null) => {
    if (onFolderChange) {
      try {
        await onFolderChange(currentAdr.metadata.id, folderPath);
        // Update local state
        setCurrentAdr(prev => ({
          ...prev,
          metadata: {
            ...prev.metadata,
            folder_path: folderPath
          }
        }));
        setShowFolderDropdown(false);
      } catch (error) {
        console.error('Failed to change folder:', error);
      }
    }
  };

  const handleTagAddLocal = async (tag: string) => {
    if (onTagAdd && !currentAdr.metadata.tags.includes(tag)) {
      try {
        await onTagAdd(currentAdr.metadata.id, tag);
        // Update local state
        setCurrentAdr(prev => ({
          ...prev,
          metadata: {
            ...prev.metadata,
            tags: [...prev.metadata.tags, tag]
          }
        }));
        setNewTagInput('');
        setShowTagDropdown(false);
      } catch (error) {
        console.error('Failed to add tag:', error);
      }
    }
  };

  const handleTagRemoveLocal = async (tag: string) => {
    if (onTagRemove) {
      try {
        await onTagRemove(currentAdr.metadata.id, tag);
        // Update local state
        setCurrentAdr(prev => ({
          ...prev,
          metadata: {
            ...prev.metadata,
            tags: prev.metadata.tags.filter(t => t !== tag)
          }
        }));
      } catch (error) {
        console.error('Failed to remove tag:', error);
      }
    }
  };

  // Manual editing handlers
  const handleEnterManualEdit = () => {
    setIsManualEditMode(true);
    setEditedContentJson(JSON.stringify(currentAdr.content, null, 2));
    setJsonError(null);
  };

  const handleCancelManualEdit = () => {
    setIsManualEditMode(false);
    setEditedContentJson('');
    setJsonError(null);
  };

  const validateAndSaveManualEdit = async () => {
    try {
      // Validate JSON
      const parsed = JSON.parse(editedContentJson);

      // Basic validation - must be an object
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        setJsonError('Content must be a valid JSON object');
        return;
      }

      // Validate required fields
      if (!parsed.context_and_problem || !parsed.decision_outcome || !parsed.consequences) {
        setJsonError('Missing required fields: context_and_problem, decision_outcome, or consequences');
        return;
      }

      setJsonError(null);
      setIsSavingManualEdit(true);

      // Call API to save manual edit (never triggers AI regeneration)
      const response = await apiClient.saveManualADREdit(
        currentAdr.metadata.id,
        parsed
      );

      // Update local state with the saved ADR
      setCurrentAdr(response.adr);

      // Notify parent component of the update
      if (onADRUpdate) {
        onADRUpdate(response.adr);
      }

      // Close manual edit mode and show success toast
      setIsManualEditMode(false);
      setEditedContentJson('');
      setRefinementToast({
        show: true,
        message: 'Manual edit saved successfully',
        type: 'success'
      });
    } catch (error) {
      if (error instanceof SyntaxError) {
        setJsonError(`Invalid JSON: ${error.message}`);
      } else {
        setJsonError(`Failed to save: ${error instanceof Error ? error.message : String(error)}`);
      }
    } finally {
      setIsSavingManualEdit(false);
    }
  };

  const handleBulkRefinement = async () => {
    if (!bulkRefinementPrompt.trim()) {
      return;
    }

    // Create refinement items for all personas with the same prompt
    const refinements: PersonaRefinementItem[] = currentAdr.persona_responses?.map(persona => ({
      persona: persona.persona,
      refinement_prompt: bulkRefinementPrompt
    })) || [];

    if (refinements.length === 0) {
      return;
    }

    // Reset bulk refine UI
    setShowBulkRefine(false);
    setBulkRefinementPrompt('');
    setBulkPersonaProviderOverrides({});

    // Use the same handler as individual refinements with model selections
    await handleRefinePersonas(
      refinements,
      undefined,
      bulkPersonaProviderOverrides,
      bulkSynthesisProviderId || undefined
    );
  };

  const getModelDisplay = (persona: Persona): string => {
    if (persona.llm_config) {
      const provider = persona.llm_config.provider || 'custom';
      const model = persona.llm_config.name;
      return `${provider}/${model}`;
    } else {
      // Use selected provider's model
      const provider = providers.find(p => p.id === selectedProviderId);
      if (provider) {
        return `${provider.provider_type}/${provider.model_name}`;
      }
      return 'default';
    }
  };

  const handleOriginalPromptRefinement = async () => {
    if (!refinedContext.trim() || !refinedPrompt.trim()) {
      return;
    }

    try {
      const response = await apiClient.refineOriginalPrompt(currentAdr.metadata.id, {
        context: refinedContext,
        problem_statement: refinedPrompt,
        persona_provider_overrides: originalPromptPersonaProviderOverrides,
        synthesis_provider_id: originalPromptSynthesisProviderId || undefined,
      });

      // Reset UI
      setShowOriginalPromptEdit(false);
      setRefinedContext('');
      setRefinedPrompt('');

      // Close modal so user can see progress
      onClose();

      // Notify parent to start polling for the refinement task
      if (onRefineQueued) {
        onRefineQueued(response.task_id);
      }

    } catch (error) {
      console.error('Failed to refine original prompt:', error);
      setRefinementToast({
        show: true,
        message: 'Failed to queue original prompt refinement. Please try again.',
        type: 'error'
      });

      // Auto-hide error toast after 5 seconds
      setTimeout(() => {
        setRefinementToast({ show: false, message: '', type: 'success' });
      }, 5000);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-200 dark:border-green-700';
      case 'proposed':
        return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-700';
      case 'rejected':
        return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-200 dark:border-red-700';
      case 'deprecated':
        return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-600';
      case 'superseded':
        return 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-700';
      default:
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-700';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center sm:p-4 z-50">
      <div className="bg-white dark:bg-gray-800 w-full h-full flex flex-col sm:h-auto sm:max-w-4xl sm:max-h-[90vh] sm:rounded-lg overflow-hidden">
        {/* Sticky Header */}
        <div className="relative flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4 sm:p-6">
          <div className="flex justify-between items-start mb-2">
            <div className="flex-1 hidden sm:block pr-12">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                {currentAdr.metadata.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              aria-label="Close"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
            <span>By {currentAdr.metadata.author}</span>
            <span>{new Date(currentAdr.metadata.created_at).toLocaleDateString()}</span>
            <div className="relative">
              <select
                value={currentAdr.metadata.status}
                onChange={(e) => handleStatusChange(e.target.value)}
                disabled={isUpdatingStatus}
                className={`px-3 py-1 rounded-full border cursor-pointer text-sm font-medium transition-colors ${getStatusColor(currentAdr.metadata.status)} ${isUpdatingStatus ? 'opacity-50 cursor-wait' : 'hover:opacity-80'
                  } focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800`}
              >
                <option value={ADRStatus.PROPOSED}>proposed</option>
                <option value={ADRStatus.ACCEPTED}>accepted</option>
                <option value={ADRStatus.REJECTED}>rejected</option>
                <option value={ADRStatus.DEPRECATED}>deprecated</option>
                <option value={ADRStatus.SUPERSEDED}>superseded</option>
              </select>
            </div>
            <button
              onClick={() => isManualEditMode ? handleCancelManualEdit() : handleEnterManualEdit()}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${isManualEditMode
                  ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                  : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-900/50'
                }`}
            >
              {isManualEditMode ? 'Cancel Edit' : 'Manual Edit (JSON)'}
            </button>
          </div>
          {/* Mobile Header Title (Minimal) */}
          <div className="flex-1 sm:hidden pr-12">
             <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">
              {currentAdr.metadata.title}
            </h2>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6 min-h-0">
          {/* Manual Edit Mode */}
          {isManualEditMode ? (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Edit ADR Content as JSON</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Edit the JSON below to manually modify the final synthesized ADR content. Changes are saved directly without AI regeneration.
              </p>

              <textarea
                value={editedContentJson}
                onChange={(e) => {
                  setEditedContentJson(e.target.value);
                  setJsonError(null);
                }}
                className="w-full h-96 px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500 dark:focus:ring-purple-400"
                spellCheck={false}
              />

              {jsonError && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-800 rounded-md">
                  <p className="text-sm text-red-700 dark:text-red-400">{jsonError}</p>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={validateAndSaveManualEdit}
                  disabled={isSavingManualEdit || !editedContentJson.trim()}
                  className="flex-1 bg-purple-600 text-white px-6 py-3 rounded-md hover:bg-purple-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  {isSavingManualEdit ? 'Saving...' : 'Save Manual Edit'}
                </button>
                <button
                  onClick={handleCancelManualEdit}
                  disabled={isSavingManualEdit}
                  className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors font-medium disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Mobile Title & Metadata (Scrolls with content) */}
              <div className="sm:hidden mb-6 space-y-4">
            <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
              <span>By {currentAdr.metadata.author}</span>
              <span>•</span>
              <span>{new Date(currentAdr.metadata.created_at).toLocaleDateString()}</span>
            </div>
            <div className="relative inline-block">
              <select
                value={currentAdr.metadata.status}
                onChange={(e) => handleStatusChange(e.target.value)}
                disabled={isUpdatingStatus}
                className={`px-3 py-1 rounded-full border cursor-pointer text-sm font-medium transition-colors ${getStatusColor(currentAdr.metadata.status)} ${isUpdatingStatus ? 'opacity-50 cursor-wait' : 'hover:opacity-80'
                  } focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800`}
              >
                <option value={ADRStatus.PROPOSED}>proposed</option>
                <option value={ADRStatus.ACCEPTED}>accepted</option>
                <option value={ADRStatus.REJECTED}>rejected</option>
                <option value={ADRStatus.DEPRECATED}>deprecated</option>
                <option value={ADRStatus.SUPERSEDED}>superseded</option>
              </select>
            </div>
          </div>

          <div className="space-y-6">
            {/* Context & Problem */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Context & Problem</h3>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{currentAdr.content.context_and_problem}</p>
            </div>

            {/* Decision Outcome */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                {isPrinciple ? 'Principle Statement' : 'Decision Outcome'}
              </h3>
              <div className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{currentAdr.content.decision_outcome}</div>
            </div>

            {/* Principle Details */}
            {currentAdr.content.principle_details && (
              <div className="space-y-6">
                {/* Rationale */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Rationale</h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {currentAdr.content.principle_details.rationale}
                  </p>
                </div>

                {/* Implications */}
                {currentAdr.content.principle_details.implications.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Implications</h3>
                    <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                      {currentAdr.content.principle_details.implications.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Proof Statements */}
                {currentAdr.content.principle_details.proof_statements.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Proof Statements</h3>
                    <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                      {currentAdr.content.principle_details.proof_statements.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Counter Arguments */}
                {currentAdr.content.principle_details.counter_arguments.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Counter Arguments</h3>
                    <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                      {currentAdr.content.principle_details.counter_arguments.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Exceptions */}
                {currentAdr.content.principle_details.exceptions.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Exceptions</h3>
                    <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                      {currentAdr.content.principle_details.exceptions.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Consequences - Structured or plain text */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Consequences</h3>
              {currentAdr.content.consequences_structured ? (
                <div className="space-y-3">
                  {currentAdr.content.consequences_structured.positive.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-green-800 dark:text-green-400 mb-2">✓ Positive</h4>
                      <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
                        {currentAdr.content.consequences_structured.positive.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {currentAdr.content.consequences_structured.negative.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-red-800 dark:text-red-400 mb-2">✗ Negative</h4>
                      <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
                        {currentAdr.content.consequences_structured.negative.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                  <div className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    {currentAdr.content.consequences.split('\n').map((line, index) => {
                      const trimmed = line.trim();
                      if (!trimmed) return null;

                      // Check if line starts with "✓ Positive" or "✗ Negative"
                      if (trimmed.startsWith('✓ Positive')) {
                        return <h4 key={index} className="text-md font-medium text-green-800 dark:text-green-400 mt-3 mb-2">{trimmed}</h4>;
                      }
                      if (trimmed.startsWith('✗ Negative')) {
                        return <h4 key={index} className="text-md font-medium text-red-800 dark:text-red-400 mt-3 mb-2">{trimmed}</h4>;
                      }

                      // Check if line starts with a bullet (- or •)
                      if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
                        const content = trimmed.substring(2).trim();
                        return (
                          <div key={index} className="flex items-start mb-1 ml-2">
                            <span className="text-gray-400 dark:text-gray-500 mr-2">•</span>
                            <span>{content}</span>
                          </div>
                        );
                      }

                      // Regular text line
                      return <p key={index} className="mb-1">{trimmed}</p>;
                    })}
                  </div>
              )}
            </div>

            {/* Considered Options */}
            {!currentAdr.content.principle_details && currentAdr.content.considered_options && currentAdr.content.considered_options.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Considered Options</h3>
                <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                  {currentAdr.content.considered_options.map((option, index) => (
                    <li key={index}>{option}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Options Details with Pros and Cons */}
            {!currentAdr.content.principle_details && currentAdr.content.options_details && currentAdr.content.options_details.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Pros & Cons of Options</h3>
                <div className="space-y-4">
                  {currentAdr.content.options_details.map((option, index) => (
                    <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50">
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">{option.name}</h4>
                      {option.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{option.description}</p>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {option.pros.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-green-700 dark:text-green-400 mb-1">Pros</div>
                            <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                              {option.pros.map((pro, idx) => (
                                <li key={idx} className="flex items-start">
                                  <span className="text-green-600 dark:text-green-400 mr-2">✓</span>
                                  <span>{pro}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {option.cons.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">Cons</div>
                            <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                              {option.cons.map((con, idx) => (
                                <li key={idx} className="flex items-start">
                                  <span className="text-red-600 dark:text-red-400 mr-2">✗</span>
                                  <span>{con}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Decision Drivers */}
            {currentAdr.content.decision_drivers && currentAdr.content.decision_drivers.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  {isPrinciple ? 'Principle Drivers' : 'Decision Drivers'}
                </h3>
                <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                  {currentAdr.content.decision_drivers.map((driver, index) => (
                    <li key={index}>{driver}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* More Information */}
            {currentAdr.content.more_information && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">More Information</h3>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{currentAdr.content.more_information}</p>
              </div>
            )}

            {/* References */}
            {currentAdr.content.referenced_adrs && currentAdr.content.referenced_adrs.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">References</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  This {isPrinciple ? 'principle' : 'ADR'} was generated with context from the following sources:
                </p>
                <ul className="space-y-2">
                  {currentAdr.content.referenced_adrs.map((ref, index) => {
                    // Handle MCP references differently
                    if (ref.type === 'mcp') {
                      return (
                        <li key={index} className="border-l-2 border-purple-400 dark:border-purple-600 pl-3 py-1">
                          <div className="text-sm text-gray-800 dark:text-gray-200 font-medium flex items-center gap-2">
                            <button
                              onClick={() => handleViewMcpResult(ref.id, ref.server_name || 'MCP', ref.title)}
                              className="px-2 py-0.5 rounded text-xs font-medium cursor-pointer transition-colors bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-800/50"
                              title="Click to view tool output"
                            >
                              MCP: {ref.server_name || 'Tool'}
                            </button>
                            <span>{ref.title}</span>
                          </div>
                          {ref.summary && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">{ref.summary}</div>
                          )}
                        </li>
                      );
                    }

                    // Check if title looks like a UUID (with or without hyphens/spaces)
                    const isUuidTitle = /^[0-9a-fA-F\-\s]{32,}$/.test(ref.title || '');

                    // If title is a UUID, try to extract real title from summary
                    let displayTitle = ref.title || ref.id;
                    let displaySummary = ref.summary;

                    if (isUuidTitle && ref.summary && ref.summary.startsWith('Title: ')) {
                      // Extract title from summary (e.g. "Title: My Title...")
                      // Remove "Title: " prefix
                      const cleanSummary = ref.summary.substring(7);
                      // Use the summary as the title since it contains the title
                      displayTitle = cleanSummary;
                      // Don't show summary separately if it's just the title
                      displaySummary = '';
                    }

                    return (
                      <li key={index} className="border-l-2 border-blue-300 dark:border-blue-700 pl-3 py-1">
                        <div className="text-sm text-gray-800 dark:text-gray-200 font-medium flex items-center gap-2">
                          <HoverCard
                            trigger={
                              <span className={`px-2 py-0.5 rounded text-xs font-medium cursor-help transition-colors ${ref.type === 'principle'
                                  ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300'
                                  : 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300'
                                }`}>
                                {ref.type === 'principle' ? 'Principle' : 'Decision'}
                              </span>
                            }
                          >
                            <div
                              className="bg-gray-900 text-white text-xs rounded py-1 px-2 shadow-lg whitespace-nowrap cursor-pointer hover:bg-gray-800 transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(ref.id);
                                // Visual feedback could be added here, but for now the action is performed
                              }}
                              title="Click to copy ID"
                            >
                              <div className="font-mono mb-1">ID: {ref.id}</div>
                              <div className="text-gray-400 text-[10px]">Click to copy</div>
                            </div>
                          </HoverCard>
                          <span>{displayTitle}</span>
                        </div>
                        {displaySummary && (
                          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">{displaySummary}</div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Folder */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Folder</h3>
              <div className="relative" ref={folderDropdownRef}>
                <button
                  onClick={() => setShowFolderDropdown(!showFolderDropdown)}
                  className="px-3 py-1.5 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-sm rounded-md hover:bg-green-100 dark:hover:bg-green-900/40 transition-colors flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  <span>{currentAdr.metadata.folder_path || '/'}</span>
                </button>

                {showFolderDropdown && (
                  <div className="absolute z-10 mt-1 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg max-h-60 overflow-y-auto">
                    <button
                      onClick={() => handleFolderChangeLocal(null)}
                      className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm text-gray-900 dark:text-gray-100"
                    >
                      / (root)
                    </button>
                    {availableFolders.map((folder) => (
                      <button
                        key={folder}
                        onClick={() => handleFolderChangeLocal(folder)}
                        className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm text-gray-900 dark:text-gray-100"
                      >
                        {folder}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Tags */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {currentAdr.metadata.tags.map((tag) => (
                  <div key={tag} className="group relative">
                    <span className="px-3 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-sm rounded-md flex items-center gap-1">
                      {tag}
                      {onTagRemove && (
                        <button
                          onClick={() => handleTagRemoveLocal(tag)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity ml-1 hover:text-red-600 dark:hover:text-red-400"
                          title="Remove tag"
                        >
                          ×
                        </button>
                      )}
                    </span>
                  </div>
                ))}

                {/* Add Tag Button */}
                {onTagAdd && (
                  <div className="relative" ref={tagDropdownRef}>
                    <button
                      onClick={() => setShowTagDropdown(!showTagDropdown)}
                      className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-sm rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      + Tag
                    </button>

                    {showTagDropdown && (
                      <div className="absolute z-10 mt-1 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg">
                        <div className="p-2 border-b border-gray-200 dark:border-gray-700">
                          <input
                            type="text"
                            value={newTagInput}
                            onChange={(e) => setNewTagInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && newTagInput.trim()) {
                                e.preventDefault();
                                handleTagAddLocal(newTagInput.trim());
                              }
                            }}
                            placeholder="New tag name..."
                            className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
                            autoFocus
                          />
                          <button
                            onClick={() => newTagInput.trim() && handleTagAddLocal(newTagInput.trim())}
                            disabled={!newTagInput.trim()}
                            className="w-full mt-1 px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed"
                          >
                            Create Tag
                          </button>
                        </div>

                        {availableTags.length > 0 && (
                          <div className="max-h-48 overflow-y-auto">
                            <div className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">Existing tags:</div>
                            {availableTags
                              .filter(tag => !currentAdr.metadata.tags.includes(tag))
                              .map((tag) => (
                                <button
                                  key={tag}
                                  onClick={() => handleTagAddLocal(tag)}
                                  className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm text-gray-900 dark:text-gray-100"
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
            </div>
          </div>

          {/* Bulk Refinement Section */}
          {showBulkRefine && currentAdr.persona_responses && currentAdr.persona_responses.length > 0 && (
            <div ref={bulkRefineRef} className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Refine All Personas</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                This refinement prompt will be applied to all {currentAdr.persona_responses.length} personas to regenerate their perspectives and create a new ADR.
              </p>

              {/* Show personas being refined with model info */}
              {!loadingModels && allPersonas.length > 0 && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Personas to Refine
                  </label>
                  <PersonaSelector
                    personas={allPersonas.filter(p =>
                      currentAdr.persona_responses?.some(pr => pr.persona === p.value)
                    )}
                    selectedPersonas={currentAdr.persona_responses?.map(pr => pr.persona) || []}
                    onTogglePersona={() => { }}
                    getModelDisplay={getModelDisplay}
                    readOnly={false}
                    compact={true}
                    providers={providers}
                    personaProviderOverrides={bulkPersonaProviderOverrides}
                    onPersonaProviderChange={(personaValue, providerId) => {
                      setBulkPersonaProviderOverrides(prev => ({
                        ...prev,
                        [personaValue]: providerId
                      }));
                    }}
                    allowModelSelection={true}
                  />
                </div>
              )}

              {/* Synthesis Model Selection */}
              {!loadingModels && providers.length > 0 && (
                <div className="mb-4">
                  <SynthesisModelSelector
                    providers={providers}
                    selectedProviderId={bulkSynthesisProviderId}
                    onSelectProvider={setBulkSynthesisProviderId}
                    label="Synthesis Model"
                    helpText="Model used to synthesize all refined perspectives into the final decision record"
                  />
                </div>
              )}

              <textarea
                value={bulkRefinementPrompt}
                onChange={(e) => setBulkRefinementPrompt(e.target.value)}
                placeholder="Enter refinement instructions to apply to all personas..."
                className="w-full px-4 py-3 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                rows={4}
              />
              <div className="flex gap-3 mt-3">
                <button
                  onClick={handleBulkRefinement}
                  disabled={!bulkRefinementPrompt.trim()}
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  Submit Bulk Refinement
                </button>
                <button
                  onClick={() => {
                    setShowBulkRefine(false);
                    setBulkRefinementPrompt('');
                  }}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Original Prompt Refinement Section */}
          {currentAdr.content.original_generation_prompt && (
            <div className="mt-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Original Request</h3>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
                View and refine the original prompt that was used to generate this {isPrinciple ? 'principle' : 'ADR'}. Refining the context will regenerate all personas with the updated prompt.
              </p>

              {!showOriginalPromptEdit ? (
                <div className="space-y-2">
                  <div className="text-sm">
                    <span className="font-medium text-gray-700 dark:text-gray-300">Prompt: </span>
                    <span className="text-gray-600 dark:text-gray-400">{currentAdr.content.original_generation_prompt.problem_statement}</span>
                  </div>
                  <div className="text-sm">
                    <span className="font-medium text-gray-700 dark:text-gray-300">Context: </span>
                    <span className="text-gray-600 dark:text-gray-400">{currentAdr.content.original_generation_prompt.context}</span>
                  </div>
                  {currentAdr.content.original_generation_prompt.constraints && currentAdr.content.original_generation_prompt.constraints.length > 0 && (
                    <div className="text-sm">
                      <span className="font-medium text-gray-700 dark:text-gray-300">Constraints: </span>
                      <span className="text-gray-600 dark:text-gray-400">{currentAdr.content.original_generation_prompt.constraints.join(', ')}</span>
                    </div>
                  )}
                  <button
                    onClick={() => {
                      setShowOriginalPromptEdit(true);
                      setRefinedContext(currentAdr.content.original_generation_prompt?.context || '');
                      setRefinedPrompt(currentAdr.content.original_generation_prompt?.problem_statement || '');
                    }}
                    className="mt-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors font-medium"
                  >
                    Edit Original Request
                  </button>
                </div>
              ) : (
                <div ref={originalPromptEditRef} className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Prompt</label>
                    <textarea
                      value={refinedPrompt}
                      onChange={(e) => setRefinedPrompt(e.target.value)}
                        className="w-full px-3 py-3 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500 dark:focus:ring-green-400"
                      rows={3}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Context</label>
                    <textarea
                      value={refinedContext}
                      onChange={(e) => setRefinedContext(e.target.value)}
                        className="w-full px-3 py-3 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-green-500 dark:focus:ring-green-400"
                      rows={3}
                    />
                  </div>

                    {/* Personas to Regenerate */}
                    {!loadingModels && allPersonas.length > 0 && (
                      <div className="mt-4">
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Personas to Regenerate</h4>
                        <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
                          This refinement prompt will be applied to all {currentAdr.persona_responses?.length || 0} personas to regenerate their perspectives and create a new {isPrinciple ? 'principle' : 'ADR'}.
                        </p>
                        <PersonaSelector
                          personas={allPersonas.filter(p =>
                            currentAdr.persona_responses?.some(pr => pr.persona === p.value)
                          )}
                          selectedPersonas={currentAdr.persona_responses?.map(pr => pr.persona) || []}
                          onTogglePersona={() => { }}
                          getModelDisplay={getModelDisplay}
                          readOnly={false}
                          compact={true}
                          providers={providers}
                          personaProviderOverrides={originalPromptPersonaProviderOverrides}
                          onPersonaProviderChange={(personaValue, providerId) => {
                            setOriginalPromptPersonaProviderOverrides(prev => ({
                              ...prev,
                              [personaValue]: providerId
                            }));
                          }}
                          allowModelSelection={true}
                        />
                      </div>
                    )}

                    {/* Synthesis Model Selection */}
                    {!loadingModels && providers.length > 0 && (
                      <SynthesisModelSelector
                        providers={providers}
                        selectedProviderId={originalPromptSynthesisProviderId}
                        onSelectProvider={setOriginalPromptSynthesisProviderId}
                        label="Synthesis Model"
                        helpText="Model used to synthesize all refined perspectives into the final decision record"
                      />
                    )}
                  <div className="flex gap-3">
                    <button
                      onClick={handleOriginalPromptRefinement}
                      disabled={!refinedContext.trim() || !refinedPrompt.trim()}
                      className="flex-1 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium"
                    >
                      Submit Refinement
                    </button>
                    <button
                      onClick={() => {
                        setShowOriginalPromptEdit(false);
                        setRefinedContext('');
                        setRefinedPrompt('');
                      }}
                      className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors font-medium"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
            </>
          )}
        </div>

        {/* Footer with Buttons (Sticky on all screens) - Only show if not in manual edit mode */}
        {!isManualEditMode && (
        <div className="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 sm:p-6">
          <div className="flex gap-2 sm:gap-4">
            {currentAdr.persona_responses && currentAdr.persona_responses.length > 0 && (
              <>
                <button
                  onClick={() => setShowPersonas(true)}
                  className="flex-1 bg-purple-600 text-white px-3 py-2 sm:px-6 sm:py-3 rounded-md hover:bg-purple-700 transition-colors font-medium flex items-center justify-center gap-2"
                  title="Show Personas"
                >
                  <span className="sm:hidden relative">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
                    </svg>
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                      {currentAdr.persona_responses.length}
                    </span>
                  </span>
                  <span className="hidden sm:inline">Show Personas ({currentAdr.persona_responses.length})</span>
                </button>
                <button
                  onClick={() => setShowBulkRefine(!showBulkRefine)}
                  className="flex-1 bg-blue-600 text-white px-3 py-2 sm:px-6 sm:py-3 rounded-md hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-2"
                  title="Refine All Personas"
                >
                  <span className="sm:hidden flex items-center gap-1">
                    <span>Refine</span>
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
                    </svg>
                  </span>
                  <span className="hidden sm:inline">{showBulkRefine ? 'Hide Bulk Refine' : 'Refine All Personas'}</span>
                </button>
              </>
            )}
            <button
              onClick={onAnalyze}
              disabled={isAnalyzing}
              className="flex-1 bg-green-600 text-white px-3 py-2 sm:px-6 sm:py-3 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center justify-center gap-2"
              title={isPrinciple ? "Analyze Principle" : "Analyze ADR"}
            >
              <span className="sm:hidden">Analyze</span>
              <span className="hidden sm:inline">{isAnalyzing ? 'Analyzing...' : (isPrinciple ? 'Analyze Principle' : 'Analyze ADR')}</span>
            </button>
          </div>
        </div>
        )}
      </div>

      {showPersonas && currentAdr.persona_responses && (
        <PersonasModal
          personas={currentAdr.persona_responses}
          adrId={currentAdr.metadata.id}
          onClose={() => setShowPersonas(false)}
          onRefine={handleRefinePersonas}
          onADRUpdate={handleADRUpdate}
        />
      )}

      {refinementToast.show && (
        <Toast
          message={refinementToast.message}
          type={refinementToast.type}
          onClose={() => setRefinementToast({ show: false, message: '', type: 'success' })}
        />
      )}

      {/* MCP Result Modal */}
      {mcpResultModal.show && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black bg-opacity-50 dark:bg-opacity-70" onClick={closeMcpResultModal}></div>
          <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  MCP Tool Result
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {mcpResultModal.serverName} / {mcpResultModal.toolName}
                </p>
              </div>
              <button
                onClick={closeMcpResultModal}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-4">
              {mcpResultModal.loading && (
                <div className="flex items-center justify-center py-8">
                  <svg className="animate-spin h-8 w-8 text-purple-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="ml-3 text-gray-600 dark:text-gray-400">Loading tool result...</span>
                </div>
              )}

              {mcpResultModal.error && (
                <div className="text-center py-8">
                  <div className="text-red-500 dark:text-red-400 mb-2">
                    <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <p className="text-gray-600 dark:text-gray-400">{mcpResultModal.error}</p>
                </div>
              )}

              {!mcpResultModal.loading && !mcpResultModal.error && mcpResultModal.data && (
                <div className="space-y-4">
                  {/* Metadata */}
                  <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 text-sm">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Server:</span>
                        <span className="ml-2 text-gray-900 dark:text-gray-100">{mcpResultModal.data.server_name}</span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Tool:</span>
                        <span className="ml-2 text-gray-900 dark:text-gray-100">{mcpResultModal.data.tool_name}</span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Status:</span>
                        <span className={`ml-2 ${mcpResultModal.data.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {mcpResultModal.data.success ? 'Success' : 'Failed'}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Time:</span>
                        <span className="ml-2 text-gray-900 dark:text-gray-100">
                          {new Date(mcpResultModal.data.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Arguments */}
                  {mcpResultModal.data.arguments && Object.keys(mcpResultModal.data.arguments).length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Arguments</h4>
                      <pre className="bg-gray-100 dark:bg-gray-900 rounded-lg p-3 text-xs overflow-x-auto text-gray-800 dark:text-gray-200">
                        {JSON.stringify(mcpResultModal.data.arguments, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Result */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Result</h4>
                    <pre className="bg-gray-100 dark:bg-gray-900 rounded-lg p-3 text-xs overflow-x-auto text-gray-800 dark:text-gray-200 max-h-96">
                      {JSON.stringify(mcpResultModal.data.result, null, 2)}
                    </pre>
                  </div>

                  {/* Error if any */}
                  {mcpResultModal.data.error && (
                    <div>
                      <h4 className="text-sm font-medium text-red-700 dark:text-red-300 mb-2">Error</h4>
                      <pre className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 text-xs overflow-x-auto text-red-800 dark:text-red-200">
                        {mcpResultModal.data.error}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(mcpResultModal.data, null, 2));
                }}
                disabled={!mcpResultModal.data}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors"
              >
                Copy JSON
              </button>
              <button
                onClick={closeMcpResultModal}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
