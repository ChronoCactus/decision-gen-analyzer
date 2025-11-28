'use client';

import { useState, useEffect } from 'react';
import { PersonaConfig, PersonaCreateRequest, PersonaUpdateRequest } from '@/types/api';

interface PersonaEditorProps {
  initialData?: PersonaConfig;
  onSave: (data: PersonaCreateRequest | PersonaUpdateRequest) => Promise<void>;
  onCancel: () => void;
  isNew?: boolean;
}

export function PersonaEditor({ initialData, onSave, onCancel, isNew = false }: PersonaEditorProps) {
  const [formData, setFormData] = useState<PersonaCreateRequest>({
    name: '',
    description: '',
    instructions: '',
    focus_areas: [],
    evaluation_criteria: [],
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name,
        description: initialData.description,
        instructions: initialData.instructions,
        focus_areas: initialData.focus_areas,
        evaluation_criteria: initialData.evaluation_criteria,
        llm_config: initialData.model_config,
      });
    }
  }, [initialData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSave(formData);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArrayChange = (
    field: 'focus_areas' | 'evaluation_criteria',
    index: number,
    value: string
  ) => {
    const newArray = [...formData[field]];
    newArray[index] = value;
    setFormData({ ...formData, [field]: newArray });
  };

  const addArrayItem = (field: 'focus_areas' | 'evaluation_criteria') => {
    setFormData({ ...formData, [field]: [...formData[field], ''] });
  };

  const removeArrayItem = (field: 'focus_areas' | 'evaluation_criteria', index: number) => {
    const newArray = [...formData[field]];
    newArray.splice(index, 1);
    setFormData({ ...formData, [field]: newArray });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Name (Identifier)
        </label>
        <input
          type="text"
          required
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          placeholder="e.g. security_expert"
          disabled={!isNew && !!initialData} // Only disable if editing existing persona
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Description
        </label>
        <input
          type="text"
          required
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          placeholder="Short description of the persona"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Instructions (System Prompt)
        </label>
        <textarea
          required
          value={formData.instructions}
          onChange={(e) => setFormData({ ...formData, instructions: e.target.value })}
          rows={10}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-mono text-sm"
          placeholder="Detailed instructions for the LLM..."
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Focus Areas
        </label>
        {formData.focus_areas.map((area, index) => (
          <div key={index} className="flex gap-2 mb-2">
            <input
              type="text"
              value={area}
              onChange={(e) => handleArrayChange('focus_areas', index, e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
            <button
              type="button"
              onClick={() => removeArrayItem('focus_areas', index)}
              className="px-3 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem('focus_areas')}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          + Add Focus Area
        </button>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Evaluation Criteria
        </label>
        {formData.evaluation_criteria.map((criteria, index) => (
          <div key={index} className="flex gap-2 mb-2">
            <input
              type="text"
              value={criteria}
              onChange={(e) => handleArrayChange('evaluation_criteria', index, e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
            <button
              type="button"
              onClick={() => removeArrayItem('evaluation_criteria', index)}
              className="px-3 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => addArrayItem('evaluation_criteria')}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          + Add Criteria
        </button>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? 'Saving...' : 'Save Persona'}
        </button>
      </div>
    </form>
  );
}
