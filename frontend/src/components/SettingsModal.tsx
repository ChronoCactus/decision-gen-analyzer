'use client';

import { useState, useEffect } from 'react';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { apiClient } from '@/lib/api';
import {
  LLMProvider,
  CreateProviderRequest,
  UpdateProviderRequest,
  MCPServerConfig,
  MCPTransportType,
  MCPToolExecutionMode,
  CreateMCPServerRequest,
  UpdateMCPServerRequest,
  ADRStatus
} from '@/types/api';
import { Toast } from './Toast';
import { InterfaceSettings } from '@/hooks/useInterfaceSettings';

interface SettingsModalProps {
  onClose: () => void;
  interfaceSettings: InterfaceSettings;
  onUpdateInterfaceSettings: (settings: Partial<InterfaceSettings>) => void;
}

type ProviderFormData = {
  name: string;
  provider_type: string;
  base_url: string;
  model_name: string;
  api_key: string;
  temperature: number;
  num_ctx: number | null;
  num_predict: number | null;
  parallel_requests_enabled: boolean;
  max_parallel_requests: number;
  is_default: boolean;
};

type MCPServerFormData = {
  name: string;
  transport_type: MCPTransportType;
  command: string;
  args: string;
  url: string;
  auth_token: string;
  enabled: boolean;
};

