'use client';

import { useState, useRef, useEffect } from 'react';
import { PersonaResponse, PersonaRefinementItem, Persona, LLMProvider } from '@/types/api';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { apiClient } from '@/lib/api';
import { PersonaSelector } from './PersonaSelector';
import { SynthesisModelSelector } from './SynthesisModelSelector';

interface PersonasModalProps {
  personas: PersonaResponse[];
  adrId: string;
  onClose: () => void;
  onRefine?: (refinements: PersonaRefinementItem[], refinementsToDelete?: Record<string, number[]>, personaProviderOverrides?: Record<string, string>, synthesisProviderId?: string) => void;
  onADRUpdate?: () => void;
}

export function PersonasModal({ personas, adrId, onClose, onRefine, onADRUpdate }: PersonasModalProps) {
  // Close this modal with ESC key
  useEscapeKey(onClose);

  // Manual editing state (bulk edit all personas)
  const [isManualEditMode, setIsManualEditMode] = useState(false);
  const [editedPersonasJson, setEditedPersonasJson] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [resynthesizeChecked, setResynthesizeChecked] = useState(false);
  const [synthesisProviderIdForManual, setSynthesisProviderIdForManual] = useState<string>('');

  // Individual persona manual editing state
  const [editingPersona, setEditingPersona] = useState<Record<string, boolean>>({});
  const [editedPersonaJson, setEditedPersonaJson] = useState<Record<string, string>>({});
  const [personaJsonError, setPersonaJsonError] = useState<Record<string, string | null>>({});
  const [personaResynthesizeChecked, setPersonaResynthesizeChecked] = useState<Record<string, boolean>>({});
  const [personaSynthesisProviderId, setPersonaSynthesisProviderId] = useState<Record<string, string>>({});

  // Track which personas are being refined and their refinement prompts
  const [refining, setRefining] = useState<Record<string, boolean>>({});
  const [refinementPrompts, setRefinementPrompts] = useState<Record<string, string>>({});
  const [refinementsToDelete, setRefinementsToDelete] = useState<Record<string, number[]>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const refinementRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const manualEditRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const bulkManualEditRef = useRef<HTMLDivElement | null>(null);

  // Model selection state
  const [allPersonas, setAllPersonas] = useState<Persona[]>([]);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');
  const [synthesisProviderId, setSynthesisProviderId] = useState<string>('');
  const [loadingModels, setLoadingModels] = useState(true);
  const [personaProviderOverrides, setPersonaProviderOverrides] = useState<Record<string, string>>({});

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
          setSynthesisProviderId(defaultProvider.id);
        }
      })
      .catch(error => {
        console.error('Failed to load personas or providers:', error);
      })
      .finally(() => {
        setLoadingModels(false);
      });
  }, []);

  // Scroll to refinement section when a persona's refine mode is activated
  useEffect(() => {
    // Find the persona that was just set to refining
    const justActivated = Object.keys(refining).find(persona => refining[persona]);
    if (justActivated && refinementRefs.current[justActivated]) {
      refinementRefs.current[justActivated]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [refining]);

  // Scroll to manual edit section when a persona's manual edit mode is activated
  useEffect(() => {
    // Find the persona that was just set to editing
    const justActivated = Object.keys(editingPersona).find(persona => editingPersona[persona]);
    if (justActivated && manualEditRefs.current[justActivated]) {
      manualEditRefs.current[justActivated]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [editingPersona]);

  // Scroll to bulk manual edit section when activated
  useEffect(() => {
    if (isManualEditMode && bulkManualEditRef.current) {
      bulkManualEditRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [isManualEditMode]);

  const formatPersonaName = (persona: string) => {
    return persona
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
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

  const handleToggleRefine = (persona: string) => {
    setRefining(prev => ({
      ...prev,
      [persona]: !prev[persona]
    }));
    // Clear the refinement prompt if we're toggling off
    if (refining[persona]) {
      setRefinementPrompts(prev => {
        const newPrompts = { ...prev };
        delete newPrompts[persona];
        return newPrompts;
      });
    }
  };

  const handleRefinementPromptChange = (persona: string, prompt: string) => {
    setRefinementPrompts(prev => ({
      ...prev,
      [persona]: prompt
    }));
  };

  const handleToggleRefinementDeletion = (persona: string, index: number) => {
    setRefinementsToDelete(prev => {
      const personaDeletions = prev[persona] || [];
      const isMarked = personaDeletions.includes(index);

      if (isMarked) {
        // Remove from deletion list
        const updated = personaDeletions.filter(i => i !== index);
        if (updated.length === 0) {
          const newPrev = { ...prev };
          delete newPrev[persona];
          return newPrev;
        }
        return { ...prev, [persona]: updated };
      } else {
        // Add to deletion list
        return { ...prev, [persona]: [...personaDeletions, index] };
      }
    });
  };

  const handleSubmitRefinements = async () => {
    if (!onRefine) return;

    // Collect all refinements with non-empty prompts
    const refinements: PersonaRefinementItem[] = Object.entries(refinementPrompts)
      .filter(([, prompt]) => prompt.trim().length > 0)
      .map(([persona, prompt]) => ({
        persona,
        refinement_prompt: prompt
      }));

    // Check if there are any changes to submit
    if (refinements.length === 0 && Object.keys(refinementsToDelete).length === 0) {
      return;
    }

    setIsSubmitting(true);
    try {      // Pass refinements, deletions, and model selections (including per-persona overrides)
      // Only pass synthesis provider ID if there are actual refinements (not just deletions)
      await onRefine(
        refinements,
        refinementsToDelete,
        personaProviderOverrides,
        refinements.length > 0 ? (synthesisProviderId || undefined) : undefined
      );
      // Reset state after successful submission
      setRefining({});
      setRefinementPrompts({});
      setRefinementsToDelete({});
      setPersonaProviderOverrides({});
    } catch (error) {
      console.error('Failed to refine personas:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Check if there are any valid refinements or deletions ready to submit
  const hasChanges =
    Object.values(refinementPrompts).some(prompt => prompt.trim().length > 0) ||
    Object.keys(refinementsToDelete).length > 0;

  // Manual editing handlers (bulk edit all personas)
  const handleEnterManualEdit = () => {
    setIsManualEditMode(true);
    setEditedPersonasJson(JSON.stringify(personas, null, 2));
    setJsonError(null);
  };

  const handleCancelManualEdit = () => {
    setIsManualEditMode(false);
    setEditedPersonasJson('');
    setJsonError(null);
    setResynthesizeChecked(false);
  };

  // Individual persona manual editing handlers
  const handleTogglePersonaEdit = (personaName: string, persona: any) => {
    setEditingPersona(prev => {
      const newEditing = { ...prev, [personaName]: !prev[personaName] };

      // If entering edit mode, initialize the JSON and default states
      if (newEditing[personaName]) {
        setEditedPersonaJson(prev => ({
          ...prev,
          [personaName]: JSON.stringify(persona, null, 2)
        }));
        setPersonaJsonError(prev => ({ ...prev, [personaName]: null }));
        setPersonaResynthesizeChecked(prev => ({ ...prev, [personaName]: false }));
        // Set default synthesis provider
        const defaultProvider = providers.find(p => p.is_default);
        if (defaultProvider) {
          setPersonaSynthesisProviderId(prev => ({ ...prev, [personaName]: defaultProvider.id }));
        }
      } else {
        // If exiting edit mode, clean up
        const newJson = { ...editedPersonaJson };
        delete newJson[personaName];
        setEditedPersonaJson(newJson);

        const newErrors = { ...personaJsonError };
        delete newErrors[personaName];
        setPersonaJsonError(newErrors);

        const newResynthesize = { ...personaResynthesizeChecked };
        delete newResynthesize[personaName];
        setPersonaResynthesizeChecked(newResynthesize);

        const newProviderId = { ...personaSynthesisProviderId };
        delete newProviderId[personaName];
        setPersonaSynthesisProviderId(newProviderId);
      }

      return newEditing;
    });
  };

  const handlePersonaJsonChange = (personaName: string, value: string) => {
    setEditedPersonaJson(prev => ({
      ...prev,
      [personaName]: value
    }));
    setPersonaJsonError(prev => ({ ...prev, [personaName]: null }));
  };

  const handleSaveIndividualPersona = async (personaName: string) => {
    try {
      const jsonValue = editedPersonaJson[personaName];
      if (!jsonValue) return;

      // Validate JSON
      const parsed = JSON.parse(jsonValue);

      // Validate it's an object with a persona field
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        setPersonaJsonError(prev => ({
          ...prev,
          [personaName]: 'Persona must be a valid JSON object'
        }));
        return;
      }

      if (!parsed.persona || typeof parsed.persona !== 'string') {
        setPersonaJsonError(prev => ({
          ...prev,
          [personaName]: 'Persona must have a "persona" field with a string value'
        }));
        return;
      }

      setPersonaJsonError(prev => ({ ...prev, [personaName]: null }));

      // Replace the edited persona in the full array
      const updatedPersonas = personas.map(p =>
        p.persona === personaName ? parsed : p
      );

      const shouldResynthesize = personaResynthesizeChecked[personaName] || false;
      const synthesisProvider = shouldResynthesize ? personaSynthesisProviderId[personaName] : undefined;

      // Save all personas with the updated one
      await apiClient.saveManualPersonaEdits(
        adrId,
        updatedPersonas,
        shouldResynthesize,
        synthesisProvider
      );

      // Exit edit mode for this persona
      setEditingPersona(prev => ({ ...prev, [personaName]: false }));

      // Clean up state
      const newJson = { ...editedPersonaJson };
      delete newJson[personaName];
      setEditedPersonaJson(newJson);

      const newResynthesize = { ...personaResynthesizeChecked };
      delete newResynthesize[personaName];
      setPersonaResynthesizeChecked(newResynthesize);

      const newProviderId = { ...personaSynthesisProviderId };
      delete newProviderId[personaName];
      setPersonaSynthesisProviderId(newProviderId);

      // Refresh the ADR to show updated data before closing
      if (onADRUpdate) {
        await onADRUpdate();
      }

      // Close modal
      onClose();
    } catch (error) {
      if (error instanceof SyntaxError) {
        setPersonaJsonError(prev => ({
          ...prev,
          [personaName]: `Invalid JSON: ${error.message}`
        }));
      } else {
        setPersonaJsonError(prev => ({
          ...prev,
          [personaName]: `Failed to save: ${error instanceof Error ? error.message : String(error)}`
        }));
      }
    }
  };

  const validateAndSaveManualEdit = async () => {
    try {
      // Validate JSON
      const parsed = JSON.parse(editedPersonasJson);

      // Validate it's an array
      if (!Array.isArray(parsed)) {
        setJsonError('JSON must be an array of persona responses');
        return;
      }

      // Basic validation of persona structure
      for (const persona of parsed) {
        if (!persona.persona || typeof persona.persona !== 'string') {
          setJsonError('Each persona must have a "persona" field with a string value');
          return;
        }
      }

      setJsonError(null);
      setIsSaving(true);

      // Call API to save manual edits
      await apiClient.saveManualPersonaEdits(
        adrId,
        parsed,
        resynthesizeChecked,
        resynthesizeChecked ? synthesisProviderIdForManual : undefined
      );

      // Refresh the ADR to show updated data before closing
      if (onADRUpdate) {
        await onADRUpdate();
      }

      // Close modal
      onClose();
    } catch (error) {
      if (error instanceof SyntaxError) {
        setJsonError(`Invalid JSON: ${error.message}`);
      } else {
        setJsonError(`Failed to save: ${error instanceof Error ? error.message : String(error)}`);
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-[60] sm:p-4">
      <div className="bg-white dark:bg-gray-800 w-full h-full sm:h-auto sm:max-w-4xl sm:max-h-[90vh] sm:rounded-lg shadow-2xl flex flex-col">
        <div className="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4 sm:p-6 relative">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100 pr-12 mb-2">Individual Persona Responses</h2>
              <div className="flex gap-2">
                <button
                  onClick={() => isManualEditMode ? handleCancelManualEdit() : handleEnterManualEdit()}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${isManualEditMode
                    ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                    : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                    }`}
                >
                  {isManualEditMode ? 'Cancel Manual Edit' : 'Manual Edit (JSON)'}
                </button>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Manual Edit Mode */}
        {isManualEditMode ? (
          <div className="flex-1 overflow-y-auto p-6">
            <div ref={bulkManualEditRef} className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Edit Personas as JSON</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Edit the JSON below to manually modify persona responses. The JSON will be validated before saving.
              </p>

              <textarea
                value={editedPersonasJson}
                onChange={(e) => {
                  setEditedPersonasJson(e.target.value);
                  setJsonError(null);
                }}
                className="w-full h-96 px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                spellCheck={false}
              />

              {jsonError && (
                <div className="mt-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-800 rounded-md">
                  <p className="text-sm text-red-700 dark:text-red-400">{jsonError}</p>
                </div>
              )}

              <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={resynthesizeChecked}
                    onChange={(e) => setResynthesizeChecked(e.target.checked)}
                    className="mt-0.5 mr-3"
                  />
                  <div className="flex-1">
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      Resynthesize final decision record
                    </span>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                      If checked, the AI will synthesize a new final decision record from your edited personas (no regeneration).
                      If unchecked, only the manual edits will be saved.
                    </p>
                  </div>
                </label>

                {resynthesizeChecked && !loadingModels && providers.length > 0 && (
                  <div className="mt-3">
                    <SynthesisModelSelector
                      providers={providers}
                      selectedProviderId={synthesisProviderIdForManual}
                      onSelectProvider={setSynthesisProviderIdForManual}
                      label="Synthesis Model"
                      helpText="Model used to synthesize the final decision record from edited personas"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <>
              {/* Show personas being refined with model info */}
              {Object.keys(refining).some(p => refining[p]) && !loadingModels && allPersonas.length > 0 && (
          <div className="flex-shrink-0 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800 p-4">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
              Personas Being Refined
            </h3>
            <PersonaSelector
              personas={allPersonas.filter(p => Object.keys(refining).some(rp => rp === p.value && refining[rp]))}
              selectedPersonas={Object.keys(refining).filter(p => refining[p])}
              onTogglePersona={() => { }}
              getModelDisplay={getModelDisplay}
              readOnly={false}
              compact={true}
              providers={providers}
              personaProviderOverrides={personaProviderOverrides}
              onPersonaProviderChange={(personaValue, providerId) => {
                setPersonaProviderOverrides(prev => ({
                  ...prev,
                  [personaValue]: providerId
                }));
              }}
              allowModelSelection={true}
            />

            <div className="mt-4">
              <SynthesisModelSelector
                providers={providers}
                selectedProviderId={synthesisProviderId}
                onSelectProvider={setSynthesisProviderId}
                label="Synthesis Model"
                helpText="Model used to synthesize refined perspectives into the final decision record"
              />
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {personas.map((persona, index) => (
            <div key={index} className="bg-gradient-to-br from-gray-50 to-white dark:from-gray-700 dark:to-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg p-6 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start flex-1 pr-4">
                  <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-2xl">
                      {persona.persona === 'technical_lead' && '👨‍💻'}
                      {persona.persona === 'architect' && '🏗️'}
                      {persona.persona === 'business_analyst' && '📊'}
                      {persona.persona === 'risk_manager' && '⚠️'}
                      {persona.persona === 'product_manager' && '📱'}
                      {persona.persona === 'customer_support' && '🎧'}
                      {persona.persona === 'security_expert' && '🔒'}
                      {persona.persona === 'devops_engineer' && '⚙️'}
                      {persona.persona === 'qa_engineer' && '✅'}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                      {formatPersonaName(persona.persona)}
                    </h3>
                    {persona.recommended_option && (
                      <span className="inline-block mt-1 px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 text-sm rounded-full">
                        Recommends: {persona.recommended_option}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleTogglePersonaEdit(persona.persona, persona)}
                    className={`px-4 py-2 rounded-md transition-colors font-medium ${editingPersona[persona.persona]
                      ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                      : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-900/50'
                      }`}
                  >
                    {editingPersona[persona.persona] ? 'Cancel' : 'Manual'}
                  </button>
                  <button
                    onClick={() => handleToggleRefine(persona.persona)}
                    className={`px-4 py-2 rounded-md transition-colors font-medium ${refining[persona.persona]
                      ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                  >
                    {refining[persona.persona] ? 'Cancel' : 'Refine'}
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                    {persona.proposed_principle ? 'Proposed Principle' : 'Perspective'}
                  </h4>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    {persona.proposed_principle || persona.perspective}
                  </p>
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                    {persona.rationale ? 'Rationale' : 'Reasoning'}
                  </h4>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    {persona.rationale || persona.reasoning}
                  </p>
                </div>

                {persona.implications && persona.implications.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Implications
                    </h4>
                    <ul className="space-y-1">
                      {persona.implications.map((item, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-blue-500 mr-2 mt-1">•</span>
                          <span className="text-gray-700 dark:text-gray-300">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {persona.counter_arguments && persona.counter_arguments.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Counter Arguments
                    </h4>
                    <ul className="space-y-1">
                      {persona.counter_arguments.map((item, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-red-500 mr-2 mt-1">✗</span>
                          <span className="text-gray-700 dark:text-gray-300">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {persona.proof_statements && persona.proof_statements.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Proof Statements
                    </h4>
                    <ul className="space-y-1">
                      {persona.proof_statements.map((item, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-green-500 mr-2 mt-1">✓</span>
                          <span className="text-gray-700 dark:text-gray-300">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {persona.exceptions && persona.exceptions.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Exceptions
                    </h4>
                    <ul className="space-y-1">
                      {persona.exceptions.map((item, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-yellow-500 mr-2 mt-1">!</span>
                          <span className="text-gray-700 dark:text-gray-300">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {persona.concerns && persona.concerns.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Key Concerns
                    </h4>
                    <ul className="space-y-1">
                      {persona.concerns.map((concern, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-yellow-500 mr-2 mt-1">⚠️</span>
                          <span className="text-gray-700 dark:text-gray-300">{concern}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {persona.requirements && persona.requirements.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Requirements
                    </h4>
                    <ul className="space-y-1">
                      {persona.requirements.map((req, i) => (
                        <li key={i} className="flex items-start">
                          <span className="text-blue-500 mr-2 mt-1">✓</span>
                          <span className="text-gray-700 dark:text-gray-300">{req}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {persona.refinement_history && persona.refinement_history.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                      Refinement History ({persona.refinement_history.length})
                    </h4>
                    <div className="space-y-2">
                      {persona.refinement_history.map((refinement, i) => {
                        const isMarkedForDeletion = refinementsToDelete[persona.persona]?.includes(i);
                        return (
                          <div
                            key={i}
                            className={`border rounded-md p-3 transition-all ${isMarkedForDeletion
                                ? 'bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-800 opacity-50'
                                : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                              }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className={`text-xs font-semibold ${isMarkedForDeletion
                                  ? 'text-red-700 dark:text-red-400 line-through'
                                  : 'text-blue-700 dark:text-blue-400'
                                }`}>
                                Refinement #{i + 1}
                                {isMarkedForDeletion && ' (Pending Deletion)'}
                              </span>
                              <button
                                onClick={() => handleToggleRefinementDeletion(persona.persona, i)}
                                className={`text-xs px-2 py-1 rounded transition-colors ${isMarkedForDeletion
                                    ? 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                                    : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50'
                                  }`}
                              >
                                {isMarkedForDeletion ? 'Undo' : 'Delete'}
                              </button>
                            </div>
                            <p className={`text-sm italic ${isMarkedForDeletion
                                ? 'text-gray-500 dark:text-gray-500 line-through'
                                : 'text-gray-700 dark:text-gray-300'
                              }`}>
                              {refinement}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {refining[persona.persona] && (
                <div ref={el => { refinementRefs.current[persona.persona] = el; }} className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                    Refinement Prompt
                  </label>
                  <textarea
                    value={refinementPrompts[persona.persona] || ''}
                    onChange={(e) => handleRefinementPromptChange(persona.persona, e.target.value)}
                    placeholder="Enter additional instructions to refine this persona's perspective..."
                    className="w-full px-4 py-3 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                    rows={4}
                  />
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    This prompt will be combined with the original request to regenerate this persona&apos;s perspective.
                  </p>
                </div>
              )}

              {editingPersona[persona.persona] && (
                <div ref={el => { manualEditRefs.current[persona.persona] = el; }} className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                    Manual Edit (JSON)
                  </label>
                  <textarea
                    value={editedPersonaJson[persona.persona] || ''}
                    onChange={(e) => handlePersonaJsonChange(persona.persona, e.target.value)}
                    className="w-full h-64 px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-mono text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500 dark:focus:ring-purple-400"
                    spellCheck={false}
                  />
                  {personaJsonError[persona.persona] && (
                    <div className="mt-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-800 rounded-md">
                      <p className="text-sm text-red-700 dark:text-red-400">{personaJsonError[persona.persona]}</p>
                    </div>
                  )}

                  <div className="mt-4 p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-md">
                    <label className="flex items-start">
                      <input
                        type="checkbox"
                        checked={personaResynthesizeChecked[persona.persona] || false}
                        onChange={(e) => setPersonaResynthesizeChecked(prev => ({
                          ...prev,
                          [persona.persona]: e.target.checked
                        }))}
                        className="mt-0.5 mr-3"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          Resynthesize final decision record
                        </span>
                        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                          If checked, the AI will synthesize a new final decision record from the edited persona.
                          If unchecked, only the manual edit will be saved.
                        </p>
                      </div>
                    </label>

                    {personaResynthesizeChecked[persona.persona] && !loadingModels && providers.length > 0 && (
                      <div className="mt-3">
                        <SynthesisModelSelector
                          providers={providers}
                          selectedProviderId={personaSynthesisProviderId[persona.persona] || ''}
                          onSelectProvider={(providerId) => setPersonaSynthesisProviderId(prev => ({
                            ...prev,
                            [persona.persona]: providerId
                          }))}
                          label="Synthesis Model"
                          helpText="Model used to synthesize the final decision record"
                        />
                      </div>
                    )}
                  </div>

                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => handleSaveIndividualPersona(persona.persona)}
                      disabled={!editedPersonaJson[persona.persona]?.trim()}
                      className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium text-sm"
                    >
                      {personaResynthesizeChecked[persona.persona] ? 'Save & Resynthesize' : 'Save Changes'}
                    </button>
                    <button
                      onClick={() => handleTogglePersonaEdit(persona.persona, persona)}
                      className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors font-medium text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                  <p className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                    Edit this persona&apos;s JSON directly. {personaResynthesizeChecked[persona.persona] ? 'The final ADR will be resynthesized after saving.' : 'Changes are saved without AI regeneration.'}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>

              {/* Footer for refinement mode */}
              {!isManualEditMode && hasChanges && (
          <div className="flex-shrink-0 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
            <div className="space-y-2">
              <button
                onClick={handleSubmitRefinements}
                disabled={isSubmitting}
                className="w-full bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {isSubmitting ? 'Submitting...' : `Submit Changes (${Object.keys(refinementPrompts).length + Object.keys(refinementsToDelete).length})`}
              </button>
              <button
                onClick={() => {
                  setRefining({});
                  setRefinementPrompts({});
                  setRefinementsToDelete({});
                }}
                className="w-full bg-transparent text-gray-600 dark:text-gray-400 px-6 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-sm"
              >
                Cancel Changes
              </button>
            </div>
          </div>
        )}

            {/* Footer for manual edit mode */}
            {isManualEditMode && (
              <div className="flex-shrink-0 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
                <div className="space-y-2">
                  <button
                    onClick={validateAndSaveManualEdit}
                    disabled={isSaving || !editedPersonasJson.trim()}
                    className="w-full bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium"
                  >
                    {isSaving ? 'Saving...' : resynthesizeChecked ? 'Save & Resynthesize' : 'Save Manual Edits'}
                  </button>
                  <button
                    onClick={handleCancelManualEdit}
                    disabled={isSaving}
                    className="w-full bg-transparent text-gray-600 dark:text-gray-400 px-6 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-sm disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
