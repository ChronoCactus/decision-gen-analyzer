'use client';

import { useState, useEffect, useCallback } from 'react';
import { GenerateADRRequest, Persona, LLMProvider, MCPServerConfig, ADRStatus } from '@/types/api';
import { apiClient } from '@/lib/api';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { InterfaceSettings } from '@/hooks/useInterfaceSettings';

interface GenerateADRModalProps {
  onClose: () => void;
  onGenerate: (request: GenerateADRRequest) => void;
  isGenerating: boolean;
  generationStartTime?: number;
  initialRecordType?: 'decision' | 'principle';
  interfaceSettings?: InterfaceSettings;
}

export function GenerateADRModal({ onClose, onGenerate, isGenerating, generationStartTime, initialRecordType = 'decision', interfaceSettings }: GenerateADRModalProps) {
  const [prompt, setPrompt] = useState('');
  const [context, setContext] = useState('');
  const [tags, setTags] = useState('');
  const [retrievalMode, setRetrievalMode] = useState('naive');
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([]);
  const [loadingPersonas, setLoadingPersonas] = useState(true);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [showContext, setShowContext] = useState(false);
  const [recordType, setRecordType] = useState<'decision' | 'principle'>(initialRecordType);

  // Status filter state - default from interface settings
  const [statusFilter, setStatusFilter] = useState<string[]>(
    interfaceSettings?.defaultStatusFilter || ['accepted']
  );

  // MCP state - AI-driven tool orchestration
  const [mcpServers, setMcpServers] = useState<MCPServerConfig[]>([]);
  const [useMcp, setUseMcp] = useState(false);

  // Detect OS for keyboard shortcut display (computed once on mount)
  const [isMac] = useState(() => {
    if (typeof navigator !== 'undefined') {
      return navigator.platform.toLowerCase().includes('mac');
    }
    return false;
  });
  const [isWin] = useState(() => {
    if (typeof navigator !== 'undefined') {
      return navigator.platform.toLowerCase().includes('win');
    }
    return false;
  });

  // Close with ESC key (unless we're generating)
  useEscapeKey(onClose, !isGenerating);

  // Timer for generation duration - only runs when generating
  useEffect(() => {
    if (!isGenerating || !generationStartTime) {
      return;
    }

    // Set initial elapsed time
    const updateElapsed = () => {
      const elapsed = Math.floor((Date.now() - generationStartTime) / 1000);
      setElapsedTime(elapsed);
    };

    updateElapsed(); // Set immediately
    const interval = setInterval(updateElapsed, 1000);

    return () => {
      clearInterval(interval);
      setElapsedTime(0); // Reset in cleanup when effect unmounts
    };
  }, [isGenerating, generationStartTime]);

  // Define handleSubmit using useCallback to avoid recreation and allow it to be used in effects
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const tagArray = tags.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);

    onGenerate({
      prompt: prompt.trim(),
      context: context.trim() || undefined,
      tags: tagArray.length > 0 ? tagArray : undefined,
      personas: selectedPersonas.length > 0 ? selectedPersonas : undefined,
      retrieval_mode: retrievalMode,
      provider_id: selectedProviderId || undefined,
      record_type: recordType,
      use_mcp: useMcp || undefined,
      status_filter: statusFilter.length > 0 ? statusFilter : undefined,
    });
  }, [prompt, context, tags, selectedPersonas, retrievalMode, selectedProviderId, recordType, useMcp, statusFilter, onGenerate]);

  // Handle keyboard shortcuts (Cmd/Ctrl + Enter)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        if (!isGenerating && prompt.trim()) {
          handleSubmit(e as any);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [prompt, isGenerating, handleSubmit]);

  useEffect(() => {
    // Load available personas, providers, and MCP servers
    Promise.all([
      apiClient.getPersonas(),
      apiClient.listProviders(),
      apiClient.listMcpServers().catch(() => ({ servers: [] })) // Don't fail if MCP servers not available
    ])
      .then(([personasResponse, providersResponse, mcpResponse]) => {
        setPersonas(personasResponse.personas);
        setProviders(providersResponse.providers);
        setMcpServers(mcpResponse.servers);

        // Set default provider (the one marked as default)
        const defaultProvider = providersResponse.providers.find(p => p.is_default);
        if (defaultProvider) {
          setSelectedProviderId(defaultProvider.id);
        }

        // Set default persona selections
        const defaultPersonas = personasResponse.personas
          .filter(p => ['technical_lead', 'architect', 'business_analyst'].includes(p.value))
          .map(p => p.value);
        setSelectedPersonas(defaultPersonas);
      })
      .catch(error => {
        console.error('Failed to load personas or providers:', error);
      })
      .finally(() => {
        setLoadingPersonas(false);
      });
  }, []);

  const togglePersona = (personaValue: string) => {
    setSelectedPersonas(prev => 
      prev.includes(personaValue)
        ? prev.filter(p => p !== personaValue)
        : [...prev, personaValue]
    );
  };

  const getEnabledMcpServers = (): MCPServerConfig[] => {
    return mcpServers.filter(s => s.is_enabled && s.tools.length > 0);
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

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center sm:p-4 z-50">
      <div className="bg-white dark:bg-gray-800 w-full h-full sm:h-auto sm:max-w-2xl sm:max-h-[90vh] sm:rounded-lg overflow-y-auto relative">
        <div className="p-4 sm:p-6">
          <div className="flex justify-between items-start mb-6">
            <div className="flex-1 pr-12">
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-2">
                <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                  Generate New {recordType === 'decision' ? 'ADR' : 'Principle'}
                </h2>
                <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1 w-fit">
                  <button
                    type="button"
                    onClick={() => setRecordType('decision')}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${recordType === 'decision'
                      ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                  >
                    Decision
                  </button>
                  <button
                    type="button"
                    onClick={() => setRecordType('principle')}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${recordType === 'principle'
                      ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                  >
                    Principle
                  </button>
                </div>
              </div>
              {providers.length > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <label htmlFor="provider-select" className="text-xs text-gray-600 dark:text-gray-400">
                    Model:
                  </label>
                  <select
                    id="provider-select"
                    value={selectedProviderId}
                    onChange={(e) => setSelectedProviderId(e.target.value)}
                    className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-mono"
                  >
                    {providers.map(provider => (
                      <option key={provider.id} value={provider.id}>
                        {provider.provider_type}/{provider.model_name}
                        {provider.is_default ? ' (default)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors z-10"
              aria-label="Close"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="prompt" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Prompt *
              </label>
              <textarea
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe the decision you want to document..."
                className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical"
                rows={3}
                required
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Describe what you want to generate an decision record for.
              </p>
            </div>

            <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden">
              <button
                type="button"
                onClick={() => setShowContext(!showContext)}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
              >
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Additional Context</span>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${showContext ? 'transform rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showContext && (
                <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                  <textarea
                    id="context"
                    value={context}
                    onChange={(e) => setContext(e.target.value)}
                    placeholder="Any additional context, constraints, or requirements..."
                    className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical"
                    rows={3}
                  />
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Optional: Provide additional context to help generate a more accurate decision record.
                  </p>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="tags" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Tags
              </label>
              <input
                id="tags"
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="architecture, database, security (comma-separated)"
                className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Optional: Comma-separated tags to categorize the ADR.
              </p>
            </div>

            <div>
              <label htmlFor="retrieval-mode" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                RAG Retrieval Mode
              </label>
              <select
                id="retrieval-mode"
                value={retrievalMode}
                onChange={(e) => setRetrievalMode(e.target.value)}
                className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="naive">Naive - Simple vector similarity search (Recommended)</option>
                <option value="local">Local - Focused entity-based retrieval</option>
                <option value="global">Global - Broader pattern analysis across knowledge graph</option>
                <option value="hybrid">Hybrid - Combines local and global approaches</option>
                <option value="mix">Mix - Integrates knowledge graph with vector search</option>
                <option value="bypass">Bypass - Direct LLM query without retrieval</option>
              </select>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Controls how related ADRs are retrieved from the knowledge base. Naive mode uses simple vector similarity without knowledge graph processing.
              </p>
              <p className="text-sm text-amber-600 dark:text-amber-400 mt-1">
                💡 <strong>Tip:</strong> Getting unrelated results? Increase the <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">COSINE_THRESHOLD</code> environment variable on your LightRAG deployment (default: 0.2, try 0.3-0.5 for stricter matching).
              </p>
            </div>

            {/* Status Filter for Referenced ADRs */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Reference Status Filter
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                Only use ADRs with these statuses as reference context. This prevents draft decisions from polluting new generations.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.values(ADRStatus).map((status) => {
                  const isSelected = statusFilter.includes(status);
                  const statusColors = {
                    [ADRStatus.PROPOSED]: 'blue',
                    [ADRStatus.ACCEPTED]: 'green',
                    [ADRStatus.DEPRECATED]: 'orange',
                    [ADRStatus.SUPERSEDED]: 'purple',
                    [ADRStatus.REJECTED]: 'red',
                  };
                  const color = statusColors[status];
                  
                  return (
                    <label
                      key={status}
                      className={`flex items-center p-2 rounded-md border cursor-pointer transition-colors ${
                        isSelected
                          ? `border-${color}-500 dark:border-${color}-400 bg-${color}-50 dark:bg-${color}-900/30`
                          : 'border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setStatusFilter([...statusFilter, status]);
                          } else {
                            setStatusFilter(statusFilter.filter(s => s !== status));
                          }
                        }}
                        className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="ml-2 text-sm text-gray-700 dark:text-gray-300 capitalize">
                        {status}
                      </span>
                    </label>
                  );
                })}
              </div>
              {statusFilter.length === 0 && (
                <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                  ⚠️ No statuses selected - all ADRs will be included regardless of status.
                </p>
              )}
            </div>

            {/* MCP Tools Toggle - AI-driven tool orchestration */}
            {getEnabledMcpServers().length > 0 && (
              <div className="border border-gray-200 dark:border-gray-700 rounded-md p-4 bg-purple-50 dark:bg-purple-900/20">
                <label className="flex items-start cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useMcp}
                    onChange={(e) => setUseMcp(e.target.checked)}
                    className="mt-0.5 mr-3 h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 dark:border-gray-600 rounded"
                  />
                  <div>
                    <span className="text-sm font-medium text-purple-700 dark:text-purple-300">
                      Use MCP Tools (AI-driven)
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      When enabled, AI will analyze your request and decide which external tools to call to gather additional context.
                      Available servers: {getEnabledMcpServers().map(s => s.name).join(', ')}
                    </p>
                  </div>
                </label>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Analysis Personas
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                Select the personas that will contribute to the ADR generation. Each persona provides a different perspective.
              </p>
              {loadingPersonas ? (
                <div className="text-sm text-gray-500 dark:text-gray-400">Loading personas...</div>
              ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {personas.map((persona) => (
                    <label
                      key={persona.value}
                      className={`flex items-start p-3 border rounded-md cursor-pointer transition-colors ${
                        selectedPersonas.includes(persona.value)
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-400'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 bg-white dark:bg-gray-700/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPersonas.includes(persona.value)}
                        onChange={() => togglePersona(persona.value)}
                        className="mt-1 mr-3 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded"
                      />
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <div className="font-medium text-sm text-gray-900 dark:text-gray-100">
                            {persona.label}
                          </div>
                          <div className="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 ml-2">
                            {getModelDisplay(persona)}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {persona.description}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
              {!loadingPersonas && selectedPersonas.length === 0 && (
                <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                  ⚠️ No personas selected. Default personas will be used.
                </p>
              )}
            </div>

            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={isGenerating || !prompt.trim()}
                className={`flex-1 text-white font-semibold rounded-lg px-6 py-3 ${isGenerating || !prompt.trim()
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700'
                  }`}
              >
                <span className="flex items-center justify-center">
                  <span className="text-white">
                    {isGenerating
                      ? `Generating... ${elapsedTime > 0 ? `(${elapsedTime}s)` : ''}`
                      : 'Generate'}
                  </span>
                  {!isGenerating && (isMac || isWin) && (
                    <>
                      {isMac && (
                        <span className="ml-3">
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="text-slate-300" viewBox="0 0 16 16">
                            <path d="M3.5 2A1.5 1.5 0 0 1 5 3.5V5H3.5a1.5 1.5 0 1 1 0-3M6 5V3.5A2.5 2.5 0 1 0 3.5 6H5v4H3.5A2.5 2.5 0 1 0 6 12.5V11h4v1.5a2.5 2.5 0 1 0 2.5-2.5H11V6h1.5A2.5 2.5 0 1 0 10 3.5V5zm4 1v4H6V6zm1-1V3.5A1.5 1.5 0 1 1 12.5 5zm0 6h1.5a1.5 1.5 0 1 1-1.5 1.5zm-6 0v1.5A1.5 1.5 0 1 1 3.5 11z" />
                          </svg>
                        </span>
                      )}
                      {isWin && (
                        <span className="ml-3 text-sm text-slate-300">Ctrl</span>
                      )}
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="text-slate-300 ml-1" viewBox="0 0 16 16">
                        <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4" />
                      </svg>
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="text-slate-300" viewBox="0 0 16 16">
                        <path d="M14.5 1.5a.5.5 0 0 1 .5.5v4.8a2.5 2.5 0 0 1-2.5 2.5H2.707l3.347 3.346a.5.5 0 0 1-.708.708l-4.2-4.2a.5.5 0 0 1 0-.708l4-4a.5.5 0 1 1 .708.708L2.707 8.3H12.5A1.5 1.5 0 0 0 14 6.8V2a.5.5 0 0 1 .5-.5" />
                      </svg>
                    </>
                  )}
                </span>
              </button>
              <button
                type="button"
                onClick={onClose}
                disabled={isGenerating}
                className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