export function SettingsModal({ onClose, interfaceSettings, onUpdateInterfaceSettings }: SettingsModalProps) {
  useEscapeKey(onClose);

  const [activeTab, setActiveTab] = useState<'providers' | 'mcp' | 'interface'>('providers');
  const [toast, setToast] = useState<{ message: string; type: 'info' | 'success' | 'warning' | 'error' } | null>(null);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null);
  const [formData, setFormData] = useState<ProviderFormData>({
    name: '',
    provider_type: 'ollama',
    base_url: '',
    model_name: '',
    api_key: '',
    temperature: 0.7,
    num_ctx: null,
    num_predict: null,
    parallel_requests_enabled: false,
    max_parallel_requests: 2,
    is_default: false,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);

  // MCP Server state
  const [mcpServers, setMcpServers] = useState<MCPServerConfig[]>([]);
  const [isMcpLoading, setIsMcpLoading] = useState(true);
  const [showMcpAddForm, setShowMcpAddForm] = useState(false);
  const [editingMcpServer, setEditingMcpServer] = useState<MCPServerConfig | null>(null);
  const [mcpFormData, setMcpFormData] = useState<MCPServerFormData>({
    name: '',
    transport_type: MCPTransportType.STDIO,
    command: '',
    args: '',
    url: '',
    auth_token: '',
    enabled: true,
  });
  const [isMcpSaving, setIsMcpSaving] = useState(false);
  const [isMcpDeleting, setIsMcpDeleting] = useState<string | null>(null);
  const [isDiscoveringTools, setIsDiscoveringTools] = useState<string | null>(null);
  const [expandedMcpServer, setExpandedMcpServer] = useState<string | null>(null);

  const validateProviderEndpoint = async (type: string, url: string) => {
    if (!url) return;

    // Check for Ollama endpoint when OpenAI is selected
    if (type === 'openai') {
      try {
        const baseUrl = url.endsWith('/') ? url.slice(0, -1) : url;
        // Use a short timeout to avoid hanging
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);
        
        const response = await fetch(`${baseUrl}/api/ps`, { 
          method: 'GET',
          signal: controller.signal
        }).catch(() => null);
        
        clearTimeout(timeoutId);

        if (response?.ok) {
          setToast({
            message: `Warning: The endpoint "${url}" appears to be an Ollama server (found /api/ps). You selected 'openai' provider type.`,
            type: 'warning'
          });
        }
      } catch {
        // Ignore network errors
      }
    }

    // Check for llama.cpp endpoint format
    if (type === 'llama_cpp') {
      if (!url.includes('/v1')) {
        setToast({
          message: "Suggestion: Llama.cpp endpoints usually require '/v1' in the path (e.g., http://localhost:8080/v1).",
          type: 'warning'
        });
      }
    }
  };

  useEffect(() => {
    if (providers.length > 0) {
      providers.forEach(p => validateProviderEndpoint(p.provider_type, p.base_url));
    }
  }, [providers]);

  useEffect(() => {
    loadProviders();
    loadMcpServers();
  }, []);

  const loadProviders = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await apiClient.listProviders();
      setProviders(response.providers);
    } catch (err) {
      setError('Failed to load providers');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMcpServers = async () => {
    try {
      setIsMcpLoading(true);
      const response = await apiClient.listMcpServers();
      setMcpServers(response.servers);
    } catch (err) {
      console.error('Failed to load MCP servers:', err);
    } finally {
      setIsMcpLoading(false);
    }
  };

  const handleAddProvider = () => {
    setFormData({
      name: '',
      provider_type: 'ollama',
      base_url: '',
      model_name: '',
      api_key: '',
      temperature: 0.7,
      num_ctx: null,
      num_predict: null,
      parallel_requests_enabled: false,
      max_parallel_requests: 2,
      is_default: false,
    });
    setEditingProvider(null);
    setShowAddForm(true);
  };

  const handleEditProvider = (provider: LLMProvider) => {
    setFormData({
      name: provider.name,
      provider_type: provider.provider_type,
      base_url: provider.base_url,
      model_name: provider.model_name,
      api_key: '', // Don't populate API key for security
      temperature: provider.temperature,
      num_ctx: provider.num_ctx || null,
      num_predict: provider.num_predict || null,
      parallel_requests_enabled: provider.parallel_requests_enabled || false,
      max_parallel_requests: provider.max_parallel_requests || 2,
      is_default: provider.is_default,
    });
    setEditingProvider(provider);
    setShowAddForm(true);
  };

  const handleCancelForm = () => {
    setShowAddForm(false);
    setEditingProvider(null);
    setFormData({
      name: '',
      provider_type: 'ollama',
      base_url: '',
      model_name: '',
      api_key: '',
      temperature: 0.7,
      num_ctx: null,
      num_predict: null,
      parallel_requests_enabled: false,
      max_parallel_requests: 2,
      is_default: false,
    });
  };

  const handleSaveProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);

    try {
      const requestData = {
        name: formData.name,
        provider_type: formData.provider_type,
        base_url: formData.base_url,
        model_name: formData.model_name,
        ...(formData.api_key ? { api_key: formData.api_key } : {}),
        temperature: formData.temperature,
        ...(formData.num_ctx ? { num_ctx: formData.num_ctx } : {}),
        ...(formData.num_predict ? { num_predict: formData.num_predict } : {}),
        parallel_requests_enabled: formData.parallel_requests_enabled,
        max_parallel_requests: formData.max_parallel_requests,
        is_default: formData.is_default,
      };

      if (editingProvider) {
        // Update existing provider
        await apiClient.updateProvider(editingProvider.id, requestData as UpdateProviderRequest);
        setToast({ message: 'Provider updated successfully', type: 'success' });
      } else {
        // Create new provider
        await apiClient.createProvider(requestData as CreateProviderRequest);
        setToast({ message: 'Provider created successfully', type: 'success' });
      }

      await loadProviders();
      handleCancelForm();
    } catch (err: any) {
      setError(err.message || 'Failed to save provider');
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteProvider = async (providerId: string) => {
    if (!confirm('Are you sure you want to delete this provider?')) {
      return;
    }

    setIsDeleting(providerId);
    setError(null);

    try {
      await apiClient.deleteProvider(providerId);
      setToast({ message: 'Provider deleted successfully', type: 'success' });
      await loadProviders();
    } catch (err: any) {
      setError(err.message || 'Failed to delete provider');
      console.error(err);
    } finally {
      setIsDeleting(null);
    }
  };

  const handleSetDefault = async (providerId: string) => {
    setError(null);
    try {
      await apiClient.updateProvider(providerId, { is_default: true });
      setToast({ message: 'Default provider set successfully', type: 'success' });
      await loadProviders();
    } catch (err: any) {
      setError(err.message || 'Failed to set default provider');
      console.error(err);
    }
  };

  // MCP Server handlers
  const handleAddMcpServer = () => {
    setMcpFormData({
      name: '',
      transport_type: MCPTransportType.STDIO,
      command: '',
      args: '',
      url: '',
      auth_token: '',
      enabled: true,
    });
    setEditingMcpServer(null);
    setShowMcpAddForm(true);
  };

  const handleEditMcpServer = (server: MCPServerConfig) => {
    setMcpFormData({
      name: server.name,
      transport_type: server.transport_type,
      command: server.command || '',
      args: server.args?.join(' ') || '',
      url: server.url || '',
      auth_token: '',
      enabled: server.is_enabled,
    });
    setEditingMcpServer(server);
    setShowMcpAddForm(true);
  };

  const handleCancelMcpForm = () => {
    setShowMcpAddForm(false);
    setEditingMcpServer(null);
    setMcpFormData({
      name: '',
      transport_type: MCPTransportType.STDIO,
      command: '',
      args: '',
      url: '',
      auth_token: '',
      enabled: true,
    });
  };

  const handleSaveMcpServer = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsMcpSaving(true);
    setError(null);

    try {
      const requestData: CreateMCPServerRequest | UpdateMCPServerRequest = {
        name: mcpFormData.name,
        transport_type: mcpFormData.transport_type,
        is_enabled: mcpFormData.enabled,
      };

      if (mcpFormData.transport_type === MCPTransportType.STDIO) {
        (requestData as CreateMCPServerRequest).command = mcpFormData.command;
        (requestData as CreateMCPServerRequest).args = mcpFormData.args ? mcpFormData.args.split(' ').filter(a => a) : [];
      } else {
        (requestData as CreateMCPServerRequest).url = mcpFormData.url;
        if (mcpFormData.auth_token) {
          (requestData as CreateMCPServerRequest).auth_token = mcpFormData.auth_token;
        }
      }

      if (editingMcpServer) {
        await apiClient.updateMcpServer(editingMcpServer.id, requestData as UpdateMCPServerRequest);
        setToast({ message: 'MCP server updated successfully', type: 'success' });
      } else {
        await apiClient.createMcpServer(requestData as CreateMCPServerRequest);
        setToast({ message: 'MCP server created successfully', type: 'success' });
      }

      await loadMcpServers();
      handleCancelMcpForm();
    } catch (err: any) {
      setError(err.message || 'Failed to save MCP server');
      console.error(err);
    } finally {
      setIsMcpSaving(false);
    }
  };

  const handleDeleteMcpServer = async (serverId: string) => {
    if (!confirm('Are you sure you want to delete this MCP server?')) {
      return;
    }

    setIsMcpDeleting(serverId);
    setError(null);

    try {
      await apiClient.deleteMcpServer(serverId);
      setToast({ message: 'MCP server deleted successfully', type: 'success' });
      await loadMcpServers();
    } catch (err: any) {
      setError(err.message || 'Failed to delete MCP server');
      console.error(err);
    } finally {
      setIsMcpDeleting(null);
    }
  };

  const handleDiscoverTools = async (serverId: string) => {
    setIsDiscoveringTools(serverId);
    setError(null);

    try {
      const response = await apiClient.discoverMcpTools(serverId);
      setToast({ message: `Discovered ${response.tools.length} tools`, type: 'success' });
      await loadMcpServers();
      setExpandedMcpServer(serverId);
    } catch (err: any) {
      setError(err.message || 'Failed to discover tools');
      console.error(err);
    } finally {
      setIsDiscoveringTools(null);
    }
  };

  const handleToggleMcpServer = async (server: MCPServerConfig) => {
    try {
      await apiClient.updateMcpServer(server.id, { is_enabled: !server.is_enabled });
      await loadMcpServers();
    } catch (err: any) {
      setError(err.message || 'Failed to update MCP server');
      console.error(err);
    }
  };

  const handleUpdateMcpTool = async (serverId: string, toolName: string, updates: { default_enabled?: boolean; execution_mode?: MCPToolExecutionMode }) => {
    try {
      await apiClient.updateMcpTool(serverId, toolName, updates);
      await loadMcpServers();
    } catch (err: any) {
      setError(err.message || 'Failed to update tool');
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-50 sm:p-4">
      <div className="relative bg-white dark:bg-gray-800 w-full h-full sm:h-auto sm:max-w-4xl sm:max-h-[90vh] sm:rounded-lg shadow-xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center relative">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Settings</h2>
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

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex px-6">
            <button
              onClick={() => setActiveTab('providers')}
              className={`py-3 px-4 font-medium text-sm border-b-2 transition-colors ${
                activeTab === 'providers'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              LLM Providers
            </button>
            <button
              onClick={() => setActiveTab('mcp')}
              className={`py-3 px-4 font-medium text-sm border-b-2 transition-colors ${activeTab === 'mcp'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
            >
              MCP Servers
            </button>
            <button
              onClick={() => setActiveTab('interface')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'interface'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
            >
              Interface
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded">
              {error}
            </div>
          )}

          {activeTab === 'providers' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    LLM Provider Configurations
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Manage your LLM provider configurations for ADR generation
                  </p>
                </div>
                {!showAddForm && (
                  <button
                    onClick={handleAddProvider}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
                  >
                    + Add Provider
                  </button>
                )}
              </div>

              {showAddForm ? (
                <form onSubmit={handleSaveProvider} className="bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
                  <h4 className="text-md font-semibold text-gray-900 dark:text-gray-100 mb-4">
                    {editingProvider ? 'Edit Provider' : 'Add New Provider'}
                  </h4>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="provider-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Name *
                      </label>
                      <input
                        id="provider-name"
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="My LLM Provider"
                      />
                    </div>

                    <div>
                      <label htmlFor="provider-type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Provider Type *
                      </label>
                      <select
                        id="provider-type"
                        required
                        value={formData.provider_type}
                        onChange={(e) => {
                          const newType = e.target.value;
                          setFormData({ ...formData, provider_type: newType });
                          validateProviderEndpoint(newType, formData.base_url);
                        }}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      >
                        <option value="ollama">Ollama</option>
                        <option value="openai">OpenAI</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="vllm">vLLM</option>
                        <option value="llama_cpp">llama.cpp</option>
                        <option value="custom">Custom</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="base-url" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Base URL *
                      </label>
                      <input
                        id="base-url"
                        type="text"
                        required
                        value={formData.base_url}
                        onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                        onBlur={() => validateProviderEndpoint(formData.provider_type, formData.base_url)}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="http://localhost:11434"
                      />
                    </div>

                    <div>
                      <label htmlFor="model-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Model Name *
                      </label>
                      <input
                        id="model-name"
                        type="text"
                        required
                        value={formData.model_name}
                        onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="gpt-oss:20b"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        API Key {editingProvider && '(leave empty to keep current)'}
                      </label>
                      <input
                        type="password"
                        value={formData.api_key}
                        onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="Optional"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Temperature
                      </label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={formData.temperature}
                        onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Context Window (num_ctx)
                      </label>
                      <input
                        type="number"
                        value={formData.num_ctx || ''}
                        onChange={(e) => setFormData({ ...formData, num_ctx: e.target.value ? parseInt(e.target.value) : null })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="Optional"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Max Tokens (num_predict)
                      </label>
                      <input
                        type="number"
                        value={formData.num_predict || ''}
                        onChange={(e) => setFormData({ ...formData, num_predict: e.target.value ? parseInt(e.target.value) : null })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="Optional"
                      />
                    </div>

                    <div className="col-span-2 border-t border-gray-200 dark:border-gray-700 pt-4 mt-2">
                      <h5 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Parallel Processing</h5>
                      <div className="flex items-start gap-4">
                        <div className="flex-1">
                          <label className="flex items-center mb-2">
                            <input
                              type="checkbox"
                              checked={formData.parallel_requests_enabled}
                              onChange={(e) => setFormData({ ...formData, parallel_requests_enabled: e.target.checked })}
                              className="mr-2"
                            />
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Enable Parallel Requests</span>
                          </label>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Allow multiple persona generation requests to run simultaneously on this provider.
                          </p>
                        </div>

                        {formData.parallel_requests_enabled && (
                          <div className="w-48">
                            <label htmlFor="max-parallel-requests" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                              Max Parallel Requests
                            </label>
                            <input
                              id="max-parallel-requests"
                              type="number"
                              min="1"
                              max="10"
                              value={formData.max_parallel_requests}
                              onChange={(e) => setFormData({ ...formData, max_parallel_requests: Math.max(1, parseInt(e.target.value) || 1) })}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={formData.is_default}
                        onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                        className="mr-2"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">Set as default provider</span>
                    </label>
                  </div>

                  <div className="flex gap-2 mt-4">
                    <button
                      type="submit"
                      disabled={isSaving}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {isSaving ? 'Saving...' : editingProvider ? 'Update Provider' : 'Add Provider'}
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelForm}
                      className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-3">
                  {isLoading ? (
                    <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                      Loading providers...
                    </div>
                  ) : providers.length === 0 ? (
                    <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                          No providers configured. Click &quot;Add Provider&quot; to get started.
                    </div>
                  ) : (
                    providers.map((provider) => (
                      <div
                        key={provider.id}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-900/30"
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                {provider.name}
                              </h4>
                              {provider.is_default && (
                                <span className="px-2 py-0.5 text-xs bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded">
                                  Default
                                </span>
                              )}
                              {provider.is_env_based && (
                                <span className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded">
                                  Environment
                                </span>
                              )}
                            </div>
                            <div className="mt-2 text-sm text-gray-600 dark:text-gray-400 space-y-1">
                              <div>
                                <span className="font-medium">Type:</span> {provider.provider_type}
                              </div>
                              <div>
                                <span className="font-medium">Model:</span> {provider.model_name}
                              </div>
                              <div>
                                <span className="font-medium">URL:</span> {provider.base_url}
                              </div>
                              <div>
                                <span className="font-medium">Temperature:</span> {provider.temperature}
                              </div>
                              {provider.num_ctx && (
                                <div>
                                  <span className="font-medium">Context:</span> {provider.num_ctx}
                                </div>
                              )}
                              {provider.parallel_requests_enabled && (
                                <div>
                                  <span className="font-medium">Parallel:</span> {provider.max_parallel_requests} requests
                                </div>
                              )}
                              {provider.has_api_key && (
                                <div className="text-green-600 dark:text-green-400">
                                  ✓ API key configured
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex gap-2">
                            {!provider.is_env_based && (
                              <>
                                {!provider.is_default && (
                                  <button
                                    onClick={() => handleSetDefault(provider.id)}
                                    className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                                  >
                                    Set Default
                                  </button>
                                )}
                                <button
                                  onClick={() => handleEditProvider(provider)}
                                  className="px-3 py-1 text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                                >
                                  Edit
                                </button>
                                <button
                                  onClick={() => handleDeleteProvider(provider.id)}
                                  disabled={isDeleting === provider.id}
                                  className="px-3 py-1 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                  {isDeleting === provider.id ? 'Deleting...' : 'Delete'}
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'mcp' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    MCP Server Configurations
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Configure Model Context Protocol servers for tool integration during ADR generation
                  </p>
                </div>
                {!showMcpAddForm && (
                  <button
                    onClick={handleAddMcpServer}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
                  >
                    + Add MCP Server
                  </button>
                )}
              </div>

              {showMcpAddForm ? (
                <form onSubmit={handleSaveMcpServer} className="bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
                  <h4 className="text-md font-semibold text-gray-900 dark:text-gray-100 mb-4">
                    {editingMcpServer ? 'Edit MCP Server' : 'Add New MCP Server'}
                  </h4>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Name *
                      </label>
                      <input
                        type="text"
                        required
                        value={mcpFormData.name}
                        onChange={(e) => setMcpFormData({ ...mcpFormData, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="My MCP Server"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Transport Type *
                      </label>
                      <select
                        required
                        value={mcpFormData.transport_type}
                        onChange={(e) => setMcpFormData({ ...mcpFormData, transport_type: e.target.value as MCPTransportType })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      >
                        <option value={MCPTransportType.STDIO}>STDIO (Command)</option>
                        <option value={MCPTransportType.HTTP}>HTTP</option>
                        <option value={MCPTransportType.SSE}>SSE</option>
                      </select>
                    </div>

                    {mcpFormData.transport_type === MCPTransportType.STDIO ? (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Command *
                          </label>
                          <input
                            type="text"
                            required
                            value={mcpFormData.command}
                            onChange={(e) => setMcpFormData({ ...mcpFormData, command: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            placeholder="npx"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Arguments
                          </label>
                          <input
                            type="text"
                            value={mcpFormData.args}
                            onChange={(e) => setMcpFormData({ ...mcpFormData, args: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            placeholder="-y @modelcontextprotocol/server-memory"
                          />
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Space-separated arguments
                          </p>
                        </div>
                      </>
                    ) : (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            URL *
                          </label>
                          <input
                            type="text"
                            required
                            value={mcpFormData.url}
                            onChange={(e) => setMcpFormData({ ...mcpFormData, url: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            placeholder="http://localhost:8080/mcp"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Auth Token {editingMcpServer && '(leave empty to keep current)'}
                          </label>
                          <input
                            type="password"
                            value={mcpFormData.auth_token}
                            onChange={(e) => setMcpFormData({ ...mcpFormData, auth_token: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                            placeholder="Optional"
                          />
                        </div>
                      </>
                    )}
                  </div>

                  <div className="mt-4">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={mcpFormData.enabled}
                        onChange={(e) => setMcpFormData({ ...mcpFormData, enabled: e.target.checked })}
                        className="mr-2"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">Enabled</span>
                    </label>
                  </div>

                  <div className="flex gap-2 mt-4">
                    <button
                      type="submit"
                      disabled={isMcpSaving}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {isMcpSaving ? 'Saving...' : editingMcpServer ? 'Update Server' : 'Add Server'}
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelMcpForm}
                      className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-3">
                  {isMcpLoading ? (
                    <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                      Loading MCP servers...
                    </div>
                  ) : mcpServers.length === 0 ? (
                    <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                      No MCP servers configured. Click &quot;Add MCP Server&quot; to get started.
                    </div>
                  ) : (
                    mcpServers.map((server) => (
                      <div
                        key={server.id}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-900/30"
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                {server.name}
                              </h4>
                              <span className={`px-2 py-0.5 text-xs rounded ${server.is_enabled
                                ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                                }`}>
                                {server.is_enabled ? 'Enabled' : 'Disabled'}
                              </span>
                            </div>
                            <div className="mt-2 text-sm text-gray-600 dark:text-gray-400 space-y-1">
                              <div>
                                <span className="font-medium">Transport:</span> {server.transport_type}
                              </div>
                              {server.transport_type === MCPTransportType.STDIO ? (
                                <div>
                                  <span className="font-medium">Command:</span> {server.command} {server.args?.join(' ')}
                                </div>
                              ) : (
                                <div>
                                  <span className="font-medium">URL:</span> {server.url}
                                </div>
                              )}
                              <div>
                                <span className="font-medium">Tools:</span> {server.tools.length} configured
                              </div>
                              {server.has_auth_token && (
                                <div className="text-green-600 dark:text-green-400">
                                  ✓ Auth token configured
                                </div>
                              )}
                            </div>

                            {/* Tools section */}
                            {server.tools.length > 0 && (
                              <div className="mt-3">
                                <button
                                  onClick={() => setExpandedMcpServer(expandedMcpServer === server.id ? null : server.id)}
                                  className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                                >
                                  {expandedMcpServer === server.id ? 'Hide tools' : 'Show tools'} ({server.tools.length})
                                </button>
                                {expandedMcpServer === server.id && (
                                  <div className="mt-2 space-y-2 pl-4 border-l-2 border-gray-200 dark:border-gray-600">
                                    {server.tools.map((tool) => (
                                      <div key={tool.tool_name} className="flex items-center justify-between text-sm">
                                        <div className="flex items-center gap-2">
                                          <input
                                            type="checkbox"
                                            checked={tool.default_enabled}
                                            onChange={() => handleUpdateMcpTool(server.id, tool.tool_name, { default_enabled: !tool.default_enabled })}
                                            className="rounded"
                                          />
                                          <span className="text-gray-900 dark:text-gray-100">{tool.display_name || tool.tool_name}</span>
                                          <span className="text-gray-500 dark:text-gray-400 text-xs">
                                            ({tool.execution_mode === MCPToolExecutionMode.INITIAL_ONLY ? 'Initial only' : 'Per persona'})
                                          </span>
                                        </div>
                                        <select
                                          value={tool.execution_mode}
                                          onChange={(e) => handleUpdateMcpTool(server.id, tool.tool_name, { execution_mode: e.target.value as MCPToolExecutionMode })}
                                          className="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                                        >
                                          <option value={MCPToolExecutionMode.INITIAL_ONLY}>Initial only</option>
                                          <option value={MCPToolExecutionMode.PER_PERSONA}>Per persona</option>
                                        </select>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          <div className="flex gap-2 flex-wrap justify-end">
                            <button
                              onClick={() => handleToggleMcpServer(server)}
                              className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                            >
                              {server.is_enabled ? 'Disable' : 'Enable'}
                            </button>
                            <button
                              onClick={() => handleDiscoverTools(server.id)}
                              disabled={isDiscoveringTools === server.id}
                              className="px-3 py-1 text-sm bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded hover:bg-purple-200 dark:hover:bg-purple-900/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                              {isDiscoveringTools === server.id ? 'Discovering...' : 'Discover Tools'}
                            </button>
                            <button
                              onClick={() => handleEditMcpServer(server)}
                              className="px-3 py-1 text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteMcpServer(server.id)}
                              disabled={isMcpDeleting === server.id}
                              className="px-3 py-1 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                              {isMcpDeleting === server.id ? 'Deleting...' : 'Delete'}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'interface' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                Interface Settings
              </h3>

              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="font-medium text-gray-900 dark:text-gray-100">
                      Auto-dismiss Notifications
                    </label>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Automatically hide success/info notifications after a delay
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      className="sr-only peer"
                      checked={interfaceSettings.autoDismissToasts}
                      onChange={(e) => onUpdateInterfaceSettings({ autoDismissToasts: e.target.checked })}
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {interfaceSettings.autoDismissToasts && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Dismiss Delay (seconds)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="60"
                      value={interfaceSettings.toastDismissTimeout}
                      onChange={(e) => onUpdateInterfaceSettings({ toastDismissTimeout: Math.max(1, parseInt(e.target.value) || 5) })}
                      className="w-full max-w-xs px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                )}

                {/* Default Status Filter */}
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Default Reference Status Filter
                  </label>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                    By default, only use ADRs with these statuses as reference context when generating new records. This prevents draft decisions from polluting new generations.
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {Object.values(ADRStatus).map((status) => {
                      const isSelected = interfaceSettings.defaultStatusFilter.includes(status);
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
                              const newFilter = e.target.checked
                                ? [...interfaceSettings.defaultStatusFilter, status]
                                : interfaceSettings.defaultStatusFilter.filter(s => s !== status);
                              onUpdateInterfaceSettings({ defaultStatusFilter: newFilter });
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
                  {interfaceSettings.defaultStatusFilter.length === 0 && (
                    <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                      ⚠️ No statuses selected - all ADRs will be included by default regardless of status.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Close
          </button>
        </div>
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
            positionType="absolute"
          />
        )}
      </div>
    </div>
  );
}
