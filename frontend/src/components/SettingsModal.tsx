'use client';

import { useState, useEffect } from 'react';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { apiClient } from '@/lib/api';
import { LLMProvider, CreateProviderRequest, UpdateProviderRequest } from '@/types/api';

interface SettingsModalProps {
  onClose: () => void;
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
  is_default: boolean;
};

export function SettingsModal({ onClose }: SettingsModalProps) {
  useEscapeKey(onClose);

  const [activeTab, setActiveTab] = useState<'providers' | 'general'>('providers');
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
    is_default: false,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);

  useEffect(() => {
    loadProviders();
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
        is_default: formData.is_default,
      };

      if (editingProvider) {
        // Update existing provider
        await apiClient.updateProvider(editingProvider.id, requestData as UpdateProviderRequest);
      } else {
        // Create new provider
        await apiClient.createProvider(requestData as CreateProviderRequest);
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
      await loadProviders();
    } catch (err: any) {
      setError(err.message || 'Failed to set default provider');
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-2xl"
          >
            ×
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
              onClick={() => setActiveTab('general')}
              className={`py-3 px-4 font-medium text-sm border-b-2 transition-colors ${
                activeTab === 'general'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              General
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
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Name *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="My LLM Provider"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Provider Type *
                      </label>
                      <select
                        required
                        value={formData.provider_type}
                        onChange={(e) => setFormData({ ...formData, provider_type: e.target.value })}
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
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Base URL *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.base_url}
                        onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        placeholder="http://localhost:11434"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Model Name *
                      </label>
                      <input
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
                      No providers configured. Click "Add Provider" to get started.
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

          {activeTab === 'general' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                General Settings
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                General settings will be added here in a future update.
              </p>
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
      </div>
    </div>
  );
}
