'use client';

import { useState } from 'react';
import { PersonaResponse, PersonaRefinementItem } from '@/types/api';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface PersonasModalProps {
  personas: PersonaResponse[];
  adrId: string;
  onClose: () => void;
  onRefine?: (refinements: PersonaRefinementItem[]) => void;
}

export function PersonasModal({ personas, onClose, onRefine }: PersonasModalProps) {
  // Close this modal with ESC key
  useEscapeKey(onClose);

  // Track which personas are being refined and their refinement prompts
  const [refining, setRefining] = useState<Record<string, boolean>>({});
  const [refinementPrompts, setRefinementPrompts] = useState<Record<string, string>>({});
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

  const handleSubmitRefinements = async () => {
    if (!onRefine) return;

    // Collect all refinements with non-empty prompts
    const refinements: PersonaRefinementItem[] = Object.entries(refinementPrompts)
      .filter(([prompt]) => prompt.trim().length > 0)
      .map(([persona, prompt]) => ({
        persona,
        refinement_prompt: prompt
      }));

    if (refinements.length === 0) return;

    setIsSubmitting(true);
    try {
      await onRefine(refinements);
      // Reset state after successful submission
      setRefining({});
      setRefinementPrompts({});
    } catch (error) {
      console.error('Failed to refine personas:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Check if there are any valid refinements ready to submit
  const hasRefinements = Object.values(refinementPrompts).some(prompt => prompt.trim().length > 0);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-[60] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6 flex justify-between items-center">
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

        <div className="p-6 space-y-6">
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

        <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
          {hasRefinements ? (
            <div className="space-y-2">
              <button
                onClick={handleSubmitRefinements}
                disabled={isSubmitting}
                className="w-full bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {isSubmitting ? 'Submitting...' : `Submit Refinements (${Object.keys(refinementPrompts).length})`}
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
