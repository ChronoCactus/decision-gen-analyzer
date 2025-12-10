'use client';

import { useState, useEffect, useCallback } from 'react';
import { ADR, FolderNode } from '@/types/api';
import { apiClient } from '@/lib/api';

interface FoldersPanelProps {
  adrs: ADR[];
  selectedFolder: string | null;
  onFolderSelect: (folderPath: string | null) => void;
  onADRFolderChange: (adrId: string, folderPath: string | null) => Promise<void>;
  onFolderCreated?: (folderPath: string) => void;
  onClose: () => void;
}

// Build a tree structure from flat folder paths
function buildFolderTree(folders: string[], adrs: ADR[]): FolderNode[] {
  const root: FolderNode[] = [];
  
  // Count ADRs per folder (including exact matches only)
  const adrCountByFolder: Record<string, number> = {};
  adrs.forEach(adr => {
    const path = adr.metadata.folder_path || '/';
    adrCountByFolder[path] = (adrCountByFolder[path] || 0) + 1;
  });

  // Sort folders to ensure parents come before children
  const sortedFolders = [...folders].sort();

  sortedFolders.forEach(folderPath => {
    const parts = folderPath.split('/').filter(Boolean);
    let currentLevel = root;

    parts.forEach((part, index) => {
      const currentPath = '/' + parts.slice(0, index + 1).join('/');
      let existing = currentLevel.find(node => node.name === part);
      
      if (!existing) {
        existing = {
          name: part,
          path: currentPath,
          children: [],
          adrCount: adrCountByFolder[currentPath] || 0,
        };
        currentLevel.push(existing);
      }
      
      currentLevel = existing.children;
    });
  });

  return root;
}

interface FolderTreeNodeProps {
  node: FolderNode;
  level: number;
  selectedFolder: string | null;
  expandedFolders: Set<string>;
  onToggleExpand: (path: string) => void;
  onSelect: (path: string) => void;
  onDrop: (adrId: string, folderPath: string) => void;
  dragOverFolder: string | null;
  onDragOver: (path: string | null) => void;
}

