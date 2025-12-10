'use client';

import { useState, useEffect, useCallback } from 'react';
import { ADR } from '@/types/api';
import { apiClient } from '@/lib/api';

interface TagWithCount {
  tag: string;
  count: number;
}

interface TagsPanelProps {
  adrs: ADR[];
  selectedTag: string | null;
  onTagSelect: (tag: string | null) => void;
  onADRTagAdd: (adrId: string, tag: string) => Promise<void>;
  onADRTagRemove: (adrId: string, tag: string) => Promise<void>;
  onClose: () => void;
}

export function TagsPanel({
  adrs,
  selectedTag,
  onTagSelect,
  onADRTagAdd,
  onADRTagRemove,
  onClose,
}: TagsPanelProps) {
  const [tags, setTags] = useState<TagWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());
  const [showNewTagInput, setShowNewTagInput] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [selectedADRForTagging, setSelectedADRForTagging] = useState<string | null>(null);

  const loadTags = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.listTags();
      setTags(response.tags);
    } catch (err) {
      console.error('Failed to load tags:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  // Refresh tag counts when ADRs change
  useEffect(() => {
    const tagCounts: Record<string, number> = {};
    adrs.forEach(adr => {
      adr.metadata.tags.forEach(tag => {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1;
      });
    });
    
    // Update counts for existing tags and add new ones
    const updatedTags = Object.entries(tagCounts)
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
    
    setTags(updatedTags);
  }, [adrs]);

  const toggleExpand = (tag: string) => {
    setExpandedTags(prev => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  const getADRsWithTag = (tag: string) => {
    return adrs.filter(adr => adr.metadata.tags.includes(tag));
  };

  const handleCreateTag = async () => {
    if (!newTagName.trim()) return;
    
    // If an ADR is selected, add the tag to it
    if (selectedADRForTagging) {
      try {
        await onADRTagAdd(selectedADRForTagging, newTagName.trim());
        setShowNewTagInput(false);
        setNewTagName('');
        setSelectedADRForTagging(null);
        loadTags();
      } catch (err) {
        console.error('Failed to add tag:', err);
      }
    } else {
      // Just show the tag input was cleared (tag needs an ADR to exist)
      setShowNewTagInput(false);
      setNewTagName('');
    }
  };

  const handleRemoveTagFromADR = async (adrId: string, tag: string) => {
    try {
      await onADRTagRemove(adrId, tag);
      loadTags();
    } catch (err) {
      console.error('Failed to remove tag:', err);
    }
  };

  // Get color class for a tag based on its hash
  const getTagColor = (tag: string) => {
    const colors = [
      'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
      'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
      'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300',
      'bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300',
      'bg-pink-100 dark:bg-pink-900/40 text-pink-700 dark:text-pink-300',
      'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300',
      'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300',
      'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300',
    ];
    
    let hash = 0;
    for (let i = 0; i < tag.length; i++) {
      hash = tag.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex-1 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Tags</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowNewTagInput(!showNewTagInput)}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
            title="Create new tag"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 md:hidden"
            title="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* New Tag Input */}
      {showNewTagInput && (
        <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
            New tag name:
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleCreateTag();
                } else if (e.key === 'Escape') {
                  setShowNewTagInput(false);
                  setNewTagName('');
                  setSelectedADRForTagging(null);
                }
              }}
              placeholder="Enter tag name..."
              className="flex-1 text-sm px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <button
              onClick={handleCreateTag}
              disabled={!newTagName.trim() || !selectedADRForTagging}
              className="px-2 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              title={!selectedADRForTagging ? 'Select a record to add this tag to' : 'Create tag'}
            >
              Add
            </button>
          </div>
          {/* ADR selector for new tag */}
          <div className="mt-2">
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              Apply to record:
            </label>
            <select
              value={selectedADRForTagging || ''}
              onChange={(e) => setSelectedADRForTagging(e.target.value || null)}
              className="w-full text-sm px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a record...</option>
              {adrs.map(adr => (
                <option key={adr.metadata.id} value={adr.metadata.id}>
                  {adr.metadata.title}
                </option>
              ))}
            </select>
          </div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Tags must be added to at least one record.
          </p>
        </div>
      )}

      {/* Tags list */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            {/* All Records */}
            <div
              className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer rounded-md mx-2 mb-1 transition-colors ${
                selectedTag === null
                  ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
              onClick={() => onTagSelect(null)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-gray-500 dark:text-gray-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
              </svg>
              <span className="text-sm font-medium">All Records</span>
              <span className="text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded-full ml-auto">
                {adrs.length}
              </span>
            </div>

            {/* Tag list */}
            <div className="px-2 space-y-1">
              {tags.map(({ tag, count }) => {
                const isExpanded = expandedTags.has(tag);
                const isSelected = selectedTag === tag;
                const taggedADRs = isExpanded ? getADRsWithTag(tag) : [];

                return (
                  <div key={tag}>
                    <div
                      className={`flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded-md transition-colors ${
                        isSelected
                          ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                          : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
                      }`}
                      onClick={() => onTagSelect(tag)}
                    >
                      {/* Expand button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleExpand(tag);
                        }}
                        className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={2}
                          stroke="currentColor"
                          className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                      </button>

                      {/* Tag badge */}
                      <span className={`text-xs px-2 py-0.5 rounded-full ${getTagColor(tag)}`}>
                        {tag}
                      </span>

                      {/* Count */}
                      <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
                        {count}
                      </span>
                    </div>

                    {/* Expanded ADR list */}
                    {isExpanded && (
                      <div className="ml-6 mt-1 space-y-1 border-l-2 border-gray-200 dark:border-gray-600 pl-2">
                        {taggedADRs.map(adr => (
                          <div
                            key={adr.metadata.id}
                            className="flex items-center gap-2 py-1 px-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded group"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3 shrink-0">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                            </svg>
                            <span className="truncate flex-1" title={adr.metadata.title}>
                              {adr.metadata.title}
                            </span>
                            {/* Remove tag button */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRemoveTagFromADR(adr.metadata.id, tag);
                              }}
                              className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-opacity"
                              title="Remove tag from this record"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {tags.length === 0 && !loading && (
              <div className="px-3 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                <p>No tags yet.</p>
                <p className="text-xs mt-1">Add tags to your records to organize them.</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Instructions */}
      <div className="px-3 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Click a tag to filter records. Expand to see tagged records.
        </p>
      </div>
    </div>
  );
}
