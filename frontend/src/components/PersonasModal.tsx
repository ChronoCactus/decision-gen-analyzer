'use client';

import { PersonaResponse } from '@/types/api';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface PersonasModalProps {
  personas: PersonaResponse[];
  onClose: () => void;
}

export function PersonasModal({ personas, onClose }: PersonasModalProps) {
  // Close this modal with ESC key
  useEscapeKey(onClose);

  const formatPersonaName = (persona: string) => {
    return persona
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

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
              <div className="flex items-center mb-4">
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
            </div>
          ))}
        </div>

        <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
          <button
            onClick={onClose}
            className="w-full bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
