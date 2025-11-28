'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { PersonaInfo } from '@/types/api';

interface PersonaListProps {
  onSelect: (personaValue: string) => void;
  onCreate: () => void;
}

export function PersonaList({ onSelect, onCreate }: PersonaListProps) {
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.getPersonas();
      setPersonas(response.personas);
    } catch (err) {
      setError('Failed to load personas');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) return <div className="p-4 text-center text-gray-600 dark:text-gray-400">Loading personas...</div>;
  if (error) return <div className="p-4 text-center text-red-500 dark:text-red-400">{error}</div>;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Available Personas</h3>
        <button
          onClick={onCreate}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
        >
          + Create New
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {personas.map((persona) => (
          <div
            key={persona.value}
            onClick={() => onSelect(persona.value)}
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-500 dark:hover:border-blue-400 cursor-pointer transition-colors bg-white dark:bg-gray-800"
          >
            <h4 className="font-medium text-gray-900 dark:text-gray-100">{persona.label}</h4>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{persona.description}</p>
            <div className="mt-2 flex gap-2">
                <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-1 rounded">
                    {persona.value}
                </span>
                {persona.llm_config && (
                    <span className="text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-300 px-2 py-1 rounded">
                        Custom Model
                    </span>
                )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
