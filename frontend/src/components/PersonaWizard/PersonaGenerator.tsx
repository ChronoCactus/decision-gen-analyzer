'use client';

import { useState } from 'react';
import { apiClient } from '@/lib/api';
import { PersonaConfig } from '@/types/api';

interface PersonaGeneratorProps {
  onGenerated: (persona: PersonaConfig) => void;
  onCancel: () => void;
}

export function PersonaGenerator({ onGenerated, onCancel }: PersonaGeneratorProps) {
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    setIsGenerating(true);
    setError(null);
    
    try {
      const persona = await apiClient.generatePersona({ prompt });
      onGenerated(persona);
    } catch (err) {
      setError('Failed to generate persona. Please try again.');
      console.error(err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Describe the Persona
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          placeholder="e.g. A cynical security engineer who is paranoid about supply chain attacks..."
        />
      </div>

      {error && (
        <div className="p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded text-sm">
          {error}
        </div>
      )}

      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleGenerate}
          disabled={isGenerating || !prompt.trim()}
          className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {isGenerating ? (
            <>
              <span className="animate-spin">⏳</span> Generating...
            </>
          ) : (
            <>
              <span>✨</span> Generate with AI
            </>
          )}
        </button>
      </div>
    </div>
  );
}
