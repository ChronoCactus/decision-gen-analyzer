'use client';

import { LLMProvider } from '@/types/api';

interface SynthesisModelSelectorProps {
  providers: LLMProvider[];
  selectedProviderId: string;
  onSelectProvider: (providerId: string) => void;
  label?: string;
  helpText?: string;
}

/**
 * Reusable synthesis model selector dropdown.
 * Shows which model will be used for the final synthesis step.
 */
export function SynthesisModelSelector({
  providers,
  selectedProviderId,
  onSelectProvider,
  label = 'Synthesis Model',
  helpText = 'Model used to synthesize all persona perspectives into the final decision record',
}: SynthesisModelSelectorProps) {
  if (providers.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <label htmlFor="synthesis-provider-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {label}
      </label>
      <select
        id="synthesis-provider-select"
        value={selectedProviderId}
        onChange={(e) => onSelectProvider(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        {providers.map(provider => (
          <option key={provider.id} value={provider.id}>
            {provider.provider_type}/{provider.model_name}
            {provider.is_default ? ' (default)' : ''}
          </option>
        ))}
      </select>
      {helpText && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {helpText}
        </p>
      )}
    </div>
  );
}
