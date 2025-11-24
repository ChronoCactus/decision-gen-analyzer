'use client';

import { useState } from 'react';
import { PersonaResponse, PersonaRefinementItem } from '@/types/api';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface PersonasModalProps {
  personas: PersonaResponse[];
  adrId: string;
  onClose: () => void;
  onRefine?: (refinements: PersonaRefinementItem[], refinementsToDelete?: Record<string, number[]>) => void;
}

export function PersonasModal({ personas, onClose, onRefine }: PersonasModalProps) {
  // Close this modal with ESC key
  useEscapeKey(onClose);

  // Track which personas are being refined and their refinement prompts
  const [refining, setRefining] = useState<Record<string, boolean>>({});
  const [refinementPrompts, setRefinementPrompts] = useState<Record<string, string>>({});
  const [refinementsToDelete, setRefinementsToDelete] = useState<Record<string, number[]>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const formatPersonaName = (persona: string) => {
    return persona
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
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
    try {
      // Pass both refinements and deletions
      await onRefine(refinements, refinementsToDelete);
      // Reset state after successful submission
      setRefining({});
      setRefinementPrompts({});
      setRefinementsToDelete({});
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

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-[60] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        <div className="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Individual Persona Responses</h2>
          <button
            onClick={onClose}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {personas.map((persona, index) => (
            <div key={index} className="bg-gradient-to-br from-gray-50 to-white dark:from-gray-700 dark:to-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mr-4">
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

              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                    Perspective
                  </h4>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">{persona.perspective}</p>
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                    Reasoning
                  </h4>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">{persona.reasoning}</p>
                </div>

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
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
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
            </div>
          ))}
        </div>

        <div className="flex-shrink-0 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
          {hasChanges ? (
            <div className="space-y-2">
              <button
                onClick={handleSubmitRefinements}
                disabled={isSubmitting}
                className="w-full bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {isSubmitting ? 'Submitting...' : `Submit Changes (${Object.keys(refinementPrompts).length + Object.keys(refinementsToDelete).length})`}
              </button>
              <button
                onClick={onClose}
                className="w-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-6 py-3 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          ) : (
              <button
                onClick={onClose}
                className="w-full bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 transition-colors font-medium"
              >
                Close
              </button>
          )}
        </div>
      </div>
    </div>
  );
}
