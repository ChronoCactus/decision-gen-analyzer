'use client';

import { useState } from 'react';
import Link from 'next/link';
import { PersonaList } from '@/components/PersonaWizard/PersonaList';
import { PersonaEditor } from '@/components/PersonaWizard/PersonaEditor';
import { PersonaGenerator } from '@/components/PersonaWizard/PersonaGenerator';
import { DiffViewer, ArrayDiffViewer } from '@/components/PersonaWizard/DiffViewer';
import { apiClient } from '@/lib/api';
import { PersonaConfig, PersonaCreateRequest, PersonaUpdateRequest } from '@/types/api';

export default function PersonasPage() {
  const [view, setView] = useState<'list' | 'create' | 'edit'>('list');
  const [createMode, setCreateMode] = useState<'manual' | 'ai'>('manual');
  const [selectedPersona, setSelectedPersona] = useState<string | null>(null);
  const [personaData, setPersonaData] = useState<PersonaConfig | undefined>(undefined);
  
  // For AI Refinement/Generation Diff
  const [draftPersona, setDraftPersona] = useState<PersonaConfig | null>(null);
  const [refinementPrompt, setRefinementPrompt] = useState('');
  const [isRefining, setIsRefining] = useState(false);

  const handleSelectPersona = async (name: string) => {
    try {
      const data = await apiClient.getPersona(name);
      setPersonaData(data);
      setSelectedPersona(name);
      setView('edit');
      setDraftPersona(null);
    } catch (err) {
      console.error('Failed to load persona', err);
    }
  };

  const handleCreate = () => {
    setPersonaData(undefined);
    setSelectedPersona(null);
    setView('create');
    setCreateMode('manual'); // Default
  };

  const handleSave = async (data: PersonaCreateRequest | PersonaUpdateRequest) => {
    if (selectedPersona) {
      await apiClient.updatePersona(selectedPersona, data);
    } else {
      await apiClient.createPersona(data as PersonaCreateRequest);
    }
    setView('list');
  };

  const handleGenerated = (persona: PersonaConfig) => {
    setPersonaData(persona); // Pre-fill editor with generated data
    setCreateMode('manual'); // Switch to editor view
  };

  const handleRefine = async () => {
    if (!personaData || !refinementPrompt.trim()) return;
    
    setIsRefining(true);
    try {
      const refined = await apiClient.refinePersona({
        prompt: refinementPrompt,
        current_persona: personaData
      });
      setDraftPersona(refined);
    } catch (err) {
      console.error('Refinement failed', err);
    } finally {
      setIsRefining(false);
    }
  };

  const acceptDraft = () => {
    if (draftPersona) {
      setPersonaData(draftPersona);
      setDraftPersona(null);
      setRefinementPrompt('');
    }
  };

  const rejectDraft = () => {
    setDraftPersona(null);
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Persona Management</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">Manage and customize AI personas for ADR analysis</p>
        </div>
        <Link 
          href="/"
          className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-4 py-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 font-medium text-sm transition-colors flex items-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Back to Dashboard
        </Link>
      </div>

      {view === 'list' && (
        <PersonaList onSelect={handleSelectPersona} onCreate={handleCreate} />
      )}

      {view === 'create' && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Create New Persona</h2>
            <div className="flex bg-gray-100 dark:bg-gray-700 rounded p-1">
              <button
                onClick={() => setCreateMode('manual')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  createMode === 'manual'
                    ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-gray-100'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                Manual
              </button>
              <button
                onClick={() => setCreateMode('ai')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  createMode === 'ai'
                    ? 'bg-white dark:bg-gray-600 shadow text-purple-600 dark:text-purple-300'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                AI Generator
              </button>
            </div>
          </div>

          {createMode === 'manual' ? (
            <PersonaEditor 
              onSave={handleSave} 
              onCancel={() => setView('list')} 
              initialData={personaData} 
              isNew={true}
            />
          ) : (
            <PersonaGenerator onGenerated={handleGenerated} onCancel={() => setView('list')} />
          )}
        </div>
      )}

      {view === 'edit' && personaData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6">Edit Persona</h2>
            <PersonaEditor 
              initialData={personaData} 
              onSave={handleSave} 
              onCancel={() => setView('list')} 
            />
          </div>

          <div className="lg:col-span-1 space-y-6">
            {/* AI Refinement Panel */}
            <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-6 border border-purple-100 dark:border-purple-900/30">
              <h3 className="text-lg font-semibold text-purple-900 dark:text-purple-100 mb-4 flex items-center gap-2">
                <span>✨</span> AI Refinement
              </h3>
              
              <div className="space-y-3">
                <textarea
                  value={refinementPrompt}
                  onChange={(e) => setRefinementPrompt(e.target.value)}
                  className="w-full px-3 py-2 border border-purple-200 dark:border-purple-800 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
                  rows={4}
                  placeholder="How should this persona be improved? (e.g. 'Make it more critical of security flaws')"
                />
                <button
                  onClick={handleRefine}
                  disabled={isRefining || !refinementPrompt.trim()}
                  className="w-full py-2 bg-purple-600 text-white rounded hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 disabled:opacity-50 transition-colors"
                >
                  {isRefining ? 'Refining...' : 'Refine with AI'}
                </button>
              </div>
            </div>

            {/* Draft Diff View */}
            {draftPersona && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border-2 border-purple-500">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Proposed Changes</h3>
                
                <div className="space-y-4 max-h-[60vh] overflow-y-auto">
                  <DiffViewer 
                    label="Description" 
                    oldText={personaData.description} 
                    newText={draftPersona.description} 
                  />
                  <DiffViewer 
                    label="Instructions" 
                    oldText={personaData.instructions} 
                    newText={draftPersona.instructions} 
                  />
                  <ArrayDiffViewer 
                    label="Focus Areas" 
                    oldArray={personaData.focus_areas} 
                    newArray={draftPersona.focus_areas} 
                  />
                  <ArrayDiffViewer 
                    label="Evaluation Criteria" 
                    oldArray={personaData.evaluation_criteria} 
                    newArray={draftPersona.evaluation_criteria} 
                  />
                </div>

                <div className="flex gap-2 mt-6">
                  <button
                    onClick={acceptDraft}
                    className="flex-1 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                  >
                    Accept Changes
                  </button>
                  <button
                    onClick={rejectDraft}
                    className="flex-1 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                  >
                    Discard
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
