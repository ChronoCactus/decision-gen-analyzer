'use client';

import { useState } from 'react';
import { ADR } from '@/types/api';
import { PersonasModal } from './PersonasModal';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface ADRModalProps {
  adr: ADR;
  onClose: () => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}

export function ADRModal({ adr, onClose, onAnalyze, isAnalyzing }: ADRModalProps) {
  const [showPersonas, setShowPersonas] = useState(false);

  // Close this modal with ESC, but only if personas modal is not open
  useEscapeKey(onClose, !showPersonas);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'proposed':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'rejected':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'deprecated':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-start mb-6">
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                {adr.metadata.title}
              </h2>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>By {adr.metadata.author}</span>
                <span>{new Date(adr.metadata.created_at).toLocaleDateString()}</span>
                <span className={`px-3 py-1 rounded-full border ${getStatusColor(adr.metadata.status)}`}>
                  {adr.metadata.status}
                </span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl"
            >
              ×
            </button>
          </div>

          <div className="space-y-6">
            {/* Context & Problem */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Context & Problem</h3>
              <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{adr.content.context_and_problem}</p>
            </div>

            {/* Decision Outcome */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Decision Outcome</h3>
              <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">{adr.content.decision_outcome}</div>
            </div>

            {/* Consequences - Structured or plain text */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Consequences</h3>
              {adr.content.consequences_structured ? (
                <div className="space-y-3">
                  {adr.content.consequences_structured.positive.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-green-800 mb-2">✓ Positive</h4>
                      <ul className="list-disc list-inside text-gray-700 space-y-1 ml-2">
                        {adr.content.consequences_structured.positive.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {adr.content.consequences_structured.negative.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-red-800 mb-2">✗ Negative</h4>
                      <ul className="list-disc list-inside text-gray-700 space-y-1 ml-2">
                        {adr.content.consequences_structured.negative.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                  <div className="text-gray-700 leading-relaxed">
                    {adr.content.consequences.split('\n').map((line, index) => {
                      const trimmed = line.trim();
                      if (!trimmed) return null;

                      // Check if line starts with "✓ Positive" or "✗ Negative"
                      if (trimmed.startsWith('✓ Positive')) {
                        return <h4 key={index} className="text-md font-medium text-green-800 mt-3 mb-2">{trimmed}</h4>;
                      }
                      if (trimmed.startsWith('✗ Negative')) {
                        return <h4 key={index} className="text-md font-medium text-red-800 mt-3 mb-2">{trimmed}</h4>;
                      }

                      // Check if line starts with a bullet (- or •)
                      if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
                        const content = trimmed.substring(2).trim();
                        return (
                          <div key={index} className="flex items-start mb-1 ml-2">
                            <span className="text-gray-400 mr-2">•</span>
                            <span>{content}</span>
                          </div>
                        );
                      }

                      // Regular text line
                      return <p key={index} className="mb-1">{trimmed}</p>;
                    })}
                  </div>
              )}
            </div>

            {/* Considered Options */}
            {adr.content.considered_options && adr.content.considered_options.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Considered Options</h3>
                <ul className="list-disc list-inside text-gray-700 space-y-1">
                  {adr.content.considered_options.map((option, index) => (
                    <li key={index}>{option}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Options Details with Pros and Cons */}
            {adr.content.options_details && adr.content.options_details.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Pros & Cons of Options</h3>
                <div className="space-y-4">
                  {adr.content.options_details.map((option, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                      <h4 className="font-semibold text-gray-900 mb-1">{option.name}</h4>
                      {option.description && (
                        <p className="text-sm text-gray-600 mb-3">{option.description}</p>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {option.pros.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-green-700 mb-1">Pros</div>
                            <ul className="text-sm text-gray-700 space-y-1">
                              {option.pros.map((pro, idx) => (
                                <li key={idx} className="flex items-start">
                                  <span className="text-green-600 mr-2">✓</span>
                                  <span>{pro}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {option.cons.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-red-700 mb-1">Cons</div>
                            <ul className="text-sm text-gray-700 space-y-1">
                              {option.cons.map((con, idx) => (
                                <li key={idx} className="flex items-start">
                                  <span className="text-red-600 mr-2">✗</span>
                                  <span>{con}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Decision Drivers */}
            {adr.content.decision_drivers && adr.content.decision_drivers.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Decision Drivers</h3>
                <ul className="list-disc list-inside text-gray-700 space-y-1">
                  {adr.content.decision_drivers.map((driver, index) => (
                    <li key={index}>{driver}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* More Information */}
            {adr.content.more_information && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">More Information</h3>
                <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{adr.content.more_information}</p>
              </div>
            )}

            {/* Referenced ADRs */}
            {adr.content.referenced_adrs && adr.content.referenced_adrs.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Referenced ADRs</h3>
                <p className="text-sm text-gray-600 mb-2">This ADR was generated with context from the following ADRs:</p>
                <ul className="space-y-2">
                  {adr.content.referenced_adrs.map((ref, index) => (
                    <li key={index} className="border-l-2 border-blue-300 pl-3 py-1">
                      {/* <div className="font-mono text-sm text-blue-700 font-semibold">{ref.id}</div>
                      {ref.title && ref.title !== ref.id && (
                        <div className="text-xs text-gray-600 mt-0.5">{ref.title}</div>
                      )} */}
                      {ref.summary && (
                        <div className="text-xs text-gray-500 mt-1 italic">{ref.summary}</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Tags */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {adr.metadata.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-md"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex gap-4 mt-8 pt-6 border-t">
            {adr.persona_responses && adr.persona_responses.length > 0 && (
              <button
                onClick={() => setShowPersonas(true)}
                className="flex-1 bg-purple-600 text-white px-6 py-3 rounded-md hover:bg-purple-700 transition-colors font-medium"
              >
                Show Personas ({adr.persona_responses.length})
              </button>
            )}
            <button
              onClick={onAnalyze}
              disabled={isAnalyzing}
              className="flex-1 bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze ADR'}
            </button>
            <button
              onClick={onClose}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors font-medium"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {showPersonas && adr.persona_responses && (
        <PersonasModal
          personas={adr.persona_responses}
          onClose={() => setShowPersonas(false)}
        />
      )}
    </div>
  );
}
