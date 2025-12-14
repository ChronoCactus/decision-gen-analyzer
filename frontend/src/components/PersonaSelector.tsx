'use client';

import { Persona, LLMProvider } from '@/types/api';

interface PersonaSelectorProps {
  personas: Persona[];
  selectedPersonas: string[];
  onTogglePersona: (personaValue: string) => void;
  getModelDisplay: (persona: Persona) => string;
  readOnly?: boolean;
  compact?: boolean;
  // New props for per-persona model selection
  providers?: LLMProvider[];
  personaProviderOverrides?: Record<string, string>; // persona_value -> provider_id
  onPersonaProviderChange?: (personaValue: string, providerId: string) => void;
  allowModelSelection?: boolean;
}

/**
 * Reusable persona selector component with checkboxes and model badges/dropdowns.
 * Used in both GenerateADRModal and refinement flows.
 * 
 * When allowModelSelection=true, displays dropdowns to change each persona's model.
 */
export function PersonaSelector({
  personas,
  selectedPersonas,
  onTogglePersona,
  getModelDisplay,
  readOnly = false,
  compact = false,
  providers = [],
  personaProviderOverrides = {},
  onPersonaProviderChange,
  allowModelSelection = false,
}: PersonaSelectorProps) {
  const getPersonaProviderDisplay = (persona: Persona): string => {
    // Check if there's an override
    const overrideProviderId = personaProviderOverrides[persona.value];
    if (overrideProviderId && providers.length > 0) {
      const provider = providers.find(p => p.id === overrideProviderId);
      if (provider) {
        return `${provider.provider_type}/${provider.model_name}`;
      }
    }
    
    // Fall back to persona's configured model or getModelDisplay
    return getModelDisplay(persona);
  };

  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 ${compact ? 'gap-2' : 'gap-3'}`}>
      {personas.map((persona) => {
        const isSelected = selectedPersonas.includes(persona.value);
        
        return (
          <label
            key={persona.value}
            className={`flex items-start ${compact ? 'p-2' : 'p-3'} border rounded-md ${
              readOnly ? 'cursor-default' : 'cursor-pointer'
            } transition-colors ${
              isSelected
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-400'
                : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 bg-white dark:bg-gray-700/50'
            } ${readOnly && !isSelected ? 'opacity-50' : ''}`}
          >
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => !readOnly && onTogglePersona(persona.value)}
              disabled={readOnly}
              className="mt-1 mr-3 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded disabled:opacity-50"
            />
            <div className="flex-1 min-w-0">
              <div className="flex flex-col gap-1.5 mb-1">
                <div className={`font-medium ${compact ? 'text-xs' : 'text-sm'} text-gray-900 dark:text-gray-100`}>
                  {persona.label}
                </div>
                
                {/* Model selection: dropdown if allowed, otherwise badge */}
                {allowModelSelection && providers.length > 0 && onPersonaProviderChange ? (
                  <select
                    value={personaProviderOverrides[persona.value] || ''}
                    onChange={(e) => {
                      e.stopPropagation();
                      onPersonaProviderChange(persona.value, e.target.value);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className={`${compact ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2 py-1'} w-full rounded border border-gray-300 dark:border-gray-500 bg-white dark:bg-gray-600 text-gray-700 dark:text-gray-200 font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 truncate`}
                  >
                    <option value="">
                      Default ({getPersonaProviderDisplay(persona)})
                    </option>
                    {providers.map(provider => (
                      <option key={provider.id} value={provider.id}>
                        {provider.provider_type}/{provider.model_name}
                      </option>
                    ))}
                  </select>
                ) : (
                    <div className={`${compact ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2 py-0.5'} rounded-full bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 flex-shrink-0`}>
                    {getPersonaProviderDisplay(persona)}
                  </div>
                )}
              </div>
              <div className={`${compact ? 'text-xs' : 'text-xs'} text-gray-500 dark:text-gray-400 mt-1`}>
                {persona.description}
              </div>
            </div>
          </label>
        );
      })}
    </div>
  );
}
