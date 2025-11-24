'use client';

import { useState } from 'react';
import { ADR, ADRStatus, PersonaRefinementItem } from '@/types/api';
import { PersonasModal } from './PersonasModal';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { apiClient } from '@/lib/api';
import { Toast } from './Toast';

interface ADRModalProps {
  adr: ADR;
  onClose: () => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
  onADRUpdate?: (updatedAdr: ADR) => void;
  onRefineQueued?: (taskId: string) => void;
}

export function ADRModal({ adr, onClose, onAnalyze, isAnalyzing, onADRUpdate, onRefineQueued }: ADRModalProps) {
  const [showPersonas, setShowPersonas] = useState(false);
  const [currentAdr, setCurrentAdr] = useState<ADR>(adr);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [showBulkRefine, setShowBulkRefine] = useState(false);
  const [bulkRefinementPrompt, setBulkRefinementPrompt] = useState('');
  const [refinementToast, setRefinementToast] = useState<{ show: boolean; message: string; type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success'
  });

  // Close this modal with ESC, but only if personas modal is not open
  useEscapeKey(onClose, !showPersonas && !showBulkRefine);

  const handleStatusChange = async (newStatus: string) => {
    if (newStatus === currentAdr.metadata.status) {
      return; // No change
    }

    setIsUpdatingStatus(true);
    try {
      const response = await apiClient.updateADRStatus(currentAdr.metadata.id, newStatus);
      const updatedAdr = response.adr;
      setCurrentAdr(updatedAdr);
      
      // Notify parent component of the update
      if (onADRUpdate) {
        onADRUpdate(updatedAdr);
      }
    } catch (error) {
      console.error('Failed to update ADR status:', error);
      alert('Failed to update ADR status. Please try again.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleRefinePersonas = async (refinements: PersonaRefinementItem[], refinementsToDelete?: Record<string, number[]>) => {
    try {
      const response = await apiClient.refinePersonas(currentAdr.metadata.id, {
        refinements,
        refinements_to_delete: refinementsToDelete,
        provider_id: undefined // Use default provider
      });

      // Close both modals so user can see progress
      setShowPersonas(false);
      onClose();

      // Notify parent to start polling for the refinement task
      if (onRefineQueued) {
        onRefineQueued(response.task_id);
      }

    } catch (error) {
      console.error('Failed to refine personas:', error);
      setRefinementToast({
        show: true,
        message: 'Failed to queue persona refinement. Please try again.',
        type: 'error'
      });

      // Auto-hide error toast after 5 seconds
      setTimeout(() => {
        setRefinementToast({ show: false, message: '', type: 'success' });
      }, 5000);
    }
  };

  const handleBulkRefinement = async () => {
    if (!bulkRefinementPrompt.trim()) {
      return;
    }

    // Create refinement items for all personas with the same prompt
    const refinements: PersonaRefinementItem[] = currentAdr.persona_responses?.map(persona => ({
      persona: persona.persona,
      refinement_prompt: bulkRefinementPrompt
    })) || [];

    if (refinements.length === 0) {
      return;
    }

    // Reset bulk refine UI
    setShowBulkRefine(false);
    setBulkRefinementPrompt('');

    // Use the same handler as individual refinements
    await handleRefinePersonas(refinements);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-200 dark:border-green-700';
      case 'proposed':
        return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-700';
      case 'rejected':
        return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-200 dark:border-red-700';
      case 'deprecated':
        return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-600';
      case 'superseded':
        return 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-700';
      default:
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-700';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-start mb-6">
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                {currentAdr.metadata.title}
              </h2>
              <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                <span>By {currentAdr.metadata.author}</span>
                <span>{new Date(currentAdr.metadata.created_at).toLocaleDateString()}</span>
                <div className="relative">
                  <select
                    value={currentAdr.metadata.status}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    disabled={isUpdatingStatus}
                    className={`px-3 py-1 rounded-full border cursor-pointer text-sm font-medium transition-colors ${getStatusColor(currentAdr.metadata.status)} ${
                      isUpdatingStatus ? 'opacity-50 cursor-wait' : 'hover:opacity-80'
                    } focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800`}
                  >
                    <option value={ADRStatus.PROPOSED}>proposed</option>
                    <option value={ADRStatus.ACCEPTED}>accepted</option>
                    <option value={ADRStatus.REJECTED}>rejected</option>
                    <option value={ADRStatus.DEPRECATED}>deprecated</option>
                    <option value={ADRStatus.SUPERSEDED}>superseded</option>
                  </select>
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 text-2xl"
            >
              ×
            </button>
          </div>

          <div className="space-y-6">
            {/* Context & Problem */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Context & Problem</h3>
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{currentAdr.content.context_and_problem}</p>
            </div>

            {/* Decision Outcome */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Decision Outcome</h3>
              <div className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{currentAdr.content.decision_outcome}</div>
            </div>

            {/* Consequences - Structured or plain text */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Consequences</h3>
              {currentAdr.content.consequences_structured ? (
                <div className="space-y-3">
                  {currentAdr.content.consequences_structured.positive.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-green-800 dark:text-green-400 mb-2">✓ Positive</h4>
                      <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
                        {currentAdr.content.consequences_structured.positive.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {currentAdr.content.consequences_structured.negative.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-red-800 dark:text-red-400 mb-2">✗ Negative</h4>
                      <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 ml-2">
                        {currentAdr.content.consequences_structured.negative.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                  <div className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    {currentAdr.content.consequences.split('\n').map((line, index) => {
                      const trimmed = line.trim();
                      if (!trimmed) return null;

                      // Check if line starts with "✓ Positive" or "✗ Negative"
                      if (trimmed.startsWith('✓ Positive')) {
                        return <h4 key={index} className="text-md font-medium text-green-800 dark:text-green-400 mt-3 mb-2">{trimmed}</h4>;
                      }
                      if (trimmed.startsWith('✗ Negative')) {
                        return <h4 key={index} className="text-md font-medium text-red-800 dark:text-red-400 mt-3 mb-2">{trimmed}</h4>;
                      }

                      // Check if line starts with a bullet (- or •)
                      if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
                        const content = trimmed.substring(2).trim();
                        return (
                          <div key={index} className="flex items-start mb-1 ml-2">
                            <span className="text-gray-400 dark:text-gray-500 mr-2">•</span>
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
            {currentAdr.content.considered_options && currentAdr.content.considered_options.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Considered Options</h3>
                <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                  {currentAdr.content.considered_options.map((option, index) => (
                    <li key={index}>{option}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Options Details with Pros and Cons */}
            {currentAdr.content.options_details && currentAdr.content.options_details.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Pros & Cons of Options</h3>
                <div className="space-y-4">
                  {currentAdr.content.options_details.map((option, index) => (
                    <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50">
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">{option.name}</h4>
                      {option.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{option.description}</p>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {option.pros.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-green-700 dark:text-green-400 mb-1">Pros</div>
                            <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                              {option.pros.map((pro, idx) => (
                                <li key={idx} className="flex items-start">
                                  <span className="text-green-600 dark:text-green-400 mr-2">✓</span>
                                  <span>{pro}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {option.cons.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">Cons</div>
                            <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                              {option.cons.map((con, idx) => (
                                <li key={idx} className="flex items-start">
                                  <span className="text-red-600 dark:text-red-400 mr-2">✗</span>
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
            {currentAdr.content.decision_drivers && currentAdr.content.decision_drivers.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Decision Drivers</h3>
                <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                  {currentAdr.content.decision_drivers.map((driver, index) => (
                    <li key={index}>{driver}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* More Information */}
            {currentAdr.content.more_information && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">More Information</h3>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{currentAdr.content.more_information}</p>
              </div>
            )}

            {/* Referenced ADRs */}
            {currentAdr.content.referenced_adrs && currentAdr.content.referenced_adrs.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Referenced ADRs</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">This ADR was generated with context from the following ADRs:</p>
                <ul className="space-y-2">
                  {currentAdr.content.referenced_adrs.map((ref, index) => (
                    <li key={index} className="border-l-2 border-blue-300 dark:border-blue-700 pl-3 py-1">
                      {/* <div className="font-mono text-sm text-blue-700 font-semibold">{ref.id}</div>
                      {ref.title && ref.title !== ref.id && (
                        <div className="text-xs text-gray-600 mt-0.5">{ref.title}</div>
                      )} */}
                      {ref.summary && (
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">{ref.summary}</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Tags */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {currentAdr.metadata.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-sm rounded-md"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Bulk Refinement Section */}
          {showBulkRefine && currentAdr.persona_responses && currentAdr.persona_responses.length > 0 && (
            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Refine All Personas</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                This refinement prompt will be applied to all {currentAdr.persona_responses.length} personas to regenerate their perspectives and create a new ADR.
              </p>
              <textarea
                value={bulkRefinementPrompt}
                onChange={(e) => setBulkRefinementPrompt(e.target.value)}
                placeholder="Enter refinement instructions to apply to all personas..."
                className="w-full px-4 py-3 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                rows={4}
              />
              <div className="flex gap-3 mt-3">
                <button
                  onClick={handleBulkRefinement}
                  disabled={!bulkRefinementPrompt.trim()}
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  Submit Bulk Refinement
                </button>
                <button
                  onClick={() => {
                    setShowBulkRefine(false);
                    setBulkRefinementPrompt('');
                  }}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="flex gap-4 mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
            {currentAdr.persona_responses && currentAdr.persona_responses.length > 0 && (
              <>
                <button
                  onClick={() => setShowPersonas(true)}
                  className="flex-1 bg-purple-600 text-white px-6 py-3 rounded-md hover:bg-purple-700 transition-colors font-medium"
                >
                  Show Personas ({currentAdr.persona_responses.length})
                </button>
                <button
                  onClick={() => setShowBulkRefine(!showBulkRefine)}
                  className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 transition-colors font-medium"
                >
                  {showBulkRefine ? 'Hide Bulk Refine' : 'Refine All Personas'}
                </button>
              </>
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
              className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors font-medium"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {showPersonas && currentAdr.persona_responses && (
        <PersonasModal
          personas={currentAdr.persona_responses}
          adrId={currentAdr.metadata.id}
          onClose={() => setShowPersonas(false)}
          onRefine={handleRefinePersonas}
        />
      )}

      {refinementToast.show && (
        <Toast
          message={refinementToast.message}
          type={refinementToast.type}
          onClose={() => setRefinementToast({ show: false, message: '', type: 'success' })}
        />
      )}
    </div>
  );
}