function FolderTreeNode({
  node,
  level,
  selectedFolder,
  expandedFolders,
  onToggleExpand,
  onSelect,
  onDrop,
  dragOverFolder,
  onDragOver,
}: FolderTreeNodeProps) {
  const isExpanded = expandedFolders.has(node.path);
  const isSelected = selectedFolder === node.path;
  const hasChildren = node.children.length > 0;
  const isDragOver = dragOverFolder === node.path;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDragOver(node.path);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDragOver(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const adrId = e.dataTransfer.getData('text/adr-id');
    if (adrId) {
      onDrop(adrId, node.path);
    }
    onDragOver(null);
  };

  return (
    <div>
      <div
        className={`flex items-center gap-1 px-2 py-1 cursor-pointer rounded-md transition-colors ${
          isSelected
            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
            : isDragOver
            ? 'bg-green-100 dark:bg-green-900/50 border-2 border-dashed border-green-500'
            : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
        }`}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={() => onSelect(node.path)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Expand/collapse button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleExpand(node.path);
          }}
          className={`p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 ${
            !hasChildren ? 'invisible' : ''
          }`}
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

        {/* Folder icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className={`w-4 h-4 shrink-0 ${
            isExpanded ? 'text-yellow-600 dark:text-yellow-400' : 'text-yellow-500 dark:text-yellow-500'
          }`}
        >
          {isExpanded ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
            />
          )}
        </svg>

        {/* Folder name */}
        <span className="truncate text-sm flex-1">{node.name}</span>

        {/* ADR count badge */}
        {(node.adrCount ?? 0) > 0 && (
          <span className="text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded-full">
            {node.adrCount}
          </span>
        )}
      </div>

      {/* Children */}
      {isExpanded && hasChildren && (
        <div>
          {node.children.map(child => (
            <FolderTreeNode
              key={child.path}
              node={child}
              level={level + 1}
              selectedFolder={selectedFolder}
              expandedFolders={expandedFolders}
              onToggleExpand={onToggleExpand}
              onSelect={onSelect}
              onDrop={onDrop}
              dragOverFolder={dragOverFolder}
              onDragOver={onDragOver}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FoldersPanel({
  adrs,
  selectedFolder,
  onFolderSelect,
  onADRFolderChange,
  onFolderCreated,
  onClose,
}: FoldersPanelProps) {
  const [folders, setFolders] = useState<string[]>([]);
  const [folderTree, setFolderTree] = useState<FolderNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null);
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderParent, setNewFolderParent] = useState<string | null>(null);

  // Count of ADRs without a folder
  const unfolderedCount = adrs.filter(adr => !adr.metadata.folder_path).length;

  const loadFolders = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.listFolders();
      setFolders(response.folders);
      setFolderTree(buildFolderTree(response.folders, adrs));
    } catch (err) {
      console.error('Failed to load folders:', err);
    } finally {
      setLoading(false);
    }
  }, [adrs]);

  useEffect(() => {
    loadFolders();
  }, [loadFolders]);

  // Rebuild tree when ADRs change (for counts)
  useEffect(() => {
    setFolderTree(buildFolderTree(folders, adrs));
  }, [folders, adrs]);

  const toggleExpand = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleDrop = async (adrId: string, folderPath: string) => {
    try {
      await onADRFolderChange(adrId, folderPath);
      // Reload folders in case a new path was created
      loadFolders();
    } catch (err) {
      console.error('Failed to move ADR to folder:', err);
    }
  };

  const handleRootDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    const adrId = e.dataTransfer.getData('text/adr-id');
    if (adrId) {
      try {
        await onADRFolderChange(adrId, null);
        loadFolders();
      } catch (err) {
        console.error('Failed to move ADR to root:', err);
      }
    }
    setDragOverFolder(null);
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    
    const folderPath = newFolderParent 
      ? `${newFolderParent}/${newFolderName.trim()}`
      : `/${newFolderName.trim()}`;
    
    // Add the folder to the local state to show it immediately
    setFolders(prev => [...prev, folderPath].sort());
    setFolderTree(buildFolderTree([...folders, folderPath], adrs));
    
    // Notify parent component
    if (onFolderCreated) {
      onFolderCreated(folderPath);
    }
    
    setShowNewFolderInput(false);
    setNewFolderName('');
    setNewFolderParent(null);
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex-1 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Folders</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              setShowNewFolderInput(true);
              setNewFolderParent(selectedFolder);
            }}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
            title="New folder"
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

      {/* New folder input */}
      {showNewFolderInput && (
        <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateFolder();
                if (e.key === 'Escape') {
                  setShowNewFolderInput(false);
                  setNewFolderName('');
                }
              }}
              placeholder="Folder name"
              className="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
              autoFocus
            />
            <button
              onClick={handleCreateFolder}
              className="p-1 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </button>
            <button
              onClick={() => {
                setShowNewFolderInput(false);
                setNewFolderName('');
              }}
              className="p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-600 rounded"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {newFolderParent && (
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Creating in: {newFolderParent}
            </div>
          )}
        </div>
      )}

      {/* Folder tree */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            {/* All Records (Root) */}
            <div
              className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer rounded-md mx-2 mb-1 transition-colors ${
                selectedFolder === null
                  ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                  : dragOverFolder === '/'
                  ? 'bg-green-100 dark:bg-green-900/50 border-2 border-dashed border-green-500'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
              onClick={() => onFolderSelect(null)}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOverFolder('/');
              }}
              onDragLeave={() => setDragOverFolder(null)}
              onDrop={handleRootDrop}
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-gray-500 dark:text-gray-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
              </svg>
              <span className="text-sm font-medium">All Records</span>
              <span className="text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded-full ml-auto">
                {adrs.length}
              </span>
            </div>

            {/* Unfoldered */}
            {unfolderedCount > 0 && (
              <div
                className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer rounded-md mx-2 mb-1 transition-colors ${
                  selectedFolder === '/'
                    ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
                }`}
                onClick={() => onFolderSelect('/')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <span className="text-sm italic">Unfiled</span>
                <span className="text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded-full ml-auto">
                  {unfolderedCount}
                </span>
              </div>
            )}

            {/* Folder tree */}
            <div className="px-2">
              {folderTree.map(node => (
                <FolderTreeNode
                  key={node.path}
                  node={node}
                  level={0}
                  selectedFolder={selectedFolder}
                  expandedFolders={expandedFolders}
                  onToggleExpand={toggleExpand}
                  onSelect={onFolderSelect}
                  onDrop={handleDrop}
                  dragOverFolder={dragOverFolder}
                  onDragOver={setDragOverFolder}
                />
              ))}
            </div>

            {folderTree.length === 0 && !loading && (
              <div className="px-3 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                <p>No folders yet.</p>
                <p className="text-xs mt-1">Drag records here to organize them.</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Instructions */}
      <div className="px-3 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Drag and drop ADR cards to organize them into folders.
        </p>
      </div>
    </div>
  );
}
