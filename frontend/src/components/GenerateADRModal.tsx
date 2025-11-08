'use client';

import { useState, useEffect } from 'react';
import { GenerateADRRequest, Persona } from '@/types/api';
import { apiClient } from '@/lib/api';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface GenerateADRModalProps {
  onClose: () => void;
  onGenerate: (request: GenerateADRRequest) => void;
  isGenerating: boolean;
  generationStartTime?: number;
}

export function GenerateADRModal({ onClose, onGenerate, isGenerating, generationStartTime }: GenerateADRModalProps) {
  const [prompt, setPrompt] = useState('');
  const [context, setContext] = useState('');
  const [tags, setTags] = useState('');
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([]);
  const [loadingPersonas, setLoadingPersonas] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isMac, setIsMac] = useState(false);
  const [isWin, setIsWin] = useState(false);

  // Close with ESC key (unless we're generating)
  useEscapeKey(onClose, !isGenerating);

  // Detect OS for keyboard shortcut display
  useEffect(() => {
    const platform = navigator.platform.toLowerCase();
    setIsMac(platform.includes('mac'));
    setIsWin(platform.includes('win'));
  }, []);

  // Timer for generation duration
  useEffect(() => {
    if (!isGenerating || !generationStartTime) {
      setElapsedTime(0);
      return;
    }

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - generationStartTime) / 1000);
      setElapsedTime(elapsed);
    }, 1000);

    return () => clearInterval(interval);
  }, [isGenerating, generationStartTime]);

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
  }, [prompt, context, tags, selectedPersonas, isGenerating]);

  useEffect(() => {
    // Load available personas
    apiClient.getPersonas()
      .then(response => {
        setPersonas(response.personas);
        // Set default selections
        const defaultPersonas = response.personas
          .filter(p => ['technical_lead', 'architect', 'business_analyst'].includes(p.value))
          .map(p => p.value);
        setSelectedPersonas(defaultPersonas);
      })
      .catch(error => {
        console.error('Failed to load personas:', error);
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const tagArray = tags.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);

    onGenerate({
      prompt: prompt.trim(),
      context: context.trim() || undefined,
      tags: tagArray.length > 0 ? tagArray : undefined,
      personas: selectedPersonas.length > 0 ? selectedPersonas : undefined,
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Generate New ADR</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 text-2xl"
            >
              ×
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical"
                rows={4}
                required
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Describe the architectural decision you want to generate an ADR for.
              </p>
            </div>

            <div>
              <label htmlFor="context" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Additional Context
              </label>
              <textarea
                id="context"
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Any additional context, constraints, or requirements..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical"
                rows={3}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Optional: Provide additional context to help generate a more accurate ADR.
              </p>
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Optional: Comma-separated tags to categorize the ADR.
              </p>
            </div>

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
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
                        <div className="font-medium text-sm text-gray-900 dark:text-gray-100">
                          {persona.label}
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
                      : 'Generate ADR'}
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
